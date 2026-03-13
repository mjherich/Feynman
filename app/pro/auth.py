from __future__ import annotations

import os
import logging
import time

import jwt
from jwt import PyJWKClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..core.db import get_or_create_user

log = logging.getLogger(__name__)

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")

HMAC_ALGORITHMS = {"HS256", "HS384", "HS512"}
ASYMMETRIC_ALGORITHMS = {"ES256", "RS256", "EdDSA"}
ALL_ALGORITHMS = list(HMAC_ALGORITHMS | ASYMMETRIC_ALGORITHMS)

_jwks_client: PyJWKClient | None = None
_jwks_client_init_time: float = 0
_JWKS_REFRESH_INTERVAL = 600  # re-create client every 10 min to pick up rotated keys

PUBLIC_PATHS = {
    "/", "/api/health",
    "/api/pro/config",
    "/api/pro/webhook",
    "/api/topics",
    "/api/agents",
    "/api/votes",
    "/api/minds",
    "/favicon.ico",
}
PUBLIC_PREFIXES = ("/static/",)


def _get_jwks_client() -> PyJWKClient | None:
    global _jwks_client, _jwks_client_init_time
    if not SUPABASE_URL:
        return None
    now = time.monotonic()
    if _jwks_client is None or (now - _jwks_client_init_time) > _JWKS_REFRESH_INTERVAL:
        jwks_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=_JWKS_REFRESH_INTERVAL)
        _jwks_client_init_time = now
        log.info("Initialized JWKS client from %s", jwks_url)
    return _jwks_client


def _decode_token(token: str) -> dict:
    """Decode and verify a Supabase JWT, supporting both HMAC and asymmetric algorithms."""
    header = jwt.get_unverified_header(token)
    token_alg = header.get("alg", "unknown")

    if token_alg in HMAC_ALGORITHMS:
        if not SUPABASE_JWT_SECRET:
            raise jwt.InvalidTokenError(
                f"Token uses {token_alg} but SUPABASE_JWT_SECRET is not set"
            )
        return jwt.decode(
            token, SUPABASE_JWT_SECRET,
            algorithms=list(HMAC_ALGORITHMS),
            audience="authenticated",
        )

    if token_alg in ASYMMETRIC_ALGORITHMS:
        client = _get_jwks_client()
        if not client:
            raise jwt.InvalidTokenError(
                f"Token uses {token_alg} but SUPABASE_URL is not set for JWKS discovery"
            )
        signing_key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token, signing_key.key,
            algorithms=list(ASYMMETRIC_ALGORITHMS),
            audience="authenticated",
        )

    raise jwt.InvalidAlgorithmError(f"Unsupported JWT algorithm: {token_alg}")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        is_public = path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES)
        is_get_api = request.method == "GET" and path.startswith("/api/")

        if is_public:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        has_token = auth_header.startswith("Bearer ")

        if not has_token:
            if is_get_api:
                return await call_next(request)
            return JSONResponse(
                {"detail": "Authentication required", "code": "auth_required"},
                status_code=401,
            )

        token = auth_header[7:]
        try:
            payload = _decode_token(token)
        except jwt.ExpiredSignatureError:
            if is_get_api:
                return await call_next(request)
            return JSONResponse({"detail": "Token expired", "code": "token_expired"}, status_code=401)
        except jwt.InvalidTokenError as e:
            log.warning("JWT validation failed: %s", e)
            if is_get_api:
                return await call_next(request)
            return JSONResponse({"detail": "Invalid token", "code": "invalid_token"}, status_code=401)

        user_id = payload.get("sub", "")
        email = payload.get("email", "")

        if not user_id:
            if is_get_api:
                return await call_next(request)
            return JSONResponse({"detail": "Invalid token claims"}, status_code=401)

        user = get_or_create_user(user_id, email)

        request.state.user_id = user_id
        request.state.email = email
        request.state.tier = user.get("tier", "free") if user else "free"

        return await call_next(request)

# Feynman Pro — Commercialization Spec

## Architecture: Single Repository (Open Core)

```
GitHub Repo:
  steveyeow/Feynman (public) — open-source core (MIT) + commercial layer (BSL)

Directory layout:
  app/core/     — MIT licensed, core product features
  app/pro/      — BSL licensed, commercial features (auth, quota, stripe)
  app/static/   — MIT licensed, frontend (includes pro UI gated by FEYNMAN_PRO flag)

Deployment:
  Local dev     — SQLite, no auth (ENABLE_AUTH not set)
  Vercel (prod) — PostgreSQL (Supabase), auth enabled (ENABLE_AUTH=true)
  Supabase      — PostgreSQL (data) + Auth (login/signup)
  Stripe        — subscriptions + usage billing
```

This follows the GitLab/Sentry open-core model: all code in one repo, commercial
features in a separate directory with a different license. No separate repos, no
syncing, no merge conflicts.

## How It Works

| Environment variable | Effect |
|---------------------|--------|
| Not set (default) | SQLite database, no auth, no payment — full open-source experience |
| `DATABASE_URL` | Use PostgreSQL instead of SQLite |
| `ENABLE_AUTH=true` | Load auth middleware, show login/subscription UI |
| `STRIPE_SECRET_KEY` | Enable Stripe payment endpoints |

The same codebase powers both open-source and commercial deployments.

## File Structure

```
Feynman/
├── LICENSE                 ← MIT (covers everything except app/pro/)
├── app/
│   ├── core/               ← MIT — product features
│   │   ├── config.py
│   │   ├── db.py           ← dual-mode: SQLite (default) or PostgreSQL
│   │   ├── minds.py
│   │   ├── providers.py
│   │   └── rag.py
│   ├── pro/                ← BSL — commercial layer
│   │   ├── LICENSE         ← Business Source License 1.1
│   │   ├── __init__.py
│   │   ├── auth.py         ← Supabase JWT middleware
│   │   ├── quota.py        ← usage tracking & free/pro limits
│   │   └── stripe.py       ← checkout, webhook, subscription portal
│   ├── static/             ← MIT — frontend
│   │   ├── app.js          ← includes pro UI (gated by window.FEYNMAN_PRO)
│   │   ├── styles.css
│   │   └── index.html
│   └── main.py             ← conditionally loads pro modules
├── scripts/
│   └── migrate_sqlite_to_pg.py
├── vercel.json
├── requirements.txt        ← includes psycopg2, PyJWT, stripe
└── SPEC-pro.md             ← this file
```

## External Services (already configured)

| Service | Status | Notes |
|---------|--------|-------|
| Stripe | Configured | Products, prices, webhook secrets in Stripe Dashboard |
| Supabase Auth | Configured | Google/GitHub OAuth set up |
| Supabase PostgreSQL | Available | Same Supabase project |
| LLM API Keys | Working | Gemini, DeepSeek, OpenAI, Kimi, Anthropic |
| Vercel | Active | Project linked to Feynman repo, env vars set |

## Vercel Deployment

Vercel project should point to the `Feynman` repo (public). Set these env vars:

**LLM keys** (already set):
- `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `KIMI_API_KEY`, `ANTHROPIC_API_KEY`

**Pro-specific**:
- `DATABASE_URL` — Supabase PostgreSQL connection string
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET`
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`
- `ENABLE_AUTH=true`
- `APP_URL` — production URL for Stripe redirects

## Quota Limits

| Feature | Free | Pro ($10/mo) |
|---------|------|-------------|
| Chats per day | 10 | 100 |
| Mind chats per day | 5 | 50 |
| Books in library | 5 | 50 |
| File uploads | 3 | 20 |
| Discover minds | 3/day | 30 |
| Create custom minds | 1 | 20 |

## Development Workflow

All development happens in the single `Feynman` repo:

- **Core features** (chat, RAG, Great Minds, frontend) — develop normally, MIT licensed
- **Commercial features** (auth, quota, payment) — develop in `app/pro/`, BSL licensed
- **Test locally** — run without `ENABLE_AUTH`, everything works with SQLite
- **Deploy** — push to main, Vercel auto-deploys with `ENABLE_AUTH=true`

No syncing, no merge conflicts, no second repo.

## Remaining Work

- [ ] Update Vercel project to point to `Feynman` repo (instead of `feynman-pro`)
- [ ] Verify all env vars are set on Vercel
- [ ] Update Stripe webhook URL to production domain
- [ ] Custom domain setup (e.g. `app.feynman.ai`)
- [ ] Test full flow: signup → free tier → hit quota → upgrade → payment → pro tier
- [ ] Archive `feynman-pro` repo (no longer needed)

# CitationPulse — Monorepo

**CitationPulse GEO** — a Generative-Engine Optimization platform that audits how often a brand is cited across ChatGPT, Perplexity, Gemini, Claude, and Google AI Overviews, surfaces gaps, and ships actionable fixes.

## Backend vs Frontend layout

The repo is split cleanly. **Backend** code is Python; **frontend** code is TypeScript/React. They communicate over HTTP (`localhost:3000` → `localhost:8000`).

### Backend (Python — FastAPI + Celery)
```
apps/api/                       # the entire Python service
├── src/citationpulse/          # package: routes, services, adapters, tasks
├── tests/                      # pytest
├── scripts/                    # python helper scripts
├── pyproject.toml              # deps + ruff + pytest + mypy
└── README.md
infra/sql/                      # Alembic migrations + schema.sql
infra/railway/                  # Railway deploy config
infra/docker/                   # Dockerfiles used by Railway prod build
infra/monitoring/               # observability notes
scripts/                        # PowerShell: setup-backend, start-api, start-worker
```

### Frontend (TypeScript — Next.js 15)
```
apps/web/                       # the entire web app (citationpulse-web)
├── src/                        # app router pages, components, lib, hooks
├── e2e/                        # Playwright e2e
├── public/                     # (created by Next on demand)
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── vitest.config.ts
├── playwright.config.ts
└── README.md
packages/shared-types/          # OpenAPI → TS types consumed by apps/web
```

### Shared / repo-wide
```
.env, .env.example              # one env file feeds both sides
package.json                    # npm workspaces: apps/web, packages/*
.github/                        # CI
docs/                           # SETUP_WINDOWS, TDD, audits
```

## Stack

| Layer       | Technology                                                                                          |
| ----------- | --------------------------------------------------------------------------------------------------- |
| Web         | Next.js 15, React 18, Tailwind, shadcn/ui                                                           |
| API         | FastAPI, SQLAlchemy 2, Pydantic v2, Alembic                                                         |
| Workers     | Celery (with `celery[sqlalchemy]` — Postgres-backed broker + result backend, **no Redis required**) |
| Database    | PostgreSQL 16+ (single store: app data, Celery broker, scan-event log, rate-limit counters)         |
| Scraping    | Playwright (Chromium) for Google AI Overviews                                                       |
| LLM clients | **OpenRouter** (single key proxies ChatGPT, Claude, Gemini, Perplexity)                             |
| Optional    | Cloudflare R2 (raw payloads), Stripe (billing), Clerk (auth) — all opt-in                           |

## Quick start

> **Windows (native, no Docker):** read [`docs/SETUP_WINDOWS.md`](docs/SETUP_WINDOWS.md). It covers Postgres 18, Python venv, Playwright Chromium, env config, migrations, and per-session run commands.

Once Postgres is running, `.env` is configured, and migrations are applied:

| What           | Command                                                                                                  | URL                                            |
| -------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Web + API (Win)| `npm run dev:stack` (from repo root; uses `scripts/start-api.ps1`)                                       | :3000 web, :8000 API                           |
| FastAPI        | `npm run dev:api` (repo root, Windows) or `uvicorn citationpulse.main:app --reload --host 0.0.0.0 --port 8000` with `PYTHONPATH=apps/api/src` | http://localhost:8000 (docs at `/docs`)        |
| Celery worker  | `celery -A citationpulse.celery_app worker -l info --pool=solo` (from `apps/api`)                        | —                                              |
| Next.js (web)  | `npm run dev` (from repo root, or `npm run dev -w citationpulse-web`)                                    | http://localhost:3000                          |

On **Windows**, the root **`npm run dev`** runs the full stack via `scripts/start-all.ps1` (web + API + worker). For web-only: **`npm run dev:web`**. Full setup: `docs/SETUP_WINDOWS.md` and production deploy: `infra/railway/README.md`.

## Environment

Copy [`.env.example`](.env.example) to `.env` at the repo root and fill in keys.

### LLM access — one key for all four engines

CitationPulse routes **every** AI call (ChatGPT, Claude, Gemini, Perplexity) through [OpenRouter](https://openrouter.ai). One key, one bill, one client, dozens of models.

1. Sign up at [openrouter.ai/keys](https://openrouter.ai/keys).
2. Add ~$5 in credits (most scans cost a fraction of a cent).
3. Paste the key into `.env` as `OPENROUTER_API_KEY=sk-or-v1-…`.

That's it — the FastAPI service auto-detects the key on next reload and unlocks all four engines.

Key vars:

- `DATABASE_URL` — `postgresql+psycopg://citationpulse:citationpulse@localhost:5432/citationpulse_geo`
- `OPENROUTER_API_KEY` — **required** for any LLM-driven scan
- `CHATGPT_MODEL`, `CLAUDE_MODEL`, `GEMINI_MODEL`, `PERPLEXITY_MODEL`, `SENTIMENT_MODEL` — optional model overrides (use OpenRouter slugs like `openai/gpt-4o:online`)
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` — leave **blank** to derive from `DATABASE_URL` (`sqla+postgresql://…` / `db+postgresql://…`)
- `SSE_POLL_INTERVAL_S`, `SSE_KEEPALIVE_INTERVAL_S` — Postgres-backed live scan stream
- `STRIPE_SECRET_KEY`, `R2_*`, `CLERK_*` — **optional**; safe to leave empty in dev

### LLM architecture (one client, four engines)

```
                    ┌─────────────────────────────────────┐
                    │  services/llm_router.py             │
   adapters/        │  ─────────────────────              │
   chatgpt   ─┐     │  • single httpx client              │
   claude    ─┼─►   │  • tenacity retries (429/5xx)       │  ─►  https://openrouter.ai/api/v1
   gemini    ─┤     │  • streaming SSE support            │
   perplexity─┘     │  • normalized citation extraction   │
                    │  • cost / token usage tracking      │
                    └─────────────────────────────────────┘
```

Each engine adapter is now a 30-line shim that calls `get_router().chat_completion(model=…)` with its OpenRouter slug. To swap a model, edit `.env` (or `core/config.py`) — no code change.

## Migrations

```powershell
cd apps/api
alembic upgrade head
```

See [`infra/sql/README.md`](infra/sql/README.md) for the full Alembic workflow.

## Useful docs

- [`docs/SETUP_WINDOWS.md`](docs/SETUP_WINDOWS.md) — native Windows runbook (Postgres + Python venv + Playwright)
- [`docs/TDD_PRODUCT_DECISIONS.md`](docs/TDD_PRODUCT_DECISIONS.md) — product decisions
- [`apps/api/README.md`](apps/api/README.md) — API package
- [`apps/web/README.md`](apps/web/README.md) — web app
- [`infra/railway/README.md`](infra/railway/README.md) — Railway deploy

## License

Proprietary.

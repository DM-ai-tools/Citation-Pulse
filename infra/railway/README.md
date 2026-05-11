# Railway deployment (production-ready)

This repo is ready for a 3-service Railway deployment:

1. `api` (FastAPI)
2. `worker` (Celery queue consumer)
3. `web` (Next.js frontend)

## Config templates

Template config files are provided:

- `infra/railway/api.railway.json`
- `infra/railway/worker.railway.json`
- `infra/railway/web.railway.json`

Use them as copy/paste references in each Railway service's Config-as-Code or service settings.

## Service setup

Use **one GitHub repo** and create **3 Railway services** from it.  
For each service, set a different **Root Directory** and Dockerfile so pip/npm stay separate.

- API root directory: `apps/api`
- Worker root directory: `apps/api`
- Web root directory: `apps/web`

### 1) API service

- Builder: `DOCKERFILE`
- Root directory: `apps/api`
- Dockerfile: `Dockerfile`
- Start command: `uvicorn citationpulse.main:app --host 0.0.0.0 --port $PORT`
- Healthcheck path: `/health`

### 2) Worker service

- Builder: `DOCKERFILE`
- Root directory: `apps/api`
- Dockerfile: `Dockerfile.worker`
- Start command: `celery -A citationpulse.celery_app worker -Q default -l info --pool=solo`
- No HTTP healthcheck needed

### 3) Web service

- Builder: `DOCKERFILE`
- Root directory: `apps/web`
- Dockerfile: `Dockerfile`
- Start command: `npm run start -- --port $PORT`
- Healthcheck path: `/`

## Required environment variables

Set these in Railway (shared variables are fine):

- `DATABASE_URL` -> Railway Postgres URL, with SQLAlchemy driver prefix:
  - `postgresql+psycopg://...`
- Optional: `FORWARDED_ALLOW_IPS=*` (or rely on the API Dockerfile / start command) so Uvicorn trusts `X-Forwarded-*` from Railway’s edge. Anonymous scan rate limits use the resolved client IP.
- Optional: `ANONYMOUS_SCAN_RATE_LIMIT_PER_HOUR` (default **24** in app settings) to tune landing-page abuse protection; use `0` only if you accept disabling that limit.
- `OPENROUTER_API_KEY` -> required for scans (set on **both** API and worker if you use a separate worker; missing key yields OpenRouter HTTP 401). After deploy, open `GET /health` on the API: `openrouter_configured` must be `true` (no quotes or stray spaces in the variable value).
- `ENVIRONMENT=production`
- `LOG_LEVEL=info`

Set these at minimum on API:

- `API_CORS_ORIGINS=https://<your-web-domain>`

Set these on Web:

- `NEXT_PUBLIC_API_URL=https://<your-api-domain>`

Optional but recommended:

- `SENTRY_DSN`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `R2_*` variables (if storing raw payloads in R2)
- `CLERK_*` variables (if auth is enabled)
- `STRIPE_*` variables (if billing is enabled)

## Database migrations

Run migrations before first production traffic. This repo ships hand-written SQL under `infra/sql/` (for example `20260208_opportunities_prompt_metrics.sql` for Top Gap Opportunities). Apply with `psql "$DATABASE_URL" -f …` or your SQL runner.

If you use Alembic locally:

```bash
cd infra/sql
alembic upgrade head
```

Use the same production `DATABASE_URL` when running this command.

## Notes

- Celery is Postgres-backed in this project (no Redis required).
- Web build-time public env vars (`NEXT_PUBLIC_*`) are wired through the Docker build.
- The web container is configured to bind Railway's dynamic `PORT`.
- If Railway says `using build driver railpack`, Docker mode is not selected yet; switch builder to `DOCKERFILE`.

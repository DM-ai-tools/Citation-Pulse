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

Railway injects **`PORT` at runtime** (commonly **`8080`**). The web `Dockerfile` runs `next start` with `--port ${PORT:-3000}`, so production binds whatever Railway assigns; **`EXPOSE 3000` in the image is only a default for local runs** and does not force Railway’s edge to use 3000.

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
- `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` (optional) — Google Ads search-volume estimates for **Top gap opportunities** (read when building scan reports). If missing, **Est. monthly searches** stays as a dash. Not used on the Web service.

Set these on Web:

- `NEXT_PUBLIC_API_URL=https://<your-api-domain>` — **must be present when `npm run build` runs** (Docker/Railway build). Changing it requires a **Web service rebuild**, not only a restart, or the browser will still use the old inlined URL (often `localhost:8000`, which breaks production data like Top gap opportunities).
- **Alternative (same-origin API):** `NEXT_PUBLIC_API_URL=same-origin` and set **`API_PROXY_TARGET=https://<your-api-domain>`** on the Web service at **build** time. The browser then calls `/api/v1/...` on the web host; Next.js rewrites proxy to FastAPI. Use this when you want one public origin or you keep seeing **404** on `multi-engine` because requests were accidentally hitting the web host instead of the API.
- `NEXT_PUBLIC_APP_VERSION` (optional) — e.g. `RAILWAY_GIT_COMMIT_SHA` or a release tag, passed as a Docker build-arg so `/dashboard` can show **App build:** in the footer and you can confirm deploy revision in the browser.

**Troubleshooting:** In DevTools → Network, if **`report`** is **200** but **`multi-engine`** / **`multi-weekly-trend`** are **404**, the URL your browser uses for `/api/v1/brands/...` is not your FastAPI app (wrong `NEXT_PUBLIC_API_URL`, or an **old API deploy** without those routes). Redeploy the **API** from current `main`, or switch to **same-origin + `API_PROXY_TARGET`**. Newer APIs also embed SoV inside the scan **report** JSON (`sov_multi_engine`, `sov_multi_weekly_trend`); after redeploying **API + Web**, the report page should stop calling those brand routes when embed is present.

Optional but recommended:

- `ANONYMOUS_SCAN_RATE_LIMIT_PER_HOUR` (default `24`) — per **resolved** public client IP.
- `ANONYMOUS_SCAN_MESH_RATE_LIMIT_PER_HOUR` (default `400`) — shared cap when the edge still looks like Railway CGNAT (`100.64/10`) or the client IP cannot be resolved; avoids false 429s for all visitors sharing one mesh hop.
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

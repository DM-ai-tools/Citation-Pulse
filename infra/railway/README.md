# Railway deployment (production-ready)

This repo is ready for a 3-service Railway deployment:

1. `api` (FastAPI)
2. `worker` (Celery queue consumer)
3. `web` (Next.js frontend)

## Config templates

Config-as-code (set each service **Root Directory** first, then point Railway at the matching file):

| Service | Root directory | Config file |
|---------|----------------|-------------|
| API | `apps/api` | `apps/api/railway.json` |
| Worker | `apps/api` | `apps/api/railway.worker.json` |
| Web | `apps/web` | `apps/web/railway.json` |

Legacy copies under `infra/railway/*.railway.json` match the same settings when root directory is set as above.

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

- `DATABASE_URL` -> Railway Postgres URL (`postgresql://…` is auto-normalized to `postgresql+psycopg://…` on startup)
- Optional: `FORWARDED_ALLOW_IPS=*` (or rely on the API Dockerfile / start command) so Uvicorn trusts `X-Forwarded-*` from Railway’s edge. Anonymous scan rate limits use the resolved client IP.
- Optional: `ANONYMOUS_SCAN_RATE_LIMIT_PER_HOUR` (default **24** in app settings) to tune landing-page abuse protection; use `0` only if you accept disabling that limit.
- `OPENROUTER_API_KEY` -> required for scans (set on **both** API and worker if you use a separate worker; missing key yields OpenRouter HTTP 401). After deploy, open `GET /health` on the API: `openrouter_configured` must be `true` (no quotes or stray spaces in the variable value).
- `ENVIRONMENT=production`
- `LOG_LEVEL=info`
- `AUTH_JWT_SECRET` -> **required** (32+ random chars; weak defaults block API startup in production)
- `AUTH_ADMIN_EMAIL` / `AUTH_ADMIN_PASSWORD` / `AUTH_ADMIN_NAME` -> seed the first admin (optional if admin already exists)

Set these at minimum on API:

- `API_CORS_ORIGINS=https://<your-web-domain>`
- `INTERNAL_PHASE1=false` in production (native auth uses `AUTH_JWT_SECRET`)
- `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` (optional) — Google Ads search-volume estimates for **Top gap opportunities** (read when building scan reports). If missing, **Est. monthly searches** stays as a dash. Not used on the Web service.

Set these on Web:

- `NEXT_PUBLIC_API_URL=https://<your-api-domain>` — **must be present when `npm run build` runs** (Docker/Railway build). Changing it requires a **Web service rebuild**, not only a restart, or the browser will still use the old inlined URL (often `localhost:8000`, which breaks production data like Top gap opportunities).
- **Alternative (same-origin API):** `NEXT_PUBLIC_API_URL=same-origin` and set **`API_PROXY_TARGET=https://<your-api-domain>`** on the Web service at **build** time. The browser then calls `/api/v1/...` on the web host; Next.js rewrites proxy to FastAPI. Use this when you want one public origin or you keep seeing **404** on `multi-engine` because requests were accidentally hitting the web host instead of the API.
- `NEXT_PUBLIC_APP_VERSION` (optional) — e.g. `RAILWAY_GIT_COMMIT_SHA` or a release tag, passed as a Docker build-arg so `/dashboard` can show **App build:** in the footer and you can confirm deploy revision in the browser.

**Troubleshooting:** In DevTools → Network, if **`report`** is **200** but SoV fetches **404**, redeploy the **API** from current `main`. The funnel report uses **`GET /api/v1/scans/{scan_id}/sov/multi-engine`** and **`…/multi-weekly-trend`** (same public access as ``/report``). The generic ``GET /api/v1/scans/{scan_id}`` route is registered **last** so it never shadows ``…/sov/…``. Newer APIs also embed SoV inside the **report** JSON; after redeploying **API + Web**, the report page prefers embed when valid.

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

## Celery / scans stuck at "Queued" (0/16)

Scans enqueue background work via **Celery** (Postgres broker). If only **API + Web** are deployed and `ENVIRONMENT=production`, tasks used to sit in the DB forever with no worker.

**Fix (pick one):**

1. **Recommended:** Add the **worker** service (`Dockerfile.worker`, same env as API). On the **API** service set `CELERY_USE_WORKER=1` so the API does not also run tasks inline.
2. **API-only (2 services):** Leave `CELERY_USE_WORKER` unset. Current API builds auto-enable inline Celery on Railway (tasks run in the API process after `POST /scans`). Redeploy the API, then start a **new** scan (old scans stay stuck).
3. **Explicit:** Set `CELERY_TASK_ALWAYS_EAGER=true` on the API service.

Verify after deploy: `GET https://<api>/health` should include `"celery_tasks_inline": true` for API-only, or `false` when using a worker with `CELERY_USE_WORKER=1`.

## Build failed: `"/src": not found` during `COPY src`

Railway is building with the **repo root** as context but the Dockerfile expects files under **`backend/`**.

**Fix (recommended):** In the backend service → **Settings** → **Root Directory** → set:

```text
backend
```

Leave **Dockerfile path** as `backend/Dockerfile` (or `Dockerfile`). Redeploy with **clear build cache**.

**Alternative:** Keep Root Directory at repo root (`.`) and set Dockerfile path to:

```text
backend/Dockerfile.monorepo-root
```

## Build failed: `exit code 137` during `pip install`

Railway build containers often have limited RAM. **137 = process killed (out of memory).**

The backend `Dockerfile` avoids upgrading pip in a separate layer and omits Playwright from core deps (install `[browser]` locally only if needed). If the build still fails:

1. **Settings → Redeploy → Clear build cache**
2. Increase the service **memory** / plan if available
3. Confirm **Root Directory** is `backend` (not repo root with wrong `COPY` paths)

## Stuck on "Initializing" or build >10 minutes

**"Initializing"** on Railway means the image built but the deploy has not passed the **health check** yet (not the same as "Building").

### Checklist

1. **Use only one backend service.** If you have both `Citation-Pulse` and `Citation-Pulse-backend`, remove or pause one. Recommended:
   - **Backend:** root `backend/`, Dockerfile `Dockerfile`, health `/health`
   - **OR** root `apps/api/`, Dockerfile `Dockerfile`, health `/health` (not both)
2. **Root directory must match the Dockerfile paths.**
   - `backend/Dockerfile` → Railway **Root Directory** = `backend` (not repo root)
   - `apps/api/Dockerfile` → Root Directory = `apps/api`
   - `apps/web/Dockerfile` → Root Directory = `apps/web`
3. **Link Postgres** to the backend: Variables → `DATABASE_URL` = reference to Postgres service.
4. **Builder = DOCKERFILE** (not Railpack). If logs say `using build driver railpack`, switch to Dockerfile in service settings.
5. **Open deploy logs** (not build only): look for `Application startup complete` or crash loops / `schema bootstrap failed`.
6. **First Docker build** can take 10–20 minutes (Playwright + ML deps). Later builds are faster with cache.
7. **Web:** set `NEXT_PUBLIC_API_URL` before build; redeploy with rebuild after changing it.

### Recommended 3-service layout

| Railway service | Root directory | Dockerfile path | Healthcheck |
|-----------------|----------------|-----------------|-------------|
| API (backend)   | **`backend`** (required) | `backend/Dockerfile` | `/health` |
| API (alt)       | `apps/api` | `apps/api/Dockerfile` | `/health` |
| Web (frontend)  | `apps/web`     | `/` |
| Postgres        | (plugin)       | — |

Optional 4th: **worker** with root `apps/api` or `backend`, `Dockerfile.worker`, no HTTP healthcheck.

## Notes

- Celery is Postgres-backed in this project (no Redis required).
- Web build-time public env vars (`NEXT_PUBLIC_*`) are wired through the Docker build.
- The web container is configured to bind Railway's dynamic `PORT`.
- If Railway says `using build driver railpack`, Docker mode is not selected yet; switch builder to `DOCKERFILE`.

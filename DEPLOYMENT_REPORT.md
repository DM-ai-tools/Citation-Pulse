# Railway deployment readiness report

**Date:** 2026-05-22  
**Scope:** Deployment configuration only (no application behavior changes in this pass).

## Summary

The canonical Railway layout uses **`apps/api`**, **`apps/web`**, and optional **`apps/api/Dockerfile.worker`**. Legacy `backend/` and `frontend/` remain for older services but should not be used for new deploys.

| Check | Status |
|-------|--------|
| API binds `0.0.0.0` + `$PORT` | Pass |
| Web binds `0.0.0.0` + `$PORT` | Pass |
| Dockerfiles support monorepo + service root | Pass |
| `railway.json` per service | Pass |
| Healthchecks (`/health`, `/landing`) | Pass |
| Env templates (`.env.railway.example`) | Pass |
| `docker-compose` for local prod-style stack | Added (`infra/docker-compose.yml`) |
| Local Docker build | Not run (Docker CLI unavailable on agent host) |
| Local `npm run build` | Blocked (Windows file lock on `node_modules`; run on CI/Railway) |
| API tests | 86 passed, 7 failed (adapter/LLM env tests — pre-existing) |

## Files changed (deployment)

| File | Change |
|------|--------|
| `apps/web/Dockerfile` | Copy `next.config.ts` + `public/` into runtime image; `HOSTNAME=0.0.0.0`; unified `/out` artifact |
| `apps/api/Dockerfile` | `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` (smaller/faster Railway builds) |
| `apps/api/Dockerfile.worker` | Same Playwright skip |
| `.dockerignore` | Monorepo-safe ignore list for root-context builds |
| `infra/docker-compose.yml` | Local postgres + api + web stack |
| `infra/railway/README.md` | Healthcheck path aligned to `/landing` |

## Railway service configuration

### API

- **Root directory:** `apps/api`
- **Dockerfile:** `Dockerfile`
- **Config:** `apps/api/railway.json`
- **Health:** `GET /health`

### Worker (optional)

- **Root directory:** `apps/api`
- **Dockerfile:** `Dockerfile.worker`
- **Config:** `apps/api/railway.worker.json`
- Set `CELERY_USE_WORKER=1` on API when using a separate worker.

### Web

- **Root directory:** `apps/web`
- **Dockerfile:** `Dockerfile`
- **Config:** `apps/web/railway.json`
- **Health:** `GET /landing`
- **Build-time required:** `NEXT_PUBLIC_API_URL` (or `same-origin` + `API_PROXY_TARGET`)

### Postgres

- Railway plugin → link `DATABASE_URL` to API (+ worker).

## Recommended Railway variables

### API (+ worker)

```env
ENVIRONMENT=production
LOG_LEVEL=info
DATABASE_URL=<from Postgres plugin>
OPENROUTER_API_KEY=<your key>
API_CORS_ORIGINS=https://<your-web>.up.railway.app
PUBLIC_ACCESS_MODE=true
AUTH_DISABLE_JWT=true
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
```

For authenticated production, set `AUTH_JWT_SECRET`, disable public mode, and rebuild web with `NEXT_PUBLIC_SKIP_AUTH=false`.

### Web (set before build)

```env
NEXT_PUBLIC_API_URL=https://<your-api>.up.railway.app
NEXT_PUBLIC_SKIP_AUTH=true
```

Or same-origin:

```env
NEXT_PUBLIC_API_URL=same-origin
API_PROXY_TARGET=https://<your-api>.up.railway.app
```

## Post-deploy verification

1. `GET https://<api>/health` → `status: ok`, `openrouter_configured: true`
2. Open `https://<web>/landing` and run a scan
3. Confirm report loads (matrix + competitor sections)
4. If scans stay queued: add worker service or redeploy API (inline Celery on Railway by default)

## Remaining warnings

- **Playwright** remains in API dependencies; browser download is skipped in Docker builds. Full browser automation may need extra setup on worker/API if used in production.
- **7 pytest failures** are environment/adapter tests (missing API keys in test env), not deployment config regressions.
- **Local npm build** may require closing dev servers and re-running `npm ci` if Windows locks `node_modules`.

## Deployment readiness

**Ready for Railway deploy** using `apps/api` + `apps/web` (+ optional worker), with variables above and a Postgres plugin linked.

See also: `RAILWAY_DEPLOY.md`, `infra/railway/README.md`, `.env.railway.example`.

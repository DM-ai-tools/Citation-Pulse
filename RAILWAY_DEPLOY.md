# Railway deployment (CitationPulse)

Canonical services use **`apps/api`** and **`apps/web`** (not legacy `backend/` / `frontend/`).

## Services

| Service | Root directory | Dockerfile | Config |
|---------|----------------|------------|--------|
| API | `apps/api` | `Dockerfile` | `apps/api/railway.json` |
| Worker (optional) | `apps/api` | `Dockerfile.worker` | `apps/api/railway.worker.json` |
| Web | `apps/web` | `Dockerfile` | `apps/web/railway.json` |
| Postgres | Railway plugin | — | Link `DATABASE_URL` to API (+ worker) |

**Two-service minimum:** API + Web (Celery runs inline on API unless `CELERY_USE_WORKER=1`).  
**Recommended:** API + Worker + Web.

## Required variables

### API (+ worker if used)

```
ENVIRONMENT=production
DATABASE_URL=<from Postgres plugin>
AUTH_JWT_SECRET=<openssl rand -hex 32>
OPENROUTER_API_KEY=<your key>
API_CORS_ORIGINS=https://<your-web>.up.railway.app
INTERNAL_PHASE1=false
```

Optional: `AUTH_ADMIN_*`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DATAFORSEO_*`, `CELERY_USE_WORKER=1` (with worker service).

### Web (set before build — triggers rebuild)

```
NEXT_PUBLIC_API_URL=https://<your-api>.up.railway.app
```

Or same-origin:

```
NEXT_PUBLIC_API_URL=same-origin
API_PROXY_TARGET=https://<your-api>.up.railway.app
```

Optional build arg: `NEXT_PUBLIC_APP_VERSION=$RAILWAY_GIT_COMMIT_SHA`

## Verify after deploy

1. `GET https://<api>/health` → `status: ok`, `openrouter_configured: true`
2. Open web `/login`, sign up / sign in
3. Run a scan on `/landing`, confirm report and dashboard load

Full troubleshooting: `infra/railway/README.md`.

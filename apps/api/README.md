# CitationPulse API (`apps/api`)

Python 3.12+ package: FastAPI control plane, Celery workers, Alembic migrations (run from repo root or `infra/sql`).

## Setup

```bash
cd apps/api
uv sync --extra dev
# or: pip install -e ".[dev]"
```

Copy root `.env.example` to `.env` and set `DATABASE_URL`, `REDIS_URL`, engine API keys.

## Migrations

From repository root:

```bash
make migrate
# or:
cd infra/sql && alembic upgrade head
```

## Run API

```bash
make dev-api
# or:
uv run uvicorn citationpulse.main:app --reload --host 0.0.0.0 --port 8000 --app-dir apps/api/src
```

Set `PYTHONPATH=apps/api/src` or install the package in editable mode.

## Celery

```bash
celery -A citationpulse.celery_app worker -Q default,browser -l info
celery -A citationpulse.celery_app beat -l info
```

Use `PYTHONPATH=apps/api/src` from monorepo root.

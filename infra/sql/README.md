# SQL & Alembic

- **Migrations:** run from repo root with `DATABASE_URL` set (same URL as the API, but Alembic needs it in the shell environment):

```bash
# POSIX
export DATABASE_URL=postgresql+psycopg://citationpulse:citationpulse@localhost:5434/citationpulse_geo
cd infra/sql && alembic upgrade head
```

```powershell
# Windows PowerShell
$env:DATABASE_URL="postgresql+psycopg://citationpulse:citationpulse@localhost:5434/citationpulse_geo"
cd infra/sql; alembic upgrade head
```

- **One-off SQL:** [`20260208_opportunities_prompt_metrics.sql`](20260208_opportunities_prompt_metrics.sql) matches revision `20260511100000` (adds `prompts.consecutive_gap_runs`, `prompt_metrics`, `opportunities`). If `alembic upgrade head` is not an option, you can `psql` that file instead.
- **Demand resolution columns:** [`20260514_demand_resolution.sql`](20260514_demand_resolution.sql) adds `prompts.demand_score`, `demand_bucket`, `demand_source`, `demand_variant`, `demand_raw_volume`, `demand_refreshed_at` plus a refresh-age index. Idempotent; mirrors the runtime bootstrap in `citationpulse/db/runtime_bootstrap.py`.

- **RLS:** optional policies for production are documented in [`rls_optional.sql`](rls_optional.sql). Apply when the API sets `SET LOCAL app.tenant_id` on every request-scoped DB connection.

- **IVFFlat:** after sufficient `citations` rows exist, add an IVFFlat index on `snippet_vec` (see TDD §7).

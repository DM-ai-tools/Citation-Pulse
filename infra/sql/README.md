# SQL & Alembic

- **Migrations:** run from repo root with `DATABASE_URL` set:

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

- **RLS:** optional policies for production are documented in [`rls_optional.sql`](rls_optional.sql). Apply when the API sets `SET LOCAL app.tenant_id` on every request-scoped DB connection.

- **IVFFlat:** after sufficient `citations` rows exist, add an IVFFlat index on `snippet_vec` (see TDD §7).

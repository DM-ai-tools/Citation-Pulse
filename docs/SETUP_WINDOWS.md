# CitationPulse GEO — Windows Native Setup

End-to-end guide to run **CitationPulse GEO** on Windows using a native PostgreSQL install and a Python virtual env. **No containers, no Redis, no `docker compose`, no `make` required.** Postgres is the single store: data, Celery broker, Celery result backend, live scan event log, and rate-limit counters.

---

## 1. Architecture overview

| Component | What it is | Port |
|---|---|---|
| **Next.js web** (`apps/web`) | Marketing landing, scan pages, full report, dashboard | **3000** |
| **FastAPI API** (`apps/api`) | REST + SSE — `/api/v1/scans`, `/health`, `/metrics`, share/public | **8000** |
| **Celery worker** (`apps/api`) | Executes the scan: fans out to engine adapters, normalises citations, scores | — (talks to Postgres) |
| **PostgreSQL 18** with `pgvector` | Domain data + `scan_events` (SSE) + `rate_limits` + Celery broker (`kombu_*`) + result backend (`celery_taskmeta`) | **5432** |
| **Playwright Chromium** | Headless browser used by the **Google AI Overviews** engine adapter only | — |

---

## 2. What's required vs optional

### Required to run a scan end-to-end

| Item | Required? | How to get / install (Windows) |
|---|---|---|
| **Node.js 20+** + npm | Yes | `winget install OpenJS.NodeJS.LTS` |
| **Python 3.12+** | Yes | Already installed (Python 3.14 works). Or `winget install Python.Python.3.12` |
| **PostgreSQL 16+** with `pgvector` extension | Yes | [PostgreSQL Windows installer](https://www.postgresql.org/download/windows/). The `pgvector` extension ships in PostgreSQL 18 packages or via `pgxn install vector` |
| **Redis 5+** | Yes (Celery broker, SSE pub/sub) | Portable zip below — no admin needed |
| **OpenAI API key** | Yes (one engine min.) | https://platform.openai.com/api-keys |
| **Anthropic API key** | Yes-ish | https://console.anthropic.com/settings/keys |
| **Google AI (Gemini) API key** | Yes-ish | https://aistudio.google.com/app/apikey |

### Optional / can be left blank

| Item | Required? | When you'd add it |
|---|---|---|
| **Playwright Chromium** | Optional (already installed on this machine — see §3.4) | Enables the **Google AI Overviews** engine. Without it, that engine is silently skipped, the others still run. |
| **Perplexity API key** | Optional | Adds the Perplexity engine to the scan |
| **`PLAYWRIGHT_PROXY_SERVER`** | Optional | Residential proxy to avoid Google rate-limiting on AIO scrapes |
| **Cloudflare R2** (`R2_*`) | Optional | Archives raw engine responses to S3-compatible storage. Without it, `raw_payload_uri` is `null`; everything else works. |
| **Stripe** (`STRIPE_*`) | Optional | Billing endpoints return **501 Not Implemented** when unset. Only needed for Phase 2 paid SaaS / DFY plans. |
| **Clerk** (`CLERK_*`) | Optional | Phase 2 SaaS auth. Phase 1 dev mode bypasses auth via `INTERNAL_PHASE1=true`. |
| **Sentry** (`SENTRY_DSN`) | Optional | Error tracking |
| **Slack webhook** (`SLACK_WEBHOOK_URL`) | Optional | Nightly alert channel |
| **Resend** (`RESEND_API_KEY`) | Optional | Transactional email for share / report links |

---

## 3. One-time setup (Windows native)

> Run all commands in **regular** PowerShell unless a step says **Administrator**.

### 3.1 PostgreSQL — create role + database

`psql` is at `C:\Program Files\PostgreSQL\18\bin\psql.exe`. Add it to PATH for this session, then create the role and DB.

```powershell
$env:Path = "C:\Program Files\PostgreSQL\18\bin;" + $env:Path

# Prompts for the postgres superuser password you set during install
psql -U postgres -h localhost -c "CREATE ROLE citationpulse LOGIN PASSWORD 'citationpulse';"
psql -U postgres -h localhost -c "CREATE DATABASE citationpulse_geo OWNER citationpulse;"
psql -U postgres -h localhost -d citationpulse_geo -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Smoke-test (password: citationpulse)
psql -U citationpulse -h localhost -d citationpulse_geo -c "select 1;"
```

> If `CREATE EXTENSION vector;` errors with "extension not found", install pgvector:
> `winget install --id PostgreSQL.pgAdmin` won't help; either rebuild PostgreSQL with `pgvector`, or use the [pgvector Windows binaries](https://github.com/pgvector/pgvector#windows).

### 3.2 Redis — not needed

This project uses **PostgreSQL for everything**: domain data, Celery broker, Celery result backend, live scan event log (SSE), and rate-limit counters. There is no Redis dependency.

If you previously installed Memurai or portable Redis for this project, you can stop the service and remove the files:

```powershell
Stop-Service Memurai -ErrorAction SilentlyContinue
Remove-Item "$env:USERPROFILE\redis-portable" -Recurse -Force -ErrorAction SilentlyContinue
```

Memurai uninstall (optional): Settings → Apps → "Memurai Developer" → Uninstall.

### 3.3 Python venv + API dependencies

```powershell
cd "c:\Users\Kushal\.cursor\ciatiation ai\apps\api"
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
pip install -e .
```

> If `playwright` fails to install on Python 3.14, install everything else first and skip Playwright:
> `pip install fastapi "uvicorn[standard]" sqlalchemy "psycopg[binary]" alembic pydantic pydantic-settings "celery[sqlalchemy]" httpx tenacity boto3 "PyJWT[crypto]" openai anthropic google-genai python-multipart email-validator typer tldextract "sentry-sdk[fastapi]" opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi python-json-logger stripe`
>
> Google AI Overviews engine will be silently skipped, the rest work fine.

### 3.4 Playwright — install browser binaries

The Python package was installed by `pip install -e .`. Now download the **Chromium browser** Playwright drives:

```powershell
cd "c:\Users\Kushal\.cursor\ciatiation ai\apps\api"
.\.venv\Scripts\Activate.ps1
python -m playwright install chromium
```

This downloads ~290 MB to `%LOCALAPPDATA%\ms-playwright\` (one-time, cached forever). After this:

- Browsers cached at `C:\Users\<you>\AppData\Local\ms-playwright\chromium-XXXX\`
- The `Google AI Overviews` engine will start producing results in scans

To verify the install:

```powershell
python -m playwright --version
python -c "from playwright.async_api import async_playwright; print('ok')"
```

### 3.5 Configure `.env` (root of repo)

Open `c:\Users\Kushal\.cursor\ciatiation ai\.env` and set these so the API points at native Postgres + portable Redis:

```ini
DATABASE_URL=postgresql+psycopg://citationpulse:citationpulse@localhost:5432/citationpulse_geo

# Celery uses Postgres too — leave blank to derive from DATABASE_URL
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=

# Unified LLM gateway — REQUIRED. Sign up at https://openrouter.ai/keys.
# This single key proxies ChatGPT, Claude, Gemini, and Perplexity.
OPENROUTER_API_KEY="sk-or-v1-..."

# Optional model overrides (defaults are fine for most users):
# CHATGPT_MODEL=openai/gpt-4o-mini:online
# CLAUDE_MODEL=anthropic/claude-3.5-haiku:online
# GEMINI_MODEL=google/gemini-2.0-flash-001:online
# PERPLEXITY_MODEL=perplexity/sonar
# SENTIMENT_MODEL=anthropic/claude-3.5-haiku

# Optional — leave blank for development
PLAYWRIGHT_PROXY_SERVER=
```

> Settings load order is `.env` first, then `../../.env` (so the **root** `.env` is what the API reads when launched from `apps/api/`).

### 3.6 Configure `apps/web/.env.local`

```ini
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3.7 Run database migrations (one-time, plus whenever the schema changes)

```powershell
cd "c:\Users\Kushal\.cursor\ciatiation ai\apps\api"
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL = "postgresql+psycopg://citationpulse:citationpulse@localhost:5432/citationpulse_geo"
cd ..\..\infra\sql
alembic upgrade head
```

---

## 4. Per-session run commands

You need **three terminals** open during dev. Each block is one terminal. Postgres runs as a Windows service in the background — nothing to start manually.

### Terminal 1 — FastAPI (uvicorn)

```powershell
cd "c:\Users\Kushal\.cursor\ciatiation ai\apps\api"
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
uvicorn citationpulse.main:app --reload --host 0.0.0.0 --port 8000 --app-dir src
```

### Terminal 2 — Celery worker

```powershell
cd "c:\Users\Kushal\.cursor\ciatiation ai\apps\api"
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
celery -A citationpulse.celery_app worker -Q default,browser -l info --pool=solo
```

> `--pool=solo` is required on Windows. Celery's default `prefork` pool only works on Linux/macOS.

### Terminal 3 — Next.js web

```powershell
cd "c:\Users\Kushal\.cursor\ciatiation ai"
npm run dev:geo:web
```

### Smoke-test the stack

```powershell
"Postgres 5432: $((Test-NetConnection -ComputerName localhost -Port 5432 -InformationLevel Quiet))"
"FastAPI 8000:  $((Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet))"
"Web 3000:      $((Test-NetConnection -ComputerName localhost -Port 3000 -InformationLevel Quiet))"
Invoke-RestMethod http://localhost:8000/health
```

All three ports `True` and `/health` returning `{ status: "ok" }` ⇒ ready to scan.

Then go to **http://localhost:3000**, fill the form, submit. You should land on `/scan/<id>` with live engine progress streaming via SSE, and `/report/<id>` once the worker finishes.

---

## 5. Playwright integration (Google AI Overviews engine)

### How it's wired in

| Layer | File | What it does |
|---|---|---|
| Engine type | `apps/api/src/citationpulse/models/domain.py` | `EngineType.GOOGLE_AIO = "google_aio"` |
| Adapter | `apps/api/src/citationpulse/adapters/google_aio.py` | Headless Chromium → `https://www.google.com/search?q=…&hl=…`, extracts visible URLs |
| Registry | `apps/api/src/citationpulse/adapters/registry.py` | Maps `EngineType.GOOGLE_AIO` → `GoogleAIOAdapter()` |
| Worker | Celery `run_engine` task | Calls the adapter for each `(prompt, engine)` pair |

### Graceful fallback

The adapter handles missing dependencies cleanly:

```python
try:
    from playwright.async_api import async_playwright
except Exception:
    return EngineResponse("", [], "", int((time.perf_counter() - t0) * 1000), None)
```

So if you never run `playwright install chromium`, that one engine returns empty, the rest of the scan still completes.

### Optional residential proxy

Google blocks data-centre IPs aggressively. For production scans, set:

```ini
PLAYWRIGHT_PROXY_SERVER=http://USER:PASS@residential-proxy.example.com:PORT
```

The adapter passes it as `launch_kwargs["proxy"]` to Chromium. For local dev you can leave it blank — most queries still return results, just less reliably.

### Browser cache location

Playwright caches Chromium at:

```
C:\Users\<you>\AppData\Local\ms-playwright\
  ├── chromium-1217\                 (full browser)
  ├── chromium_headless_shell-1217\  (headless variant the adapter uses)
  ├── ffmpeg-1011\
  └── winldd-1007\
```

To upgrade the browser when Playwright bumps versions: `python -m playwright install chromium` again.

---

## 6. Engine API key (single OpenRouter key)

CitationPulse uses **one** API key to access all four AI engines via [OpenRouter](https://openrouter.ai). This avoids having to manage four separate billing accounts and lets you swap models per-engine through `.env` only.

| Var | What | Where to get |
|---|---|---|
| `OPENROUTER_API_KEY` | **Required.** Auth for ChatGPT, Claude, Gemini, Perplexity. | https://openrouter.ai/keys |
| `OPENROUTER_HTTP_REFERER` (optional) | Sent as `HTTP-Referer` header — appears on the public leaderboard if you opt-in. | — |
| `OPENROUTER_APP_TITLE` (optional) | Sent as `X-Title` header. | — |

**Steps**:

1. Open [https://openrouter.ai/keys](https://openrouter.ai/keys) and click **Create Key**.
2. Add at least $5 of credits at [https://openrouter.ai/credits](https://openrouter.ai/credits) — typical scans cost <$0.01 each.
3. Paste the key into `.env` as `OPENROUTER_API_KEY=sk-or-v1-…`.
4. Restart uvicorn (the `--reload` flag picks up the change automatically).

**Choosing models**: by default we use cost-efficient flagship models with web search enabled (`gpt-4o-mini:online`, `claude-3.5-haiku:online`, `gemini-2.0-flash-001:online`, `perplexity/sonar`). To upgrade, override per-engine in `.env`:

```ini
CHATGPT_MODEL=openai/gpt-4o:online              # bigger, more accurate
CLAUDE_MODEL=anthropic/claude-3.5-sonnet:online # bigger Claude
GEMINI_MODEL=google/gemini-2.0-pro-exp:online   # Gemini 2.0 Pro
PERPLEXITY_MODEL=perplexity/sonar-pro           # bigger sonar
```

Browse all available models at [https://openrouter.ai/models](https://openrouter.ai/models).

If `OPENROUTER_API_KEY` is empty, the scan endpoint will run with **zero LLM engines** — the matrix will be empty until you add the key.

---

## 7. Optional integrations — when and how

### 7.1 Cloudflare R2 (raw payload archive)

Stores raw engine responses (JSON / HTML) for audit + reprocessing without re-paying engine costs.

| Var | What |
|---|---|
| `R2_ACCOUNT_ID` | Cloudflare account ID (right sidebar of Dashboard → R2) |
| `R2_ACCESS_KEY_ID` | API token "Access Key ID" |
| `R2_SECRET_ACCESS_KEY` | API token "Secret Access Key" (shown once) |
| `R2_BUCKET_RAW_PAYLOADS` | Bucket name (default `citationpulse-raw`) |
| `R2_PUBLIC_BASE_URL` | If you front the bucket with a custom domain |

`apps/api/src/citationpulse/storage/r2.py` is a soft-no-op when these are blank (just logs a warning).

### 7.2 Stripe (billing — Phase 2)

| Var | What |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_…` / `sk_live_…` |
| `STRIPE_WEBHOOK_SECRET` | Verifies inbound webhook signatures |
| `STRIPE_PRICE_SAAS` | Price ID for the **$597/mo** SaaS plan |
| `STRIPE_PRICE_DFY` | Price ID for the **$1200/mo** DFY plan |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` (web) | Browser key |

Until set, `/api/v1/billing/checkout-saas` and `…/checkout-dfy` return **501 Not Implemented**. Scans / reports / dashboard work without Stripe.

### 7.3 Clerk (auth — Phase 2)

`apps/api/src/citationpulse/api/deps.py` runs in **dev-bypass** when `INTERNAL_PHASE1=true` and `CLERK_JWKS_URL` is empty — every request is treated as an anonymous tenant, which is what you want for local development. Set `CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUDIENCE`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` only when you flip the SaaS phase on.

### 7.4 Observability

| Var | What |
|---|---|
| `SENTRY_DSN` | Error tracking |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry traces (Tempo / Honeycomb / etc.) |
| `LOG_LEVEL` | `info` / `debug` |

---

## 8. Common errors & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `psycopg.errors.ConnectionTimeout … port: 5434` | API still reading the wrong port | Edit root `.env` → `DATABASE_URL=…localhost:5432…`, restart uvicorn |
| Form toast: **"Failed to fetch"** | API process not running on `:8000` | Start uvicorn (Terminal 2) |
| Scan stuck on **"STARTING…"** | Celery worker not running | Start `celery … worker --pool=solo` (Terminal 2). Confirm Postgres on `:5432`. |
| Toast shows raw JSON `[{ code: too_small … }]` | Stale browser bundle from before `safeParse` fix | Hard-refresh browser (`Ctrl+Shift+R`) |
| Celery exits with `BillardOSError on Windows` | Default prefork pool | Add `--pool=solo` |
| `playwright._impl._errors.Error: Executable doesn't exist at …chromium-XXXX` | Browser binaries not downloaded | `python -m playwright install chromium` (in venv) |
| `psql: error: FATAL: password authentication failed for user "citationpulse"` | Role / password mismatch | Re-run `CREATE ROLE citationpulse LOGIN PASSWORD 'citationpulse'` (or `ALTER ROLE …`) |
| Browser shows `{"detail":"Not Found"}` at `:8000/` | You opened FastAPI's root in a browser | That's normal — use `/docs` for the interactive API, or hit `/api/v1/...` from the web app |

---

## 9. Where to dig in code

| Concern | Path |
|---|---|
| API config / settings | `apps/api/src/citationpulse/core/config.py` |
| FastAPI app + routes | `apps/api/src/citationpulse/main.py`, `apps/api/src/citationpulse/api/v1/*.py` |
| Celery tasks | `apps/api/src/citationpulse/tasks/geo.py`, `apps/api/src/citationpulse/celery_app.py` |
| Engine adapters | `apps/api/src/citationpulse/adapters/*.py` |
| DB models | `apps/api/src/citationpulse/models/domain.py` |
| Migrations | `infra/sql/versions/*.py` |
| Web entry / form | `apps/web/src/app/(marketing)/page.tsx`, `apps/web/src/components/marketing/ScanForm.tsx` |
| Live scan / report | `apps/web/src/app/scan/[scanId]/page.tsx`, `apps/web/src/app/report/[scanId]/page.tsx` |
| Web API client | `apps/web/src/services/scans.ts`, `apps/web/src/services/apiClient.ts` |

---

## 10. Auto-start helper (optional)

Drop this into the repo root as `scripts/start-stack.ps1` and run with `pwsh` / `powershell` to spawn uvicorn + celery + web in three new windows.

```powershell
$repo = $PSScriptRoot | Split-Path -Parent
$venv = "$repo\apps\api\.venv\Scripts\Activate.ps1"
Start-Process pwsh -ArgumentList "-NoExit","-Command","cd '$repo\apps\api'; . '$venv'; `$env:PYTHONPATH='src'; uvicorn citationpulse.main:app --reload --port 8000 --app-dir src"
Start-Process pwsh -ArgumentList "-NoExit","-Command","cd '$repo\apps\api'; . '$venv'; `$env:PYTHONPATH='src'; celery -A citationpulse.celery_app worker -Q default,browser -l info --pool=solo"
Start-Process pwsh -ArgumentList "-NoExit","-Command","cd '$repo'; npm run dev:geo:web"
```

---

## License

Same as the repo (Proprietary / demo).

#requires -Version 5.1
<#
.SYNOPSIS
  One-shot bring-up for the CitationPulse GEO backend on Windows (no Docker).

  - Installs Memurai (Redis for Windows) via winget if missing.
  - Creates Python venv (.venv) using Python 3.14 (or latest installed).
  - Installs apps/api[dev] in editable mode.
  - Creates `citationpulse` role + `citationpulse_geo` DB on the local
    PostgreSQL 18 (will prompt for the `postgres` superuser password).
  - Rewrites root .env to point at native ports (5432 / 6379).
  - Runs Alembic migrations.

  After this, run `scripts\start-api.ps1` (terminal A) and
  `scripts\start-worker.ps1` (terminal B).

.NOTES
  Run from repo root in a NEW PowerShell window. The Memurai install step
  needs administrator rights — re-launch elevated if winget fails.
#>

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repo
Write-Host "==> Repo: $repo" -ForegroundColor Cyan

# ---- 1) Memurai (Redis for Windows) ----------------------------------------
$mem = Get-Service Memurai -ErrorAction SilentlyContinue
if (-not $mem) {
  Write-Host "==> Installing Memurai (Redis for Windows)…" -ForegroundColor Cyan
  try {
    winget install --id Memurai.MemuraiDeveloper --silent `
      --accept-source-agreements --accept-package-agreements
  } catch {
    Write-Warning "Memurai install failed — re-run this script from an elevated PowerShell."
    throw
  }
  $mem = Get-Service Memurai -ErrorAction SilentlyContinue
}
if ($mem -and $mem.Status -ne 'Running') { Start-Service Memurai }
Write-Host "    Memurai: $((Get-Service Memurai).Status)" -ForegroundColor Green

# ---- 2) Postgres role + DB --------------------------------------------------
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
if (-not (Test-Path $psql)) { throw "psql not found at $psql — is PostgreSQL 18 installed?" }
Write-Host "==> Creating role + DB (you will be prompted for the 'postgres' superuser password)…" -ForegroundColor Cyan

# Helper: run a single SQL statement against the postgres DB
function Invoke-PgSql([string]$sql, [string]$db = "postgres") {
  & $psql -U postgres -d $db -v ON_ERROR_STOP=1 -c $sql
}

# Idempotent role + DB creation (psql DDL doesn't support IF NOT EXISTS for ROLE/DATABASE
# in all versions, so we use DO blocks / catch).
$createRole = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'citationpulse') THEN
    CREATE ROLE citationpulse LOGIN PASSWORD 'citationpulse';
  END IF;
END
`$`$;
"@
Invoke-PgSql $createRole

$dbExists = (& $psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='citationpulse_geo';").Trim()
if ($dbExists -ne "1") {
  Invoke-PgSql "CREATE DATABASE citationpulse_geo OWNER citationpulse;"
} else {
  Write-Host "    Database citationpulse_geo already exists — skipping create." -ForegroundColor Yellow
}

try {
  Invoke-PgSql "CREATE EXTENSION IF NOT EXISTS vector;" "citationpulse_geo"
  Write-Host "    pgvector extension OK." -ForegroundColor Green
} catch {
  Write-Warning "pgvector extension is not installed for PostgreSQL 18."
  Write-Warning "Install it from https://github.com/pgvector/pgvector/releases (Windows zip), then re-run this script."
  throw
}

# ---- 3) Rewrite root .env to native ports ----------------------------------
$envPath = Join-Path $repo ".env"
if (Test-Path $envPath) {
  Write-Host "==> Updating .env to use localhost:5432 and localhost:6379…" -ForegroundColor Cyan
  $orig = Get-Content $envPath -Raw
  $next = $orig -replace 'localhost:5434', 'localhost:5432' `
                -replace 'localhost:6380', 'localhost:6379'
  if ($orig -ne $next) {
    Set-Content -Path $envPath -Value $next -Encoding UTF8 -NoNewline
    Write-Host "    .env rewritten." -ForegroundColor Green
  } else {
    Write-Host "    .env already uses native ports." -ForegroundColor Yellow
  }
}

# ---- 4) Python venv + deps --------------------------------------------------
if (-not (Test-Path "$repo\.venv\Scripts\python.exe")) {
  Write-Host "==> Creating .venv with Python 3.14…" -ForegroundColor Cyan
  & py -3.14 -m venv .venv
}
& "$repo\.venv\Scripts\python.exe" -m pip install -U pip wheel setuptools

Write-Host "==> Installing apps/api in editable mode…" -ForegroundColor Cyan
& "$repo\.venv\Scripts\python.exe" -m pip install -e ".\apps\api[dev]"

# ---- 5) Alembic migrations --------------------------------------------------
Write-Host "==> Running Alembic migrations…" -ForegroundColor Cyan
$env:DATABASE_URL = "postgresql+psycopg://citationpulse:citationpulse@localhost:5432/citationpulse_geo"
Push-Location "$repo\infra\sql"
try {
  & "$repo\.venv\Scripts\python.exe" -m alembic upgrade head
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "==> SETUP COMPLETE" -ForegroundColor Green
Write-Host "    Terminal A: .\scripts\start-api.ps1"
Write-Host "    Terminal B: .\scripts\start-worker.ps1   (only needed for scans to actually progress)"

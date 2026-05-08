#requires -Version 5.1
<#
.SYNOPSIS
  Start a Celery worker that actually executes scan jobs (terminal B).
  Run AFTER scripts\start-api.ps1 is up.
#>

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repo

if (-not (Test-Path "$repo\.venv\Scripts\python.exe")) {
  throw "No .venv found. Run scripts\setup-backend.ps1 first."
}

. "$repo\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH = "apps\api\src"

Write-Host "==> Starting Celery worker (default queue) …" -ForegroundColor Cyan
celery -A citationpulse.celery_app worker -Q default -l info

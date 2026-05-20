#requires -Version 5.1
<#
.SYNOPSIS
  Start a Celery worker that actually executes scan jobs (terminal B).
  Run AFTER scripts\start-api.ps1 is up.
#>

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repo

$venv = if (Test-Path "$repo\apps\api\.venv\Scripts\celery.exe") { "$repo\apps\api\.venv" }
        elseif (Test-Path "$repo\.venv\Scripts\celery.exe") { "$repo\.venv" }
        else { throw "No venv with celery. Run: cd apps\api; py -3.14 -m venv .venv; pip install -e ." }

. "$repo\scripts\load-env.ps1"
$env:PYTHONPATH = "apps\api\src"
$celery = Join-Path $venv "Scripts\celery.exe"

Write-Host "==> Starting Celery worker …" -ForegroundColor Cyan
& $celery -A citationpulse.celery_app worker -Q default,browser -l info --pool=solo

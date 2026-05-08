#requires -Version 5.1
<#
.SYNOPSIS
  Start the FastAPI backend on http://localhost:8000 (terminal A).
#>

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repo

if (-not (Test-Path "$repo\.venv\Scripts\python.exe")) {
  throw "No .venv found. Run scripts\setup-backend.ps1 first."
}

. "$repo\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH = "apps\api\src"

Write-Host "==> Starting uvicorn on http://localhost:8000 …" -ForegroundColor Cyan
uvicorn citationpulse.main:app --reload --host 0.0.0.0 --port 8000

#requires -Version 5.1
<#
.SYNOPSIS
  Start the FastAPI backend on http://localhost:8000 (terminal A).
#>

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repo

$venv = if (Test-Path "$repo\apps\api\.venv\Scripts\uvicorn.exe") { "$repo\apps\api\.venv" }
        elseif (Test-Path "$repo\.venv\Scripts\uvicorn.exe") { "$repo\.venv" }
        else { throw "No venv with uvicorn. Run: cd apps\api; py -3.14 -m venv .venv; pip install -e ." }

. "$repo\scripts\load-env.ps1"
$env:PYTHONPATH = "apps\api\src"
$uvicorn = Join-Path $venv "Scripts\uvicorn.exe"

$portFile = Join-Path $repo ".dev-api-port"
$port = if ($env:DEV_API_PORT) { [int]$env:DEV_API_PORT }
        elseif (Test-Path $portFile) { [int](Get-Content $portFile -Raw) }
        else { 8000 }

$reloadDir = Join-Path $repo "apps\api\src"
# --reload on Windows often leaves ghost listeners on :8000 after Ctrl+C; opt in with DEV_API_RELOAD=1
$useReload = $env:DEV_API_RELOAD -eq "1"
Write-Host "==> Starting uvicorn on http://localhost:$port …" -ForegroundColor Cyan
if ($useReload) {
    & $uvicorn citationpulse.main:app --reload --reload-dir $reloadDir --host 0.0.0.0 --port $port
} else {
    & $uvicorn citationpulse.main:app --host 0.0.0.0 --port $port
}

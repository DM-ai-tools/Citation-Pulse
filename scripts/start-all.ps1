#requires -Version 5.1
# Start web (:3000), API (:8000), Celery in this terminal. Cleans old processes first.
# Usage:  npm run dev
#         npm run restart

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repo

$nodePath = "C:\Program Files\nodejs"
if ($env:Path -notlike "*$nodePath*") {
    $env:Path = "$nodePath;" + $env:Path
}

& "$repo\scripts\clean-dev.ps1"
$portFile = Join-Path $repo ".dev-api-port"
if (Test-Path $portFile) {
    $env:DEV_API_PORT = (Get-Content $portFile -Raw).Trim()
    $apiPort = [int]$env:DEV_API_PORT
    $webEnv = Join-Path $repo "apps\web\.env.local"
    if (Test-Path $webEnv) {
        $content = Get-Content $webEnv -Raw
        $target = "http://127.0.0.1:$apiPort"
        $updated = $content
        $updated = $updated -replace 'API_PROXY_TARGET=http://127\.0\.0\.1:\d+', "API_PROXY_TARGET=$target"
        $updated = $updated -replace 'API_PROXY_TARGET=http://localhost:\d+', "API_PROXY_TARGET=$target"
        $updated = $updated -replace 'NEXT_PUBLIC_API_URL=http://localhost:\d+', "NEXT_PUBLIC_API_URL=http://localhost:$apiPort"
        if ($updated -ne $content) {
            Set-Content -Path $webEnv -Value $updated -Encoding utf8 -NoNewline
            Write-Host "Updated apps/web/.env.local -> API port $apiPort" -ForegroundColor Yellow
        }
    }
}

if (-not (Test-Path "$repo\node_modules\concurrently")) {
    Write-Host "Installing dev dependencies…" -ForegroundColor Yellow
    npm.cmd install
}

Write-Host ""
$apiPort = if ($env:DEV_API_PORT) { $env:DEV_API_PORT } else { "8000" }
Write-Host "Dev stack running (keep this terminal open):" -ForegroundColor Green
Write-Host "  Web     http://localhost:3000/login  (root redirects here)"
Write-Host "  API     http://localhost:$apiPort/docs"
Write-Host "  Stop    Ctrl+C  then  npm run stop"
Write-Host "  Restart npm run restart"
Write-Host ""

npm.cmd run stack:run

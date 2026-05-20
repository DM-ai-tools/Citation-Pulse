#requires -Version 5.1
# Free ports 3000/8000+ and stop leftover dev processes (safe to run before every start).

$ErrorActionPreference = "SilentlyContinue"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repo

function Test-PortBindable([int]$Port) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            try { $listener.Stop() } catch { }
        }
    }
}

function Stop-ListenersOnPort([int]$Port) {
    $pids = @(
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    foreach ($procId in $pids) {
        if (-not $procId -or $procId -le 0) { continue }
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        cmd /c "taskkill /F /PID $procId /T" 2>$null | Out-Null
    }
}

function Stop-VenvPythonProcesses {
    $venvPy = Join-Path $repo "apps\api\.venv\Scripts\python.exe"
    Get-CimInstance Win32_Process -Filter "name='python.exe' OR name='pythonw.exe'" -ErrorAction SilentlyContinue |
        ForEach-Object {
            $kill = $false
            if ($_.ExecutablePath -and $_.ExecutablePath -ieq $venvPy) { $kill = $true }
            elseif ($_.CommandLine -match [regex]::Escape($repo) -and $_.CommandLine -match 'uvicorn|celery|citationpulse') {
                $kill = $true
            }
            if ($kill) {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                cmd /c "taskkill /F /PID $($_.ProcessId) /T" 2>$null | Out-Null
            }
        }
}

Write-Host "Cleaning dev processes…" -ForegroundColor Yellow

if (Test-Path "$repo\node_modules\.bin\kill-port.cmd") {
    & "$repo\node_modules\.bin\kill-port.cmd" 3000 8000 8001 8002 2>$null
}

Stop-VenvPythonProcesses
Get-CimInstance Win32_Process -Filter "name='celery.exe'" -ErrorAction SilentlyContinue |
    ForEach-Object { cmd /c "taskkill /F /PID $($_.ProcessId) /T" 2>$null | Out-Null }

foreach ($round in 1..3) {
    Stop-ListenersOnPort 3000
    Stop-ListenersOnPort 8000
    Stop-ListenersOnPort 8001
    Stop-ListenersOnPort 8002
    Start-Sleep -Milliseconds 800
}

Stop-VenvPythonProcesses
Start-Sleep -Seconds 1

$apiPort = 8000
foreach ($candidate in 8000, 8001, 8002, 8003) {
    if (Test-PortBindable $candidate) {
        $apiPort = $candidate
        break
    }
}

$env:DEV_API_PORT = "$apiPort"
Set-Content -Path (Join-Path $repo ".dev-api-port") -Value $apiPort -Encoding ascii -NoNewline

$webOk = Test-PortBindable 3000
if (-not $webOk) {
    Write-Host "Warning: port 3000 is in use. Stop the other Next.js server or run: npm run stop" -ForegroundColor Red
}

if ($apiPort -ne 8000) {
    Write-Host "Port 8000 is stuck (Windows ghost socket). Using API port $apiPort instead." -ForegroundColor Yellow
    Write-Host "  Update apps/web/.env.local: NEXT_PUBLIC_API_URL=http://localhost:$apiPort" -ForegroundColor Yellow
}

if ($webOk) {
    Write-Host "Web port 3000 is free. API will use port $apiPort." -ForegroundColor Green
}

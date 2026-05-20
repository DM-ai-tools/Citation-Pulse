#requires -Version 5.1
# Stop web, API, Celery, and free ports 3000/8000.

$repo = (Resolve-Path "$PSScriptRoot\..").Path
& "$repo\scripts\clean-dev.ps1"

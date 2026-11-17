# Launch DA Sumit
$ErrorActionPreference = "Stop"

# Always run from the folder this script lives in.
Set-Location -Path $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Virtual environment not found. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# launch.py waits until the server is actually ready, then opens the browser.
& $python (Join-Path $PSScriptRoot "launch.py")

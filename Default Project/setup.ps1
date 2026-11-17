# Sumit07 setup script (Windows PowerShell)
# Installs Python (if needed), creates a virtual environment, and installs dependencies.

$ErrorActionPreference = "Stop"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "   Sumit07 - AI Data Analyst setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

function Test-Python {
    try {
        python --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

if (-not (Test-Python)) {
    Write-Host "Python was not found." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing Python 3.12 via winget..." -ForegroundColor Yellow
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        Write-Host ""
        Write-Host "Python installed. Please CLOSE this window, open a new PowerShell, and re-run setup.ps1." -ForegroundColor Yellow
        exit 0
    } else {
        Write-Host "winget is not available. Install Python 3.10+ from https://www.python.org/downloads/ and re-run this script." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Green
python -m venv .venv

Write-Host "Activating and installing dependencies..." -ForegroundColor Green
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env - add your OPENAI_API_KEY before running." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "Start the app with:" -ForegroundColor Cyan
Write-Host "   .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "   streamlit run app.py" -ForegroundColor White

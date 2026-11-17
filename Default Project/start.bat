@echo off
REM ============================================================
REM  DA Sumit - one-click start
REM  Runs the server in the background, waits until it is ready,
REM  then opens the browser. Closing this window does NOT stop it.
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   First run detected - installing everything now...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
    if errorlevel 1 (
        echo.
        echo   Setup failed. See the messages above.
        pause
        exit /b 1
    )
)

echo.
echo   ============================================
echo      DA Sumit - Autonomous AI Data Analyst
echo   ============================================
echo.

REM Already running? Just open it.
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { if((Invoke-WebRequest 'http://127.0.0.1:8501/_stcore/health' -UseBasicParsing -TimeoutSec 2).Content.Trim() -eq 'ok'){ exit 0 } } catch {}; exit 1"
if not errorlevel 1 (
    echo   DA Sumit is already running. Opening it...
    start "" "http://127.0.0.1:8501"
    ping -n 3 127.0.0.1 >nul
    exit /b 0
)

echo   Starting the server in the background...
set DA_SUMIT_NO_BROWSER=1
start "" ".venv\Scripts\pythonw.exe" launch.py

echo   Waiting for the server to be ready...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 180;$i++){ try { if((Invoke-WebRequest 'http://127.0.0.1:8501/_stcore/health' -UseBasicParsing -TimeoutSec 2).Content.Trim() -eq 'ok'){ $ok=$true; break } } catch {}; Start-Sleep -Milliseconds 400 }; if(-not $ok){ exit 1 }"

if errorlevel 1 (
    echo.
    echo   The server did not start. Last lines from outputs\server.log:
    echo   ------------------------------------------------------------
    powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path 'outputs\server.log') { Get-Content 'outputs\server.log' -Tail 25 } else { 'server.log not found' }"
    echo   ------------------------------------------------------------
    echo.
    echo   Please screenshot this window and share it.
    pause
    exit /b 1
)

echo.
echo   DA Sumit is running at http://127.0.0.1:8501
echo.
echo   You can safely CLOSE this window - the app keeps running in the background.
echo   To stop it later, double-click stop.bat.
echo.
start "" "http://127.0.0.1:8501"
ping -n 4 127.0.0.1 >nul
exit /b 0

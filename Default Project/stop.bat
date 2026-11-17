@echo off
REM ============================================================
REM  DA Sumit - stop the background server
REM ============================================================
echo.
echo   Stopping DA Sumit...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue; if ($conns) { $conns | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; 'Server stopped.' } else { 'DA Sumit was not running.' }"

echo.
ping -n 3 127.0.0.1 >nul

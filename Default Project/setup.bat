@echo off
REM ============================================================
REM  DA Sumit - one-time setup
REM  Bypasses PowerShell execution policy so it always works.
REM ============================================================
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

echo.
pause

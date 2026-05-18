@echo off
setlocal

cd /d "%~dp0"

set "INTERVAL_SECONDS=60"

echo PC-Monitor is running. Press Ctrl+C to stop.
echo.

:loop
echo ==================================================
echo [%date% %time%] Starting monitor check...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Program\monitor.ps1"

if errorlevel 1 (
    echo [%date% %time%] Monitor finished with warnings or errors. ExitCode=%errorlevel%
) else (
    echo [%date% %time%] Monitor finished successfully.
)

echo Waiting %INTERVAL_SECONDS% seconds before next check...
timeout /t %INTERVAL_SECONDS% /nobreak >nul
echo.
goto loop

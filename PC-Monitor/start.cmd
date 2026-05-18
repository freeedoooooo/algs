@echo off
setlocal

cd /d "%~dp0"

set "INTERVAL_SECONDS=60"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format ''yyyy-MM-dd HH:mm:ss''"') do set "NOW=%%i"

echo PC-Monitor is running. Press Ctrl+C to stop.
echo.

:loop
echo ==================================================
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format ''yyyy-MM-dd HH:mm:ss''"') do set "NOW=%%i"
echo [%NOW%] Starting monitor check...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Program\monitor.ps1"

if errorlevel 1 (
    for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format ''yyyy-MM-dd HH:mm:ss''"') do set "NOW=%%i"
    echo [%NOW%] Monitor finished with warnings or errors. ExitCode=%errorlevel%
) else (
    for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format ''yyyy-MM-dd HH:mm:ss''"') do set "NOW=%%i"
    echo [%NOW%] Monitor finished successfully.
)

echo Waiting %INTERVAL_SECONDS% seconds before next check...
timeout /t %INTERVAL_SECONDS% /nobreak >nul
echo.
goto loop

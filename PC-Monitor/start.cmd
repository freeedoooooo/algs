@echo off
setlocal

cd /d "%~dp0"

echo Running PC-Monitor...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0monitor.ps1"

echo.
if errorlevel 1 (
    echo Monitor finished with warnings or errors. ExitCode=%errorlevel%
) else (
    echo Monitor finished successfully.
)

echo.
pause

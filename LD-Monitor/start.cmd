@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0core\start.ps1" -Inline
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="2" (
    timeout /t 3 /nobreak >nul
)
exit /b %EXIT_CODE%

@echo off
setlocal

set "ROOT=%~dp0"
if exist "%ROOT%Monitor.exe" (
    start "" "%ROOT%Monitor.exe"
    exit /b
)

echo Monitor.exe not found.
exit /b 1

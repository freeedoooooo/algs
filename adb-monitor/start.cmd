@echo off
setlocal

set "ROOT=%~dp0"
set "EXE1=%ROOT%AdbMonitor.Gui.exe"
set "EXE2=%ROOT%src\AdbMonitor.Gui\bin\Release\net8.0-windows\win-x64\publish\AdbMonitor.Gui.exe"

if exist "%EXE1%" (
    start "" "%EXE1%"
    exit /b
)

if exist "%EXE2%" (
    start "" "%EXE2%"
    exit /b
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%ROOT%core\gui.ps1"

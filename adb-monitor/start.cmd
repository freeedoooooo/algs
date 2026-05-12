@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0monitor-gui.ps1"

@echo off
setlocal

REM 获取脚本所在目录（支持中文路径和空格）
set "SCRIPT_DIR=%~dp0"

REM 切换到脚本目录，确保相对路径正确
cd /d "%SCRIPT_DIR%"

REM 启动 PowerShell GUI（自动传递配置文件路径）
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA ^
    -File "%SCRIPT_DIR%monitor-gui.ps1" ^
    -ConfigPath "%SCRIPT_DIR%monitor.config"

REM 如果执行失败，显示错误信息
if errorlevel 1 (
    echo.
    echo [错误] GUI 启动失败
    echo 请检查：
    echo   1. monitor.config 文件是否存在
    echo   2. PowerShell 版本是否在 3.0 以上
    echo   3. 是否有足够的权限
    echo.
    pause
)

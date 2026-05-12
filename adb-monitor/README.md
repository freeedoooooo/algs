# adb-monitor

## 推荐入口

- 开发/调试：双击 `start.cmd`（优先启动已发布的 exe，找不到则回退到 PowerShell GUI）
- 正式分发：发布 `src\AdbMonitor.Gui\AdbMonitor.Gui.csproj` 生成的 `AdbMonitor.Gui.exe`
- 发布机器需要 .NET 8 SDK，目标机器不需要额外运行时环境

## 目录说明

- `monitor.config`：外部配置
- `core\runner.ps1`：后台循环
- `core\check.ps1`：单次健康检查
- `core\gui.ps1`：旧版 PowerShell GUI，当前保留作兼容
- `src\AdbMonitor.Gui\`：原生 WinForms GUI 源码
- `log\`：运行日志
- `runtime\`：运行时文件

## 配置重点

- `ldplayer_path`：雷电模拟器主目录
- `common_ldplayer_dirs`：备用雷电路径，按顺序兜底
- `schedule_interval_seconds`：轮询间隔，单位秒
- `expected_healthy_devices`：期望健康模拟器数量
- `alert_cooldown_minutes`：邮件告警冷却时间
- `mail_user` / `mail_password` / `mail_to`：邮件告警配置
- `log_max_size_mb`：单日志文件最大值
- `log_retention_days`：日志保留天数

## 说明

- 日志和运行时文件都已加入 `.gitignore`
- 目标机器只需要原生 Windows，不需要 Python 等额外环境
- 发布命令示例：`dotnet publish .\src\AdbMonitor.Gui\AdbMonitor.Gui.csproj -c Release -r win-x64 --self-contained true`

# adb-monitor

## 根目录保留的文件

- `start.cmd`：双击打开 GUI，并自动启动后台监控
- `monitor.config`：监控配置文件
- `README.md`：使用说明

## 内部目录

- `core/gui.ps1`：GUI 主程序，不需要手动执行
- `core/runner.ps1`：后台监控循环
- `core/check.ps1`：单次健康检查
- `runtime/`：运行时文件
- `log/`：日志目录

## 使用方式

1. 双击 `start.cmd`
2. 在 GUI 中查看日志、打开配置、启动或停止监控
3. 关闭 GUI 时，后台监控会自动停止

## 配置说明

- `ldplayer_path`：雷电模拟器主目录
- `common_ldplayer_dirs`：备用雷电目录，按顺序尝试
- `schedule_interval_seconds`：监控间隔，单位为秒
- `expected_healthy_devices`：期望健康模拟器数量
- `alert_cooldown_minutes`：告警冷却时间
- `alert_state_file`：告警冷却状态文件
- `mail_enabled`：是否启用邮件告警
- `mail_user`：发件邮箱
- `mail_password`：SMTP 授权码
- `mail_to`：收件邮箱列表
- `log_directory`：日志目录
- `log_file_name`：日志文件名前缀
- `log_max_size_mb`：单个日志文件大小上限
- `log_retention_days`：日志保留天数

# adb-monitor

当前目录结构：

- 根目录
  `start.ps1`、`stop.ps1`、`monitor.config`、`README.md`
- `core/`
  内部脚本：`check.ps1`、`runner.ps1`
- `runtime/`
  运行态文件：`runner.pid`、`alert.state.json`
- `log/`
  日志目录

## 常用命令

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\core\check.ps1
```

## 监控规则

- 每次检查会统计当前 ADB 连接设备中的健康模拟器数量
- 设备状态必须是 `device`
- `adb shell getprop sys.boot_completed` 必须返回 `1`
- 每次执行结束后会额外输出一个空行，方便区分每轮结果

## 日志规则

- 每天一个日志文件，例如 `monitor-20260511.log`
- 只保留最近 7 天日志
- 单个日志超过 50MB 时直接删除后重写
- 黑窗口输出与日志文件内容保持一致
- 黑窗口每 3600 秒清屏一次

## 配置说明

- `ldplayer_path`
  主模拟器目录，优先使用；失效后自动走备用规则
- `common_ldplayer_dirs`
  备用目录列表，按顺序尝试，前面的优先级更高
- `expected_healthy_devices`
  期望健康数量，低于该值会输出错误日志并触发告警逻辑
- `alert_cooldown_minutes`
  告警冷却时间。处于冷却期内时，不重复发送同类告警邮件
- `mail_enabled`
  是否启用邮件通知
- `mail_user`
  发件邮箱，必须填写完整邮箱地址
- `mail_password`
  发件邮箱 SMTP 授权码
- `mail_to`
  收件邮箱列表，使用分号分隔，必须填写完整邮箱地址
- `mail_smtp_host`
  SMTP 服务器地址
- `mail_smtp_port`
  SMTP 端口
- `mail_smtp_ssl`
  是否启用 SSL
- `mail_subject_prefix`
  邮件主题前缀
- `mail_timeout_seconds`
  邮件发送超时时间
- `alert_state_file`
  告警冷却状态文件

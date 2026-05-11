# adb-monitor

现在目录按职责拆成 4 块：

- 根目录
  `start.ps1`、`stop.ps1`、`monitor.config`、`README.md`
- `core/`
  内部执行脚本：`check.ps1`、`runner.ps1`
- `runtime/`
  运行态文件：`runner.pid`
- `log/`
  日志文件

## 常用命令

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\core\check.ps1
```

## 规则

- 每天一个日志文件
- 日志名形如 `monitor-YYYYMMDD.log`
- 只保留最近 7 天
- 单文件超过 50MB 直接删掉重写
- 黑窗口输出和日志内容保持一致

## 配置

- `ldplayer_path`
  主路径，优先使用；失效后自动走备用规则
- `common_ldplayer_dirs`
  备用路径列表，前两个优先级最高
- `expected_healthy_devices`
  期望健康运行的模拟器数量，低于这个值会打印 `ERROR`
- `alert_cooldown_minutes`
  预留给后续通知使用，用来控制重复提醒间隔
- `mail_enabled`
  是否启用邮件通知
- `mail_user`
  发件邮箱
- `mail_password`
  发件邮箱授权码
- `mail_to`
  收件邮箱列表，分号分隔
- `mail_smtp_host`
  SMTP 服务器，QQ 邮箱一般是 `smtp.qq.com`
- `mail_smtp_port`
  SMTP 端口，默认 `587`
- `mail_smtp_ssl`
  是否启用 SSL
- `mail_subject_prefix`
  邮件主题前缀
- `mail_timeout_seconds`
  SMTP 发送超时时间
- `alert_state_file`
  告警冷却状态文件
- `schedule_interval_seconds`
  定时执行间隔
- `window_clear_interval_seconds`
  清屏间隔，默认 3600 秒
- `log_directory`
  日志目录
- `log_file_name`
  日志基础名，默认 `monitor.log`
- `log_max_size_mb`
  单文件最大值
- `log_retention_days`
  日志保留天数

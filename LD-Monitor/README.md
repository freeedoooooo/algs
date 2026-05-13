# LD-Monitor

轻量脚本版雷电模拟器健康监控工具。

## 你平时只需要关心这些文件

- `start.cmd`
  双击启动监控，黑窗口会持续显示最新监控结果
- `stop.cmd`
  双击停止监控，窗口会保留，方便查看停止结果
- `monitor.config`
  给普通用户修改的配置文件
  这里只保留了最常用、最需要改的几项

## monitor.config 里建议只改什么

- `computer_name`
  这台电脑的名称，会显示在日志和告警邮件里
- `ldplayer_path`
  雷电安装目录
  不填也可以，程序会自动尝试常见目录和注册表路径
- `expected_healthy_devices`
  这台电脑正常应该有多少个健康模拟器
- `mail_enabled`
  是否开启邮件告警
- `mail_to`
  告警邮件收件人
- `alert_cooldown_minutes`
  邮件冷却时间，避免短时间重复轰炸

## 其他目录说明

- `core/`
  内部脚本和默认配置
  普通用户一般不需要修改
- `log/`
  日志目录
  日志按天生成
- `runtime/`
  运行状态目录
  保存 PID、邮件冷却状态等内部文件

## 最常用的使用方式

1. 双击 `start.cmd`
2. 如果需要改配置，编辑 `monitor.config`
3. 需要停止时，双击 `stop.cmd`

## 监控规则

- 只统计当前 ADB 已连接的健康设备数量
- 设备状态必须是 `device`
- `adb shell getprop sys.boot_completed` 必须返回 `1`
- 没有发现设备时，会明确打印“当前未发现已连接的模拟器设备”

## 日志规则

- 每天一个日志文件，例如 `monitor-20260513.log`
- 只保留最近 7 天日志
- 单个日志文件超过 50MB 时，直接删除后重新写
- 黑窗口输出与日志文件内容保持一致
- 黑窗口会按设定时间自动清屏一次

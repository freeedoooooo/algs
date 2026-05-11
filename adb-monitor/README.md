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

这样平时你只需要关注根目录，内部逻辑和运行痕迹分别收进子目录。

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

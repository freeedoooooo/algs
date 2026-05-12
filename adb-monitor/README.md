# adb-monitor

## 目录

- `Monitor.exe`、`*.dll`：运行程序
- `core\`：后台脚本
- `runtime\`：运行时状态
- `log\`：日志
- `source\`：源码

## 使用

1. 双击 `start.cmd`
2. 需要改配置就编辑 `monitor.config`
3. 日志和运行状态在 `log\`、`runtime\` 下

## 发布

```powershell
dotnet publish .\source\AdbMonitor.Gui\AdbMonitor.Gui.csproj -c Release -r win-x64 --self-contained true
```

## 说明

- 目标机器不需要 Python
- 只支持 64 位 Windows
- 分发时请带上整个 `adb-monitor` 目录

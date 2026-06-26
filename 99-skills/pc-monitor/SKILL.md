---
name: pc-monitor
description: 检测远程电脑在线状态。通过 Ping + 端口检测（默认 7899）判断电脑是否在线、半通或离线。适用于监控局域网内多台 PC 的网络连通性。当用户需要检查远程电脑状态、批量检测网络连通性、排查电脑掉线问题时使用。
---

# PC Monitor

检测远程电脑在线状态。

## 配置文件格式

配置文件为 XML 格式（参考 `references/Machine.xml`）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
    <Group Name="group1">
        <Machine Name="1" IP="192.168.1.11" Port="7899" UserName="pc1" PassWord="pwd" Mac="C8-60-00-70-6F-3F" />
    </Group>
</root>
```

## 使用方式

直接运行检测脚本：

```powershell
# 检测全部电脑
powershell -ExecutionPolicy Bypass -File scripts/check_online.ps1 -ConfigPath "D:\PROJECT\...\Machine.xml"

# 仅检测指定分组（group1 / group2 / group3）
powershell -ExecutionPolicy Bypass -File scripts/check_online.ps1 -ConfigPath "..." -Group "group1"

# 仅检测指定电脑（Name 字段值）
powershell -ExecutionPolicy Bypass -File scripts/check_online.ps1 -ConfigPath "..." -MachineName "5"

# 调整超时（毫秒，默认 1000）
powershell -ExecutionPolicy Bypass -File scripts/check_online.ps1 -ConfigPath "..." -Timeout 2000
```

## 检测逻辑

**核心原则：端口通 = 在线**（因为很多机器禁用了 ICMP，但服务端口是开放的）

| 状态 | 含义 | 判定条件 |
|------|------|----------|
| **[ONLINE] [OK/OK]** | 电脑完全可达 | Ping ✅ + 端口 ✅ |
| **[ONLINE] [NO-ICMP/OK]** | 在线但禁用了 ICMP | Ping ❌ + 端口 ✅ |
| **[HALF] [OK/FAIL]** | IP 可达但端口未开放（服务未启动） | Ping ✅ + 端口 ❌ |
| **[OFFLINE] [FAIL/-]** | 完全无法通信 | Ping ❌ + 端口 ❌ |

> **注意**：判断优先级：端口 > Ping。只要端口通就判定为在线。

## 邮件报警

当检测到离线/半通电脑时，加 `-Notify` 参数自动发邮件通知：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_online.ps1 -ConfigPath "..." -Notify
```

- 发件邮箱: 2504601121@qq.com (QQ SMTP)
- 收件邮箱: 195836303@qq.com, 3198127828@qq.com
- 触发条件: 存在 OFFLINE 或 HALF 状态的电脑
- 邮件内容: 离线电脑列表 + 汇总统计

## 状态码说明

| 状态码 | 含义 |
|--------|------|
| `[OK/OK]` | Ping 通 + 端口通 |
| `[NO-ICMP/OK]` | Ping 不通（禁用 ICMP）+ 端口通 |
| `[OK/FAIL]` | Ping 通 + 端口不通（半通，服务未启动） |
| `[FAIL/-]` | Ping 不通 + 端口不通（离线） |

## 技术说明

- **Ping 检测**：使用 `Win32_PingStatus` WMI 查询（兼容 PowerShell 5.1）
- **端口检测**：使用 `System.Net.Sockets.TcpClient` 异步连接
- **默认端口**：7899（可在配置文件中自定义）
- **默认超时**：1000ms（可通过 -Timeout 参数调整）

# 本地开发端口转发说明

本地开发调试时，通过 `kubectl port-forward` 将集群 `c1-ns-dev` 命名空间内各微服务的 ClusterIP Service
端口映射到本地，实现本地应用无缝调用集群内服务。

## 前置条件

- 已安装并配置好 `kubectl`，且能正常访问目标集群。
- 已切换到正确的 context，确保可以访问 `c1-ns-dev` 命名空间。

## 端口映射一览

| 服务 Service     | 说明           | 本地端口  | 集群端口  |
|----------------|--------------|-------|-------|
| `c1-p-rbac`    | 权限 / RBAC 服务 | 20001 | 20001 |
| `c1-p-mdm`     | 主数据（MDM）服务   | 20002 | 20002 |
| `c1-b-extract` | 数据抽取服务       | 30001 | 30001 |
| `c1-b-report`  | 报表服务         | 30002 | 30002 |
| `c1-b-data`    | 数据服务         | 30003 | 30003 |
| `c1-b-rule`    | 规则服务         | 30004 | 30004 |
| `c1-b-govern`  | 数据治理服务       | 30005 | 30005 |

> 端口映射规则为 `本地端口:集群端口`，上表保持两端一致，便于对照配置。

## 转发命令

每条命令会占用当前终端并持续运行，需为每个服务单独开启一个终端窗口（或使用后台任务方式运行）。

```bash
# 权限 / RBAC 服务
kubectl port-forward -n c1-ns-dev svc/c1-p-rbac    20001:20001
```

```bash
# 主数据（MDM）服务
kubectl port-forward -n c1-ns-dev svc/c1-p-mdm     20002:20002
```

```bash
# 数据抽取服务
kubectl port-forward -n c1-ns-dev svc/c1-b-extract 30001:30001
```

```bash
# 报表服务
kubectl port-forward -n c1-ns-dev svc/c1-b-report  30002:30002
```

```bash
# 数据服务
kubectl port-forward -n c1-ns-dev svc/c1-b-data    30003:30003
```

```bash
# 规则服务
kubectl port-forward -n c1-ns-dev svc/c1-b-rule    30004:30004
```

```bash
# 数据治理服务
kubectl port-forward -n c1-ns-dev svc/c1-b-govern  30005:30005
```

## 使用说明

1. 按需选择要调试的服务，只转发本地应用实际依赖（如 Feign 客户端调用）的服务端口即可，无需全部启动。
2. 启动转发后，本地应用即可通过 `127.0.0.1:<本地端口>` 访问对应集群服务。
3. 转发进程需保持运行；关闭终端或按 `Ctrl+C` 会中断对应的端口转发。
4. 若出现连接断开，重新执行对应命令即可恢复。

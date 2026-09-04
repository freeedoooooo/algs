# 04-platform — 平台级服务

DIB 平台的 4 个基础微服务，属于平台层（认证、网关、权限、主数据）。

## 文件清单

| 文件 | 包含服务 |
|------|---------|
| `all-services.yaml` | 4 个 Deployment + 4 个 Service |

## 服务概览

| 服务 | 容器端口 | 访问类型 | 外部端口 | 说明 |
|------|---------|---------|---------|------|
| auth-server | 9090 | **NodePort** | 30090 | SSO 认证中心，外部可访问 |
| gateway | 20000 | **NodePort** | 30000 | API 网关，外部流量入口 |
| auth-resource | 20001 | ClusterIP | — | 权限资源管理，仅集群内部访问 |
| mdm | 20002 | ClusterIP | — | 主数据管理，仅集群内部访问 |

## 部署命令

```bash
# 单独部署平台服务（需先部署 02-config 和 03-infra）
kubectl apply -f 04-platform/all-services.yaml

# 或通过部署脚本
bash 06-scripts/deploy-all.sh platform
```

---

## 各服务详解

### 1. auth-server（SSO 认证中心）

- **镜像**：`10.0.6.183:8088/c1/platform-auth-server:latest`
- **端口**：9090
- **访问**：NodePort 30090，外部可通过 `http://<任意节点IP>:30090` 访问
- **健康检查**：`GET /actuator/health`
- **资源**：512Mi ~ 2Gi 内存
- **作用**：统一登录认证，颁发 Token，对接 OAuth2 协议

### 2. gateway（API 网关）

- **镜像**：`10.0.6.183:8088/c1/platform-gateway:latest`
- **端口**：20000
- **访问**：NodePort 30000，**所有外部 API 请求的入口**
- **健康检查**：`GET /actuator/health`
- **资源**：512Mi ~ 2Gi 内存
- **作用**：路由转发、限流、鉴权，前端和外部系统统一通过此端口访问后端

### 3. auth-resource（权限资源管理）

- **镜像**：`10.0.6.183:8088/c1/platform-auth-resource:latest`
- **端口**：20001
- **访问**：ClusterIP，仅集群内部访问（由 gateway 转发）
- **健康检查**：`GET /api/auth/actuator/health`
- **资源**：512Mi ~ 2Gi 内存
- **作用**：管理用户、角色、菜单、权限等数据

### 4. mdm（主数据管理）

- **镜像**：`10.0.6.183:8088/c1/platform-mdm:latest`
- **端口**：20002
- **访问**：ClusterIP，仅集群内部访问
- **健康检查**：`GET /api/mdm/actuator/health`
- **资源**：512Mi ~ 2Gi 内存
- **作用**：主数据（组织、人员、字典等）管理，使用 MinIO 存储附件

---

## Deployment 通用结构

每个服务的 Deployment 结构一致，核心部分：

```yaml
spec:
  template:
    spec:
      imagePullSecrets:           # 镜像仓库认证
        - name: dib-registry-secret
      containers:
        - env:                    # 单独注入 C1_ENV
            - name: C1_ENV
              valueFrom:
                configMapKeyRef:
                  name: dib-common-config
                  key: C1_ENV
          envFrom:                # 批量注入所有配置
            - configMapRef:
                name: dib-common-config
          volumeMounts:
            - name: app-logs      # 日志目录（Pod 删除即清空）
              mountPath: /opt/app/logs
            - name: fonts         # 系统字体（PDF 导出需要）
              mountPath: /usr/share/fonts
```

**关键设计**：
- `envFrom` 将 ConfigMap 中所有键值对注入为环境变量
- `app-logs` 使用 `emptyDir`，日志随 Pod 生命周期
- `fonts` 挂载宿主机 `/usr/share/fonts`，确保 PDF/Excel 导出时字体正常

## Service 类型说明

| 类型 | 含义 | 使用场景 |
|------|------|---------|
| **NodePort** | 在每个节点上开放固定端口，外部可通过 `节点IP:端口` 访问 | auth-server、gateway |
| **ClusterIP** | 仅分配集群内部 IP，外部无法直接访问 | auth-resource、mdm |

## 访问链路

```
外部浏览器 / 前端
    ↓
http://<节点IP>:30000  (gateway NodePort)
    ↓
gateway (路由转发)
    ↓
┌─ auth-resource (内部 :20001)
├─ mdm           (内部 :20002)
├─ service-*     (内部 :30001~30005)
└─ data-dg       (内部 :30005)
```

## 常见问题

**Q: NodePort 30000 被占用怎么办？**
修改 `all-services.yaml` 中 gateway 的 `nodePort` 值（范围 30000-32767），或让 K8s 自动分配（删除 `nodePort` 字段）。

**Q: Pod 一直 CrashLoopBackOff？**
查看日志定位原因：
```bash
kubectl -n c1-idc-test logs deployment/gateway --tail=100
```
常见原因：Nacos 未就绪、数据库连不上、配置错误。

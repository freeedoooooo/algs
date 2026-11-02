# c1-app 微前端部署 Chart

C1 微前端应用的 Helm 部署 Chart，采用**双层 Nginx 架构**。

> **当前部署范围：仅各微前端容器（第二层），不含入口网关（第一层）。**
> 网关模板已保留，通过 `gateway.enabled` 开关控制，默认关闭，需要时一键启用。

---

## 一、架构说明

```
浏览器
  │
  ▼
┌─────────────────────────────┐
│  第一层：入口网关 (gateway)   │  ← 当前【不部署】enabled=false
│  路由分发 + 后端 API 代理      │     由外部/已有 Nginx 承担入口职责
│  剥离 URL 前缀后转发           │
└─────────────────────────────┘
  │  proxy_pass http://c1-app-xxx/
  ▼
┌─────────────────────────────┐
│  第二层：微前端容器            │  ← 当前【部署这部分】
│  纯静态文件 + SPA 回退         │
│  /healthz 健康检查            │
└─────────────────────────────┘
```

- **第二层容器完全通用**：所有微前端共用同一份镜像内 `nginx.conf`，静态产物统一放在容器 `/opt/app/`，容器不感知自己的应用名。
- **URL 前缀剥离**由第一层负责（`proxy_pass` 尾部带 `/`），第二层只从根目录提供静态服务。
- **健康检查**统一使用容器内置 `/healthz` 端点，不依赖任何静态文件（兼容 app-nav 这类无 index.html 的组件库）。

---

## 二、目录结构

```
helm-c1-frontend/
├── Chart.yaml                    # Chart 元数据（name: c1-app）
├── README.md                     # 本文档
├── values.yaml                   # dev 环境默认值（142 / worker-5.142）
├── values-test.yaml              # test 环境（70 / worker-5.70）
├── nginx.conf                    # 第一层网关路由配置（仅网关启用时使用）
├── Dockerfile                    # 第一层网关镜像（仅网关启用时使用）
└── templates/
    ├── frontends.yaml            # 【生效】第二层微前端容器（遍历 .Values.frontends）
    ├── gateway.yaml              # 【默认关闭】第一层网关 Deployment + Service
    └── configmap-nginx.yaml      # 【默认关闭】网关 nginx.conf 的 ConfigMap
```

---

## 三、部署的微前端容器

由 `values.yaml` 的 `frontends` 段驱动，`templates/frontends.yaml` 遍历生成每个应用的 Deployment + Service。

| 应用 (Service 名) | 镜像 | 容器端口 | Service 类型 |
|---|---|---|---|
| c1-app-portal | c1/c1-app-portal | 80 | ClusterIP |
| c1-app-data | c1/c1-app-data | 80 | ClusterIP |
| c1-app-nav | c1/c1-app-nav | 80 | ClusterIP |
| c1-app-report | c1/c1-app-report | 80 | ClusterIP |
| c1-app-system | c1/c1-app-system | 80 | ClusterIP |

- Service 名 = `frontends` 的 key，需与网关 `nginx.conf` 中 `proxy_pass http://<名字>/` 的主机名保持一致。
- 全部为 **ClusterIP**：仅供集群内部（第一层网关）访问，不对外暴露。
- BI 前端（`c1-app-bi`）默认注释，如有独立容器化需求可在 `frontends` 下取消注释启用。

---

## 四、前置条件

1. **各微前端镜像已构建并推送到镜像仓库**（`imageRegistry`）。
   - 每个应用的构建产物放入其 `docker/app/` 目录，用通用 Dockerfile + nginx.conf 构建。
   - 镜像内静态文件位于 `/opt/app/`，nginx 监听 80，提供 `/healthz` 端点。
2. **集群节点已打标签** `node-name=<nodeName>`（用于 nodeSelector 调度）。
3. **目标 namespace 已存在**（如 `c1-ns-dev` / `c1-ns-test`）。

---

## 五、关键配置项（values）

| 配置项 | 说明 | dev 默认值 |
|---|---|---|
| `namespace` | 部署命名空间 | `c1-ns-dev` |
| `imageRegistry` | 镜像仓库前缀 | `10.0.6.183:8088` |
| `image.tag` | 所有前端容器统一镜像 tag | `idc-dev_latest` |
| `imagePullPolicy` | 拉取策略 | `Always` |
| `nodeName` | 调度节点 | `worker-5.142` |
| `frontendResources` | 微前端容器默认资源（可被各 frontend 的 `resources` 覆盖） | 见文件 |
| `frontends.<name>` | 各微前端应用定义（image / port / replicas） | 见上表 |
| `gateway.enabled` | **是否部署第一层网关** | `false`（当前不部署） |

> 单个应用如需自定义资源，在对应 frontend 下增加 `resources` 即可覆盖 `frontendResources`。

---

## 六、部署命令

```bash
# 进入 chart 目录
cd "docs-c1/80 运维软件/helm-c1-frontend"

# dev 环境（仅微前端，网关关闭）
helm install c1-app . --namespace c1-ns-dev

# test 环境
helm install c1-app . --values values-test.yaml --namespace c1-ns-test

# 升级
helm upgrade c1-app . --namespace c1-ns-dev
```

> 发布名（`c1-app`）可自定义。

**部署前建议先本地渲染校验：**

```bash
helm lint .
helm template c1-app .                 # 查看默认（仅微前端）渲染结果
helm template c1-app . --values values-test.yaml
```

---

## 七、部署验证

```bash
# 查看 Pod（应有 5 个 c1-app-xxx，状态 Running 且 READY 1/1）
kubectl get pods -n c1-ns-dev -l tier=frontend

# 查看 Service
kubectl get svc -n c1-ns-dev -l tier=frontend

# 容器内健康检查（应返回 ok）
kubectl exec -n c1-ns-dev deploy/c1-app-data -- wget -qO- http://127.0.0.1:80/healthz
```

因均为 ClusterIP，集群外无法直接访问，需通过第一层网关或临时端口转发验证：

```bash
kubectl port-forward -n c1-ns-dev svc/c1-app-data 8080:80
# 浏览器访问 http://localhost:8080/
```

---

## 八、后续启用第一层网关

当需要由本 Chart 一并提供入口网关时：

1. 把 `values.yaml`（或对应环境 values）中的 `gateway.enabled` 改为 `true`；
2. 确认 `nginx.conf` 中各 `proxy_pass` 主机名与 `frontends` 的 key 一致；
3. 构建并推送网关镜像 `c1/c1-frontend-gateway`（用本目录 `Dockerfile`）；
4. 重新 `helm upgrade`。

启用后将额外渲染：
- `ConfigMap/c1-frontend-gateway-nginx`（由 `nginx.conf` 自动生成）
- `Deployment + Service/c1-frontend-gateway`（NodePort 对外，健康检查 `/healthz`）

> 同集群多环境注意 NodePort 全局唯一：dev=30091 / test=30191，勿冲突。

---

## 九、多环境说明

| 环境 | values 文件 | namespace | 节点 | 网关 NodePort |
|---|---|---|---|---|
| dev (142) | `values.yaml` | `c1-ns-dev` | worker-5.142 | 30091 |
| test (70) | `values-test.yaml` | `c1-ns-test` | worker-5.70 | 30191 |

NodePort 分段约定：142→300xx / 70→301xx / 101→302xx / 239→303xx。

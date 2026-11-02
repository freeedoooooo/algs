# helm-infra — 基础设施独立 Chart 集合

本目录将原先集中在 `../helm-c1-backend` 的「大 Chart」中的**基础设施部分**（公共配置、Nacos、Redis、Nginx）按职责拆分为多个独立的小
Chart，每个组件一个目录、一次发布，便于独立升级、回滚与故障隔离。

> 原 `../helm-c1-backend` 保持不变，可作为整体部署方案继续存在；本目录 + `../helm-backend` 是**逐组件独立部署**方案。

---

## 一、目录结构

```
helm-infra/
├── README.md          # 本文档
├── config/            # 公共 ConfigMap（c1-configmap-common）—— 全局前置依赖
├── nacos/             # 注册中心（NodePort）
├── redis/             # 缓存（NodePort）
├── nginx/             # 前端入口网关（ClusterIP，走 Ingress 域名）
├── dataease/          # DataEase v2 服务端 + 专属 MySQL 8.4（BI 后端，配套 ../helm-frontend/c1-app-bi）
└── ingress/           # Traefik IngressController + IngressClass + Ingress（独立方案）
```

每个子目录都是一个**可独立安装的 Helm Chart**，结构一致：

- `Chart.yaml`：`name` 即组件名（= K8s 资源名前缀）。
- `values.yaml`：dev（142）环境完整配置。
- `values-test.yaml` / `values-pro-bank.yaml` / `values-pro-sh.yaml`：其余 3 套环境**仅覆盖差异项**（namespace /
  nodeName / 镜像 tag / 连接地址等），其余继承 `values.yaml`。
- `templates/`：组件的 K8s 资源清单。

---

## 二、组件说明

| Chart     | 作用                                                                          | Service 类型            | 关键依赖           |
|-----------|-----------------------------------------------------------------------------|-----------------------|----------------|
| `config`  | 渲染公共 ConfigMap `c1-configmap-common`，被全部 9 个后端服务 `envFrom` 注入，并被 redis 引用密码 | 无（仅 ConfigMap）        | 无（最先部署）        |
| `nacos`   | 服务注册中心，外挂 MySQL 存储                                                          | NodePort              | 外部 MySQL       |
| `redis`   | 缓存，密码取自 `c1-configmap-common` 的 `C1_REDIS_PASSWORD`                         | NodePort              | `config`       |
| `nginx`   | 前端入口网关（路由分发 + 后端 API 代理）；内置 `nginx.conf` 并渲染为 `c1-configmap-nginx` 后挂载      | ClusterIP             | `config`、前端各应用 |
| `dataease` | DataEase v2.10.9 服务端（官方镜像，自带 UI/API，监听 8100）+ 专属 MySQL 8.4 独立环境；Service 固定名 `c1-dataease:8100` 供网关 `/bi/de2api/`、`/bi/websocket/` 代理 | NodePort（管理口 30090/30190） | 自带专属 MySQL（chart 内置）；与 `../helm-frontend/c1-app-bi` 的 `dataeaseExternal.enabled` 互斥 |
| `ingress` | Traefik 入口控制器与域名路由                                                          | LoadBalancer/NodePort | 独立             |

> **ConfigMap 归属**：
> - `c1-configmap-common` 被多方共享（后端 9 服务 + redis），拆分后**只由 `config` 这一个 Chart 渲染**，避免多个 Chart
    争抢同一资源导致的归属冲突。
> - `c1-configmap-nginx` **仅被 `nginx` 单一消费**，故内聚在 `nginx` Chart 内：配置以根目录 `nginx.conf` 文件形式版本化，经
    `templates/configmap.yaml`（`.Files.Get` 逐字读取）渲染为 ConfigMap，与 nginx Deployment 一起部署/升级，不再需 Kuboard
    手动维护。

---

## 三、部署顺序与卸载（重要）

基础设施必须**先于**后端业务服务部署，且 `config` 最先：

```
config  →  nacos / redis  →  nginx  →  （../helm-backend 各后端服务）
```

### 安装 Helm

```bash
# kubectl 机器上安装 helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4 | bash

# 验证
helm version
```

```bash
cd "docs-c1/01_产品部署/k8s/helm-infra"

# 1) 公共 ConfigMap（全局前置）
helm upgrade --install c1-config ./config -n c1-ns-dev --server-side=false

# 2) 注册中心 / 缓存
helm upgrade --install c1-nacos ./nacos -n c1-ns-dev --server-side=false
helm upgrade --install c1-redis ./redis -n c1-ns-dev --server-side=false

# 3) 前端入口网关
helm upgrade --install c1-nginx ./nginx -n c1-ns-dev --server-side=false
```

切换环境时追加对应 values（如 test）：

```bash
helm upgrade --install c1-config ./config --values ./config/values-test.yaml -n c1-ns-test --server-side=false
helm upgrade --install c1-nacos ./nacos --values ./nacos/values-test.yaml -n c1-ns-test --server-side=false
helm upgrade --install c1-redis ./redis --values ./redis/values-test.yaml -n c1-ns-test --server-side=false
helm upgrade --install c1-nginx ./nginx --values ./nginx/values-test.yaml -n c1-ns-test --server-side=false
```

### 查看 / 回滚 / 卸载

```bash
cd "docs-c1/01_产品部署/k8s/helm-infra"

# —— 查看 ——
helm list -n c1-ns-dev                    # 已安装的 release
helm history c1-nacos -n c1-ns-dev        # 某 release 的版本历史

# —— 回滚（升级出问题时）——
helm rollback c1-nacos 1 -n c1-ns-dev     # 回滚到指定版本号

# —— 卸载 / 删除（按部署的逆序，config 最后卸）——
helm uninstall c1-nginx -n c1-ns-dev
helm uninstall c1-redis -n c1-ns-dev
helm uninstall c1-nacos -n c1-ns-dev
helm uninstall c1-config -n c1-ns-dev     # 删公共 ConfigMap，需确认无后端服务再依赖它
```

> - **卸载顺序与部署相反**：先卸依赖方（nginx / 后端服务），最后才卸被依赖的 `config`；否则先删 `c1-configmap-common`
    会导致还在运行的后端服务 `envFrom` 失效。
> - `helm uninstall c1-config` 会删除公共 ConfigMap `c1-configmap-common`（影响全部 9 个后端服务），执行前务必确认。
> - `helm uninstall` 只删除该 chart 渲染的资源，不会删 namespace；如需保留 release 历史可加 `--keep-history`。卸载为集群写操作（尤其
    ConfigMap），请由运维确认后手动执行。

---

## 四、多环境说明

| 环境             | values 文件              | namespace        | 节点           | NodePort 分段 |
|----------------|------------------------|------------------|--------------|-------------|
| dev (142)      | `values.yaml`          | `c1-ns-dev`      | worker-5.142 | 300xx       |
| test (70)      | `values-test.yaml`     | `c1-ns-test`     | worker-5.70  | 301xx       |
| pro-bank (101) | `values-pro-bank.yaml` | `c1-ns-pro-bank` | worker-5.101 | 302xx       |
| pro-sh (239)   | `values-pro-sh.yaml`   | `c1-ns-pro-sh`   | worker-5.239 | 303xx       |

> 四套环境同集群多节点，NodePort 全局唯一、按环境分段。

---

## 五、关键约定

1. **`--server-side=false`**：所有 helm 命令强制携带，避免与 Jenkins `kubectl set image` 产生字段冲突。
2. **发布名**：建议 `c1-<组件名>`（如 `c1-config` / `c1-nacos`），环境区分通过 namespace + values 文件实现。
3. **ConfigMap 中的 `NAMESPACE` 占位符**：`config` Chart 渲染时会用当前 `namespace` 替换 `config` 块内的 `NAMESPACE`
   字样，生成集群内服务发现地址。

---

## 六、部署前本地校验

```bash
helm lint ./config ./nacos ./redis ./nginx
helm template c1-config ./config
helm template c1-redis  ./redis --values ./redis/values-test.yaml
```

> 集群写操作（尤其 ConfigMap）请由运维在确认无误后手动执行，本目录仅提供 Chart 与本地只读校验命令。

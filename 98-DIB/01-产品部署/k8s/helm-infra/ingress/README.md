# helm-c1-ingress —— C1 多环境共享 Ingress Chart

一个共享的 **Traefik Ingress Controller**，按**域名(host)** 把外部流量路由到各环境自己的 `c1-nginx`，
从而**彻底取消 NodePort 端口分段**（300xx/301xx/302xx/303xx），4 个环境同集群也不再互相抢端口。

> 本 Chart 只负责 **Ingress 层**（Traefik Controller + 各环境 Ingress），**不改动 `helm-c1`**。
> 启用后 `helm-c1` 侧需配合调整（服务改 ClusterIP、OAuth 对外地址改域名），详见[第八节](#八配合-helm-c1-的改动重要)。

---

## 一、为什么需要它

- **痛点**：4 个环境同集群，NodePort 全局唯一，每个服务都要按环境分段错开端口，繁琐且极易冲突。
- **关键事实**：每个环境**真正的对外入口只有 `c1-nginx`**（托管前端 + 反代 `/api/*`、`/sso/`、`/api-oauth/`），其余服务的 NodePort 基本是顺带暴露。
- **方案**：部署一个共享 Traefik（监听固定 80/443），按域名把流量转发到各 namespace 的 `c1-nginx`；应用服务全部改 ClusterIP，删掉所有 NodePort 分段。4 个域名解析到**同一个入口 IP**，靠 Host 头区分环境。

---

## 二、架构与路由

```
                 浏览器 / curl
                      │
     DNS A 记录（4 个域名全部指向同一入口 IP）
       c1-dev.dibdata.cn   c1-test.dibdata.cn
       c1-bank.dibdata.cn  c1-sh.dibdata.cn
                      │
                      ▼
   ┌──────────────────────────────────────────┐
   │  共享 Traefik Controller (本 Chart 部署)     │
   │  namespace: c1-ns-ingress                   │
   │  hostNetwork 监听 :80 / :443（钉在入口节点）  │
   │  按 Host 头匹配 Ingress 规则                 │
   └──────────────────────────────────────────┘
        │Host: dev   │Host: test  │Host: bank │Host: sh
        ▼            ▼            ▼           ▼
   c1-ns-dev    c1-ns-test  c1-ns-pro-bank  c1-ns-pro-sh
   c1-nginx     c1-nginx     c1-nginx        c1-nginx
   :80          :80          :80             :80
```

| 环境 | 域名（占位，可改） | namespace | 后端 Service | 端口 |
|------|-------------------|-----------|-------------|------|
| dev  | c1-dev.dibdata.cn  | c1-ns-dev      | c1-nginx | 80 |
| test | c1-test.dibdata.cn | c1-ns-test     | c1-nginx | 80 |
| bank | c1-bank.dibdata.cn | c1-ns-pro-bank | c1-nginx | 80 |
| sh   | c1-sh.dibdata.cn   | c1-ns-pro-sh   | c1-nginx | 80 |

- 每个 Ingress 创建在**对应环境自己的 namespace** 下（Ingress 后端 Service 必须与 Ingress 同 namespace）。
- 路由规则：`ingressClassName: traefik` + `host: <域名>` + `path: / (Prefix) → c1-nginx:80`。
  nginx 内部已按 `/api/*`、`/sso/` 分流，**Ingress 无需再拆路径**。
- 4 个域名的 DNS A 记录全部指向**同一个入口 IP**（hostNetwork 模式 = 入口节点 IP，默认 master-6.183 = `10.0.6.183`）。

> **后端端口统一为 80：** c1-nginx 容器的 nginx 配置已将主入口 `listen` 改为 **80**（同时删除了旧的 80 端口 SSO 纠偏 server——该纠偏是 NodePort 时代为补回丢失端口而设，域名方案下已多余）。因改为 ClusterIP，Service 端口不再需要全局唯一（各环境在自己 namespace 内），4 套环境均用 80，互不冲突，也彻底取消了 30091/30191 等硬编码分段。

---

## 三、目录结构

```
helm-c1-ingress/
├── Chart.yaml                     # name: c1-ingress, version 1.0.0, appVersion traefik-v3.1
├── values.yaml                    # Traefik 配置 + environments 列表（含全部 4 环境）
├── README.md                      # 本文档
└── templates/
    ├── ingressclass.yaml          # IngressClass: traefik
    ├── traefik-rbac.yaml          # ServiceAccount + ClusterRole + ClusterRoleBinding
    ├── traefik-deployment.yaml    # Deployment（hostNetwork / nodePort 由 values 切换）
    ├── traefik-service.yaml       # ClusterIP 或 NodePort（视 mode）
    └── ingresses.yaml             # range .Values.environments → 每环境一个 Ingress
```

一个 release 管全部环境：`helm install c1-ingress . -n c1-ns-ingress --create-namespace`。

---

## 四、前置条件

1. **Traefik 镜像已推入私仓**（离线环境）：`10.0.6.183:8088/library/traefik:v3.1`。
   > 因 K3s 安装时 `--disable traefik`，本方案自带 Traefik 部署。
2. **入口节点已打标签** `node-name=<traefik.nodeName>`（默认 `master-6.183`），且该节点 **80/443/9000 端口空闲**（hostNetwork 模式）。
   > 调度到 master 必须配套 `traefik.tolerations` 容忍 master/control-plane 污点（values 已默认内置），否则 Pod 会一直 Pending。
3. **各环境 `c1-nginx` Service 已存在**于对应 namespace，且端口与 `environments[].servicePort` 一致（统一 `80`）。
4. **内网 DNS 可新增域名 A 记录**，把 4 个域名指向同一入口 IP。

---

## 五、关键配置项（values.yaml）

### Traefik Controller

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `traefik.image` | Traefik 镜像（需先推入私仓） | `10.0.6.183:8088/library/traefik:v3.1` |
| `traefik.namespace` | Traefik 自身部署 namespace | `c1-ns-ingress` |
| `traefik.replicas` | 副本数 | `1` |
| `traefik.nodeName` | 入口节点（hostNetwork 下 DNS 指向此节点 IP） | `master-6.183` |
| `traefik.useNodeSelector` | 是否用 nodeSelector 把 Traefik 钉在 nodeName 上 | `true` |
| `traefik.tolerations` | 容忍 master/control-plane 污点（调度到 master 必需） | 已内置两条 |
| `traefik.exposure.mode` | 暴露方式：`hostNetwork` \| `nodePort` | `hostNetwork` |
| `traefik.exposure.webPort` | http 入口端口 | `80` |
| `traefik.exposure.websecurePort` | https 入口端口 | `443` |
| `traefik.exposure.traefikPort` | Traefik 内部 / ping 端口 | `9000` |
| `traefik.exposure.webNodePort` | mode=nodePort 时的 http NodePort | `30080` |
| `traefik.exposure.websecureNodePort` | mode=nodePort 时的 https NodePort | `30443` |
| `traefik.extraArgs` | 追加的 Traefik 启动参数（可选） | `[]` |
| `traefik.imagePullSecrets` | 镜像拉取 secret（可选） | `[]` |

**暴露方式对比：**

| mode | URL 形态 | 说明 |
|---|---|---|
| `hostNetwork`（默认） | `http://<域名>` | 容器直接用宿主机 80/443，URL 干净；需入口节点 80/443/9000 空闲 |
| `nodePort` | `http://<域名>:30080` | Service 暴露 30080/30443，不占用宿主机 80；仍是全环境共用一组端口 |

### IngressClass

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `ingressClass.name` | IngressClass 名称 | `traefik` |
| `ingressClass.controller` | 控制器标识 | `traefik.io/ingress-controller` |
| `ingressClass.isDefault` | 是否设为集群默认 IngressClass | `false` |

### environments（各环境路由）

每个环境一条记录，字段如下：

| 字段 | 说明 |
|---|---|
| `name` | 环境标识（仅用于命名 Ingress 资源 `c1-ingress-<name>`） |
| `host` | 对外域名（部署前替换为真实内网域名，DNS A 记录指向入口节点 IP） |
| `namespace` | 该环境所在 namespace（Ingress 会创建在此，后端 Service 须同 namespace） |
| `serviceName` | 后端 Service 名（默认 `c1-nginx`，即前端网关） |
| `servicePort` | 后端 Service 端口（各环境统一 `80`） |
| `tlsSecret` | 可选：https 证书 secret 名（须存在于该 namespace），配置后 Ingress 自动启用 TLS |

---

## 六、部署命令

```bash
# 进入 chart 目录
cd "docs-c1/80 运维软件/helm-c1-ingress"

# 本地渲染校验（强烈建议部署前先做）
helm lint .
helm template c1-ingress .

# 部署（一个 release 管全部环境）
helm install c1-ingress . -n c1-ns-ingress --create-namespace

# 升级（修改 values 后）
helm upgrade c1-ingress . -n c1-ns-ingress

# 卸载
helm uninstall c1-ingress -n c1-ns-ingress
```

**按需修改：**

- **换域名**：编辑 `values.yaml` 的 `environments[].host`（默认 `*.dibdata.cn`，可按需替换）。
- **切换暴露方式**：把 `traefik.exposure.mode` 改为 `nodePort`，访问 URL 变为 `http://<域名>:30080`。
- **换入口节点**：修改 `traefik.nodeName`，并确保新节点已打 `node-name` 标签、80/443/9000 空闲；若换到 master 类节点，务必保留 `traefik.tolerations`。
- **启用 https**：在对应环境条目增加 `tlsSecret: <证书secret名>`，并确认该 secret 已存在于环境 namespace。

---

## 七、部署验证

```bash
# 1. Traefik Pod Running（c1-ns-ingress）
kubectl -n c1-ns-ingress get pods -l app.kubernetes.io/name=traefik

# 2. 4 条 Ingress 就绪且有 ADDRESS
kubectl get ingress -A -l app.kubernetes.io/instance=c1-ingress

# 3. host 路由验证（同一入口 IP，靠 Host 头区分环境）
curl -H "Host: c1-dev.dibdata.cn"  http://<入口IP>/     # 命中 dev 前端
curl -H "Host: c1-test.dibdata.cn" http://<入口IP>/     # 命中 test 前端

# 4. Traefik 自身健康（入口节点上，hostNetwork 模式）
curl http://<入口IP>:9000/ping                          # 返回 OK

# 5. 浏览器访问（DNS 生效后），走通登录即验证 OAuth 回跳正常
#    http://c1-dev.dibdata.cn
```

---

## 八、配合 helm-c1 的改动（重要）

> 本 Chart **不修改** `helm-c1`，但启用后 `helm-c1` 侧需做如下调整才能形成干净 URL 的完整链路。

1. **服务改 ClusterIP**：各 `values-*.yaml` 中 `nginx.serviceType`、`services.*.serviceType` 由 `NodePort` 改 `ClusterIP`，删除所有 `nodePort*` 字段（端口分段彻底作废）。
   > `nacos/redis` 若需外部工具访问可保留 NodePort，属可选。
2. **nginx 端口归一**：`nginx.port` 统一为 `80`（容器 nginx 配置的主入口 `listen` 也需同步改为 80，Ingress 后端也按 80）。
3. **OAuth 对外地址改域名（关键，否则 SSO 回跳失败）**：各环境 `C1_OAUTH_CLIENT_HOST`、`C1_OAUTH_SERVER_HOST`、`C1_OAUTH_REDIRECT_URI` 由 `http://<节点IP>:<nginxNodePort>` 改为 `http://<环境域名>`，例如 dev → `http://c1-dev.dibdata.cn`。
4. **集群内地址无需改**：`C1_*_SERVER_HOST_INNER` 等 `*.svc.cluster.local` 保持不变。
5. **生效顺序与回退**：先部署 helm-c1-ingress（Traefik + Ingress）→ 再按上述改 helm-c1 values 并 `helm upgrade` 各环境。
   > 回退方案：保留原 NodePort 分段不删，即可与新链路双通道并存。

---

## 九、DNS 配置

- 在内网 DNS 为 4 个域名各加一条 A 记录，**全部指向同一入口 IP**：
  - `hostNetwork` 模式：入口节点 IP（默认 master-6.183 = `10.0.6.183`）。
  - `nodePort` 模式：同样指向入口节点 IP，访问 URL 带 `:30080`。
- 域名默认 `*.dibdata.cn`（c1-dev / c1-test / c1-bank / c1-sh），如有变动在 `values.yaml` 的 `environments[].host` 修改。

---

## 十、假设与约束

- 内网 DNS 可新增域名 A 记录。
- Traefik 镜像可提前推入私仓 `10.0.6.183:8088`（离线环境）。
- 入口节点默认 `master-6.183`（=10.0.6.183），需已打 `node-name` 标签且 80/443/9000 空闲（hostNetwork 模式）；调度到 master 依靠 `traefik.tolerations` 容忍污点。如需 HA，可后续在入口前置 VIP/LB，不在本方案范围。
- 现有 `helm-c1` 已部署，`c1-nginx` Service 存在于各环境 namespace。

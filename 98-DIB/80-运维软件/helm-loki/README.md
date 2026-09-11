# DIB 日志系统（官方 Chart 版）

基于 **Grafana 官方 Helm Chart** 的日志方案（Loki + Promtail + Grafana），用 **umbrella chart（伞形依赖）** 方式复用官方最佳实践，避免手写 templates。

## 为什么用官方 Chart

官方 `grafana/loki` chart 默认内置了日志采集的最佳实践：

| 能力 | 官方 chart 默认配置 |
|------|-------------------|
| Promtail `__path__` 精确拼接 | ⭐ 默认 `pod_uid + container` 精确拼接 |
| CRI 格式解析（剥 `时间戳/stdout/F`） | ⭐ 默认开启 |
| Pod 标签提取（ns/pod/container/node） | ⭐ 默认 job 已配 |
| 探针（startup/liveness/readiness） | ⭐ 官方已调好 |
| Loki schema/retention/compactor | ⭐ values 覆盖即可 |
| 存储 PVC / 部署模式切换 | ⭐ `deploymentMode` 一键切 |

**代价**：官方 chart 的 values 层级较深、跨版本 key 会漂移，所以**部署前必须做一次校准**。本方案已用 `helm template` 实测完成校准，并修复了 **5 处离线部署阻断项**（副本冲突 / loki 镜像 registry / 3 个 docker.io 辅助镜像），详见下方「✅ 部署前校准」。

---

## 目录结构

```
helm-loki/
├── Chart.yaml          # umbrella：声明依赖官方 loki / promtail / grafana chart
├── values.yaml         # 只覆盖离线环境差异项（镜像仓库、部署模式、存储、采集）
├── README.md           # 本文件
└── charts/             # （执行 helm dependency update 后生成）依赖 chart 的 .tgz
```

---

## 架构概览

```
┌────────────────────────── K3s 集群 ──────────────────────────┐
│                                                               │
│  c1-ns-test（业务）  微服务 stdout → containerd →             │
│                      /var/log/pods/<ns>_<pod>_<uid>/<c>/0.log │
│                                    │                          │
│                                    ▼                          │
│  c1-ns-log（日志栈，官方 chart 部署）                          │
│   ┌────────────────┐  HTTP push   ┌──────────────┐            │
│   │ c1-promtail     │ ───────────▶ │ c1-loki       │            │
│   │ (DaemonSet)     │  :3100       │ (SingleBinary)│            │
│   │ 官方默认采集配置 │              │ PVC 10Gi/7天  │            │
│   └────────────────┘              └──────┬───────┘            │
│                                          │ LogQL              │
│                                          ▼                    │
│                                  ┌──────────────┐             │
│                                  │ c1-grafana    │             │
│                                  │ (NodePort     │             │
│                                  │  :30300)      │             │
│                                  └──────────────┘             │
└───────────────────────────────────────────────────────────────┘
```

- **Loki**：`deploymentMode: SingleBinary`（monolithic 单体），K3s / 小规模最佳实践，关闭 gateway/cache/canary 省资源；存储用 `filesystem`（K3s `local-path` PVC，落在 master 本地盘）。
- **Promtail**：DaemonSet，容忍 master 污点，全节点采集；`pipelineStages` 叠加了 `cri + multiline + level`。
- **Grafana**：NodePort 30300，自动配置 Loki 数据源。
- **调度**：Loki / Grafana 用 `nodeSelector: node-name=master-6.183` 钉在 master，并配了容忍 master `NoSchedule` 污点的 `tolerations`（缺了会一直 Pending）。

---

## ✅ 部署前校准（已用 helm template 实测验证）

> 本节结论**均由 `helm dependency update` + `helm template` 实测得出**（helm v4.1.4；`charts/` 已含官方 loki-6.24.0 / promtail-6.16.6 / grafana-8.7.1）。实测渲染：947 行清单、**3 个镜像全部指向 `10.0.6.183:8088`**、service 名与端口全部匹配、无 validate 报错。以下为实测结论，非推测。

官方 chart 跨版本 key 会漂移，`Chart.yaml` 里三个 `version` 已按 ArtifactHub 核对（见下表）。

### 1. chart 版本 ↔ 镜像 tag 对应（已核对）

| 依赖 | Chart.yaml 版本 | 默认 appVersion | values 锁定 tag | 结论 |
|------|----------------|----------------|----------------|------|
| loki | `6.24.0` | 3.3.2 | 3.3.2 | ✅ 精确吻合 |
| promtail | `6.16.6` | 3.0.0 | 3.3.2 | ⚠️ 无 chart 精确对应 3.3.2，靠 `image.tag` 锁定（promtail 3.x 配置向后兼容） |
| grafana | `8.7.1` | 11.4.0 | 11.4.0 | ✅ 精确吻合 |

> 因 values.yaml 用 `image.tag` 显式锁定镜像，chart 的 appVersion 只是「不覆盖时的默认值」，实际以 tag 为准。

复核命令：

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm search repo grafana/loki     --versions | head
helm search repo grafana/promtail --versions | head
helm search repo grafana/grafana  --versions | head
```

### ⚠️ 官方两项重大变更（影响后续升级，当前离线部署不受阻）

1. **Loki 开源版 chart 迁移**：2026-03 起 `grafana/loki` 转为企业版(GEL)专用，开源版迁到 `grafana-community/helm-charts`（fork 自 chart 6.55.0）。本方案锁定的 `6.24.0` 在旧仓库仍可拉取；将来要升到 6.55.0 以上，需把该依赖的 `repository` 改成 community 仓库。
2. **Promtail 已 EOL**（2026-03-02，此前 LTS 到 2026-02-28）：**EOL ≠ 不能用**，现有 3.3.2 部署照常运行，只是不再有 bug/安全补丁。官方替代品是 **Grafana Alloy**（chart `grafana/alloy`，改用 River 语法）。离线内网短期可继续用 Promtail；有安全合规要求时再评估迁移（官方提供 promtail→alloy 配置转换工具）。

### 2. values 的 key 层级（已验证：镜像 key = `loki.loki.image`）

官方 `grafana/loki` chart 内部有一个**叫 `loki` 的配置块**，作为子 chart 时挂在伞形 `loki:` 别名下，于是出现 **`loki.loki.*`** 双层结构：

```yaml
loki:                    # ← 伞形 chart 里子 chart 的别名（= grafana/loki 的根）
  deploymentMode: ...    #   chart 根级 key（singleBinary/gateway/fullnameOverride 也在这层）
  singleBinary: ...
  loki:                  # ← chart 内部的「配置块」（config 文件内容）
    auth: ...            #   auth/commonConfig/storage/schemaConfig/limits_config/compactor 在这层
    storage: ...
    image: ...           #   ⭐ 镜像就在这层！helper 读 .Values.loki.image（已验证），不是根级 loki.image
```

> **已验证（读 chart `_helpers.tpl` 源码 + helm template 实测）**：loki 容器镜像由 helper `loki.lokiImage` 生成，读取 **`.Values.loki.image`**（= 伞形的 `loki.loki.image`），**不是**根级 `loki.image`。
>
> ⚠️ **踩过的坑（已修复）**：镜像若写在根级 `loki.image`，registry **不生效**，渲染出的镜像会回退成 `docker.io/grafana/loki:3.3.2`，离线部署直接 ImagePullBackOff。本方案 `values.yaml` 已把镜像正确放在 `loki.loki.image`，实测渲染为 `10.0.6.183:8088/grafana/loki:3.3.2` ✅。
>
> 等效写法（一次性覆盖 loki 所有镜像 registry，可绕开层级）：`loki.global.image.registry: 10.0.6.183:8088`。

### 3. helm template 干跑实测（镜像全部私有仓库）

> **已实测**：`charts/` 含官方 loki-6.24.0 / promtail-6.16.6 / grafana-8.7.1，`helm template c1-loki-stack helm-loki -n c1-ns-log` **退出码 0、947 行清单、无 validate 报错**。

```bash
# 复现命令（需先 helm dependency update helm-loki 把依赖拉进 charts/）
helm template c1-loki-stack helm-loki -n c1-ns-log | grep "image:" | sort -u
```

实测输出（**仅 3 个镜像，全部指向私有仓库**；反向 grep `docker.io/kiwigrid/busybox/bats` 为空）：

```
10.0.6.183:8088/grafana/grafana:11.4.0
10.0.6.183:8088/grafana/loki:3.3.2
10.0.6.183:8088/grafana/promtail:3.3.2
```

同时实测确认 `promtail.config.snippets.extraRelabelConfigs` 已渲染生效（`action: drop` + `regex: promtail`），promtail 不采集自身日志，避免反馈循环。

### 4. Loki service 名与端口（已验证：`c1-loki` ClusterIP 3100）

`values.yaml` 里 promtail 推送地址和 grafana 数据源都写死为 `http://c1-loki:3100`。已用 helm template 实测确认（`fullnameOverride: c1-loki` 生效）：

| Service | 类型 | 端口 | 实测结论 |
|---------|------|------|---------|
| `c1-loki` | ClusterIP | 3100 (http-metrics) + 9095 (grpc) | ✅ promtail push `http://c1-loki:3100/loki/api/v1/push`、grafana 数据源 `http://c1-loki:3100` 均命中 |
| `c1-grafana` | NodePort | 30300 → 3000 | ✅ 与 values `grafana.service.nodePort: 30300` 一致 |
| `c1-promtail` | — | containerPort 3101 | ✅ `http_listen_port: 3101` |
| `loki-headless` / `loki-memberlist` | ClusterIP | 3100 / 7946 | SingleBinary 内部用，无需改 |

> 结论：service 名与端口**全部匹配，无需回填修改**。装完仍可用 `kubectl -n c1-ns-log get svc` 复核。

### 5. ⚠️ 两个部署阻断项（已实测发现并修复，勿删）

以下是纯靠读文档/猜测**发现不了**、必须 `helm template` 实测才暴露的问题，`values.yaml` 已修复：

**① SingleBinary 必须把 read/write/backend 副本归零**

chart 默认 `read/write/backend.replicas` 各为 **3**、`singleBinary.replicas` 为 0。只设 `singleBinary.replicas: 1` 而不归零另外三个，会触发官方 `validate.yaml` 直接 `fail`（`helm install` 失败）：

> `You have more than zero replicas configured for both the single binary and simple scalable targets...`

修复（`values.yaml` 已加）：

```yaml
loki:
  deploymentMode: SingleBinary
  read:    { replicas: 0 }
  write:   { replicas: 0 }
  backend: { replicas: 0 }
  singleBinary: { replicas: 1 }
```

**② 三个 docker.io 辅助镜像必须关闭（离线环境拉不到会 ImagePullBackOff）**

官方 chart 默认引入 3 个走 `docker.io` 的辅助容器，本项目均用不到，已在 `values.yaml` 关闭：

| 辅助镜像 | 来源开关 | 默认 | 修复 | 理由 |
|---------|---------|------|------|------|
| `kiwigrid/k8s-sidecar:1.28.0` | `loki.sidecar.rules.enabled` | true | **false** | recording/alerting 规则 sidecar，本项目未用 |
| `busybox:1.31.1` | `grafana.initChownData.enabled` | true | **false** | grafana pod 已带 `fsGroup:472`，PVC 自动 chown |
| `bats/bats:v1.4.1` | `grafana.testFramework.enabled` | true | **false** | 仅 `helm test` 用，install 不需要 |

> 加上第 2 节的镜像 key 修复（`loki.image` → 内层 `loki.loki.image`），共 **5 处修复**。修复后实测：渲染镜像从「6 个含 3 个 docker.io」降到 **3 个全私有仓库**，validate.yaml 不再报错。

---

## 部署

### 前置：私有仓库需已有这三个镜像

确认私有仓库中已有这三个镜像即可：

```
10.0.6.183:8088/grafana/loki:3.3.2
10.0.6.183:8088/grafana/promtail:3.3.2
10.0.6.183:8088/grafana/grafana:11.4.0
```

### 方式一：在线拉取依赖后打包推 OCI（推荐）

```bash
cd "docs-c1/80 运维软件"

# 1. 拉取官方依赖 chart 到 helm-loki/charts/（需联网）
helm dependency update helm-loki

# 2. 打包 + 推送到私有 OCI 仓库
helm package helm-loki
helm push c1-loki-stack-1.0.0.tgz oci://10.0.6.183:8088/helm --plain-http

# 3. 安装（自动创建 c1-ns-log）
helm install c1-loki-stack oci://10.0.6.183:8088/helm/c1-loki-stack \
  --version 1.0.0 \
  -n c1-ns-log \
  --plain-http \
  --create-namespace
```

### 方式二：纯离线（无网环境）

在**有网机器**上把依赖和镜像都备齐，再拷进内网：

```bash
# (有网机器) 拉 chart 依赖
helm dependency update helm-loki          # 生成 helm-loki/charts/*.tgz

# (有网机器) 拉镜像并推私有仓库（若内网仓库无法联网，则 docker save/load 中转）
docker pull grafana/loki:3.3.2
docker tag  grafana/loki:3.3.2 10.0.6.183:8088/grafana/loki:3.3.2
docker push 10.0.6.183:8088/grafana/loki:3.3.2
# promtail、grafana 同理

# 把整个 helm-loki/（含 charts/）拷到内网，直接从本地目录安装
helm install c1-loki-stack helm-loki -n c1-ns-log --create-namespace
```

> `charts/` 里已有依赖 .tgz 时，Helm **不会**再联网拉取，可完全离线安装。

### 改动配置后重新部署

改了 `values.yaml`（如加 tolerations、调存储大小）后：**未安装**用上面的 `install`；**已安装**用 `upgrade` 原地更新：

```bash
# 本地目录方式（离线推荐）
helm upgrade c1-loki-stack helm-loki -n c1-ns-log

# OCI 方式（需先 bump Chart.yaml 的 version 并重新 package + push）
helm upgrade c1-loki-stack oci://10.0.6.183:8088/helm/c1-loki-stack \
  --version <新版本> -n c1-ns-log --plain-http
```

---

## 验证

```bash
# 1. 三个组件都应 Running / Ready
kubectl -n c1-ns-log get pods -o wide
#   c1-loki-0            Running
#   c1-promtail-xxxxx    Running（每个节点一个）
#   c1-grafana-xxxxx     Running

# 2. Promtail 采集目标（确认 __path__ 拼接正确、有 activeTargets）
kubectl -n c1-ns-log port-forward ds/c1-promtail 9080:3101
#   浏览器打开 http://localhost:9080/targets ，看每个 target 的 __path__ 是否指向真实日志文件

# 3. Loki 就绪（READY 1/1 即代表 /ready 探针通过；loki 镜像无 wget/curl，别在容器内查）
kubectl -n c1-ns-log get pod c1-loki-0
#   如需手动查：port-forward 后在节点上 curl
kubectl -n c1-ns-log port-forward c1-loki-0 3100:3100   # 另开终端 curl http://localhost:3100/ready

# 4. Grafana 访问
#   http://<节点IP>:30300   admin / admin123
#   Explore → 选 Loki 数据源 → 查询 {namespace="c1-ns-test"}
```

---

## 使用（在 Grafana 查询日志）

浏览器打开 `http://<节点IP>:30300`，用 `admin / admin123` 登录 → 左侧 **Explore** → 数据源选 **Loki**。

### LogQL 查询示例

```
# 看某业务 namespace 的全部日志
{namespace="c1-ns-test"}

# 定位到具体 Pod
{namespace="c1-ns-test", pod="c1-b-extract-xxx-yyy"}

# 只看 ERROR（values 的 pipelineStages 已把 level 提为标签）
{namespace="c1-ns-test", level="ERROR"}

# 全文关键字过滤（LogQL 行过滤器）
{namespace="c1-ns-test"} |= "Exception"

# 正则匹配一批 Pod
{namespace="c1-ns-test", pod=~"c1-b-.*"}
```

> `level` 标签来自 `values.yaml` 的 `promtail.config.snippets.pipelineStages`（`regex + labels`）；若某类日志格式不含 `INFO/WARN/...`，该标签会缺失，用全文关键字 `|= "ERROR"` 兜底。

### ⚠️ 默认没有预置 Dashboard

本方案的 `values.yaml` **只配了 Loki 数据源，没配 Dashboard**，所以默认走 **Explore + LogQL** 直接查。

想要下拉式面板，在 Grafana 里手动新建 Dashboard，Explore 调好后 **Save** 即可（数据已落 PVC，重启不丢）；或通过官方 chart 的 `grafana.dashboardProviders` + `grafana.dashboards` 挂入 JSON Dashboard。

---

## 关键配置速查（values.yaml）

| 配置项 | 路径 | 默认值 | 说明 |
|--------|------|--------|------|
| Loki 部署模式 | `loki.deploymentMode` | `SingleBinary` | 小规模单体；大规模改 `SimpleScalable` |
| ⚠️ 三目标副本 | `loki.read/write/backend.replicas` | `0` | SingleBinary 必须归零，否则 validate.yaml 报错（见校准 5①）|
| Loki 存储大小 | `loki.singleBinary.persistence.size` | `10Gi` | PVC 容量 |
| 日志保留时长 | `loki.loki.limits_config.retention_period` | `168h` | 7 天 |
| Loki 调度节点 | `loki.singleBinary.nodeSelector` | `node-name=master-6.183` | 自定义标签，非 kubernetes.io/hostname |
| Loki/Grafana 污点容忍 | `loki.singleBinary.tolerations`、`grafana.tolerations` | master+control-plane / NoSchedule | ⚠️ 缺了会 Pending |
| Loki 存储类型 | `loki.loki.storage.type` | `filesystem` | 本地盘(local-path PVC)；要 HA/大规模改对象存储(MinIO/S3) |
| 多租户鉴权 | `loki.loki.auth.enabled` | `false` | 集群内部用，关闭 |
| Promtail 推送地址 | `promtail.config.clients[0].url` | `http://c1-loki:3100/...` | ⚠️ 与 Loki svc 名一致 |
| Promtail 采集管道 | `promtail.config.snippets.pipelineStages` | `cri+multiline+level` | 解析/合并/提级别 |
| Promtail 排除自身采集 | `promtail.config.snippets.extraRelabelConfigs` | `drop promtail` | 避免 promtail pod 采集自己的日志形成反馈循环 |
| Grafana 外部端口 | `grafana.service.nodePort` | `30300` | NodePort |
| Grafana 管理员密码 | `grafana.adminPassword` | `admin123` | 首次登录后修改 |
| Grafana 数据源 | `grafana.datasources` | Loki `:3100` | ⚠️ 与 Loki svc 名一致 |
| 私有镜像仓库 | 各 `image.registry`（loki 在**内层** `loki.loki.image`）| `10.0.6.183:8088` | ⚠️ loki 双层 key，已验证 helper 读 `.Values.loki.image`（见校准 2）|
| ⚠️ 关 loki 规则 sidecar | `loki.sidecar.rules.enabled` | `false` | 否则拉 docker.io/kiwigrid（见校准 5②）|
| ⚠️ 关 grafana initChown | `grafana.initChownData.enabled` | `false` | 否则拉 docker.io/busybox（见校准 5②）|
| ⚠️ 关 grafana test | `grafana.testFramework.enabled` | `false` | 否则拉 docker.io/bats（见校准 5②）|

> 只覆盖了差异项，其余全部沿用官方默认值。查看更多：`helm show values grafana/<chart> --version <ver>`。

---

## 故障排查

| 现象 | 排查 |
|------|------|
| Pod `ImagePullBackOff`（loki 镜像回退 docker.io）| 镜像 key 层级写错 → 必须在**内层** `loki.loki.image`（helper 读 `.Values.loki.image`），或改用 `loki.global.image.registry`（见校准 2）|
| Pod `ImagePullBackOff`（镜像是 kiwigrid/busybox/bats）| 辅助容器未关 → `loki.sidecar.rules.enabled:false`、`grafana.initChownData.enabled:false`、`grafana.testFramework.enabled:false`（见校准 5②）|
| `helm install` 直接失败，报 "more than zero replicas ... single binary and simple scalable" | SingleBinary 未归零三目标 → 确认 `loki.read/write/backend.replicas: 0`（见校准 5①）|
| Pod 一直 `Pending`（不调度） | master 有污点但缺 tolerations → 确认 `loki.singleBinary.tolerations`、`grafana.tolerations` 已配 master+control-plane/NoSchedule；再查节点是否有 `node-name=master-6.183` 标签 |
| Promtail `/ready` 500「no logs to tail」 | `__path__` 没匹配到文件 → port-forward 看 `/targets`，确认宿主机 `/var/log/pods` 已挂载 |
| Grafana 查不到日志 | 数据源 url 与 Loki svc 名不符 → `kubectl get svc` 核对，改 `grafana.datasources` |
| Loki 起不来、报 schema/存储错 | `loki.loki.storage.type` 与 `schemaConfig` 的 `object_store` 必须都是 `filesystem` |
| 依赖拉取失败 | 网络问题 → 用「方式二」离线，把 `.tgz` 手动放进 `charts/` |
| 装完 service 名对不上 | 官方版本命名差异 → 以 `kubectl get svc` 实际为准，回填 values |

---

## 卸载

```bash
helm uninstall c1-loki-stack -n c1-ns-log

# PVC 默认不会随卸载删除，需手动清理（谨慎，会丢历史日志）
kubectl -n c1-ns-log get pvc
# kubectl -n c1-ns-log delete pvc <loki/grafana 的 pvc>
```

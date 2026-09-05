# 07-helm — Helm 部署方案

本目录是 DIB 微服务的 **Helm Chart**，将 `01-install` 到 `06-scripts` 的所有部署配置整合为一套模板 + 变量的方案。

> **前置条件**：K3s 集群已安装（`01-install`），`helm` 命令已安装。

---

## 前置知识：为什么需要 Helm

如果你已经用过 `02-config` 到 `06-scripts` 的 kubectl 方案，你会发现两个问题：

**问题一：多环境配置麻烦**

```
kubectl 方案：4 个环境 = 4 份几乎相同的 YAML
  configmap-dev.yaml      ← 90% 内容相同，只有几个值不同
  configmap-test.yaml
  configmap-uat.yaml
  configmap-prod.yaml
  改一个镜像地址，要改 4 个文件
```

**问题二：没有版本管理**

```
kubectl 方案：升级和回滚全靠人记
  kubectl set image deployment/gateway gateway=...:v3.0.0   # 升级
  # 出问题了想回滚？得记得原来的镜像版本是什么
  kubectl set image deployment/gateway gateway=...:v2.0.0   # 手动回滚
```

**Helm 的解决方案**：

```
Helm 方案：模板只有一份，不同环境只改 values 文件
  templates/gateway.yaml    ← 模板（所有环境共用）
  values-dev.yaml           ← 开发环境的差异配置
  values-test.yaml          ← 测试环境的差异配置
  values-prod.yaml          ← 生产环境的差异配置
```

---

## 目录结构

```
07-helm/
├── Chart.yaml                      # Chart 元信息（名称、版本）
├── values.yaml                     # 默认配置（所有参数的完整定义）
├── values-dev.yaml                 # 开发环境覆盖配置
├── values-test.yaml                # 测试环境覆盖配置
├── values-prod.yaml                # 生产环境覆盖配置
└── templates/                      # YAML 模板文件（按层级分组）
    ├── 01-base/                    # 基础配置（部署前必须存在）
    │   ├── namespace.yaml          #   命名空间
    │   ├── configmap.yaml          #   公共配置（环境变量）
    │   └── image-pull-secret.yaml  #   镜像仓库认证
    ├── 02-infra/                   # 基础设施层
    │   ├── nacos.yaml              #   Nacos 注册中心
    │   └── redis.yaml              #   Redis 缓存
    ├── 03-platform/                # 平台服务层
    │   ├── auth-server.yaml        #   SSO 认证中心
    │   ├── gateway.yaml            #   API 网关
    │   ├── auth-resource.yaml      #   权限资源管理
    │   └── mdm.yaml                #   主数据管理
    └── 04-business/                # 业务服务层
        ├── service-extract.yaml    #   资料提取
        ├── service-report.yaml     #   报告生成
        ├── service-data.yaml       #   数据资源
        ├── service-rule.yaml       #   规则引擎
        └── data-dg.yaml            #   数据治理
```

**对比 kubectl 方案的目录**：

```
kubectl 方案（01~06）：               Helm 方案（07）：
├── 02-config/                       ├── values.yaml          ← 所有配置集中在这里
│   ├── namespace.yaml               │
│   ├── configmap.yaml               ├── templates/           ← 所有模板集中在这里
│   └── image-pull-secret.yaml       │   ├── namespace.yaml
├── 03-infra/                        │   ├── configmap.yaml
│   ├── nacos.yaml                   │   ├── nacos.yaml
│   └── redis.yaml                   │   └── ...
├── 04-platform/                     │
│   └── all-services.yaml            └── values-prod.yaml     ← 生产环境只改这个文件
├── 05-business/
│   └── all-services.yaml
└── 06-scripts/
    ├── deploy-all.sh
    └── verify.sh
```

kubectl 方案有 6 个目录、10+ 个文件；Helm 方案只有 1 个目录、模板 + values。

---

## 核心原理：模板 + 变量

### 模板文件里有什么

模板文件不是写死的 YAML，里面有 `{{ }}` 占位符：

```yaml
# templates/configmap.yaml（模板）

apiVersion: v1
kind: ConfigMap
metadata:
  name: dib-common-config
  namespace: {{ .Values.namespace }}       # ← 占位符
data:
  {{- range $key, $value := .Values.config }}
  {{ $key }}: {{ $value | quote }}         # ← 占位符
  {{- end }}
```

### values 文件提供变量值

```yaml
# values.yaml（默认配置）

namespace: c1-idc-test

config:
  C1_ENV: "idc-test-c1"
  DB_URL: "jdbc:mysql://10.0.6.161:3306/..."
  REDIS_HOST: "redis.c1-idc-test.svc.cluster.local"
  ...
```

### Helm 渲染过程

```
helm install 时，Helm 做的事：

步骤 1：读取 values.yaml（默认值）
         + values-prod.yaml（覆盖值）
         → 合并为最终配置

步骤 2：遍历 templates/ 目录下的每个文件
         把 {{ .Values.xxx }} 替换为实际值

步骤 3：生成最终的 YAML
         提交给 K8s API Server

模板：namespace: {{ .Values.namespace }}
values：namespace: c1-idc-prod
结果：namespace: c1-idc-prod
```

---

## 快速开始

### 安装 Helm

```bash
# K3s Server 节点上执行
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# 验证
helm version
```

### 部署（首次安装）

```bash
# 进入 Chart 目录
cd 07-helm

# 部署到测试环境（使用 values-test.yaml 覆盖默认配置）
helm install dib-test . --values values-test.yaml

# 部署到生产环境
helm install dib-prod . --values values-prod.yaml
```

**命令拆解**：

| 部分 | 含义 |
|------|------|
| `helm install` | 安装一个新应用 |
| `dib-test` | 给这次安装起的名字（Release 名称） |
| `.` | Chart 位置：当前目录 |
| `--values values-test.yaml` | 用这个文件覆盖 values.yaml 中的默认值 |

### 验证部署

```bash
# 查看 Release 状态
helm list

# 查看渲染后的 YAML（不部署，只看会生成什么）
helm template dib-test . --values values-test.yaml

# 查看 K8s 资源
kubectl -n c1-idc-test get pods
```

---

## 升级与回滚

### 升级

```bash
# 场景 1：修改了 values-prod.yaml 中的配置
# 比如把 gateway.replicas 从 2 改为 3
helm upgrade dib-prod . --values values-prod.yaml

# 场景 2：升级镜像版本
# 修改 values-prod.yaml 中的 image.tag: v2.0.0 → v3.0.0
helm upgrade dib-prod . --values values-prod.yaml
```

### 回滚

```bash
# 查看历史版本
helm history dib-prod

# 回滚到上一版本
helm rollback dib-prod

# 回滚到指定版本
helm rollback dib-prod 1
```

### 卸载

```bash
# 删除整个 Release（所有资源都会被删除）
helm uninstall dib-prod
```

---

## 多环境部署

### 一套模板，多个 values

```
                    ┌─────────────────────┐
                    │   templates/        │
                    │   （模板只有一份）    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │ values-dev   │  │ values-test  │  │ values-prod  │
     │ tag: latest  │  │ tag: v2.0.0  │  │ tag: v2.0.0  │
     │ replicas: 1  │  │ replicas: 1  │  │ replicas: 2  │
     │ DB: 开发库    │  │ DB: 测试库    │  │ DB: 生产库    │
     └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
            │                 │                 │
            ▼                 ▼                 ▼
     helm install       helm install       helm install
     dib-dev            dib-test           dib-prod
```

### 部署 4 个环境

```bash
# 每个环境一条命令
helm install dib-dev  . --values values-dev.yaml
helm install dib-test . --values values-test.yaml
helm install dib-uat  . --values values-uat.yaml     # 按需创建
helm install dib-prod . --values values-prod.yaml
```

### 各环境独立管理

```bash
# 查看各环境状态
helm list                    # 列出所有 Release
helm history dib-dev         # 查看开发环境历史
helm history dib-prod        # 查看生产环境历史

# 单独升级某个环境
helm upgrade dib-dev . --values values-dev.yaml

# 单独回滚某个环境
helm rollback dib-prod 1
```

---

## values.yaml 参数说明

### 全局参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `namespace` | K8s 命名空间 | `c1-idc-test` |
| `imageRegistry` | 镜像仓库地址 | `10.0.6.183:8088` |
| `image.tag` | 默认镜像版本 | `latest` |
| `imagePullPolicy` | 镜像拉取策略 | `Always` |

### 镜像仓库认证

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `registry.server` | 仓库地址 | `10.0.6.183:8088` |
| `registry.username` | 用户名 | `admin` |
| `registry.password` | 密码 | `admin123` |

### 微服务参数（每个服务相同结构）

```yaml
services:
  gateway:                        # 服务名
    tier: platform                # 层级：platform / business
    image: "c1/platform-gateway"  # 镜像名（不含 registry 和 tag）
    port: 20000                   # 容器端口
    serviceType: NodePort         # Service 类型：ClusterIP / NodePort
    nodePort: 30000               # NodePort 端口（仅 NodePort 类型有效）
    healthPath: /actuator/health  # 健康检查路径
    replicas: 1                   # 副本数
    tag: v2.0.0                   # 可选：覆盖全局 image.tag
    resources:                    # 资源限制
      requests:
        cpu: "250m"
        memory: "512Mi"
      limits:
        cpu: "1000m"
        memory: "2Gi"
```

---

## 与 kubectl 方案的对比

| 操作 | kubectl 方案（01~06） | Helm 方案（07） |
|------|---------------------|----------------|
| 部署 | `bash 06-scripts/deploy-all.sh` | `helm install dib . --values values.yaml` |
| 改配置 | 改 YAML → `kubectl apply` | 改 values → `helm upgrade` |
| 换环境 | 手动改多个 YAML | 换 values 文件 |
| 回滚 | 手动记住旧版本，逐个还原 | `helm rollback dib 1` |
| 查看历史 | 没有 | `helm history dib` |
| 新增服务 | 改 YAML + 改脚本 | 在 values.yaml 加一段服务配置 |

---

## 常见问题

#### Q1: 已有 kubectl 方案，为什么还要 Helm？

**Q：** 01~06 的 kubectl 方案已经能正常部署，为什么还要搞 Helm？

**A：** 两种方案解决不同的问题：

| 场景 | kubectl 方案 | Helm 方案 |
|------|------------|----------|
| 首次部署，1-2 个环境 | ✓ 够用 | 可以但没必要 |
| 4 个环境，配置差异大 | 维护成本高 | ✓ 一套模板搞定 |
| 需要版本管理和回滚 | 没有 | ✓ 自动记录 |
| 交付给客户部署 | 给客户一堆 YAML | ✓ 给客户 Chart + values |

**建议**：当前如果只有 1 个环境，继续用 kubectl 方案即可。等环境数量增加或需要版本管理时，再迁移到 Helm。两套方案可以并存，不影响。

---

#### Q2: Helm 和 kubectl 方案能同时用吗？

**Q：** 如果先用 kubectl 部署了，后来想用 Helm，需要先把 kubectl 部署的资源删掉吗？

**A：** 需要。因为 Helm 会认为"没有用 Helm 部署过的资源 = 不存在"，升级时会重新创建，可能导致冲突。

```bash
# 正确做法：先清理 kubectl 部署的资源
kubectl delete namespace c1-idc-test

# 然后用 Helm 重新部署
helm install dib-test . --values values-test.yaml
```

---

#### Q3: values 文件只写差异部分，Helm 怎么知道其他参数？

**Q：** `values-prod.yaml` 里只写了 `namespace`、`image.tag` 等几个参数，其他参数（如 `nacos.image`、`redis.storage`）没写，不会丢失吗？

**A：** 不会。Helm 的 values 合并逻辑是**覆盖，不是替换**：

```
合并过程：

values.yaml（默认值）          values-prod.yaml（覆盖值）
┌────────────────────┐         ┌────────────────────┐
│ namespace: c1-idc-test│       │ namespace: c1-idc-prod│
│ image.tag: latest    │  +    │ image.tag: v2.0.0    │
│ nacos.image: ...     │       │ (没有 nacos 配置)     │
│ redis.storage: 2Gi   │       │ (没有 redis 配置)     │
└────────────────────┘         └────────────────────┘
              │
              ▼
         最终合并结果
┌────────────────────┐
│ namespace: c1-idc-prod│  ← 被覆盖
│ image.tag: v2.0.0    │  ← 被覆盖
│ nacos.image: ...     │  ← 保持默认
│ redis.storage: 2Gi   │  ← 保持默认
└────────────────────┘
```

所以 values-prod.yaml **只需要写和默认值不同的参数**，其余自动用 values.yaml 中的默认值。

---

#### Q4: 怎么预览 Helm 会生成什么 YAML？

**Q：** 部署前想看看 Helm 最终会生成什么样的 YAML，怎么操作？

**A：** 用 `helm template` 命令，只渲染不部署：

```bash
# 渲染并输出到终端
helm template dib-test . --values values-test.yaml

# 渲染并保存到文件
helm template dib-test . --values values-test.yaml > rendered.yaml

# 只渲染某个模板文件
helm template dib-test . --values values-test.yaml -s templates/configmap.yaml
```

`helm template` 不会连接 K8s 集群，纯本地渲染，适合检查模板语法和变量替换是否正确。

---

#### Q5: 新增一个微服务，Helm 怎么操作？

**Q：** 如果 DIB 新增了一个微服务 `service-new`，用 Helm 怎么部署？

**A：** 只需要在 `values.yaml` 的 `services` 下加一段配置，模板会自动生成对应的 Deployment 和 Service：

```yaml
# 在 values.yaml 的 services 下新增：

  service-new:
    tier: business
    image: "c1/c1-new"
    port: 30006
    serviceType: ClusterIP
    healthPath: /api/new/actuator/health
    replicas: 1
    resources:
      requests:
        cpu: "250m"
        memory: "512Mi"
      limits:
        cpu: "1000m"
        memory: "2Gi"
```

```bash
# 升级部署（Helm 会自动创建新资源，不影响现有服务）
helm upgrade dib-test . --values values-test.yaml
```

不需要改任何模板文件 — 因为 `business-deployments.yaml` 和 `business-services.yaml` 用的是 `range` 循环，会自动遍历 `services` 下的所有服务。

---

#### Q6: 镜像仓库密码怎么安全管理？

**Q：** `values.yaml` 里有镜像仓库密码，提交到 Git 仓库不安全怎么办？

**A：** 三种方案，安全性递增：

**方案一：values 文件不提交密码（推荐）**

```bash
# values-prod.yaml 中不写 registry 密码
# 部署时通过 --set 传入
helm install dib-prod . \
  --values values-prod.yaml \
  --set registry.username=actual_user \
  --set registry.password=actual_password
```

**方案二：用外部 values 文件**

```bash
# values-prod-secrets.yaml 不提交到 Git（加入 .gitignore）
helm install dib-prod . \
  --values values-prod.yaml \
  --values values-prod-secrets.yaml
```

**方案三：使用 K8s Secret 管理**

将密码存入 K8s Secret，模板中引用 Secret 而非 values。适合生产环境。

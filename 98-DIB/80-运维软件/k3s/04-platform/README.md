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

## 前置知识：平台服务层在整个架构中的位置

在部署之前，先理解这 4 个服务在整个系统中的角色：

```
外部浏览器 / 前端 APP
    │
    │  http://<节点IP>:30000
    ▼
┌─────────────────────────────────────────────────────────┐
│                    平台服务层（本目录）                     │
│                                                         │
│  ┌─────────────┐    ┌─────────────┐                     │
│  │ auth-server  │    │  gateway    │  ← NodePort 对外    │
│  │ (SSO 认证)   │    │ (API 网关)  │    外部流量从这里进   │
│  └─────────────┘    └──────┬──────┘                     │
│                            │ 路由转发                     │
│  ┌─────────────┐    ┌──────┴──────┐                     │
│  │auth-resource│    │    mdm      │  ← ClusterIP 内部    │
│  │(权限/角色)   │    │ (主数据)    │    只被 gateway 调用  │
│  └─────────────┘    └─────────────┘                     │
└─────────────────────────────────────────────────────────┘
    │                        │
    ▼                        ▼
┌─────────────────────────────────────────────────────────┐
│                    业务服务层（05-business）               │
│  service-extract / service-report / service-data / ...  │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    基础设施层（03-infra）                  │
│  Nacos（注册中心）  Redis（缓存）  MySQL（数据库）         │
└─────────────────────────────────────────────────────────┘
```

**通俗理解**：把整个系统想象成一家公司——

- **gateway** = 公司前台，所有外来访客（API 请求）先到前台，前台指引你去正确的部门
- **auth-server** = 门卫 / 保安，负责检查你的工牌（Token），确认你有权进入
- **auth-resource** = HR 部门，管理谁能访问哪些系统功能（权限、角色、菜单）
- **mdm** = 档案室，管理公司最基础的数据（组织架构、人员信息、字典等）

为什么 auth-resource 和 mdm 不对外暴露？因为它们不直接接待外部请求，所有请求都由 gateway 统一转发。这样做的好处是**安全**（减少攻击面）和**解耦**（内部服务可以随意改端口，不影响外部）。

---

## all-services.yaml 通用结构详解

4 个服务的 YAML 结构高度一致，每个服务都包含一对 **Deployment**（运行容器）+ **Service**（提供网络入口）。理解了一个，其余三个只是端口和镜像名不同。

### 一、Deployment 通用部分

以 auth-server 为例，逐段讲解每个 Deployment 都相同的结构：

#### 1.1 外层元信息与副本控制

```yaml
apiVersion: apps/v1
kind: Deployment                     # 资源类型：Deployment
metadata:
  name: auth-server                  # Deployment 名称，kubectl 操作时用
  namespace: c1-idc-test             # 所属命名空间
  labels:
    app: auth-server                 # 标签
    tier: platform                   # tier 标签标识"层级"：platform = 平台层
spec:
  replicas: 1                        # 副本数：始终保持 1 个 Pod
                                     # 平台服务当前都是单副本，需要高可用时改为 >1
  strategy:
    type: RollingUpdate              # 更新策略：滚动更新（默认值）
                                     # 先启动新 Pod，等新 Pod Ready 后再删旧 Pod
                                     # 与 03-infra 的 Recreate 不同——因为平台服务不使用 PVC
                                     # 没有 PVC 数据冲突，可以安全地同时运行新旧 Pod
  selector:
    matchLabels:
      app: auth-server               # 通过标签匹配 Pod（与 03-infra 中 Q7 讲的原理相同）
```

**与 03-infra 的区别**：Nacos/Redis 使用 `Recreate` 策略是因为它们有 PVC，两个 Pod 同时写同一个 PVC 会冲突。平台服务不使用 PVC（日志用 emptyDir），所以可以用 `RollingUpdate`，实现零停机更新。

#### 1.2 镜像拉取认证

```yaml
      imagePullSecrets:              # 镜像仓库认证凭据
        - name: dib-registry-secret  # 引用 02-config 中创建的 Secret
```

**作用**：告诉 K3s "拉取镜像时，用这个凭据去登录私有仓库"。如果不配置，K3s 会匿名拉取，私有仓库会拒绝。

**类比**：就像下载 APP 时需要先登录应用商店账号一样，`imagePullSecrets` 就是 K3s 的"应用商店登录凭据"。

#### 1.3 环境变量注入（核心机制）

```yaml
          env:                                    # ← 方式一：逐个指定
            - name: C1_ENV                        #   从 ConfigMap 中取某一个 Key
              valueFrom:
                configMapKeyRef:
                  name: dib-common-config
                  key: C1_ENV
            - name: TZ
              value: "Asia/Shanghai"              #   也可以直接写死一个值

          envFrom:                                # ← 方式二：批量注入
            - configMapRef:                       #   把 ConfigMap 中所有 Key-Value
                name: dib-common-config           #   一次性全部注入为环境变量
```

**先说结论：`C1_ENV` 确实被注入了两次，功能上重复了。** 下面解释为什么。

#### `configMapKeyRef` 各字段的含义

```yaml
configMapKeyRef:
  name: dib-common-config    # ← 去哪个 ConfigMap 取？（ConfigMap 的名称）
  key: C1_ENV                # ← 取 ConfigMap 里的哪个字段？
```

- `name` = ConfigMap 的名称，就是 `02-config/configmap.yaml` 里 `metadata.name` 的值。它告诉 K3s "去哪本'书'里找"
- `key` = ConfigMap 里的具体字段名。它告诉 K3s "找'书'里的哪一页"

类比：`name` 是"哪本书"，`key` 是"书里的哪一页"。每次只能翻一页（取一个 key）。

#### `env` 每次只能注入一个 key，要注入多个就得写多条

当前 YAML 中，`env` 部分从 ConfigMap 里**只取了 `C1_ENV` 这一个 key**（`TZ` 是直接写死的，不来自 ConfigMap）。其余所有变量全靠 `envFrom` 批量注入。

如果想用 `env` 方式从 ConfigMap 取多个 key，必须**一条一条写**，每条独立指定 `configMapKeyRef`：

```yaml
env:
  - name: C1_ENV
    valueFrom:
      configMapKeyRef:
        name: dib-common-config    # 同一本"书"
        key: C1_ENV                # 第 1 页

  - name: DB_URL
    valueFrom:
      configMapKeyRef:
        name: dib-common-config    # 同一本"书"（每次都要写，K3s 不会帮你记住上一条）
        key: DB_URL                # 第 2 页

  - name: REDIS_HOST
    valueFrom:
      configMapKeyRef:
        name: dib-common-config    # 同一本"书"
        key: REDIS_HOST            # 第 3 页
```

可以看到，如果 ConfigMap 有 20 个字段，用 `env` 方式就得写 20 条——太麻烦了。这就是 `envFrom` 存在的意义：一条搞定全部。

#### 两种方式的本质区别

| | `env`（逐个指定） | `envFrom`（批量注入） |
|---|---|---|
| 做了什么 | 从 ConfigMap 中挑出**指定的 Key**，注入为环境变量 | 把 ConfigMap 中**所有 Key-Value** 都注入为环境变量 |
| 类比 | 去超市只买清单上列的 3 样东西 | 把超市整个货架搬回家 |

用 `dib-common-config` 举例，它里面有这些内容：

```yaml
# 02-config/configmap.yaml 的内容
data:
  C1_ENV: "idc-test-c1"
  NACOS_SERVER_ADDR: "http://nacos.c1-idc-test.svc.cluster.local:8848"
  REDIS_HOST: "redis.c1-idc-test.svc.cluster.local"
  DB_URL: "jdbc:mysql://10.0.6.161:3306/..."
  DB_USERNAME: "root"
  DB_PASSWORD: "Dib12345*"
  ... (还有很多)
```

**只有 `envFrom` 的效果**（假设 YAML 里只写了 `envFrom`，没有 `env`）：

```
envFrom 把 ConfigMap 里的所有内容都注入了：
  C1_ENV=idc-test-c1              ← 也在这里面
  NACOS_SERVER_ADDR=http://...
  REDIS_HOST=redis.c1-idc-test...
  DB_URL=jdbc:mysql://...
  DB_USERNAME=root
  DB_PASSWORD=Dib12345*
  ... 全部都在
```

所以 `envFrom` 已经包含了 `C1_ENV`，**`env` 里再写一遍 `C1_ENV` 完全是多余的，删掉也不影响运行**。

#### 那为什么还要多写一遍 `C1_ENV`？

纯粹是**给人看的标注**。想象你半年后回来看这个 YAML，如果只有 `envFrom`，你得去翻 ConfigMap 才知道这个服务用了哪些变量。单独列出 `C1_ENV` 相当于在说："注意，这个服务特别依赖 `C1_ENV` 这个变量"。

**实际效果等价于只写 `envFrom`**，`env` 里那个 `C1_ENV` 是冗余的。

#### 那 `TZ` 呢？为什么用 `env` 而不是 `envFrom`？

因为 `TZ=Asia/Shanghai` 是一个**写死的固定值**，不在 ConfigMap 里。`env` 除了能从 ConfigMap 取值，还能直接写死一个值：

```yaml
env:
  - name: TZ
    value: "Asia/Shanghai"       # 直接写死，不引用任何 ConfigMap
```

#### 总结：两种方式各自干什么

```
env 做的事情：                    envFrom 做的事情：
┌──────────────────────┐         ┌──────────────────────┐
│ ① C1_ENV             │         │                      │
│    ← 从 ConfigMap 取  │         │  ConfigMap 里的       │
│    （重复了，可删）    │         │  所有内容             │
│                      │         │  C1_ENV, DB_URL,      │
│ ② TZ=Asia/Shanghai   │         │  REDIS_HOST, ...     │
│    ← 直接写死的值     │         │  全部注入             │
│    （ConfigMap 里没有）│         │                      │
└──────────────────────┘         └──────────────────────┘
            │                                │
            └────────────┬───────────────────┘
                         ▼
                  容器内的环境变量
                  C1_ENV=idc-test-c1
                  TZ=Asia/Shanghai
                  DB_URL=jdbc:mysql://...
                  REDIS_HOST=redis...
                  ... (全部可用)
```

#### Spring Boot 如何使用这些变量？

应用启动时：
1. 读取 `C1_ENV` 的值（如 `idc-test-c1`），决定加载哪个 `application-{profile}.yml`
2. 在 `application-idc-test-c1.yml` 中通过 `${DB_URL}`、`${REDIS_HOST}` 等引用其他变量
3. 完成数据库连接、Redis 连接、Nacos 注册等初始化

```
ConfigMap                        Pod 容器                         Spring Boot
┌────────────────┐   envFrom    ┌──────────────────┐   读取      ┌────────────────┐
│ C1_ENV: "xxx"  │ ──────────→ │ C1_ENV=xxx       │ ────────→  │ application-   │
│ DB_URL: "jdbc…"│             │ DB_URL=jdbc…     │            │ {C1_ENV}.yml   │
│ REDIS_HOST: ...│             │ REDIS_HOST=...   │            │                │
│ ...            │             │ ...              │            │ 用 ${DB_URL}   │
└────────────────┘             └──────────────────┘            │ 连接数据库      │
                                                               └────────────────┘
```

#### 1.4 资源限制

```yaml
          resources:
            requests:                # 最低保障
              cpu: "250m"            # 0.25 核
              memory: "512Mi"        # 512MB
            limits:                  # 上限
              cpu: "1000m"           # 最多 1 核
              memory: "2Gi"          # 最多 2GB
```

**通俗理解**：`requests` 是"保底工资"，`limits` 是"天花板"。平台服务都是 Java 应用（Spring Boot），启动时吃内存较多，稳定后回落。512Mi ~ 2Gi 的范围能覆盖大部分场景。

**CPU 单位说明**：`250m` = 0.25 核 = 1/4 个 CPU 核心。`1000m` = 1 整核。`m` 是"毫核"（milli-core）的缩写。

#### 1.5 数据卷挂载

```yaml
          volumeMounts:
            - name: app-logs         # 日志目录
              mountPath: /opt/app/logs
            - name: fonts            # 系统字体
              mountPath: /usr/share/fonts
              readOnly: true         # 只读挂载（容器不能修改宿主机字体文件）

      volumes:
        - name: app-logs
          emptyDir: {}               # 临时目录，Pod 删除即清空
        - name: fonts
          hostPath:                  # 挂载宿主机目录
            path: /usr/share/fonts
            type: DirectoryOrCreate  # 目录不存在则自动创建
```

**两种数据卷对比**：

| 数据卷 | 类型 | 生命周期 | 作用 |
|--------|------|---------|------|
| `app-logs` | `emptyDir` | Pod 存在就在；**Pod 删除则清空** | 应用日志暂存。不需要持久化，因为日志通常由日志平台（如 ELK）采集 |
| `fonts` | `hostPath` | 跟随宿主机 | 挂载宿主机的字体文件，确保 PDF / Excel 导出时中文字体正常显示 |

**`emptyDir` vs `PVC`（03-infra 用的）**：

```
emptyDir:                              PVC:
┌──────────────┐                      ┌──────────────┐
│  Pod         │                      │  Pod         │
│  ┌────────┐  │                      │  ┌────────┐  │
│  │app-logs│  │  ← Pod 删除 → 清空   │  │nacos-  │  │  ← Pod 删除 → 数据保留
│  │(临时)   │  │                      │  │data    │  │
│  └────────┘  │                      │  │(持久化) │  │
└──────────────┘                      │  └────┬─────┘  │
                                      └───────┼────────┘
                                              ▼
                                      节点本地磁盘 / 网络存储
```

#### 1.6 存活探针（Liveness Probe）

```yaml
          livenessProbe:                    # 存活检查
            httpGet:
              path: /actuator/health        # Spring Boot Actuator 健康检查接口
              port: 9090
            initialDelaySeconds: 60         # 启动后等 60s 再开始探测
            periodSeconds: 15               # 每 15s 探测一次
            timeoutSeconds: 5               # 单次超时 5s
            failureThreshold: 5             # 连续失败 5 次 → 重启容器
```

**工作原理**：K3s 每隔 15 秒向容器的 `http://localhost:9090/actuator/health` 发一个 HTTP GET 请求。如果返回 HTTP 200，说明容器"活着"；如果连续 5 次没返回 200，K3s 判定容器"死了"，自动重启。

**为什么 `initialDelaySeconds` 设为 60？** Java 应用（Spring Boot）启动慢——要加载类、初始化 Spring 容器、连接数据库、注册 Nacos，首次启动通常需要 30-90 秒。如果探测太早，会误判为"启动失败"然后反复重启。

#### 1.7 就绪探针（Readiness Probe）

```yaml
          readinessProbe:                   # 就绪检查
            httpGet:
              path: /actuator/health
              port: 9090
            initialDelaySeconds: 30         # 启动后等 30s 开始探测
            periodSeconds: 10               # 每 10s 探测一次
            timeoutSeconds: 5
            failureThreshold: 3             # 连续失败 3 次 → 从 Service 摘除
```

**与存活探针的区别**（这是 K3s 新手最容易混淆的概念之一）：

```
                     存活探针失败                    就绪探针失败
                     ────────────                   ────────────
K3s 的反应：         重启容器                       不重启，但停止转发流量
类比：              人晕倒了 → 做心肺复苏            人还没睡醒 → 不安排工作
触发条件：           进程卡死/OOM                    还在启动中/依赖服务不可用
```

**就绪探针的实际意义**：假设 gateway 正在启动，还没准备好接收请求。如果没有就绪探针，用户的请求会被转发到一个还没启动完的 gateway，导致报错。有了就绪探针，K3s 会等 gateway 完全就绪后，才把流量转过来。

---

### 二、Service — 网络入口

每个服务都配一个 Service，提供稳定的网络入口。Service 有两种类型：

| 类型 | 含义 | 使用场景 | 本目录中的服务 |
|------|------|---------|--------------|
| **NodePort** | 在每个节点上开一个固定端口，外部可通过 `节点IP:端口` 访问 | 需要外部直接访问的服务 | auth-server、gateway |
| **ClusterIP** | 仅分配集群内部 IP，外部无法直接访问 | 只被内部服务调用的服务 | auth-resource、mdm |

**NodePort 的流量路径**：

```
外部浏览器
    │
    │  http://10.0.6.100:30000
    │                 │
    │                 ▼
    │           ┌─────────────┐
    │           │ NodePort    │  ← 每个节点都开放了 30000 端口
    │           │ :30000      │    （不管 Pod 在哪台节点）
    │           └──────┬──────┘
    │                  │
    │                  ▼
    │           ┌─────────────┐
    │           │ Service     │  ← port: 20000
    │           │ (ClusterIP) │
    │           └──────┬──────┘
    │                  │
    │                  ▼
    │           ┌─────────────┐
    │           │ gateway Pod │  ← targetPort: 20000
    │           │ :20000      │
    │           └─────────────┘
```

**ClusterIP 的流量路径**（以 auth-resource 为例）：

```
gateway Pod 内部
    │
    │  http://auth-resource.c1-idc-test.svc.cluster.local:20001
    │                                          │
    │                                          ▼
    │                                    ┌─────────────┐
    │                                    │ Service     │  ← port: 20001
    │                                    │ (ClusterIP) │    没有 NodePort
    │                                    └──────┬──────┘    外部到不了这里
    │                                           │
    │                                           ▼
    │                                    ┌─────────────┐
    │                                    │auth-resource│  ← targetPort: 20001
    │                                    │ Pod :20001  │
    │                                    └─────────────┘
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

**在系统中的角色**：当用户在前端登录时，请求流程如下：

```
前端 → gateway(:30000) → auth-server(:30090) → 验证用户名密码 → 返回 Token
                                                                  │
后续请求：                                                         │
前端 → gateway → 携带 Token → gateway 校验 Token 有效性 ←────────┘
```

### 2. gateway（API 网关）

- **镜像**：`10.0.6.183:8088/c1/platform-gateway:latest`
- **端口**：20000
- **访问**：NodePort 30000，**所有外部 API 请求的入口**
- **健康检查**：`GET /actuator/health`
- **资源**：512Mi ~ 2Gi 内存
- **作用**：路由转发、限流、鉴权，前端和外部系统统一通过此端口访问后端

**为什么 gateway 是最重要的服务？** 它是所有外部流量的唯一入口。如果 gateway 挂了，整个系统对外不可用（但内部服务之间仍然正常）。

```
前端 APP / 浏览器
    │
    │  所有请求都走 30000 端口
    ▼
gateway(:20000)
    │
    ├── /api/auth/**    → auth-resource(:20001)
    ├── /api/mdm/**     → mdm(:20002)
    ├── /api/extract/** → service-extract(:30001)
    ├── /api/report/**  → service-report(:30002)
    ├── /api/data/**    → service-data(:30003)
    ├── /api/rule/**    → service-rule(:30004)
    └── /api/dg/**      → data-dg(:30005)
```

### 3. auth-resource（权限资源管理）

- **镜像**：`10.0.6.183:8088/c1/platform-auth-resource:latest`
- **端口**：20001
- **访问**：ClusterIP，仅集群内部访问（由 gateway 转发）
- **健康检查**：`GET /api/auth/actuator/health`
- **资源**：512Mi ~ 2Gi 内存
- **作用**：管理用户、角色、菜单、权限等数据

**注意健康检查路径**：与 auth-server 不同，auth-resource 的健康检查路径是 `/api/auth/actuator/health`（多了 `/api/auth` 前缀）。这是因为 auth-resource 配置了 context-path，所有接口都在 `/api/auth` 路径下。

### 4. mdm（主数据管理）

- **镜像**：`10.0.6.183:8088/c1/platform-mdm:latest`
- **端口**：20002
- **访问**：ClusterIP，仅集群内部访问
- **健康检查**：`GET /api/mdm/actuator/health`
- **资源**：512Mi ~ 2Gi 内存
- **作用**：主数据（组织、人员、字典等）管理，使用 MinIO 存储附件

---

## DNS 地址汇总

部署完成后，集群内部可通过以下 DNS 地址互相访问：

| 服务 | 集群内部 DNS | 端口 |
|------|-------------|------|
| auth-server | `auth-server.c1-idc-test.svc.cluster.local` | 9090 |
| gateway | `gateway.c1-idc-test.svc.cluster.local` | 20000 |
| auth-resource | `auth-resource.c1-idc-test.svc.cluster.local` | 20001 |
| mdm | `mdm.c1-idc-test.svc.cluster.local` | 20002 |

**DNS 规则**：`<Service名称>.<命名空间>.svc.cluster.local`

> 实际上，在同一个 namespace 内的 Pod 可以直接用 Service 名称访问（如 `http://gateway:20000`），不需要写完整的 DNS 后缀。跨 namespace 才需要完整写法。

---

## 完整访问链路

```
外部浏览器 / 前端 APP
    │
    │  http://<节点IP>:30000
    ▼
gateway (NodePort 30000)
    │
    │  路由转发（根据 URL 路径匹配）
    │
    ├─→ auth-server     (NodePort 30090, 也可被 gateway 内部调用)
    │
    ├─→ auth-resource   (ClusterIP :20001)
    │
    ├─→ mdm             (ClusterIP :20002)
    │
    ├─→ service-extract (ClusterIP :30001, 05-business 部署)
    ├─→ service-report  (ClusterIP :30002)
    ├─→ service-data    (ClusterIP :30003)
    ├─→ service-rule    (ClusterIP :30004)
    └─→ data-dg         (ClusterIP :30005)
```

**一次完整的 API 请求流程**（以"查询用户列表"为例）：

```
① 浏览器发起请求
   GET http://10.0.6.100:30000/api/auth/users
   │
② 请求到达 K3s 节点的 30000 端口（NodePort）
   │  K3s 根据 Service 配置，转发到 gateway 的 Service
   │
③ gateway 收到请求
   │  解析 URL：/api/auth/users → 匹配路由 → 转发到 auth-resource
   │  同时校验请求头中的 Token（调用 auth-server 验证）
   │
④ auth-resource 处理请求
   │  查询数据库，获取用户列表
   │
⑤ 原路返回
   auth-resource → gateway → 节点 30000 端口 → 浏览器
```

---

## 访问方式

### 从外部访问 NodePort 服务

```bash
# 直接通过节点 IP 访问
curl http://<节点IP>:30000/actuator/health    # gateway 健康检查
curl http://<节点IP>:30090/actuator/health    # auth-server 健康检查

# 浏览器访问
# http://<节点IP>:30000  → gateway API 入口
# http://<节点IP>:30090  → auth-server SSO 服务
```

### 从外部访问 ClusterIP 服务（调试用）

ClusterIP 服务外部无法直接访问，需要用 `port-forward` 建隧道：

```bash
# 把 auth-resource 的 20001 端口转发到本地
kubectl -n c1-idc-test port-forward svc/auth-resource 20001:20001
# 然后浏览器访问 http://localhost:20001/api/auth/actuator/health

# 把 mdm 的 20002 端口转发到本地
kubectl -n c1-idc-test port-forward svc/mdm 20002:20002
# 然后浏览器访问 http://localhost:20002/api/mdm/actuator/health
```

### 进入容器内部调试

```bash
# 进入 gateway 容器的 Shell
kubectl -n c1-idc-test exec -it deploy/gateway -- /bin/sh

# 在容器内可以：
# 查看环境变量
env | grep C1_ENV

# 测试到其他服务的网络连通性
wget -qO- http://auth-resource:20001/api/auth/actuator/health
wget -qO- http://mdm:20002/api/mdm/actuator/health
wget -qO- http://nacos:8848/nacos/actuator/health
```

---

## 常见问题

### 一、部署与启动相关

#### Q1: 部署顺序有要求吗？

**Q：** 必须先部署 03-infra 才能部署 04-platform 吗？

**A：** **必须**。平台服务启动时会做以下事情：
1. 连接 Nacos 注册中心（`NACOS_SERVER_ADDR`）注册自己
2. 连接 Redis（`REDIS_HOST`）初始化缓存
3. 连接数据库（`DB_URL`）加载配置

如果 Nacos / Redis / 数据库还没就绪，服务启动会失败，Pod 进入 `CrashLoopBackOff` 状态。

**正确的部署顺序**：

```
02-config（命名空间 + 配置）
    ↓
03-infra（Nacos + Redis）← 等待 Pod 全部 Ready
    ↓
04-platform（平台服务）  ← 本目录
    ↓
05-business（业务服务）
```

---

#### Q2: Pod 一直 CrashLoopBackOff 怎么办？

**Q：** 部署后 Pod 反复重启，状态显示 CrashLoopBackOff，怎么排查？

**A：** 按以下步骤排查：

```bash
# 第一步：看 Pod 事件（能看到镜像拉取失败、资源不足等问题）
kubectl -n c1-idc-test describe pod <pod-name>

# 第二步：看容器日志（能看到 Java 启动报错）
kubectl -n c1-idc-test logs deployment/gateway --tail=200

# 第三步：看上一次的崩溃日志（如果容器已经重启过）
kubectl -n c1-idc-test logs deployment/gateway --previous
```

**常见原因**：

| 现象 | 可能原因 | 检查方法 |
|------|---------|---------|
| `ImagePullBackOff` | 镜像仓库认证失败 | 检查 `dib-registry-secret` 是否正确 |
| 启动后报 `Connection refused` | Nacos / Redis / 数据库未就绪 | 检查 03-infra 的 Pod 是否 Ready |
| 报 `Unknown database` | 数据库地址或名称错误 | 检查 ConfigMap 中的 `DB_URL` |
| 启动 60s 后被杀 | 健康检查超时 | 增大 `initialDelaySeconds` 或检查服务启动日志 |

---

#### Q3: 4 个服务可以同时部署吗？有依赖关系吗？

**Q：** `all-services.yaml` 里 4 个服务一起 `kubectl apply`，它们之间有启动顺序吗？

**A：** 可以同时 apply，K3s 会同时创建 4 个 Deployment。但各服务的 Pod **启动速度不同**，先启动完的会等后启动的：

- **auth-server** 和 **gateway** 启动时会尝试连接 Nacos 注册，如果 Nacos 还没好会重试
- **gateway** 路由到 auth-resource / mdm 时，如果目标 Pod 还没 Ready，就绪探针会阻止流量转发

所以 `kubectl apply -f all-services.yaml` 一条命令即可，不需要手动按顺序。但前提条件是 **03-infra 的 Nacos 和 Redis 已经 Ready**。

---

### 二、网络与访问相关

#### Q4: NodePort 30000 被占用怎么办？

**Q：** 节点上的 30000 端口已经被其他程序占用了，怎么处理？

**A：** 两种方案：

**方案一：换一个 NodePort**（推荐）

修改 `all-services.yaml` 中 gateway 的 `nodePort` 值：

```yaml
  ports:
    - port: 20000
      targetPort: 20000
      nodePort: 30100      # 改为 30100（或其他 30000-32767 范围内未被占用的值）
```

**方案二：让 K3s 自动分配**

删除 `nodePort` 字段，K3s 会自动分配一个 30000-32767 范围内未被占用的端口：

```yaml
  ports:
    - port: 20000
      targetPort: 20000
      # 不写 nodePort，K3s 自动分配
```

分配后通过 `kubectl -n c1-idc-test get svc gateway` 查看实际分配的端口。

---

#### Q5: 外部访问 gateway 用 30000 端口，内部微服务之间也用 30000 吗？

**Q：** 内部服务调用 gateway 时，是用 NodePort 30000 还是用 ClusterIP 20000？

**A：** 内部服务应该用 **Service 名称 + port**（即 `http://gateway:20000`），不走 NodePort。

```
外部请求：  http://<节点IP>:30000      → NodePort → gateway Pod
内部请求：  http://gateway:20000       → ClusterIP → gateway Pod
```

NodePort 只是给外部访问用的"后门"，内部流量走 NodePort 会多绕一层（先到节点端口，再转到 Service），没有意义。

---

#### Q6: auth-server 既是 NodePort 又能被 gateway 内部调用？

**Q：** auth-server 配了 NodePort 30090，gateway 内部调用它时也用 30090 吗？

**A：** 不是。gateway 内部调用 auth-server 用的是 **Service 名称 + port**：

```
外部访问 auth-server：  http://<节点IP>:30090   （走 NodePort）
gateway 调用 auth-server：http://auth-server:9090 （走 ClusterIP，即 Service 的 port）
```

NodePort 不影响 ClusterIP 的功能——NodePort 只是在 ClusterIP 的基础上，额外在每个节点上开了一个端口。集群内部的 DNS 和 port 始终可用。

---

### 三、配置与运维相关

#### Q7: 修改了 ConfigMap 中的配置，怎么让平台服务重启生效？

**Q：** 修改了 `02-config/configmap.yaml` 中的数据库密码，但服务还在用旧密码，怎么办？

**A：** ConfigMap 修改后会自动更新，但 Pod 内的环境变量**不会自动刷新**（因为环境变量是 Pod 启动时注入的）。需要重启 Pod：

```bash
# 重启所有平台服务
kubectl -n c1-idc-test rollout restart deployment/auth-server
kubectl -n c1-idc-test rollout restart deployment/gateway
kubectl -n c1-idc-test rollout restart deployment/auth-resource
kubectl -n c1-idc-test rollout restart deployment/mdm

# 或一条命令重启所有 Deployment
kubectl -n c1-idc-test rollout restart deployment
```

**注意**：`rollout restart` 是滚动重启（RollingUpdate），不会中断服务——先启动新 Pod，新 Pod Ready 后再删旧 Pod。

---

#### Q8: 怎么判断平台服务是否部署成功？

**Q：** 部署完成后，怎么确认一切正常？

**A：** 分三步验证：

**第一步：检查 Pod 状态**

```bash
kubectl -n c1-idc-test get pods -l tier=platform
```

期望输出（所有 Pod 都是 Running，READY 为 1/1）：

```
NAME                              READY   STATUS    RESTARTS   AGE
auth-server-xxxxx-yyyyy           1/1     Running   0          5m
gateway-xxxxx-yyyyy               1/1     Running   0          5m
auth-resource-xxxxx-yyyyy         1/1     Running   0          5m
mdm-xxxxx-yyyyy                   1/1     Running   0          5m
```

**第二步：检查健康状态**

```bash
# 通过 port-forward 检查内部健康
kubectl -n c1-idc-test port-forward svc/gateway 20000:20000 &
curl http://localhost:20000/actuator/health
# 期望返回：{"status":"UP"}
```

**第三步：检查 Nacos 注册**

```bash
# 通过 port-forward 访问 Nacos 控制台
kubectl -n c1-idc-test port-forward svc/nacos 8848:8848
# 浏览器打开 http://localhost:8848/nacos
# 登录 → 服务管理 → 服务列表
# 应该能看到 auth-server、gateway、auth-resource、mdm 都已注册
```

---

#### Q9: 怎么查看平台服务的日志？

**Q：** 想看 gateway 的运行日志，怎么操作？

**A：**

```bash
# 实时查看日志（类似 tail -f）
kubectl -n c1-idc-test logs -f deployment/gateway

# 查看最近 100 行
kubectl -n c1-idc-test logs deployment/gateway --tail=100

# 查看日志文件（容器内 /opt/app/logs 目录）
kubectl -n c1-idc-test exec -it deploy/gateway -- ls /opt/app/logs
kubectl -n c1-idc-test exec -it deploy/gateway -- cat /opt/app/logs/gateway.log
```

**注意**：日志存储在 `emptyDir` 中，Pod 重启后日志会清空。如果需要保留日志，建议部署日志采集工具（如 ELK）。

---

#### Q10: 怎么更新平台服务的镜像版本？

**Q：** 开发团队发布了新版本的 gateway 镜像，怎么在不中断服务的情况下更新？

**A：**

```bash
# 方法一：直接 set image（快速更新）
kubectl -n c1-idc-test set image deployment/gateway \
  gateway=10.0.6.183:8088/c1/platform-gateway:v2.0.0

# 观察更新进度
kubectl -n c1-idc-test rollout status deployment/gateway

# 如果新版本有问题，回滚到上一版本
kubectl -n c1-idc-test rollout undo deployment/gateway
```

**滚动更新过程**（因为策略是 `RollingUpdate`）：

```
时间线：
  T1: 旧 Pod 运行中 (v1.0)
  T2: kubectl set image → K3s 创建新 Pod (v2.0)
  T3: 新 Pod 启动中... 旧 Pod 仍在运行（服务不中断）
  T4: 新 Pod 就绪探针通过 → K3s 开始把流量转到新 Pod
  T5: 旧 Pod 被删除
  T6: 只有新 Pod (v2.0) 在运行

  用户视角：全程无感知，零停机
```

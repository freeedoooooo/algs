# 03-infra — 基础设施服务

部署 DIB 微服务前，需要先启动 Nacos（注册中心）和 Redis（缓存）。

## 文件清单

| 文件 | 服务 | 端口 | 存储 |
|------|------|------|------|
| `nacos.yaml` | Nacos v2.3.2（Standalone） | 8848 (HTTP), 9848 (gRPC) | PVC 5Gi |
| `redis.yaml` | Redis 7.0 | 6379 | PVC 2Gi |

## 部署命令

```bash
# 单独部署基础设施
kubectl apply -f 03-infra/nacos.yaml
kubectl apply -f 03-infra/redis.yaml

# 或通过部署脚本（会自动等待就绪）
bash 06-scripts/deploy-all.sh infra
```

---

## 前置知识：YAML 中的三种资源

每个 YAML 文件都包含 3 种 K8s 资源，先理解它们各自的角色：

```
PVC（存储）  →  相当于一块硬盘，数据持久化，Pod 删了数据还在
Deployment（运行）  →  管理容器，保证始终有 N 个 Pod 在运行
Service（网络）  →  给 Pod 分配一个固定的内部 IP 和 DNS 名
```

三者通过名称关联：Deployment 的 volumeMounts 引用 PVC，Service 的 selector 匹配 Deployment 的 labels。

---

## nacos.yaml 逐行详解

### 一、PVC — 持久化存储

```yaml
apiVersion: v1
kind: PersistentVolumeClaim          # 资源类型：持久卷申请（向 K8s 申请一块存储）
metadata:
  name: nacos-data-pvc               # 存储卷名称，Deployment 中通过此名称引用
  namespace: c1-idc-test             # 所属命名空间
  labels:
    app: nacos                       # 标签，方便 kubectl 筛选
spec:
  accessModes:
    - ReadWriteOnce                  # 读写模式：只能被一个节点挂载（单机够用）
                                     # 如果是 ReadWriteMany 则支持多节点同时挂载
  resources:
    requests:
      storage: 5Gi                   # 申请 5GB 磁盘空间
                                     # K3s 使用 local-path，会在节点本地创建目录
```

**通俗理解**：PVC 就像提前预定了一块 5GB 的硬盘给 Nacos 用，Nacos 的配置数据、元数据都存这里，Pod 重启或删除后数据不丢失。

---

### 二、Deployment — 容器运行配置

#### 2.1 外层元信息

```yaml
apiVersion: apps/v1
kind: Deployment                     # 资源类型：Deployment（管理 Pod 的控制器）
metadata:
  name: nacos                        # Deployment 名称，kubectl 操作时用
  namespace: c1-idc-test
  labels:
    app: nacos                       # 给 Deployment 自身打标签
spec:
  replicas: 1                        # 副本数：始终保持 1 个 Pod 运行
                                     # Nacos 单机模式只能跑 1 个，改成 >1 会冲突
  strategy:
    type: Recreate                   # 更新策略：先删旧 Pod 再建新 Pod
                                     # 另一种是 RollingUpdate（滚动更新），但 Nacos 用 PVC
                                     # 如果两个 Pod 同时挂载同一个 PVC 会数据冲突
                                     # 所以用 Recreate 确保同一时刻只有一个 Pod 在写数据
  selector:
    matchLabels:
      app: nacos                     # Deployment 通过此标签管理 Pod
                                     # 意思是：所有 labels 包含 app=nacos 的 Pod 都归我管
```

#### 2.2 Pod 模板

```yaml
  template:                          # 以下是 Pod 的模板定义
    metadata:
      labels:
        app: nacos                   # 给 Pod 打标签，必须和上面的 selector 匹配
                                     # Service 的 selector 也是匹配这个标签
    spec:
      containers:
        - name: nacos                # 容器名称（一个 Pod 可以有多个容器，这里只有一个）
          image: nacos/nacos-server:v2.3.2   # 镜像地址和版本
                                             # v2.3.2 是固定版本，避免自动升级出问题
          imagePullPolicy: IfNotPresent      # 拉取策略：本地没有才拉取
                                             # 其他值：Always（每次都拉取）、Never（只用本地）
```

#### 2.3 端口声明

```yaml
          ports:
            - containerPort: 8848    # Nacos HTTP API 端口
              name: http             # 端口名称，Service 中通过名称引用
              protocol: TCP          # 协议，HTTP/gRPC 都是 TCP
            - containerPort: 9848    # Nacos gRPC 端口（客户端与服务端通信）
              name: grpc
              protocol: TCP
```

**说明**：`containerPort` 只是声明"容器会监听这些端口"，并不做端口映射。外部能不能访问取决于 Service 的配置。

#### 2.4 环境变量（Nacos 运行参数）

```yaml
          env:
            - name: MODE
              value: "standalone"    # 运行模式：单机模式
                                     # 不设置则默认 cluster 模式，需要外部数据库
                                     # standalone 不需要任何外部依赖，开箱即用

            - name: NACOS_AUTH_ENABLE
              value: "true"          # 开启 Nacos 的登录认证
                                     # 不开启的话任何人都能直接操作 Nacos 配置

            - name: NACOS_AUTH_IDENTITY_KEY
              value: "admin"         # 节点间认证的身份标识 Key
            - name: NACOS_AUTH_IDENTITY_VALUE
              value: "admin"         # 节点间认证的身份标识 Value
                                     # 单机模式下这两个值用不到，但 Nacos 要求必须配置
                                     # 否则启动会报错

            - name: NACOS_AUTH_TOKEN
              value: "VGhpc0lz..."   # JWT 签名密钥（Base64 编码）
                                     # 原文必须 ≥32 个字符，编码后用于 Nacos 的 Token 签发
                                     # 修改会导致已签发的 Token 失效，需要重新登录

            - name: TZ
              value: "Asia/Shanghai" # 容器内时区，默认是 UTC
                                     # 不设的话日志时间会比北京时间少 8 小时
```

#### 2.5 资源限制

```yaml
          resources:
            requests:                # 最低保障：K8s 调度时确保有这些资源才分配 Pod
              cpu: "250m"            # 250m = 0.25 核（m 是毫核，1000m = 1 整核）
              memory: "512Mi"        # 512Mi = 512 MB 内存
            limits:                  # 上限：超过这个值会被限制或杀掉
              cpu: "1000m"           # 最多用 1 核 CPU，超过会被限流（变慢但不会死）
              memory: "1Gi"          # 最多用 1GB 内存，超过会 OOM 被杀
```

**通俗理解**：`requests` 是"保底工资"，`limits` 是"天花板"。Nacos 是 Java 应用，启动时会吃掉较多内存，稳定后回落。

#### 2.6 数据卷挂载

```yaml
          volumeMounts:
            - name: nacos-data              # 与下方 volumes 的 name 对应
              mountPath: /home/nacos/data   # 容器内路径：Nacos 的数据目录
                                            # 配置数据、元数据都存在这里
            - name: nacos-logs
              mountPath: /home/nacos/logs   # 日志目录
```

#### 2.7 存活探针（Liveness Probe）

```yaml
          livenessProbe:                    # 存活检查：K8s 定期探测容器是否"活着"
            httpGet:                        # 探测方式：发 HTTP 请求
              path: /nacos/actuator/health  # 请求路径：Nacos 的健康检查接口
              port: 8848                    # 请求端口
            initialDelaySeconds: 30         # 容器启动后等 30s 再开始探测
                                            # Java 应用启动慢，太早探测会误判为失败
            periodSeconds: 15               # 每 15s 探测一次
            timeoutSeconds: 5               # 单次探测超时 5s，超过视为失败
            failureThreshold: 5             # 连续失败 5 次 → 判定容器"死亡"→ 重启容器
```

**作用**：如果 Nacos 进程卡死或健康接口无响应，K8s 会自动重启它。

#### 2.8 就绪探针（Readiness Probe）

```yaml
          readinessProbe:                   # 就绪检查：K8s 定期探测容器是否"准备好接收流量"
            httpGet:
              path: /nacos/actuator/health
              port: 8848
            initialDelaySeconds: 20         # 启动后等 20s 开始探测
            periodSeconds: 10               # 每 10s 探测一次
            timeoutSeconds: 5
            failureThreshold: 3             # 连续失败 3 次 → 从 Service 的 Endpoints 中移除
                                            # 意思是：不再把流量转发给这个 Pod
```

**与存活探针的区别**：
- 存活探针失败 → **重启容器**（认为进程坏了）
- 就绪探针失败 → **不重启，但停止转发流量**（认为还没准备好）

#### 2.9 数据卷定义

```yaml
      volumes:                              # 定义 Pod 可用的数据卷
        - name: nacos-data
          persistentVolumeClaim:
            claimName: nacos-data-pvc       # 引用上面定义的 PVC，挂载为持久化存储
        - name: nacos-logs
          emptyDir: {}                      # emptyDir：临时目录，Pod 删除后自动清空
                                            # 日志不需要持久化，Pod 重建后重新生成即可
```

---

### 三、Service — 网络入口

```yaml
apiVersion: v1
kind: Service                          # 资源类型：Service（给 Pod 提供稳定的网络入口）
metadata:
  name: nacos                          # Service 名称，也是 DNS 名称
  namespace: c1-idc-test
  labels:
    app: nacos
spec:
  type: ClusterIP                      # Service 类型：仅集群内部可访问
                                       # 其他类型：NodePort（外部可通过节点 IP 访问）
                                       # Nacos 只需要内部访问，微服务通过 DNS 找到它
  ports:
    - name: http                       # 端口名称（可随意，便于识别）
      port: 8848                       # Service 对外暴露的端口
      targetPort: 8848                 # 转发到 Pod 的端口（对应 containerPort）
      protocol: TCP
    - name: grpc
      port: 9848                       # gRPC 端口，Nacos 2.x 客户端通信用
      targetPort: 9848
      protocol: TCP
  selector:
    app: nacos                         # 流量转发给哪些 Pod？
                                       # 匹配所有 labels 包含 app=nacos 的 Pod
                                       # 这就是 Service 和 Deployment 的关联方式
```

**通俗理解**：Service 就像一个内部"电话总机"。其他微服务只需要拨打 `nacos.c1-idc-test.svc.cluster.local:8848`，K8s 会自动把请求转发到 Nacos Pod。即使 Pod 重启 IP 变了，Service 的 DNS 和端口永远不变。

---

## redis.yaml 逐行详解

### 一、PVC — 持久化存储

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data-pvc               # Redis 数据存储卷名称
  namespace: c1-idc-test
  labels:
    app: redis
spec:
  accessModes:
    - ReadWriteOnce                  # 单节点读写
  resources:
    requests:
      storage: 2Gi                   # 申请 2GB（Redis 数据量通常不大，2GB 足够）
```

---

### 二、Deployment — 容器运行配置

#### 2.1 外层元信息

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: c1-idc-test
  labels:
    app: redis
spec:
  replicas: 1                        # 单副本
  strategy:
    type: Recreate                   # 同 Nacos，避免多 Pod 同时写 PVC
  selector:
    matchLabels:
      app: redis
```

#### 2.2 容器与镜像

```yaml
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7.0           # Redis 官方镜像 7.0 版本
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 6379    # Redis 默认端口
              name: redis
              protocol: TCP
```

#### 2.3 启动命令与参数

```yaml
          command:
            - redis-server           # 覆盖容器默认的启动命令
          args:                      # 传给 redis-server 的参数
            - "--requirepass"
            - "$(REDIS_PASSWORD)"    # 密码认证，值来自环境变量 REDIS_PASSWORD
                                     # 不设密码的话任何人都能直接操作 Redis
            - "--appendonly"
            - "yes"                  # 开启 AOF 持久化：每次写操作都追加到日志文件
                                     # 默认是 RDB 快照模式（定时保存），AOF 更安全
                                     # 宕机后最多丢失 1 秒的数据
            - "--maxmemory"
            - "512mb"                # 最大内存限制：Redis 最多用 512MB
                                     # 不设的话会一直吃内存直到系统 OOM
            - "--maxmemory-policy"
            - "allkeys-lru"          # 内存满时的淘汰策略：
                                     # allkeys-lru = 淘汰最近最少使用的 Key
                                     # 适合缓存场景，热点数据保留，冷数据自动清除
                                     # 其他策略：noeviction（满了就报错，不推荐）
                                     #          volatile-lru（只淘汰设了过期时间的 Key）
```

#### 2.4 环境变量

```yaml
          env:
            - name: REDIS_PASSWORD
              valueFrom:                    # 从 ConfigMap 中读取密码
                configMapKeyRef:            # 而不是直接写死在 YAML 里
                  name: dib-common-config   # 引用 02-config/configmap.yaml
                  key: REDIS_PASSWORD       # 取其中的 REDIS_PASSWORD 字段
                                            # 好处：改密码只需改 ConfigMap，不用改这里
            - name: TZ
              value: "Asia/Shanghai"        # 时区，同 Nacos
```

#### 2.5 资源限制

```yaml
          resources:
            requests:
              cpu: "100m"             # 保底 0.1 核（Redis 很轻量）
              memory: "256Mi"         # 保底 256MB
            limits:
              cpu: "500m"             # 上限 0.5 核
              memory: "768Mi"         # 上限 768MB（略大于 maxmemory 512MB
                                      # 因为 Redis 进程本身也有内存开销）
```

#### 2.6 数据卷挂载

```yaml
          volumeMounts:
            - name: redis-data
              mountPath: /data        # Redis 默认数据目录
                                      # AOF 文件保存在 /data/appendonly.aof
```

#### 2.7 存活探针

```yaml
          livenessProbe:
            exec:                     # 探测方式：执行命令（不是 HTTP）
              command:
                - sh
                - -c
                - "redis-cli -a $REDIS_PASSWORD ping | grep PONG"
                                      # 执行 redis-cli ping，期望返回 PONG
                                      # 如果 Redis 卡死，命令不会返回 PONG → 判定失败
            initialDelaySeconds: 10   # Redis 启动很快，10s 足够
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3       # 连续失败 3 次 → 重启容器
```

#### 2.8 就绪探针

```yaml
          readinessProbe:
            exec:
              command:
                - sh
                - -c
                - "redis-cli -a $REDIS_PASSWORD ping | grep PONG"
            initialDelaySeconds: 5    # Redis 启动极快，5s 即可
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3       # 连续失败 3 次 → 停止转发流量
```

#### 2.9 数据卷定义

```yaml
      volumes:
        - name: redis-data
          persistentVolumeClaim:
            claimName: redis-data-pvc   # 引用 PVC，持久化 /data 目录
```

---

### 三、Service — 网络入口

```yaml
apiVersion: v1
kind: Service
metadata:
  name: redis                        # Service 名称 = DNS 名称
  namespace: c1-idc-test
  labels:
    app: redis
spec:
  type: ClusterIP                    # 仅集群内部可访问
  ports:
    - name: redis
      port: 6379                     # 对外端口
      targetPort: 6379               # 转发到 Pod 的端口
      protocol: TCP
  selector:
    app: redis                       # 匹配 labels 包含 app=redis 的 Pod
```

---

## DNS 地址汇总

部署完成后，其他 Pod 可以通过以下地址访问：

| 服务 | 集群内部 DNS | 端口 |
|------|-------------|------|
| Nacos HTTP | `nacos.c1-idc-test.svc.cluster.local` | 8848 |
| Nacos gRPC | `nacos.c1-idc-test.svc.cluster.local` | 9848 |
| Redis | `redis.c1-idc-test.svc.cluster.local` | 6379 |

**DNS 规则**：`<Service名称>.<命名空间>.svc.cluster.local`

---

## 访问方式

```bash
# 从外部访问 Nacos（端口转发到本地）
kubectl -n c1-idc-test port-forward svc/nacos 8848:8848
# 然后浏览器打开 http://localhost:8848/nacos
# 默认账号: nacos / nacos

# 从外部调试 Redis（进入容器内部执行命令）
kubectl -n c1-idc-test exec -it deploy/redis -- redis-cli -a dibredis
```

---

## 常见问题

### 一、基础运维问题

#### Q1: PVC 一直 Pending 怎么办？

**Q：** 执行 `kubectl apply` 后，PVC 状态一直是 Pending，怎么处理？

**A：** K3s 默认使用 `local-path` StorageClass，会在节点本地创建目录。检查：
```bash
kubectl get pvc -n c1-idc-test                    # 查看 PVC 状态
kubectl describe pvc nacos-data-pvc -n c1-idc-test  # 查看 Events 中的错误原因
```
常见原因：节点磁盘空间不足。

---

#### Q2: Nacos 启动很慢？

**Q：** Nacos Pod 一直不是 Ready 状态，是不是启动失败了？

**A：** Java 应用首次启动通常需要 30-60s，`initialDelaySeconds: 30` 已预留了等待时间。如果节点性能较低，可以适当增大。

---

#### Q3: Redis 内存满了会怎样？

**Q：** Redis 设置了 `maxmemory 512mb`，内存满了会报错吗？

**A：** 设置了 `maxmemory-policy: allkeys-lru`，内存满时会自动淘汰最近最少使用的 Key，不会报错。适合做缓存，但如果当数据库用（要求数据不丢）需要改用 `noeviction` 并加大 `maxmemory`。

---

### 二、PVC 与存储相关

#### Q4: PVC 申请的 5Gi 是哪台机器的磁盘？

**Q：** PVC 声明了 `storage: 5Gi`，这 5Gi 是哪台机器的硬盘？是一块独立的硬盘吗？

**A：** 不是独立硬盘。K3s 默认使用 `local-path` StorageClass，它的工作方式是：

1. K3s 调度器决定把 Nacos Pod 放到某个节点（比如 `10.0.6.100`）
2. `local-path-provisioner` 在那台节点的本地文件系统上创建一个目录，典型路径：
   ```
   /var/lib/rancher/k3s/storage/<pvc-uuid>/
   ```
3. 这个目录被挂载到容器内的 `/home/nacos/data`
4. **数据就物理存储在那台节点的本地磁盘上**

所以 5Gi 用的是 Nacos Pod 被调度到的那台机器的本地磁盘空间，不是一块独立的网络存储。

---

#### Q5: Recreate 策略下，Pod 重建一定在同一个节点吗？数据会丢吗？

**Q：** `strategy.type: Recreate` 先删旧 Pod 再建新 Pod，新 Pod 肯定在原来的 node 上重建吧？

**A：** 不一定。`Recreate` 只管"顺序"（先删后建），不管"位置"。新 Pod 落在哪个节点完全由 K8s 调度器决定。分两种情况：

**情况一：容器崩溃，节点还活着（最常见）**

Pod 还在原节点，K8s 原地重启容器，重新挂载同一个本地目录，数据完好。这是最常见的场景（OOM、进程卡死、健康检查失败等）。

**情况二：整个节点宕机**

新 Pod 被调度到另一台节点，`local-path` 在新节点上创建一个空目录，原来的数据在那台宕掉的机器上，新 Pod 读不到。

**如何加固？**

- 简单方案：加 `nodeSelector` 把 Pod 固定到特定节点（节点挂了 Nacos 起不来，但数据不丢）
- 彻底方案：换 NFS 或 Longhorn 等网络存储（数据跟节点无关，Pod 在任何节点都能读到）

---

### 三、架构与配置相关

#### Q6: 当前方案就是单 Pod 场景？Nacos 多节点（集群模式）怎么配？

**Q：** 现在的配置是应对某个服务只能由一个 Pod 运行的场景对吧？如果要 Nacos 多节点怎么配？

**A：** 是的。当前 `standalone` + `replicas: 1` + `Recreate` + `ReadWriteOnce` 的组合就是为单 Pod 设计的，体现在：

| 配置项 | 当前值 | 含义 |
|--------|--------|------|
| `MODE` | `standalone` | Nacos 内嵌 Derby 数据库，不依赖外部存储 |
| `replicas` | `1` | 只跑一个 Pod |
| `strategy.type` | `Recreate` | 避免两个 Pod 同时写同一个 PVC |
| `accessModes` | `ReadWriteOnce` | PVC 只能被一台节点挂载 |

**如果要扩展为集群模式，核心变化：**

```
Standalone（当前）:                    Cluster（多节点）:
┌─────────────┐                      ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Nacos Pod    │  ← 内嵌 Derby       │ Nacos-1  │ │ Nacos-2  │ │ Nacos-3  │
│ replicas: 1  │    数据存本地 PVC    └────┬─────┘ └────┬─────┘ └────┬─────┘
└─────────────┘                          └─────────────┼─────────────┘
                                                       │
                                               ┌───────┴───────┐
                                               │ 外部 MySQL    │  ← 共享数据库
                                               └───────────────┘
```

- `MODE` 改为 `cluster`
- `replicas` 改为 3（推荐奇数）
- 必须配置外部 MySQL（Nacos 集群不再用内嵌 Derby，数据存在 MySQL 中）
- 添加 Headless Service（`clusterIP: None`）用于集群成员自动发现
- PVC 仍需要，但只存日志和缓存，不再存核心数据
- 策略可改为 `RollingUpdate`（数据在 MySQL，不存在 PVC 冲突）

---

#### Q7: 为什么 YAML 中三处都写了 `app: nacos`，不是重复声明吗？

**Q：** `selector`、`template.labels`、`Service.selector` 三处都写了 `app: nacos`，为什么？

**A：** 不是重复声明，三处各有不同作用，通过**相同的标签值**把三种资源串联起来：

```
Deployment                        Service
┌──────────────────┐              ┌──────────────────┐
│ ① selector:      │              │ ③ selector:      │
│    app: nacos    │              │    app: nacos    │
│                  │              │                  │
│  "我管 app=nacos │              │  "流量给 app=nacos│
│    的 Pod"       │              │    的 Pod"       │
└────────┬─────────┘              └────────┬─────────┘
         │                                 │
         │         ┌───────────┐           │
         │  匹配    │           │    匹配    │
         ├────────►│  Pod      │◄──────────┤
         │         │ ② labels: │           │
         │         │ app:nacos │           │
         └─────────────────────────────────┘
                   Pod 模板上打的标签
                   决定了 Pod "是谁"
```

- **② 是桥梁** — Pod 模板上打的标签，决定了 Pod "是谁"
- **① 通过相同的标签找到 Pod** — Deployment 说"我管 `app=nacos` 的 Pod"
- **③ 也通过相同的标签找到 Pod** — Service 说"流量转给 `app=nacos` 的 Pod"

三处标签值必须一致，这是 K8s 中 Deployment、Pod、Service 三者建立关联的唯一方式。K8s 没有用"名字引用"，而是用"标签匹配"来建立关系，这就是 K8s 的设计哲学 — 松耦合、基于标签的匹配。

---

#### Q8: 不同 namespace 下相同标签会互相影响吗？

**Q：** 如果有一个生产环境 Nacos 但 namespace 不同，那生产环境的 namespace 也归这个 Deployment 管吗？

**A：** 不会。标签选择器只在同一个 namespace 内有效，不同 namespace 完全隔离。

```
namespace: c1-idc-test                    namespace: c1-idc-prod
┌─────────────────────────┐               ┌─────────────────────────┐
│  Deployment: nacos      │               │  Deployment: nacos      │
│  selector: app: nacos   │               │  selector: app: nacos   │
│         │               │               │         │               │
│         ▼               │               │         ▼               │
│  ┌──────────┐           │               │  ┌──────────┐           │
│  │ Pod      │ ← 归我管  │               │  │ Pod      │ ← 归我管  │
│  └──────────┘           │               │  └──────────┘           │
│                         │               │                         │
└─────────────────────────┘               └─────────────────────────┘
            ╳ ╳ ╳ ╳  互不感知  ╳ ╳ ╳ ╳
```

K8s 中所有资源的标签选择器都以 namespace 为边界：

| 资源 | 作用范围 |
|------|----------|
| Deployment 的 `selector.matchLabels` | 仅本 namespace |
| Service 的 `selector` | 仅本 namespace |
| PVC | 仅本 namespace |
| DNS | `nacos.c1-idc-test.svc.cluster.local` ≠ `nacos.c1-idc-prod.svc.cluster.local` |

---

### 四、镜像与运行时相关

#### Q9: K3s 的镜像和 Docker 的镜像是同一个东西吗？共享吗？

**Q：** `imagePullPolicy: IfNotPresent` 检查的镜像，与 `docker images` 中看到的镜像是共享的吗？

**A：** 镜像格式是同一个东西（OCI 标准），但**存储不共享**。

用下载文件来类比：同一个 `report.pdf`，Chrome 下载存到 `C:\Downloads\`，Firefox 下载存到 `D:\Browser\Downloads\`，文件本身一模一样，只是存放目录不同。

对应到容器：同一个 `nacos/nacos-server:v2.3.2`，Docker 拉取存到 `/var/lib/docker/overlay2/`，K3s (containerd) 拉取存到 `/var/lib/rancher/k3s/agent/containerd/`。

| | Docker | K3s (containerd) |
|---|--------|------------------|
| 运行时 | dockerd | containerd |
| 镜像存储路径 | `/var/lib/docker/` | `/var/lib/rancher/k3s/agent/containerd/` |
| 管理命令 | `docker images` | `k3s crictl images` |

所以 `IfNotPresent` 查的是 containerd 自己的镜像库，不是 Docker 的。Docker 拉过的镜像 K3s 不知道，需要重新拉取或通过 `k3s ctr images import` 导入。两者都可以从同一个私有仓库拉取，因为镜像格式通用。

---

#### Q10: Docker 和 K3s 的运行时一样吗？

**Q：** Docker 与 K3s 拉取镜像的运行时一样吗？

**A：** 底层一样，上层不同：

```
Docker 的架构：                    K3s 的架构：

┌──────────────┐                  ┌──────────────┐
│  docker CLI  │                  │  kubectl     │
└──────┬───────┘                  └──────┬───────┘
       ▼                                 ▼
┌──────────────┐                  ┌──────────────┐
│   dockerd    │  ← Docker 引擎   │  containerd  │  ← 直接用
│  (多了构建、  │    额外功能       │  (没有中间层) │
│   网络、卷等) │                  │              │
└──────┬───────┘                  └──────┬───────┘
       ▼                                 ▼
┌──────────────┐                  ┌──────────────┐
│  containerd  │                  │  containerd  │  ← 同一个东西
└──────┬───────┘                  └──────┬───────┘
       ▼                                 ▼
┌──────────────┐                  ┌──────────────┐
│    runc      │                  │    runc      │  ← 同一个东西
└──────────────┘                  └──────────────┘
```

K3s 去掉了 dockerd 这层"胖中间件"，直接用 containerd 干活，所以更轻量。但底层 runtime（runc）和镜像标准（OCI）完全一致。

通俗类比：Docker 是全功能轿车（能开、能修、能改装），K3s 是赛车（只要最核心的功能，拆掉一切多余的东西），但两者用的是同一个发动机和同一种汽油。

---

### 五、网络与端口相关

#### Q11: port、targetPort、nodePort 三者区别是什么？

**Q：** Service 配置中有 `port`、`targetPort`、`nodePort` 三个端口字段，怎么理解？

**A：** 三者分别对应流量经过的三层：

```
外部访问（浏览器）：

  你的电脑
    │
    │  http://10.0.6.100:30848/nacos
    │                 │
    │                 ▼
    │           ① nodePort: 30848
    │           （节点物理端口，外部入口）
    │                 │
    │                 ▼
    │           ② port: 8848
    │           （Service 虚拟端口，内部寻址）
    │                 │
    │                 ▼
    │           ③ targetPort: 8848
    │           （容器实际监听的端口）
    │                 │
    │                 ▼
    │           Nacos 容器（监听 8848）


集群内部访问（其他微服务）：

  gateway Pod
    │
    │  http://nacos.c1-idc-test.svc.cluster.local:8848
    │                                          │
    │                                          ▼
    │                                    ② port: 8848
    │                                    （跳过 nodePort，直接走 Service）
    │                                          │
    │                                          ▼
    │                                    ③ targetPort: 8848
    │                                          │
    │                                          ▼
    │                                    Nacos 容器
```

| 端口 | 谁用 | 谁能访问 | 必须配吗 |
|------|------|---------|----------|
| `nodePort` | 外部流量入口 | 浏览器、外部系统 | 可选（不写则自动分配 30000-32767） |
| `port` | Service 自身的端口 | 集群内部 Pod | **必须** |
| `targetPort` | Pod 容器实际监听的端口 | 不直接访问，由 Service 转发 | **必须** |

---

#### Q12: 什么是"不做端口转换"？多个 Service 可以配相同的 port 吗？

**Q：** 说 port 和 targetPort 相同就是"不做端口转换"，怎么理解？多个 Service 的 port 可以一样吗？

**A：**

**不做端口转换：** 当 `port` 和 `targetPort` 值相同时（都是 8848），Service 不做端口转换，请求直达容器。调用方看到的端口号跟容器实际监听的一模一样。

**做了端口转换的例子：**
```yaml
port: 80              # Service 对外 80
targetPort: 8848      # 转发到 Pod 的 8848
# 80 ≠ 8848 → 端口变了 → 做了转换
# 好处：调用方不需要知道容器真实端口，统一用 80
```

**`nodePort` 为什么不能也是 8848？** 因为 K8s 强制限制 nodePort 范围为 30000-32767，8848 不在这个范围内。

**多个 Service 可以配相同的 port 吗？** 可以。因为每个 Service 有独立的 DNS 名和 ClusterIP，互不冲突：
```bash
http://c1-p-gateway:80     → c1-p-gateway Pod:20000
http://c1-p-oauth:80       → c1-p-oauth Pod:9090
http://c1-p-mdm:80         → c1-p-mdm Pod:20002
# 三个 Service 都是 port=80，但 DNS 名不同，不会串
```

但 `nodePort` 必须唯一，因为所有 Service 共享同一个节点 IP，端口必须不同才能区分转给谁。

---

### 六、开发调试与运维相关

#### Q13: 开发环境怎么方便地访问 Nacos、Redis、Swagger？

**Q：** 开发环境为了访问微服务的 Swagger 和查看 Redis 内容，是不是 Service type 都应该设置为 NodePort？

**A：** NodePort 可以用，但更推荐 `port-forward`。

**方式一：NodePort**

把 Service type 从 `ClusterIP` 改为 `NodePort`，通过 `节点IP:端口` 访问。NodePort = ClusterIP + 在每台节点上开一个端口做转发，改了之后集群内部的访问不受影响。

**方式二：port-forward（推荐）**

`kubectl port-forward` 在你电脑和集群 Pod 之间建一条隧道，让你用 `localhost` 访问远端服务：

```bash
# 启动隧道
kubectl -n c1-idc-test port-forward svc/nacos 8848:8848
# 终端显示：Forwarding from 127.0.0.1:8848 -> 8848
# 然后浏览器访问 http://localhost:8848/nacos

# Redis 同理
kubectl -n c1-idc-test port-forward svc/redis 6379:6379
# 本地 Redis 客户端连接 localhost:6379
```

```
port-forward 的本质：

你的电脑                              K3s 节点
┌──────────────┐                     ┌──────────────────┐
│  localhost   │                     │   Nacos Pod      │
│  :8848      │                     │   :8848          │
│      │       │    kubectl 建立的    │     ▲            │
│      ▼       │    隧道            │     │            │
│  kubectl     │◄═══════════════════►│  转发流量         │
│  进程        │                     │                  │
└──────────────┘                     └──────────────────┘
```

| | NodePort | port-forward |
|---|---------|-------------|
| 谁开端口 | 节点物理机 | 你的电脑 |
| 谁能访问 | 任何人 | 只有你 |
| 持续时间 | 永久（直到删除 Service） | 临时（关掉终端就断） |
| 安全性 | 低（暴露在网络上） | 高（只有本地能访问） |

**生产环境**除网关用 Ingress 对外暴露外，其他服务全部 ClusterIP，运维通过堡垒机 + port-forward 操作。

---

#### Q14: Windows 开发机怎么连接 K3s 集群？

**Q：** 要在 Windows 本地用 `kubectl port-forward`，是不是要安装一个 kube server？

**A：** 不需要装 Server，只需要装一个客户端工具 `kubectl`，再从 K3s 节点上拿一个配置文件。

**第一步：Windows 上安装 kubectl**

```powershell
# 方法一：直接下载 exe
# 去 https://dl.k8s.io/release/v1.30.4/bin/windows/amd64/kubectl.exe
# 下载后放到一个目录，加入 PATH 环境变量

# 方法二：用 winget 安装
winget install Kubernetes.kubectl
```

**第二步：从 K3s Server 节点拿配置文件**

```bash
# 在 K3s Server 节点上执行
# 把 server 地址改为节点实际 IP（不要用 127.0.0.1）
cat /etc/rancher/k3s/k3s.yaml
```

将输出的 YAML 保存到 Windows 的 `C:\Users\<用户名>\.kube\config`。

**验证连接：**

```powershell
kubectl get nodes
# 应该能看到 K3s 集群的节点列表
```

```
K3s Server 节点 (10.0.6.100)           你的 Windows 电脑
┌──────────────────────┐              ┌──────────────────────┐
│  /etc/rancher/       │   复制文件    │  C:\Users\xxx\      │
│  k3s/k3s.yaml ───────┼─────────────►│    .kube\config      │
│                      │              │                      │
│  K3s Server          │              │  kubectl.exe         │
│  :6443 ◄─────────────┼──────────────┼── kubectl get nodes  │
│  (API Server)        │   HTTPS      │  kubectl port-forward│
└──────────────────────┘              └──────────────────────┘
```

kubectl 就是个"遥控器"，config 就是"配对码"，有了这两样就能从 Windows 上远程操控 K3s 集群。这是 K8s 世界的标准做法。

---

#### Q15: Kuboard 能替代 kubectl 吗？能访问 Nacos 管理页面吗？

**Q：** 部署了 Kuboard 后，是不是就不用每个人装 kubectl 配 config 了？Kuboard 中能访问 Nacos 的管理页面吗？

**A：**

**关于替代 kubectl：** Kuboard 是"K8s 资源管理面板"，它自己已经配好了 kubectl 和 config，替你跟集群通信。团队成员打开浏览器访问 Kuboard 即可，覆盖了 80% 日常操作：

| 操作 | 用 kubectl | 用 Kuboard |
|------|-----------|------------|
| 看 Pod 状态 | `kubectl get pods` | 网页上直接看 |
| 看日志 | `kubectl logs -f xxx` | 网页上点"日志"按钮 |
| 重启服务 | `kubectl rollout restart` | 网页上点"重启"按钮 |
| 扩缩容 | `kubectl scale --replicas=3` | 网页上改数字 |
| **port-forward** | **✓ 必须用 kubectl** | **✗ 做不了** |
| **exec 进容器** | **✓ 必须用 kubectl** | 有网页终端，但不好用 |

**关于访问 Nacos 管理页面：** Kuboard **不能**访问 Nacos 的管理页面。Kuboard 管的是"容器活没活"（Pod 状态、日志、资源），Nacos 管的是"微服务注册和配置"（服务列表、配置项），各管各的：

```
Kuboard（管容器）                    Nacos（管微服务）
┌──────────────────────┐            ┌──────────────────────┐
│  Pod 状态：Running ✓  │            │  服务注册列表          │
│  副本数：1/1         │            │  配置管理              │
│  CPU / 内存 / 日志    │            │  命名空间 / 权限       │
└──────────────────────┘            └──────────────────────┘
```

访问 Nacos 页面仍需通过 port-forward 或 NodePort。高级调试（port-forward、exec 进容器）也仍需 kubectl。

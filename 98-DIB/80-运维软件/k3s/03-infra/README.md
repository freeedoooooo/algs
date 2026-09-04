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

**Q: PVC 一直 Pending 怎么办？**
K3s 默认使用 `local-path` StorageClass，会在节点本地创建目录。检查：
```bash
kubectl get pvc -n c1-idc-test                    # 查看 PVC 状态
kubectl describe pvc nacos-data-pvc -n c1-idc-test  # 查看 Events 中的错误原因
```
常见原因：节点磁盘空间不足。

**Q: Nacos 启动很慢？**
Java 应用首次启动通常需要 30-60s，`initialDelaySeconds: 30` 已预留了等待时间。如果节点性能较低，可以适当增大。

**Q: Redis 内存满了会怎样？**
设置了 `maxmemory-policy: allkeys-lru`，内存满时会自动淘汰最近最少使用的 Key，不会报错。适合做缓存，但如果当数据库用（要求数据不丢）需要改用 `noeviction` 并加大 `maxmemory`。

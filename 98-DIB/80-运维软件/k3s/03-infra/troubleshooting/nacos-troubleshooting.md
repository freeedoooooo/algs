# Nacos 在 K3s 离线环境的部署踩坑记录与解决方案

> 本文记录在**离线内网 K3s 集群**中部署 Nacos v2.3.2（Standalone）全过程遇到的坑，
> 按"现象 → 根因 → 解决 → 验证"的结构整理，供后续部署到其他离线环境时避坑。
> 配套的 `nacos.yaml` 逐行讲解见同目录 `README.md`。

---

## 一、环境背景速览

| 项 | 值 | 说明 |
|------|------|------|
| K3s 版本 | v1.30.4+k3s1（对应 K8s 1.30） | 运行时为 containerd，非 docker |
| 命名空间 | `c1-idc-test` | Nacos / Redis / 微服务都在此 |
| Server 节点 | `dev6183`（10.0.6.183） | 控制面，已打污点，同时跑 Harbor |
| Agent 节点 | `Bank-AI-Credit-5142`（10.0.5.142） | 工作节点，**2 核 CPU / 31G 内存 / iowait 高** |
| 私有镜像仓库 | Harbor `10.0.6.183:8088` | 离线环境所有镜像来源 |
| 外部 MySQL | `10.0.6.161:3306`（root/Dib12345*） | 最终用于替代 Derby |
| Nacos 镜像 | `nacos/nacos-server:v2.3.2` | 自带 MySQL 驱动 |
| Nacos 端口 | 8848(HTTP) / 9848(gRPC) | Service 类型 ClusterIP |
| 存储 | PVC `nacos-data-pvc`（local-path） | 卷落在节点本地 `/var/lib/rancher/k3s/storage/` |

**关键前提**：这是一个**完全离线**的内网环境，节点无法访问 `registry-1.docker.io`、`docker.io` 等公网仓库，所有镜像必须先推到 Harbor `10.0.6.183:8088`。这是后面一系列"镜像拉取失败"坑的总根源。

---

## 二、踩坑总览（快速索引）

| # | 阶段 | 现象 | 根因 | 解决方向 |
|---|------|------|------|---------|
| 1 | 离线镜像 | 所有 Pod 卡 `ContainerCreating`，`failed to get sandbox image i/o timeout` | pause 沙箱镜像拉不到 | 导入 k3s airgap 离线镜像包 |
| 2 | 离线镜像 | 推镜像报 `unauthorized: project rancher not found` | Harbor 项目未预建 | 先在 Harbor 建项目 |
| 3 | 离线镜像 | PVC 一直 `Pending`，provisioner 日志 helper pod 拉镜像失败 | local-path helper pod 用 busybox | 把 busybox 推到 Harbor |
| 4 | 离线镜像 | 节点不从私有仓库拉镜像 | registries.yaml 未配置 | install.sh 自动配置 / 批量下发 |
| 5 | 节点调度 | Nacos 跑到了 Server 节点而非 Agent | 未约束调度 | Server 打污点 + Nacos 加 nodeSelector |
| 6 | 节点调度 | `strict decoding error: unknown field "spec.template.nodeSelector"` | nodeSelector 层级放错 | 移到 `spec.template.spec` 下 |
| 7 | 运维操作 | `systemctl restart k3s` 报 Unit not found | Agent 服务名不同 | Agent 用 `k3s-agent` |
| 8 | Derby | `derby-data exists ... does not contain service.properties` | 首次建库被打断，目录半成品损坏 | 清坏目录 + 加 startupProbe |
| 9 | Derby | 建库期间容器被反复重启 | 缺 startupProbe，被 liveness/readiness 误杀 | 加 startupProbe 冻结前两个探针 |
| 10 | Derby | `java.sql.SQLTimeoutException: Login timeout exceeded` | Agent 节点 iowait 46.9%，Derby 建库超时 | **外挂 MySQL 替代 Derby（终极解法）** |

---

## 三、阶段一：离线镜像链（一连串"拉不到镜像"）

离线环境部署的第一个拦路虎不是 Nacos 本身，而是**镜像拉不下来**。K3s 里一个 Pod 要跑起来，涉及好几种镜像，任何一个拉不到都会卡住。

### 坑 1：pause 沙箱镜像拉取失败 → 所有 Pod 卡 ContainerCreating

**现象**

`	ext
Failed to create pod sandbox: rpc error: code = Unknown desc =
failed to get sandbox image rancher/mirrored-pause:3.6:
failed to resolve image "docker.io/rancher/mirrored-pause:3.6":
no available registry endpoint: ... i/o timeout
`

所有 Pod（包括系统组件）卡在 `ContainerCreating`，起不来。

**根因**

K3s 用 containerd，每个 Pod 启动前要先创建一个"沙箱"（pause 容器）来持有网络命名空间。这个 pause 镜像默认从 docker.io 拉，离线环境拉不到，于是**任何 Pod 都无法创建**。

**解决**

导入与 K3s 版本匹配的官方离线镜像包（airgap images）：

`ash
sudo mkdir -p /var/lib/rancher/k3s/agent/images
sudo cp k3s-airgap-images-amd64.tar.zst /var/lib/rancher/k3s/agent/images/
sudo systemctl restart k3s        # Server 节点；Agent 节点用 k3s-agent（见坑 7）
`

重启后 K3s 自动导入该目录下的镜像。

**验证**

`ash
sudo k3s crictl images | grep pause
# 应看到 rancher/mirrored-pause:3.6
`

> ⚠️ 离线镜像包版本必须与 K3s 版本匹配，否则里面的 pause / coredns / traefik 等版本对不上会引发别的问题。

---

### 坑 2：向 Harbor 推送镜像前必须先创建项目

**现象**

```text
unauthorized: project rancher not found
```

`docker push 10.0.6.183:8088/rancher/xxx` 时被拒。

**根因**

Harbor 要求目标 **project（项目）必须先存在**，不会在 push 时自动创建。仓库路径 `10.0.6.183:8088/rancher/...` 里的 `rancher` 就是一个 project 名。

**解决**

推送前先建项目（Web 控制台或 API 均可）：

```bash
curl.exe -u "admin:你的Harbor密码" -X POST \
  "http://10.0.6.183:8088/api/v2.0/projects" \
  -H "Content-Type: application/json" \
  -d '{"project_name":"rancher","public":true}'
```

建 `public:true` 的公开项目，K3s 节点拉镜像时免认证，省掉 imagePullSecret。

**验证**

```bash
curl http://10.0.6.183:8088/v2/rancher/tags/list
```

---

### 坑 3：local-path helper pod 镜像拉取失败 → PVC 一直 Pending

**现象**

PVC 卡在 `Pending`，`local-path-provisioner` 日志显示创建卷时启动的 helper pod 拉镜像失败。

**根因**

K3s 默认存储类 `local-path` 在**创建/删除卷**时会临时起一个 helper pod 去节点上建目录，这个 helper pod 的镜像（`rancher/mirrored-library-busybox:1.34.1` 或 `busybox`）定义在 ConfigMap `local-path-config` 的 `helperPod.yaml` 里。离线环境同样拉不到 → 卷创建超时 → PVC 永远 Pending。

**解决**

1. 查出 helper pod 用的镜像名：

```bash
kubectl -n kube-system get configmap local-path-config \
  -o jsonpath='{.data.helperPod\.yaml}' | grep image:
```

2. 把该镜像推到 Harbor（以 busybox 为例）：

```bash
docker pull busybox:latest
docker tag busybox:latest 10.0.6.183:8088/library/busybox:latest
docker push 10.0.6.183:8088/library/busybox:latest
```

若是 `rancher/mirrored-library-busybox:1.34.1`，则 tag/push 到 `10.0.6.183:8088/rancher/mirrored-library-busybox:1.34.1`。

3. 让 helperPod.yaml 指向 Harbor 里的镜像（改 ConfigMap 或在 registries.yaml 里配 mirror）。

**验证**

```bash
kubectl get pvc -n c1-idc-test          # PVC 应变为 Bound
kubectl describe pvc nacos-data-pvc -n c1-idc-test
```

> 📌 `local-path` 是 `WaitForFirstConsumer` 绑定模式：PVC 要等到有 Pod 真正使用它、被调度到某节点后，才在该节点本地创建目录并绑定。所以"先建 PVC 显示 Pending、部署 Nacos 后才 Bound"是正常现象，别误判。

---

### 坑 4：节点未配置 registries.yaml，不从私有仓库拉镜像

**现象**

镜像明明推到了 Harbor，节点却还去 docker.io 拉，超时失败。

**根因**

K3s 节点需要通过 `/etc/rancher/k3s/registries.yaml` 知道"docker.io 的镜像要去哪个私有 mirror 拉"。没配就默认走公网。

**解决**

项目已用 `install.sh` 的 `configure_registry` 函数在装节点时自动生成 registries.yaml；存量节点用 `06-scripts/update-registries.sh` 批量下发并按角色重启 k3s / k3s-agent（前提是运行节点配了 SSH 免密）。

**验证**

```bash
cat /etc/rancher/k3s/registries.yaml
sudo k3s crictl images        # 确认镜像从 10.0.6.183:8088 拉取成功
```

---

## 四、阶段二：节点调度（让 Nacos 落在指定节点）

### 坑 5：Nacos 被调度到 Server 节点而非 Agent

**现象**

Nacos Pod 起来在了 Server 节点（dev6183），但希望它跑在 Agent 工作节点上。

**根因**

默认调度器只看资源是否够，不区分"控制面/工作节点"。Server 节点资源够就会被选中。

**解决（两件事配合）**

- **给 Server 打污点（Taint）**——集群级"排斥"，让普通 Pod 默认不调度到 Server：

```bash
kubectl taint nodes dev6183 node-role.kubernetes.io/control-plane:NoSchedule
```

- **给 Nacos 加 nodeSelector**——Pod 级"吸引"，指定只落在带某标签的节点：

```bash
kubectl label nodes Bank-AI-Credit-5142 role=dib-worker
```

**Taint vs nodeSelector 的区别**（容易混）：

| | Taint（污点） | nodeSelector（节点选择器） |
|---|---|---|
| 作用方向 | 排斥：节点拒绝 Pod | 吸引：Pod 指定节点 |
| 作用范围 | 集群级，影响所有 Pod | 单 Pod 级，只影响自己 |
| 配置位置 | 打在 Node 上 | 写在 Pod spec 里 |

> 💡 只有 1 个 Agent 且 Server 已打污点时，nodeSelector 其实是冗余的（Pod 只能去 Agent）。但两者配合更稳妥，污点是保护 Server 的关键，务必保留。

---

### 坑 6：nodeSelector 层级放错 → strict decoding error

**现象**

```text
Error from server (BadRequest): error when creating "nacos.yml":
strict decoding error: unknown field "spec.template.nodeSelector"
```

且此时 PVC 已创建、Service unchanged，但 **Deployment 创建失败**。

**根因**

`nodeSelector` 被错误地放在了 `spec.template` 下（与 `metadata`、`spec` 平级），正确位置必须在 **`spec.template.spec`** 下。K8s 1.25+ 默认开启严格字段校验（strict decoding），未知字段直接报错。

**错误 vs 正确**

```yaml
# ❌ 错误：nodeSelector 在 template 下
  template:
    metadata:
      labels:
        app: nacos
    nodeSelector:          # 层级错了
      role: dib-worker
    spec:
      containers:
        - name: nacos
```

```yaml
# ✅ 正确：nodeSelector 在 template.spec 下
  template:
    metadata:
      labels:
        app: nacos
    spec:
      nodeSelector:        # 移进 spec 内
        role: dib-worker
      containers:
        - name: nacos
          image: nacos/nacos-server:v2.3.2
```

**验证**

```bash
kubectl apply -f nacos.yml --dry-run=server   # 先干跑校验字段
kubectl get pod -n c1-idc-test -o wide        # 确认落在 Bank-AI-Credit-5142
```

> ⚠️ 另一个易踩的点：**文件名差异**。本地工作区是 `nacos.yaml`，服务器上 apply 的是 `nacos.yml`，改动务必同步到实际 apply 的那个文件，否则改了没生效。

---

### 坑 7：Agent 节点重启服务用错服务名

**现象**

在 Agent 节点执行 `systemctl restart k3s` 报 `Unit k3s.service not found`。

**根因**

K3s 的 **Server 节点**服务名是 `k3s`，**Agent 节点**服务名是 `k3s-agent`，两者不同。

**解决**

```bash
sudo systemctl restart k3s-agent      # Agent 节点
sudo systemctl restart k3s            # Server 节点
# 不确定时先查：
systemctl list-units --type=service | grep k3s
```

> ⚠️ 排查期间**不要随意重启 k3s-agent**——正好在 Nacos 首次建库时重启，会把建库过程打断，直接导致坑 8 的目录损坏。

---

## 五、阶段三：Derby 数据库（本次排查的核心大戏）

Nacos Standalone 默认用**内嵌 Derby 数据库**，数据存在 `/home/nacos/data/derby-data`。这一阶段三个坑环环相扣，本质是**同一个根因的因果链**。

### 因果链全景

```text
① Derby 首次建库（写 service.properties 等一堆小文件 + fsync）
        ↓  Agent 节点 iowait 46.9%，建库慢到超过 30 秒
② HikariCP 登录超时 → "Login timeout exceeded"（坑 10）
        ↓  建库被硬生生中断，目录只建了一半
③ 留下损坏目录 → "derby-data exists 但没有 service.properties"（坑 8）
        ↓  期间容器又被探针反复杀（坑 9）
④ CrashLoopBackOff，越清越坏、越坏越清
```

**关键结论：`Login timeout exceeded`（坑 10）才是病根，"目录损坏"（坑 8）只是它留下的后遗症。** 只清目录治标不治本，必须解决建库超时。

---

### 坑 8：Derby 目录半成品损坏

**现象**

```text
The database directory '/home/nacos/data/derby-data' exists.
However, it does not contain the expected 'service.properties' file.
```

Pod 快速失败（约 17 秒），Exit Code 1（非 OOM 的 137），CrashLoopBackOff，Restart Count 不断增长。

**根因**

Derby 首次建库途中被打断（重启 k3s-agent、删 Pod、或被探针杀），`derby-data` 只建了一半——目录在，但缺关键的 `service.properties`。之后每次启动读到这个半成品就报错。

**关键诊断（区分"损坏"与"OOM"）**

```bash
kubectl -n c1-idc-test describe pod <nacos-pod>
# 看 Last State: Terminated / Reason / Exit Code
#   Exit Code 1  → 应用错误（Derby 损坏）
#   Exit Code 137 → OOMKilled（内存不足，另一条路）
# 看 Started / Finished 时间差：17 秒 = 快速失败，不是超时被杀
```

**解决**

清掉损坏目录（数据在 local-path 卷里，需到 Agent 节点物理删除）：

```bash
kubectl -n c1-idc-test scale deployment nacos --replicas=0
# 到 Agent 节点（Bank-AI-Credit-5142）执行：
VOL=$(ls -d /var/lib/rancher/k3s/storage/*nacos-data-pvc* | head -1)
rm -rf $VOL/derby-data
kubectl -n c1-idc-test scale deployment nacos --replicas=1
```

> ⚠️ 但注意：**如果是全新卷（刚建 8 分钟）也损坏**，说明不是"旧数据残留"，而是"每次首次建库都被打断"——这时光删 PVC / 清目录没用，得往下找坑 9、坑 10 的真正原因。

---

### 坑 9：缺 startupProbe，建库期间被探针误杀

**现象**

Derby 还在慢慢建库，容器就被 K8s 重启了，建库永远完不成。

**根因**

原 yaml 只有 `livenessProbe` 和 `readinessProbe`。Java 应用 + Derby 首次建库启动很慢，在健康接口还没就绪时，livenessProbe 连续失败 → K8s 判定容器"死了" → 重启 → 建库被打断（回到坑 8）。

**三种探针的区别**

| 探针 | 失败后果 | 作用 |
|------|---------|------|
| livenessProbe（存活） | **重启容器** | 判断进程是否卡死 |
| readinessProbe（就绪） | 摘流量（不重启） | 判断是否能接请求 |
| startupProbe（启动） | 成功前**冻结上面两个** | 保护慢启动应用 |

**解决**

加 `startupProbe`。它在成功前会**冻结** liveness/readiness，给应用充足的启动窗口，成功后才把接力棒交给后两者：

```yaml
          startupProbe:
            httpGet:
              path: /nacos/actuator/health
              port: 8848
            initialDelaySeconds: 20     # 启动后等 20s 再探
            periodSeconds: 10           # 每 10s 探一次
            timeoutSeconds: 5           # 单次超时 5s
            failureThreshold: 30        # 最多容忍连续失败 30 次
```

**最大启动窗口公式**：`initialDelaySeconds + failureThreshold × periodSeconds`
本例 = `20 + 30 × 10 = 320 秒`，即最多给 Nacos 320 秒完成启动，期间不会被 liveness 杀。

> 📌 `startupProbe` 是 K8s 1.16 引入、1.20 GA 的官方标准特性，专治慢启动应用，是常规方案。`successThreshold` 对 startup/liveness 必须为 1。
>
> ⚠️ startupProbe 只能**防将来**建库被打断，**无法修复已损坏**的目录。所以坑 8 的清目录 + 坑 9 的 startupProbe 要一起做。

---

### 坑 10：Derby Login timeout exceeded（真正病根）

**现象**

清掉损坏目录、加了 startupProbe 后，报错从"目录损坏"变成了：

```text
Caused by: java.sql.SQLTimeoutException: Login timeout exceeded
    at org.apache.derby.jdbc.InternalDriver.timeLogin(...)
    ...
    at com.zaxxer.hikari.pool.HikariPool.checkFailFast(...)
```

这其实是**进展**——说明损坏问题解决了，卡点前移到了"建库超时"。

**根因定位（Agent 节点资源诊断）**

在 Agent 节点 `Bank-AI-Credit-5142` 上诊断：

```bash
uptime                 # load average: 0.46, 0.75, 0.53（负载很低）
nproc                  # 2（只有 2 核，小机器）
top -bn1 | head -20    # %Cpu(s): 3.1 us, 3.1 sy, 46.9 id, 46.9 wa  ← wa 高达 46.9%！
free -h                # Mem available 16G，Swap 仅用 114M（内存健康）
```

判读：

- **内存健康**：available 16G，swap 几乎没用 → 排除内存不足。
- **CPU 没过载**：load 0.46 < 2 核，idle 还有 46.9% → 排除 CPU 忙。
- **磁盘 I/O 是瓶颈**：`wa`（iowait，CPU 空等磁盘的时间）高达 **46.9%**（正常应 <5%）→ **磁盘 I/O 严重拖后腿**。

**结论**：Derby 首次建库是 **I/O 密集型**（大量小文件写 + fsync），在这台 iowait 快 50% 的 2 核小机器上，建库慢到超过 HikariCP 的连接超时（30 秒）→ `Login timeout exceeded` → 建库中断 → 目录损坏 → 死循环。这也解释了为什么**同样的 Nacos 之前在 Server 节点能成功**——Server 盘没这么忙。

**解决：外挂 MySQL 替代内嵌 Derby（终极方案）**

把数据库 I/O 从"慢的 Agent 本地盘"搬到"另一台健康的 MySQL 服务器"，从根本上绕开 iowait 瓶颈。详见第六章。

> 💡 为什么调高 CPU limit 没用：瓶颈是磁盘 iowait 不是 CPU，加 CPU 解决不了慢盘。方向应是"别在慢盘上建库"。

---

## 六、终极方案：外挂 MySQL 替代 Derby

### 6.1 为什么能根治

```text
Derby 内嵌：  Nacos 建库 I/O → Agent 节点慢盘（iowait 46.9%）→ 超时 → 损坏
外挂 MySQL：  Nacos 建库 I/O → 网络 → MySQL 服务器（10.0.6.161）的盘 → Agent 盘零压力
```

顺带好处：数据不再绑死 Agent 本地盘，那块盘挂了配置也不丢；且为将来扩展集群模式打基础。

### 6.2 前置条件

| 条件 | 说明 |
|------|------|
| MySQL 可达 | Agent 节点能连通 `10.0.6.161:3306` |
| 独立数据库 | 必须用专用库 `nacos_config`，**不可**混入产品库 `dib_report_copilot` |
| 导入表结构 | 启动前必须先把 `mysql-schema.sql` 导入 `nacos_config` |
| 驱动 | v2.3.2 官方镜像自带 MySQL connector，离线无需额外装 |

### 6.3 操作步骤

**第 1 步：验证 Agent 节点能连通 MySQL**

```bash
# 在 Agent 节点执行（无需 mysql 客户端）
timeout 3 bash -c 'cat < /dev/null > /dev/tcp/10.0.6.161/3306' \
  && echo "端口通" || echo "端口不通"
```

不通则要放通跨网段防火墙（Agent 是 10.0.5.x，MySQL 是 10.0.6.x）。

**第 2 步：从镜像里取出建表脚本 mysql-schema.sql**

离线环境不用去公网下，脚本就在镜像里 `/home/nacos/conf/mysql-schema.sql`：

```bash
docker images | grep nacos                     # 确认镜像全名
docker create --name tmp-nacos <nacos镜像>
docker cp tmp-nacos:/home/nacos/conf/mysql-schema.sql ./mysql-schema.sql
docker rm tmp-nacos
```

若镜像只在 k3s containerd 里，可起一个 `command:["sleep","3600"]` 的临时 Pod 覆盖入口，再 `kubectl exec ... -- cat /home/nacos/conf/mysql-schema.sql > mysql-schema.sql`。

**第 3 步：建 Nacos 专用库并导入表结构**

```bash
mysql -h10.0.6.161 -P3306 -uroot -p'Dib12345*' \
  -e "CREATE DATABASE IF NOT EXISTS nacos_config DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"

mysql -h10.0.6.161 -P3306 -uroot -p'Dib12345*' nacos_config < mysql-schema.sql

mysql -h10.0.6.161 -P3306 -uroot -p'Dib12345*' nacos_config -e "SHOW TABLES;"
# 应看到 config_info、his_config_info、users、roles、tenant_info 等十几张表
```

**第 4 步：修改 nacos.yaml 的 env（完整配置）**

```yaml
          env:
            # ---------- 运行模式 ----------
            - name: MODE
              value: "standalone"              # 单节点模式（与用不用 MySQL 无关，保持不动）
            # ---------- 外挂 MySQL：替代内嵌 Derby ----------
            - name: SPRING_DATASOURCE_PLATFORM
              value: "mysql"                   # ★总开关：设为 mysql 才走外挂库；不设=内嵌 Derby
            - name: MYSQL_SERVICE_HOST
              value: "10.0.6.161"
            - name: MYSQL_SERVICE_PORT
              value: "3306"
            - name: MYSQL_SERVICE_DB_NAME
              value: "nacos_config"            # ★专用库，切勿用产品库 dib_report_copilot
            - name: MYSQL_SERVICE_USER
              value: "root"
            - name: MYSQL_SERVICE_PASSWORD
              value: "Dib12345*"
            - name: MYSQL_SERVICE_DB_PARAM
              value: "characterEncoding=utf8&connectTimeout=1000&socketTimeout=3000&autoReconnect=true&useUnicode=true&useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true"
                                               # MySQL8 必须带 allowPublicKeyRetrieval=true&useSSL=false
            # ---------- 鉴权 ----------
            - name: NACOS_AUTH_ENABLE
              value: "true"
            - name: NACOS_AUTH_IDENTITY_KEY
              value: "admin"
            - name: NACOS_AUTH_IDENTITY_VALUE
              value: "admin"
            - name: NACOS_AUTH_TOKEN
              value: "VGhpc0lzTXlDdXN0b21TZWNyZXRLZXkwMTIzNDU2Nzg="
            # ---------- 时区 ----------
            - name: TZ
              value: "Asia/Shanghai"
```

**第 5 步：清旧 PVC，重新部署**

```bash
kubectl -n c1-idc-test delete deployment nacos
kubectl -n c1-idc-test delete pvc nacos-data-pvc
grep -A1 SPRING_DATASOURCE_PLATFORM nacos.yml   # 确认改动已同步到实际 apply 的文件
kubectl apply -f nacos.yml
kubectl -n c1-idc-test logs -f deploy/nacos
```

### 6.4 验证成功标志

日志出现关键行——注意是 **external storage**（而非之前的 embedded storage）：

```text
Nacos started successfully in stand alone mode. use external storage
```

```bash
kubectl -n c1-idc-test get pod -o wide          # 1/1 Running，落在 Agent 节点
kubectl -n c1-idc-test port-forward svc/nacos 8848:8848
# 浏览器 http://localhost:8848/nacos
```

### 6.5 配套调整

- **resources 不用调高 CPU**：改用 MySQL 后建库 I/O 不在 Agent 盘，当前 `limits cpu 1000m / memory 1Gi` 够用。
- **startupProbe 保留**：Java 应用启动仍需几十秒，继续防误杀，无害。

---

## 七、经验总结与最佳实践

### 离线环境部署检查清单

- [ ] 导入与 K3s 版本匹配的 airgap 离线镜像包（pause 等系统镜像）
- [ ] Harbor 预建所有需要的 project（rancher / library / nacos 等），设为 public
- [ ] 业务镜像 + local-path helper pod 镜像（busybox）都推到 Harbor
- [ ] 每个节点配好 `/etc/rancher/k3s/registries.yaml`
- [ ] 应用镜像也提前推到 Harbor（nacos-server:v2.3.2）

### 慢节点部署有状态应用的注意事项

- **先看节点体质再部署**：`nproc` + `top` 看 iowait（`wa`）。iowait 高（>20%）的节点不适合跑"首次建库 I/O 密集"的有状态应用（Derby、初始化建表等）。
- **能用外部数据库就别用内嵌**：内嵌 Derby 把 I/O 压力全压在 Pod 所在节点；外挂 MySQL 把压力转移出去，更稳更持久。
- **慢启动应用必配 startupProbe**：给足启动窗口，别让 liveness 在启动期误杀。
- **建库期间别打断**：不要重启 k3s-agent、不要删 Pod、不要反复 apply。

### 排查方法论（本次奏效的思路）

1. **看退出码分清方向**：Exit 1 = 应用错误；Exit 137 = OOM。
2. **看时间差分清快慢失败**：17 秒快速失败 ≠ 超时被杀。
3. **报错变化 = 进展信号**：从"目录损坏"变"Login timeout"，说明卡点前移，别当成"反复横跳"。
4. **抓根因别治标**：清目录是治标，建库超时才是根因；根因在慢盘，最终靠外挂 MySQL 绕开。

---

## 八、附录：关键命令速查

```bash
# --- 镜像 ---
sudo k3s crictl images | grep nacos          # 查 k3s 里的镜像
cat /etc/rancher/k3s/registries.yaml         # 查私有仓库配置

# --- 调度 ---
kubectl get nodes --show-labels              # 查节点标签
kubectl describe node dev6183 | grep Taints  # 查污点
kubectl get pod -n c1-idc-test -o wide       # 查 Pod 落在哪个节点

# --- Nacos 排障 ---
kubectl -n c1-idc-test get pvc               # PVC 状态
kubectl -n c1-idc-test describe pod <pod>    # 事件 / 退出码 / 重启次数
kubectl -n c1-idc-test logs -f deploy/nacos  # 实时日志

# --- 节点资源（Agent 上执行）---
uptime && nproc                              # 负载 vs 核数
top -bn1 | head -20                          # 看 %wa（iowait）
free -h                                      # 内存 / swap

# --- 服务重启 ---
sudo systemctl restart k3s-agent             # Agent 节点
sudo systemctl restart k3s                   # Server 节点
```

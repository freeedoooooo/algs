# DIB 微服务 K3s 部署指南

本目录包含 DIB 微服务体系从 Docker Compose 迁移至 K3s 集群的完整部署配置。

---

## 目录结构

```
k3s/
├── README.md                           # 本文档
├── 01-install/
│   └── install.sh                      # K3s 集群安装脚本 (支持 server + agent 多节点)
├── 02-config/
│   ├── namespace.yaml                  # 命名空间 (c1-idc-test)
│   ├── configmap.yaml                  # 全部配置 (地址 + 密码明文，后续可迁移至 Secret)
│   └── image-pull-secret.yaml          # 私有镜像仓库认证凭据
├── 03-infra/
│   ├── nacos.yaml                      # Nacos 注册中心 (Deployment + Service + PVC)
│   └── redis.yaml                      # Redis 缓存 (Deployment + Service + PVC)
├── 04-platform/
│   └── all-services.yaml               # 4 个平台服务 (auth-server / gateway / auth-resource / mdm)
├── 05-business/
│   └── all-services.yaml               # 5 个业务服务 (extract / report / data / rule / dg)
└── 06-scripts/
    ├── deploy-all.sh                   # 一键部署脚本
    └── verify.sh                       # 健康检查验证脚本
```

> 当前所有配置（含密码）均为明文存放在 `02-config/configmap.yaml` 中，方便调试。生产环境稳定后可迁移至 K8s Secret 进行加密管理。

---

## 架构概览

```
K3s 集群 (namespace: c1-idc-test)
├── 基础设施层
│   ├── Nacos v2.3.2    → ClusterIP :8848  (注册中心)
│   └── Redis 7.0       → ClusterIP :6379  (缓存)
├── 平台服务层
│   ├── auth-server      → NodePort 30090  (SSO 认证，对外暴露)
│   ├── gateway          → NodePort 30000  (API 网关，对外暴露)
│   ├── auth-resource    → ClusterIP :20001 (权限资源，内部访问)
│   └── mdm              → ClusterIP :20002 (主数据，内部访问)
├── 业务服务层
│   ├── service-extract  → ClusterIP :30001 (资料提取)
│   ├── service-report   → ClusterIP :30002 (报告生成)
│   ├── service-data     → ClusterIP :30003 (数据资源)
│   ├── service-rule     → ClusterIP :30004 (规则引擎)
│   └── data-dg          → ClusterIP :30005 (数据治理)
└── 外部依赖 (保持独立部署)
    ├── MySQL/OpenGauss  → 192.168.10.141:5432
    └── MinIO            → 10.0.6.163:9000
```

---

## 前置条件

| 项目 | 要求 |
|------|------|
| 操作系统 | CentOS 7/8、Ubuntu 20.04/22.04、Debian 11/12 |
| CPU | >= 4 核 |
| 内存 | >= 32 GB (extract 服务需要 18G) |
| 磁盘 | >= 100 GB |
| Docker | 已安装 (用于构建镜像) |
| 网络 | 能访问私有仓库 `10.0.6.183:8088` |

---

## 部署步骤

### 第一步：安装 K3s 集群

将整个 `k3s/` 目录上传到所有目标 Linux 服务器（Server 节点 + Agent 节点）：

```bash
# 从本地上传到每台服务器
scp -r k3s/ root@<Server_IP>:/opt/k3s-deploy/
scp -r k3s/ root@<Agent1_IP>:/opt/k3s-deploy/
scp -r k3s/ root@<Agent2_IP>:/opt/k3s-deploy/
```

#### 1.1 安装 Server 节点（控制面，有且仅有一个）

```bash
# 登录 Server 节点
cd /opt/k3s-deploy
bash 01-install/install.sh server
```

安装完成后，脚本会自动：
- 配置私有镜像仓库 `10.0.6.183:8088`
- 安装 K3s Server（使用国内镜像加速）
- 配置 kubectl 访问权限
- 验证节点就绪
- **输出 Agent 加入命令**（包含 Server IP 和 Token，务必保存）

输出示例：
```
  Agent 节点加入命令:
  ─────────────────────────────────────────
  bash 01-install/install.sh agent \
    --server-ip 10.0.6.100 \
    --token K10xxxxxxxxx::server:xxxxxxxxx
  ─────────────────────────────────────────
```

#### 1.2 安装 Agent 节点（工作节点，可多个）

```bash
# 登录每台 Agent 节点
cd /opt/k3s-deploy
bash 01-install/install.sh agent \
  --server-ip <Server节点IP> \
  --token <Server输出的Token>
```

> Token 获取方式（在 Server 节点执行）：`cat /var/lib/rancher/k3s/server/node-token`

#### 1.3 验证集群

回到 Server 节点，确认所有节点就绪：

```bash
kubectl get nodes -o wide
# 应看到所有节点状态为 Ready，ROLE 分别为 control-plane / worker
```

#### 1.4 卸载

```bash
# 在 Server 或 Agent 节点执行均可
bash 01-install/install.sh --uninstall
```

### 第二步：修改配置文件

**部署前必须修改以下文件中的占位值为实际环境参数。**

#### 2.1 修改 `02-config/configmap.yaml`

打开 `02-config/configmap.yaml`，根据实际环境修改以下配置项：

```yaml
# 环境标识 (idc-test-c1 / pro)
C1_ENV: "idc-test-c1"

# 数据库 JDBC URL（完整连接地址，对应 .env 中的 C1_DB_URL）
DB_URL: "jdbc:mysql://10.0.6.161:3306/dib_report_copilot?..."

# Nacos 地址
# 如果使用 K3s 内部 Nacos（本方案默认），保持不动
# 如果使用外部 Nacos，改为外部地址：
# NACOS_SERVER_ADDR: "http://10.0.5.70:8848"

# MinIO 地址
MINIO_ENDPOINT: "http://10.0.6.163:9000"  # ← 改为实际 MinIO 地址

# OCR 服务地址
OCR_SERVER: "http://192.168.10.91:8089/"  # ← 改为实际 OCR 地址
```

#### 2.2 修改 `02-config/configmap.yaml` 中的密码

`02-config/configmap.yaml` 底部包含所有密码（明文），根据实际环境修改：

```yaml
# 数据库凭据
DB_USERNAME: "gaussdb"         # ← 改为实际用户名
DB_PASSWORD: "Dib@123456"      # ← 改为实际密码

# Redis 密码
REDIS_PASSWORD: "dibredis"     # ← 改为实际密码

# Nacos 认证
NACOS_PASSWORD: "c1@2025"      # ← 改为实际密码

# OAuth 客户端凭据
OAUTH_CLIENT_CREDENTIALS: "123456"
```

#### 2.3 生成 `02-config/image-pull-secret.yaml`

使用 kubectl 命令自动生成正确的镜像仓库认证（替换实际的用户名密码）：

```bash
kubectl create secret docker-registry dib-registry-secret \
  --namespace=c1-idc-test \
  --docker-server=10.0.6.183:8088 \
  --docker-username=<仓库用户名> \
  --docker-password=<仓库密码> \
  --docker-email=<邮箱> \
  --dry-run=client -o yaml > 02-config/image-pull-secret.yaml
```

> 如果镜像仓库无需认证（匿名拉取），可以跳过此步骤，并删除所有 Deployment YAML 中的 `imagePullSecrets` 段落。

### 第三步：一键部署

```bash
# 全量部署（推荐首次使用）
bash 06-scripts/deploy-all.sh

# 也可以分步部署：
bash 06-scripts/deploy-all.sh base       # 仅部署基础配置
bash 06-scripts/deploy-all.sh infra      # 仅部署 Nacos + Redis
bash 06-scripts/deploy-all.sh platform   # 仅部署平台服务
bash 06-scripts/deploy-all.sh business   # 仅部署业务服务
```

部署顺序（自动执行）：
1. **基础配置** → 命名空间、ConfigMap、镜像认证
2. **基础设施** → Nacos、Redis（等待就绪后继续）
3. **平台服务** → auth-server → gateway → auth-resource → mdm
4. **业务服务** → extract → report → data → rule → dg

指定镜像版本：

```bash
C1_VERSION=v1.0.0 bash 06-scripts/deploy-all.sh
```

### 第四步：验证部署

```bash
# 完整验证（Pod 状态 + Ready + Service）
bash 06-scripts/verify.sh

# 快速检查（仅 Pod 状态）
bash 06-scripts/verify.sh quick
```

手动验证：

```bash
# 查看所有 Pod 状态
kubectl -n c1-idc-test get pods -o wide

# 查看某个 Pod 的详细事件（排查启动失败）
kubectl -n c1-idc-test describe pod <pod-name>

# 查看容器日志
kubectl -n c1-idc-test logs -f <pod-name>

# 查看所有 Service
kubectl -n c1-idc-test get svc
```

---

## 访问地址

部署完成后，通过以下地址访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| API 网关 | `http://<节点IP>:30000` | 所有业务 API 入口 |
| SSO 认证 | `http://<节点IP>:30090` | 单点登录服务 |
| Nacos 控制台 | `http://<节点IP>:8848/nacos` | 需额外配置 NodePort |
| Kuboard | `http://<Kuboard_IP>:8000` | K8s 可视化管理 |

> 注意：Nacos 默认是 ClusterIP，如需从外部访问需将其 Service 类型改为 NodePort。

---

## 常用运维命令

### 查看状态

```bash
# Pod 状态
kubectl -n c1-idc-test get pods -o wide

# 资源使用
kubectl -n c1-idc-test top pods

# Service 列表
kubectl -n c1-idc-test get svc -o wide

# 查看 Pod 日志
kubectl -n c1-idc-test logs -f deployment/auth-server
kubectl -n c1-idc-test logs -f deployment/gateway --tail=100
```

### 重启服务

```bash
# 重启单个服务
kubectl -n c1-idc-test rollout restart deployment/auth-server

# 重启所有业务服务
kubectl -n c1-idc-test rollout restart deployment/service-extract deployment/service-report deployment/service-data deployment/service-rule deployment/data-dg
```

### 更新配置

修改 ConfigMap 后需要重启 Pod 才能生效：

```bash
# 修改配置
kubectl -n c1-idc-test edit configmap dib-common-config

# 重启所有 Pod 使配置生效
kubectl -n c1-idc-test rollout restart deployment
```

### 扩缩容

```bash
# 将 gateway 扩展到 2 副本
kubectl -n c1-idc-test scale deployment/gateway --replicas=2

# 缩回 1 副本
kubectl -n c1-idc-test scale deployment/gateway --replicas=1
```

### 更新镜像版本

```bash
# 更新单个服务镜像
kubectl -n c1-idc-test set image deployment/auth-server auth-server=10.0.6.183:8088/c1/platform-auth-server:v2.0.0

# 查看 rollout 状态
kubectl -n c1-idc-test rollout status deployment/auth-server

# 回滚到上一版本
kubectl -n c1-idc-test rollout undo deployment/auth-server
```

### 删除资源

```bash
# 删除所有 DIB 资源（有确认提示）
bash 06-scripts/deploy-all.sh delete

# 或手动删除
kubectl delete namespace dib
```

---

## 故障排查

### Pod 一直处于 Pending

```bash
kubectl -n c1-idc-test describe pod <pod-name>
```

常见原因：
- 镜像拉取失败 → 检查 `imagePullSecrets` 和仓库连通性
- 资源不足 → 检查节点内存是否满足 extract (18Gi) 等高内存服务需求

### Pod 反复重启 (CrashLoopBackOff)

```bash
# 查看容器日志
kubectl -n c1-idc-test logs <pod-name> --previous

# 查看事件
kubectl -n c1-idc-test describe pod <pod-name>
```

常见原因：
- 数据库连接失败 → 检查 `02-config/configmap.yaml` 中的 DB_URL
- Nacos 注册失败 → 检查 Nacos 是否已启动、NACOS_SERVER_ADDR 是否正确
- 密码错误 → 检查 `02-config/configmap.yaml` 中的密码字段

### Service 无法访问

```bash
# 检查 Endpoint 是否存在
kubectl -n c1-idc-test get endpoints

# 测试集群内 DNS 解析
kubectl -n c1-idc-test run test-dns --image=busybox --rm -it -- nslookup gateway.c1-idc-test.svc.cluster.local
```

---

## 服务资源参考

| 服务 | JVM 堆内存 | K8s requests | K8s limits | 端口 |
|------|-----------|-------------|-----------|------|
| auth-server | 512m ~ 2g | 512Mi / 250m | 2Gi / 1000m | 9090 |
| gateway | 512m ~ 2g | 512Mi / 250m | 2Gi / 1000m | 20000 |
| auth-resource | 512m ~ 2g | 512Mi / 250m | 2Gi / 1000m | 20001 |
| mdm | 512m ~ 2g | 512Mi / 250m | 2Gi / 1000m | 20002 |
| service-extract | 12g ~ 16g | 12Gi / 500m | 18Gi / 2000m | 30001 |
| service-report | 1g ~ 2g | 1Gi / 250m | 3Gi / 1000m | 30002 |
| service-data | 4g | 4Gi / 500m | 6Gi / 1500m | 30003 |
| service-rule | 1g ~ 2g | 1Gi / 250m | 3Gi / 1000m | 30004 |
| data-dg | 512m ~ 1g | 512Mi / 250m | 1.5Gi / 1000m | 30005 |

> 所有服务总内存需求约 **40Gi**，建议 K3s 节点配置 64GB 以上内存。

---

## 与 Kuboard 集成

K3s 安装完成后，脚本会输出 Kuboard 连接指引。核心步骤：

1. 登录 Kuboard → 点击「导入集群」
2. API Server 地址填写：`https://<K3s节点IP>:6443`
3. 获取 Token：
   ```bash
   # 创建 Kuboard 专用 ServiceAccount
   kubectl create sa kuboard-sa -n kube-system
   kubectl create clusterrolebinding kuboard-sa --clusterrole=cluster-admin --serviceaccount=kube-system:kuboard-sa
   
   # 获取 Token
   kubectl -n kube-system create secret generic kuboard-sa-token --from-literal=token=$(kubectl -n kube-system get secret $(kubectl -n kube-system get sa kuboard-sa -o jsonpath='{.secrets[0].name}') -o jsonpath='{.data.token}') -o jsonpath='{.data.token}' | base64 -d
   ```
4. 将 Token 粘贴到 Kuboard 完成导入

导入后可在 Kuboard 中直观地查看 `c1-idc-test` 命名空间下所有工作负载的状态、日志和资源使用情况。

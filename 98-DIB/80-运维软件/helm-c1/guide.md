# DIB 微服务 K3s 部署指南

本目录包含 DIB 微服务体系在 K3s 集群上的完整部署配置，使用 Helm Chart 统一管理。

---

## 目录结构

```
k3s/
├── README.md                           # 本文档
├── 01-install/
│   └── install.sh                      # K3s 集群安装脚本 (支持 server + agent 多节点)
├── 07-helm/                            # 产品 Helm Chart（微服务部署）
│   ├── Chart.yaml                      # Chart 元信息
│   ├── values.yaml                     # 默认配置（所有参数完整定义）
│   ├── values-dev.yaml                 # 开发环境覆盖
│   ├── values-test.yaml                # 测试环境覆盖
│   ├── values-prod.yaml                # 生产环境覆盖
│   ├── nginx.conf                      # Nginx 配置文件
│   └── templates/                      # YAML 模板
│       ├── 01-base/configmap.yaml      # 公共环境变量 ConfigMap
│       ├── 02-infra/                   # 基础设施：Nacos、Redis、Nginx
│       ├── 03-platform/                # 平台服务：Gateway、OAuth、RBAC、MDM
│       └── 04-business/                # 业务服务：Extract、Report、Data、Rule、Govern
└── 08-logging/                         # 日志系统 Helm Chart（独立部署）
    ├── Chart.yaml                      # Chart 元信息
    ├── values.yaml                     # 日志系统配置
    └── templates/                      # YAML 模板
        ├── loki.yaml                   # Loki 日志存储
        ├── promtail.yaml               # Promtail 日志采集
        └── grafana.yaml                # Grafana 可视化
```

---

## 架构概览

```
K3s 集群
├── namespace: c1-ns-test（产品微服务）
│   ├── 基础设施层
│   │   ├── Nginx 1.17.8     → NodePort 30091  (前端网关)
│   │   ├── Nacos v2.3.2     → NodePort 30848  (注册中心，外挂 MySQL)
│   │   └── Redis 7.0        → NodePort 30379  (缓存，maxmemory 2G)
│   ├── 平台服务层
│   │   ├── c1-p-oauth       → NodePort 30090  (OAuth2 认证中心)
│   │   ├── c1-p-gateway     → NodePort 30020  (API 网关)
│   │   ├── c1-p-rbac        → NodePort 30021  (权限资源管理)
│   │   └── c1-p-mdm         → NodePort 30022  (主数据管理)
│   └── 业务服务层
│       ├── c1-b-extract     → NodePort 30031  (资料提取，高内存)
│       ├── c1-b-report      → NodePort 30032  (报告生成)
│       ├── c1-b-data        → NodePort 30033  (数据资源，高内存)
│       ├── c1-b-rule        → NodePort 30034  (规则引擎)
│       └── c1-b-govern      → NodePort 30035  (数据治理)
└── 外部依赖
    ├── MySQL            → 10.0.6.161:3306
    ├── MinIO            → 10.0.6.163:9000
    └── OCR              → 192.168.10.91:8089
```

---

## 前置条件

| 项目 | 要求 |
|------|------|
| 操作系统 | CentOS 7/8、Ubuntu 20.04/22.04、Debian 11/12 |
| CPU | >= 8 核 |
| 内存 | >= 32 GB |
| 磁盘 | >= 100 GB |
| Helm | >= v3.x |
| 网络 | 能访问私有仓库 `10.0.6.183:8088` |

---

## 部署步骤

### 第一步：安装 K3s 集群

将整个 `k3s/` 目录上传到所有目标 Linux 服务器：

```bash
scp -r k3s/ root@<Server_IP>:/opt/k3s-deploy/
```

#### 1.1 安装 Server 节点

```bash
cd /opt/k3s-deploy
bash 01-install/install.sh server
```

安装完成后保存输出的 Agent 加入命令。

#### 1.2 安装 Agent 节点

```bash
bash 01-install/install.sh agent \
  --server-ip <Server节点IP> \
  --token <Token>
```

#### 1.3 验证集群

```bash
kubectl get nodes -o wide
```

### 第二步：配置 Helm values

编辑 `07-helm/values.yaml`，根据实际环境修改以下关键配置：

```yaml
# 命名空间
namespace: c1-ns-test

# 镜像仓库
imageRegistry: "10.0.6.183:8088"
image:
  tag: idc-test-c1_latest

# 节点调度（所有 Pod 调度到该节点）
nodeName: worker-5.142

# 数据库
config:
  C1_DB_URL: "jdbc:mysql://10.0.6.161:3306/dib_report_copilot?..."
  C1_DB_USERNAME: "root"
  C1_DB_PASSWORD: "Dib12345*"

# Nacos 外挂 MySQL
nacos:
  mysql:
    host: "10.0.6.161"
    database: "nacos_dev"

# MinIO / OCR 等外部服务地址
config:
  C1_MINIO_ENDPOINT: "http://10.0.6.163:9000"
  C1_OCR_SERVER: "http://192.168.10.91:8089/"
```

### 第三步：打包并推送 Chart

在 Windows 开发机上执行：

```powershell
# 打包
helm package 07-helm

# 推送到 Harbor（HTTP 仓库需加 --plain-http）
helm push c1-1.0.0.tgz oci://10.0.6.183:8088/helm --plain-http
```

### 第四步：安装部署

在 K3s Server 节点执行：

```bash
# 首次安装（自动创建 namespace）
helm install c1 oci://10.0.6.183:8088/helm/c1 \
  --version 1.0.0 \
  -n c1-ns-test \
  --plain-http \
  --create-namespace

# 后续更新（修改 values.yaml 后重新打包推送）
helm upgrade c1 oci://10.0.6.183:8088/helm/c1 \
  --version 1.0.1 \
  -n c1-ns-test \
  --plain-http
```

### 第五步：验证部署

```bash
# 查看所有 Pod
kubectl -n c1-ns-test get pods -o wide

# 查看 Service
kubectl -n c1-ns-test get svc

# 查看某个 Pod 详情（排查启动问题）
kubectl -n c1-ns-test describe pod <pod-name>

# 查看日志
kubectl -n c1-ns-test logs -f <pod-name>
```

> 日志系统（Loki + Promtail + Grafana）独立部署，详见 [08-logging/README.md](./08-logging/README.md)

---

## 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| Nginx 前端 | `http://<节点IP>:30091` | 前端页面 + SSO 代理 |
| API 网关 | `http://<节点IP>:30020` | 所有业务 API 入口 |
| SSO 认证 | `http://<节点IP>:30090` | OAuth2 认证服务 |
| Nacos 控制台 | `http://<节点IP>:30848/nacos` | 注册中心管理 |
| Redis | `<节点IP>:30379` | 缓存服务 |
| Kuboard | `http://<Kuboard_IP>:8000` | K8s 可视化管理 |

---

## 常用运维命令

### 查看状态

```bash
# Pod 状态
kubectl -n c1-ns-test get pods -o wide

# 资源使用
kubectl -n c1-ns-test top pods

# Service 列表
kubectl -n c1-ns-test get svc -o wide
```

### 升级 / 回滚

```bash
# 升级到新版本
helm upgrade c1 oci://10.0.6.183:8088/helm/c1 --version 1.0.1 -n c1-ns-test --plain-http

# 查看 release 历史
helm history c1 -n c1-ns-test

# 回滚到上一版本
helm rollback c1 -n c1-ns-test

# 回滚到指定版本
helm rollback c1 <revision> -n c1-ns-test
```

### 重启服务

```bash
# 重启单个服务
kubectl -n c1-ns-test rollout restart deployment/c1-p-oauth

# 重启所有业务服务
kubectl -n c1-ns-test rollout restart deploy/c1-b-extract deploy/c1-b-report deploy/c1-b-data deploy/c1-b-rule deploy/c1-b-govern
```

### 更新镜像版本

修改 `values.yaml` 中的 `image.tag`，重新打包推送后执行 `helm upgrade`。

### 卸载

```bash
# 卸载 release（保留 namespace）
helm uninstall c1 -n c1-ns-test

# 删除整个 namespace（清除所有资源）
kubectl delete namespace c1-ns-test
```

---

## 服务资源配额

### 基础设施层

| 服务 | CPU req | CPU lim | Mem req | Mem lim | 端口 |
|------|---------|---------|---------|---------|------|
| c1-nginx | 100m | 1000m | 128Mi | 256Mi | 30091 |
| c1-nacos | 100m | 1000m | 1Gi | 2Gi | 30848 |
| c1-redis | 100m | 1000m | 1Gi | 3Gi | 30379 |

### 平台服务层

| 服务 | CPU req | CPU lim | Mem req | Mem lim | 端口 |
|------|---------|---------|---------|---------|------|
| c1-p-oauth | 100m | 500m | 512Mi | 1Gi | 30090 |
| c1-p-gateway | 100m | 500m | 512Mi | 1Gi | 30020 |
| c1-p-rbac | 100m | 500m | 512Mi | 1Gi | 30021 |
| c1-p-mdm | 100m | 500m | 512Mi | 1Gi | 30022 |

### 业务服务层

| 服务 | CPU req | CPU lim | Mem req | Mem lim | 端口 |
|------|---------|---------|---------|---------|------|
| c1-b-extract | 250m | 2000m | 3Gi | 6Gi | 30031 |
| c1-b-report | 250m | 2000m | 1536Mi | 3Gi | 30032 |
| c1-b-data | 250m | 2000m | 2Gi | 4Gi | 30033 |
| c1-b-rule | 250m | 2000m | 1Gi | 2Gi | 30034 |
| c1-b-govern | 250m | 2000m | 512Mi | 1Gi | 30035 |

### 资源汇总

| 指标 | 值 |
|------|------|
| CPU requests 总计 | ~1950m（约 2 核） |
| CPU limits 总计 | ~13.7 核 |
| 内存 requests 总计 | ~12Gi |
| 内存 limits 总计 | ~24Gi |

> 日志系统资源配额详见 [08-logging/README.md](./08-logging/README.md#配置说明)

> CPU limits 可以超过物理核数，K8s 调度只看 requests。limits 是突发上限，服务不会一直跑满。

---

## 健康探针配置

所有 Java 服务统一 startupProbe 配置：

```yaml
startupProbe:
  initialDelaySeconds: 60    # 容器启动后 60 秒开始探测
  periodSeconds: 10          # 每 10 秒探测一次
  failureThreshold: 10       # 最多允许 10 次失败
  # 最大等待时间 = 60 + 10×10 = 160 秒
```

livenessProbe 和 readinessProbe 不设 `initialDelaySeconds`，等 startupProbe 成功后自动开始。

---

## 故障排查

### Pod 一直处于 Pending

```bash
kubectl -n c1-ns-test describe pod <pod-name>
```

常见原因：
- 镜像拉取失败 → 检查 imagePullSecrets 和仓库连通性
- PVC 不存在 → 重新 `helm install` 会自动创建
- CPU requests 超过 limits → 检查 values.yaml 资源配置

### Pod 反复重启 (CrashLoopBackOff)

```bash
# 查看容器日志
kubectl -n c1-ns-test logs <pod-name> --previous

# 查看事件
kubectl -n c1-ns-test describe pod <pod-name>
```

常见原因：
- Nacos 启动慢被杀 → 检查 startupProbe 配置和 CPU limits
- 数据库连接失败 → 检查 ConfigMap 中的 DB_URL
- OOM → 检查 JVM 内存参数和容器 limits

### Namespace 删除卡住 (Terminating)

```bash
# 强制清除 finalizers
kubectl proxy &
curl -X PUT http://localhost:8001/api/v1/namespaces/c1-ns-test/finalize \
  -H "Content-Type: application/json" \
  --data '{"kind":"Namespace","apiVersion":"v1","metadata":{"name":"c1-ns-test"},"spec":{"finalizers":[]}}'
```

---

## 与 Kuboard 集成

1. 登录 Kuboard → 点击「导入集群」
2. API Server 地址填写：`https://<K3s节点IP>:6443`
3. 获取 Token：
   ```bash
   kubectl create sa kuboard-sa -n kube-system
   kubectl create clusterrolebinding kuboard-sa --clusterrole=cluster-admin --serviceaccount=kube-system:kuboard-sa
   kubectl -n kube-system create secret generic kuboard-sa-token \
     --from-literal=token=$(kubectl -n kube-system get secret \
     $(kubectl -n kube-system get sa kuboard-sa -o jsonpath='{.secrets[0].name}') \
     -o jsonpath='{.data.token}') -o jsonpath='{.data.token}' | base64 -d
   ```
4. 将 Token 粘贴到 Kuboard 完成导入

导入后可在 `c1-ns-test` 命名空间下直观查看所有工作负载状态、日志和资源使用情况。

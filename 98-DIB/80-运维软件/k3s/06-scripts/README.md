# 06-scripts — 运维脚本

自动化部署和健康检查脚本，在 **Server 节点**（10.0.6.183）上执行。

## 文件清单

| 文件 | 作用 |
|------|------|
| `deploy-all.sh` | 一键部署所有服务，支持按层级部署 |
| `verify.sh` | 健康检查验证脚本 |

---

## deploy-all.sh

### 用法

```bash
# 在 k3s 部署包根目录下执行

# 全量部署（推荐首次使用）
# 按顺序执行: base → infra → platform → business
bash 06-scripts/deploy-all.sh

# 仅部署某一层
bash 06-scripts/deploy-all.sh base       # 基础配置（Namespace + ConfigMap + Secret）
bash 06-scripts/deploy-all.sh infra      # 基础设施（Nacos + Redis）
bash 06-scripts/deploy-all.sh platform   # 平台服务（auth-server / gateway / auth-resource / mdm）
bash 06-scripts/deploy-all.sh business   # 业务服务（extract / report / data / rule / dg）

# 删除所有资源（需确认）
bash 06-scripts/deploy-all.sh delete

# 指定镜像版本（默认 latest）
C1_VERSION=idc-test-c1_latest bash 06-scripts/deploy-all.sh
```

### 执行流程

```
all 模式:
  deploy_base()       → kubectl apply namespace / configmap / image-pull-secret
       ↓
  deploy_infra()      → kubectl apply nacos / redis
       ↓                 等待 nacos 就绪 (120s)
       ↓                 等待 redis 就绪 (60s)
  deploy_platform()   → kubectl apply all-services.yaml (platform)
       ↓                 等待 4 个服务逐一就绪 (各 180s)
  deploy_business()   → kubectl apply all-services.yaml (business)
       ↓                 等待 5 个服务逐一就绪 (extract 300s, 其余 180s)
  print_summary()     → 输出访问地址和常用命令
```

### 各函数说明

| 函数 | 应用的文件 | 等待超时 |
|------|-----------|---------|
| `deploy_base` | `02-config/namespace.yaml`<br>`02-config/configmap.yaml`<br>`02-config/image-pull-secret.yaml` | 无等待 |
| `deploy_infra` | `03-infra/nacos.yaml`<br>`03-infra/redis.yaml` | nacos 120s<br>redis 60s |
| `deploy_platform` | `04-platform/all-services.yaml` | 每个服务 180s |
| `deploy_business` | `05-business/all-services.yaml` | extract 300s<br>其余 180s |
| `delete_all` | 按 business → platform → infra → base 逆序删除 | — |

### 输出示例

部署完成后会输出汇总信息：

```
============================================
  DIB 微服务部署完成
============================================

  命名空间: c1-idc-test
  镜像版本: latest

  外部访问地址:
    Gateway:       http://<NODE_IP>:30000
    Auth Server:   http://<NODE_IP>:30090

  内部服务地址 (K3s DNS):
    Nacos:         http://nacos.c1-idc-test.svc.cluster.local:8848
    Redis:         redis.c1-idc-test.svc.cluster.local:6379
    ...
```

---

## verify.sh

### 用法

```bash
# 完整验证（Pod 状态 + Ready 状态 + Service 检查）
bash 06-scripts/verify.sh

# 快速检查（仅 Pod 状态）
bash 06-scripts/verify.sh quick
```

### 检查项目

| 检查类型 | 说明 | 模式 |
|---------|------|------|
| Pod 状态 | 检查每个 Pod 是否为 `Running` | quick + full |
| Ready 状态 | 检查 Pod 的 Ready 条件是否为 `True` | full only |
| Service | 检查每个 Service 是否已分配 ClusterIP | full only |

### 检查的服务列表

```
基础设施:  nacos, redis
平台服务:  auth-server, gateway, auth-resource, mdm
业务服务:  service-extract, service-report, service-data, service-rule, data-dg
```

### 输出示例

```
============================================
  DIB 微服务健康检查
  命名空间: c1-idc-test
  模式: full
============================================

[STEP] 检查 Pod 状态...

  [OK]   nacos: Pod Running
  [OK]   redis: Pod Running
  [OK]   auth-server: Pod Running
  ...
  [FAIL] service-extract: Pod 状态异常 (Pending)

============================================
  检查结果: 10 通过, 1 失败
============================================
```

如果有失败项，脚本会提示排查命令：
```bash
kubectl -n c1-idc-test describe pod <pod-name>   # 查看详细事件
kubectl -n c1-idc-test logs <pod-name>           # 查看容器日志
```

---

## 典型使用场景

### 场景 1：首次全量部署

```bash
# 1. 确认集群正常
kubectl get nodes

# 2. 修改配置
vi 02-config/configmap.yaml

# 3. 全量部署
bash 06-scripts/deploy-all.sh

# 4. 验证
bash 06-scripts/verify.sh
```

### 场景 2：更新配置后重启

```bash
# 1. 修改配置
vi 02-config/configmap.yaml

# 2. 应用配置
kubectl apply -f 02-config/configmap.yaml

# 3. 重启所有 Pod 使新配置生效
kubectl -n c1-idc-test rollout restart deployment

# 4. 等待重启完成
kubectl -n c1-idc-test rollout status deployment/nacos --timeout=120s
kubectl -n c1-idc-test rollout status deployment/redis --timeout=60s
# ... 其余服务类似
```

### 场景 3：只更新某个业务服务

```bash
# 只重新部署业务服务（不影响 infra 和 platform）
bash 06-scripts/deploy-all.sh business
```

### 场景 4：清理重建

```bash
# 1. 删除所有资源
bash 06-scripts/deploy-all.sh delete

# 2. 重新部署
bash 06-scripts/deploy-all.sh
```

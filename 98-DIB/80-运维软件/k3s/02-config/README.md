# 02-config — 基础配置

部署前**必须**先应用本目录的配置，后续所有服务都依赖这些资源。

## 文件清单

| 文件 | 资源类型 | 作用 |
|------|---------|------|
| `namespace.yaml` | Namespace | 创建 `c1-idc-test` 命名空间，隔离所有 DIB 资源 |
| `configmap.yaml` | ConfigMap | 集中存放所有微服务的配置（数据库、Redis、Nacos 等） |
| `image-pull-secret.yaml` | Secret | 私有镜像仓库的认证凭据 |

## 部署命令

```bash
# 单独应用
kubectl apply -f 02-config/namespace.yaml
kubectl apply -f 02-config/configmap.yaml
kubectl apply -f 02-config/image-pull-secret.yaml

# 或通过部署脚本自动执行
bash 06-scripts/deploy-all.sh base
```

---

## 各文件详解

### namespace.yaml

创建一个名为 `c1-idc-test` 的 Kubernetes 命名空间，所有后续资源都部署在这个命名空间下。

**原理**：Namespace 是 K8s 的多租户隔离机制，不同 Namespace 下的资源名称可以重复，互不干扰。删除 Namespace 会级联删除其下所有资源。

### configmap.yaml

存放所有微服务共享的环境变量，各 Pod 通过 `envFrom` 一次性注入全部配置。

**需要修改的配置项**（根据实际环境）：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `C1_ENV` | 环境标识，对应 Spring Profile | `idc-test-c1` / `pro` |
| `DB_URL` | 完整 JDBC 连接 URL | `jdbc:mysql://IP:3306/db?...` |
| `DB_DRIVER` | 数据库驱动类 | `com.mysql.cj.jdbc.Driver` |
| `DB_USERNAME` | 数据库用户名 | `root` |
| `DB_PASSWORD` | 数据库密码 | — |
| `REDIS_HOST` | Redis 地址 | K8s 内部: `redis.c1-idc-test.svc.cluster.local` |
| `REDIS_PASSWORD` | Redis 密码 | — |
| `NACOS_SERVER_ADDR` | Nacos 地址 | K8s 内部: `http://nacos.c1-idc-test.svc.cluster.local:8848` |
| `NACOS_NAMESPACE` | Nacos 命名空间 | `dev-c1` / `pro-c1` |
| `MINIO_ENDPOINT` | MinIO 对象存储地址 | `http://10.0.6.163:9000` |
| `OCR_SERVER` | OCR 识别服务地址 | `http://192.168.10.91:8089/` |
| `GATEWAY_OAUTH_*` | OAuth 认证服务地址 | — |

**配置注入原理**：

```
configmap.yaml                    Pod 容器内环境变量
┌─────────────────┐    envFrom    ┌────────────────────┐
│ C1_ENV: "xxx"   │ ──────────→  │ C1_ENV=xxx         │
│ DB_URL: "jdbc…" │ ──────────→  │ DB_URL=jdbc…       │
│ REDIS_HOST: ... │ ──────────→  │ REDIS_HOST=...     │
└─────────────────┘              └────────────────────┘
```

Spring Boot 启动时读取 `C1_ENV` 决定加载哪个 `application-{profile}.yml`，其余变量通过 `${DB_URL}` 等方式引用。

**修改后生效方式**：
- ConfigMap 本身会热更新（`kubectl apply` 后立即生效）
- 但 Pod 内的环境变量**不会自动刷新**，需要重启 Pod：
  ```bash
  kubectl -n c1-idc-test rollout restart deployment
  ```

### image-pull-secret.yaml

存放私有镜像仓库 `10.0.6.183:8088` 的认证凭据，类型为 `kubernetes.io/dockerconfigjson`。

**生成方式**（推荐用 kubectl 命令）：

```bash
kubectl create secret docker-registry dib-registry-secret \
  --namespace=c1-idc-test \
  --docker-server=10.0.6.183:8088 \
  --docker-username=<用户名> \
  --docker-password=<密码> \
  --docker-email=<邮箱> \
  --dry-run=client -o yaml > image-pull-secret.yaml
```

**如果仓库无需认证**（如公开仓库或已配置 `--insecure-registry`）：
1. 删除本文件
2. 从各 Deployment 的 `spec.template.spec.imagePullSecrets` 中移除引用

**引用位置**（每个 Deployment 中）：
```yaml
spec:
  template:
    spec:
      imagePullSecrets:
        - name: dib-registry-secret   # ← 引用本 Secret
```

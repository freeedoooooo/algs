# DIB 监控系统 — helm-prometheus 部署文档

> 裸装 Prometheus（无 Operator、无 CRD），轻量适合小团队。
> 与 `helm-loki`（日志系统）共用同一个 Grafana 实例，实现日志 + 指标统一看板。

## 架构

```
helm-prometheus（裸装，~300 行 YAML）
├── Prometheus Server (StatefulSet, 1 副本)
│   ├── 自动发现 Pod annotation → actuator/prometheus
│   └── PVC 10Gi, 保留 7 天
├── Node Exporter (DaemonSet, 可选)
│   └── 每节点 CPU / 内存 / 磁盘 / 网络指标
└── Grafana: 复用 helm-loki 的 c1-grafana
```

镜像仅 **2 个**：`prometheus:v2.55.0` + `node-exporter:v1.8.2`

## 部署步骤

### 1. 推送镜像

在有网机器上拉取源镜像，打标签后推送到私有仓库：

| 源镜像 | 推送到私有仓库 |
|--------|---------------|
| `quay.io/prometheus/prometheus:v2.55.0` | `10.0.6.183:8088/prometheus/prometheus:v2.55.0` |
| `quay.io/prometheus/node-exporter:v1.8.2` | `10.0.6.183:8088/prometheus/node-exporter:v1.8.2` |

```bash
# prometheus
docker pull quay.io/prometheus/prometheus:v2.55.0
docker tag quay.io/prometheus/prometheus:v2.55.0 10.0.6.183:8088/prometheus/prometheus:v2.55.0
docker push 10.0.6.183:8088/prometheus/prometheus:v2.55.0

# node-exporter
docker pull quay.io/prometheus/node-exporter:v1.8.2
docker tag quay.io/prometheus/node-exporter:v1.8.2 10.0.6.183:8088/prometheus/node-exporter:v1.8.2
docker push 10.0.6.183:8088/prometheus/node-exporter:v1.8.2
```

### 2. 安装

```bash
cd helm-prometheus
helm install c1-prometheus . -n c1-ns-log
```

### 3. 更新 helm-loki 的 Grafana 数据源

helm-loki 的 `values.yaml` 已配置 Prometheus 数据源（`http://c1-prometheus:9090`）。
首次部署时需要 upgrade helm-loki 使数据源生效：

```bash
cd ../helm-loki
helm upgrade c1-loki-stack . -n c1-ns-log
```

### 4. 验证

```bash
# 检查 Pod 状态
kubectl -n c1-ns-log get pods -l app=c1-prometheus
kubectl -n c1-ns-log get pods -l app=c1-node-exporter

# 预期：
# c1-prometheus-0           1/1  Running  0  1m
# c1-node-exporter-xxx      1/1  Running  0  1m

# 检查采集目标（Web UI）
kubectl -n c1-ns-log port-forward svc/c1-prometheus 9090:9090
# 浏览器打开 http://localhost:9090/targets
```

## Spring Boot 微服务自动发现

与 kube-prometheus-stack 方案完全相同——通过 Pod annotation 自动发现。

### 微服务需要的注解

```yaml
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"                    # 可选，默认 8080
        prometheus.io/path: "/actuator/prometheus"     # 可选，默认此路径
```

### Spring Boot 需要的依赖

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,prometheus
```

### 采集的 namespace

在 `values.yaml` 的 `scrapeNamespaces` 列表中配置，当前：
- `c1-ns-test`（业务 namespace）
- `c1-ns-log`（日志/监控系统）

新增 namespace 时，编辑 `values.yaml` 后 `helm upgrade` 即可。

## 常用 Grafana Dashboard

在 Grafana 中切换到 **Prometheus** 数据源即可查询指标。

推荐导入 Dashboard ID：

| Dashboard | ID | 用途 |
|-----------|------|------|
| Node Exporter Full | 1860 | 节点级 CPU / 内存 / 磁盘 / 网络 |
| JVM Micrometer | 4701 | Spring Boot JVM 指标 |
| Spring Boot Statistics | 12900 | Spring Boot 应用指标 |

导入方式：Grafana -> Dashboards -> Import -> 输入 Dashboard ID -> Load

## 配置速查表

| 配置项 | 值 | 说明 |
|--------|------|------|
| `image.repository` | `prometheus/prometheus` | Prometheus Server 镜像 |
| `image.tag` | `v2.55.0` | 锁定版本 |
| `retention` | `7d` | TSDB 保留时间 |
| `storage` | `10Gi` | PVC 大小 |
| `nodeSelector` | `node-name: master-6.183` | 调度到指定节点 |
| `tolerations` | master / control-plane | 容忍 master 污点 |
| `nodeExporter.enabled` | `true` | 是否部署 node-exporter |
| `scrapeNamespaces` | c1-ns-test, c1-ns-log | 自动发现的 namespace |

## 注意事项

1. **无 CRD**：不需要 ServiceMonitor / PodMonitor，采集规则全部在 ConfigMap 的 `prometheus.yml` 中管理。

2. **升级简单**：改 values.yaml → `helm upgrade`，ConfigMap 变更会自动滚动重启（checksum 注解）。

3. **Grafana 数据源**：URL 为 `http://c1-prometheus:9090`（同 namespace 短名），已在 helm-loki 的 values.yaml 中配置。

4. **Prometheus Web UI**：`port-forward` 到 9090 可查看采集目标状态（`/targets`）、配置（`/config`）、规则（`/rules`）。

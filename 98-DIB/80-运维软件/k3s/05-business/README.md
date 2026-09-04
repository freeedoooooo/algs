# 05-business — 业务服务

DIB 的 5 个核心业务微服务，处理资料提取、报告生成、数据资源、规则引擎、数据治理。

## 文件清单

| 文件 | 包含服务 |
|------|---------|
| `all-services.yaml` | 5 个 Deployment + 5 个 Service |

## 服务概览

| 服务 | 容器端口 | 内存范围 | 特点 | 说明 |
|------|---------|---------|------|------|
| service-extract | 30001 | 12Gi ~ 18Gi | **高内存** | 资料提取，JVM 配置 12g-16g |
| service-report | 30002 | 1Gi ~ 3Gi | 普通 | 报告生成 |
| service-data | 30003 | 4Gi ~ 6Gi | **高内存** | 数据资源，JVM 配置 4g |
| service-rule | 30004 | 1Gi ~ 3Gi | 普通 | 规则引擎 |
| data-dg | 30005 | 512Mi ~ 1.5Gi | 轻量 | 数据治理 |

所有服务均为 **ClusterIP** 类型，仅集群内部可访问，外部请求通过 gateway 转发。

## 部署命令

```bash
# 单独部署业务服务（需先部署 02-config、03-infra、04-platform）
kubectl apply -f 05-business/all-services.yaml

# 或通过部署脚本
bash 06-scripts/deploy-all.sh business
```

---

## 各服务详解

### 1. service-extract（资料提取）

- **镜像**：`10.0.6.183:8088/c1/c1-extract:latest`
- **端口**：30001
- **健康检查**：`GET /api/extract/actuator/health`（启动延迟 90s）
- **资源**：requests 12Gi / limits 18Gi 内存
- **额外挂载**：
  - `/tmp` → emptyDir（5Gi 限制），用于临时文件处理
  - 额外注入 `OCR_SERVER` 环境变量（OCR 服务地址）
- **作用**：从各类文档中提取结构化数据，需要大量内存处理图片和 PDF

### 2. service-report（报告生成）

- **镜像**：`10.0.6.183:8088/c1/c1-report:latest`
- **端口**：30002
- **健康检查**：`GET /api/report/actuator/health`
- **资源**：requests 1Gi / limits 3Gi 内存
- **额外挂载**：`/opt/app/tmp` → emptyDir
- **作用**：根据提取的数据生成分析报告

### 3. service-data（数据资源）

- **镜像**：`10.0.6.183:8088/c1/c1-data:latest`
- **端口**：30003
- **健康检查**：`GET /api/data/actuator/health`
- **资源**：requests 4Gi / limits 6Gi 内存
- **作用**：数据资源管理，包括维度数据、指标数据的查询和计算

### 4. service-rule（规则引擎）

- **镜像**：`10.0.6.183:8088/c1/c1-rule:latest`
- **端口**：30004
- **健康检查**：`GET /api/rule/actuator/health`
- **资源**：requests 1Gi / limits 3Gi 内存
- **作用**：业务规则计算、校验规则执行

### 5. data-dg（数据治理）

- **镜像**：`10.0.6.183:8088/c1/c1-dg:latest`
- **端口**：30005
- **健康检查**：`GET /api/dg/actuator/health`
- **资源**：requests 512Mi / limits 1.5Gi 内存（最轻量）
- **作用**：数据治理、数据质量检查

---

## 资源分配说明

```
节点总内存
├── service-extract   ████████████████  12Gi (请求) ~ 18Gi (限制)
├── service-data      █████             4Gi (请求) ~ 6Gi (限制)
├── service-report    ██                1Gi (请求) ~ 3Gi (限制)
├── service-rule      ██                1Gi (请求) ~ 3Gi (限制)
├── data-dg           █                 512Mi (请求) ~ 1.5Gi (限制)
└── 其他 (infra + platform + OS)        约 4Gi
```

**最低节点内存建议**：Worker 节点至少 24Gi 可用内存（所有业务服务同时运行时）。

如果节点内存不足，可以：
1. 将高内存服务（extract、data）调度到内存更大的节点
2. 降低 limits 值（但可能导致 OOMKilled）
3. 减少同时运行的业务服务数量

## 服务间调用关系

```
gateway (:20000)
    ↓ 路由转发
    ├── service-extract (:30001)  ←→  OCR 外部服务
    ├── service-report  (:30002)
    ├── service-data    (:30003)
    ├── service-rule    (:30004)
    └── data-dg         (:30005)
    
所有服务 → Nacos (注册/发现)
所有服务 → Redis (缓存)
所有服务 → MySQL (持久化)
service-extract/report → MinIO (文件存储)
```

## 常见问题

**Q: service-extract 频繁 OOMKilled？**
该服务 JVM 配置 12g-16g，需要至少 18Gi 的 limits。检查节点可用内存：
```bash
kubectl describe node bank-ai-credit-5142 | grep -A5 "Allocated resources"
```

**Q: 服务启动很慢，健康检查一直失败？**
Java 微服务首次启动需要加载大量类，`initialDelaySeconds` 已设为 60-90s。如果节点性能低，可以增大该值或检查 Pod 事件：
```bash
kubectl -n c1-idc-test describe pod -l app=service-extract
```

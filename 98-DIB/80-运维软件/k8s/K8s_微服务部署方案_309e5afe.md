# K8s 微服务完整部署实施方案

## 一、服务清单与资源规划

共 9 个后端微服务 + 1 个 Nginx 前端入口 + Nacos（K8s 内部署）：

| 服务 | Spring Name | 端口 | Context Path | Docker JAR | JVM 内存 |
|------|------------|------|-------------|-----------|---------|
| eureka-server | eureka-server | 7102 | / | data-cloud-eureka-server.jar | 512m-2g |
| auth-server | auth-server | 9090 | /sso | platform-auth-server.jar | 512m-2g |
| auth-resource | auth-resource | 20001 | /api/auth | platform-auth-resource.jar | 512m-1g |
| mdm | mdm | 20002 | /api/mdm | platform-mdm.jar | 512m-2g |
| gateway | gateway | 20000 | / | platform-gateway.jar | 512m-2g |
| service-data-dg | service-data-dg | 30005 | / | c1-dg.jar | 512m-1g |
| service-extract | service-extract | 30001 | /api/extract | c1-extract.jar | 12g-16g |
| service-report | service-report | 30002 | /api/report | c1-report.jar | 1g-2g |
| service-data | service-data | 30003 | /api/data | c1-data.jar | 4g-4g |
| service-rule | service-rule | 30004 | /api/rule | c1-rule.jar | 1g-2g |

**外部依赖**：MySQL/OpenGauss、Redis、Nacos、MinIO

## 二、K8s 目录结构

```
k8s/
  namespace.yaml                          # 命名空间
  base/
    configmap-app.yaml                    # 通用配置（Nacos/Redis/DB 地址等）
    secret-db.yaml                        # 数据库凭据
    secret-redis.yaml                     # Redis 凭据
    secret-nacos.yaml                     # Nacos 凭据
  nacos/
    statefulset.yaml                      # Nacos 有状态部署
    service.yaml
  services/
    eureka-server/
      deployment.yaml
      service.yaml
    auth-server/
      deployment.yaml
      service.yaml
    auth-resource/
      deployment.yaml
      service.yaml
    mdm/
      deployment.yaml
      service.yaml
    gateway/
      deployment.yaml
      service.yaml
    service-data-dg/
      deployment.yaml
      service.yaml
    service-extract/
      deployment.yaml
      service.yaml
    service-report/
      deployment.yaml
      service.yaml
    service-data/
      deployment.yaml
      service.yaml
    service-rule/
      deployment.yaml
      service.yaml
  frontend/
    nginx-configmap.yaml                  # Nginx 配置
    deployment.yaml                       # Nginx 前端
    service.yaml
  ingress/
    ingress.yaml                          # 入口规则
  hpa/
    service-data-hpa.yaml                 # 弹性伸缩（按需）
    service-extract-hpa.yaml
```

## 三、各层详细实施内容

### 3.1 Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: dib-c1
  labels:
    app.kubernetes.io/part-of: dib-c1
```

### 3.2 ConfigMap -- 通用环境变量

所有服务共享的基础配置通过 ConfigMap 注入，各服务再通过 Deployment env 补充差异项：

```yaml
# k8s/base/configmap-app.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: dib-c1-config
  namespace: dib-c1
data:
  # Nacos
  NACOS_SERVER_ADDR: "nacos-headless.dib-c1.svc.cluster.local:8848"
  NACOS_NAMESPACE: "dev-c1"
  NACOS_USERNAME: "c1"
  # Redis
  REDIS_HOST: "redis-host"          # 按实际修改
  REDIS_PORT: "6379"
  REDIS_DATABASE: "0"
  # MySQL
  MYSQL_HOST: "mysql-host"          # 按实际修改
  MYSQL_PORT: "3306"
  MYSQL_DATABASE: "dib_report_copilot"
  # MinIO
  MINIO_ENDPOINT: "http://minio-host:9000"
  MINIO_ACCESS_KEY: "minioadmin"
  MINIO_BUCKET: "c1-bucket"
  # 通用
  JAVA_TOOL_OPTIONS: "-Dfile.encoding=UTF-8"
  TZ: "Asia/Shanghai"
```

### 3.3 Secrets -- 敏感信息

```yaml
# k8s/base/secret-db.yaml
apiVersion: v1
kind: Secret
metadata:
  name: dib-c1-db-secret
  namespace: dib-c1
type: Opaque
stringData:
  MYSQL_USERNAME: "root"
  MYSQL_PASSWORD: "xxx"             # 按实际填写
  OPENGAUSS_USERNAME: "gaussdb"     # auth-server 用
  OPENGAUSS_PASSWORD: "xxx"         # 按实际填写

# k8s/base/secret-redis.yaml
apiVersion: v1
kind: Secret
metadata:
  name: dib-c1-redis-secret
  namespace: dib-c1
type: Opaque
stringData:
  REDIS_PASSWORD: "xxx"             # 按实际填写

# k8s/base/secret-nacos.yaml
apiVersion: v1
kind: Secret
metadata:
  name: dib-c1-nacos-secret
  namespace: dib-c1
type: Opaque
stringData:
  NACOS_PASSWORD: "xxx"             # 按实际填写
```

### 3.4 Nacos 部署（K8s 内）

Nacos 使用 StatefulSet 部署，确保服务发现在集群内可用：

```yaml
# k8s/nacos/statefulset.yaml -- 简化版，生产建议用 MySQL 后端存储
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: nacos
  namespace: dib-c1
spec:
  serviceName: nacos-headless
  replicas: 1
  selector:
    matchLabels:
      app: nacos
  template:
    metadata:
      labels:
        app: nacos
    spec:
      containers:
        - name: nacos
          image: nacos/nacos-server:v2.3.0
          ports:
            - containerPort: 8848
              name: client
            - containerPort: 9848
              name: grpc
          env:
            - name: MODE
              value: "standalone"
            - name: NACOS_AUTH_ENABLE
              value: "true"
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2"
              memory: "2Gi"
---
# k8s/nacos/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: nacos-headless
  namespace: dib-c1
spec:
  clusterIP: None
  ports:
    - port: 8848
      name: client
    - port: 9848
      name: grpc
  selector:
    app: nacos
```

### 3.5 各微服务 Deployment + Service 模板

以 **service-data** 为典型示例（其他服务结构相同，仅参数不同）：

```yaml
# k8s/services/service-data/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: service-data
  namespace: dib-c1
  labels:
    app: service-data
    tier: backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: service-data
  template:
    metadata:
      labels:
        app: service-data
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "30003"
        prometheus.io/path: "/actuator/prometheus"
    spec:
      containers:
        - name: service-data
          image: hub.dibtime.com/dib-c1/c1-data:latest    # 按实际镜像仓库调整
          imagePullPolicy: Always
          ports:
            - containerPort: 30003
              name: http
          env:
            - name: C1_ENV
              value: "k8s"                               # 对应 application-k8s.yml
            # --- 从 ConfigMap 注入 ---
            - name: SPRING_CLOUD_NACOS_DISCOVERY_SERVER_ADDR
              valueFrom:
                configMapKeyRef:
                  name: dib-c1-config
                  key: NACOS_SERVER_ADDR
            - name: SPRING_CLOUD_NACOS_DISCOVERY_NAMESPACE
              valueFrom:
                configMapKeyRef:
                  name: dib-c1-config
                  key: NACOS_NAMESPACE
            - name: SPRING_DATA_REDIS_HOST
              valueFrom:
                configMapKeyRef:
                  name: dib-c1-config
                  key: REDIS_HOST
            - name: SPRING_DATA_REDIS_PORT
              valueFrom:
                configMapKeyRef:
                  name: dib-c1-config
                  key: REDIS_PORT
            - name: SPRING_DATA_REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: dib-c1-redis-secret
                  key: REDIS_PASSWORD
            # --- 数据库（service-data 本身无 datasource，如有则添加） ---
          resources:
            requests:
              cpu: "1"
              memory: "4Gi"
            limits:
              cpu: "2"
              memory: "5Gi"
          # 健康检查
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 30003
            initialDelaySeconds: 60
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 30003
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          # 日志持久化（可选）
          volumeMounts:
            - name: app-logs
              mountPath: /opt/app/logs
      volumes:
        - name: app-logs
          emptyDir: {}
      imagePullSecrets:
        - name: harbor-registry-secret
```

```yaml
# k8s/services/service-data/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: service-data
  namespace: dib-c1
  labels:
    app: service-data
spec:
  type: ClusterIP
  ports:
    - port: 30003
      targetPort: 30003
      protocol: TCP
      name: http
  selector:
    app: service-data
```

### 3.6 各服务参数差异汇总

| 服务 | image | 端口 | JVM args (在 Dockerfile ENTRYPOINT 中) | requests/limits | 需要 DB | 需要 Nacos |
|------|-------|------|---------------------------------------|----------------|---------|-----------|
| eureka-server | data-cloud-eureka-server.jar | 7102 | -Xms512m -Xmx2g | 512Mi/2Gi | 否 | 否 |
| auth-server | platform-auth-server.jar | 9090 | -Xms512m -Xmx2g | 512Mi/2Gi | OpenGauss | 是 |
| auth-resource | platform-auth-resource.jar | 20001 | -Xms512m -Xmx1g | 512Mi/1Gi | MySQL | 是 |
| mdm | platform-mdm.jar | 20002 | -Xms512m -Xmx2g | 512Mi/2Gi | MySQL | 是 |
| gateway | platform-gateway.jar | 20000 | -Xms512m -Xmx2g | 512Mi/2Gi | 否 | 是 |
| service-data-dg | c1-dg.jar | 30005 | -Xms512m -Xmx1g | 512Mi/1Gi | MySQL | 是 |
| service-extract | c1-extract.jar | 30001 | -Xms12g -Xmx16g | 12Gi/16Gi | MySQL | 是 |
| service-report | c1-report.jar | 30002 | -Xms1g -Xmx2g | 1Gi/2Gi | 否 | 否 |
| service-data | c1-data.jar | 30003 | -Xms4g -Xmx4g | 4Gi/5Gi | 否 | 是 |
| service-rule | c1-rule.jar | 30004 | -Xms1g -Xmx2g | 1Gi/2Gi | MySQL | 否 |

### 3.7 Gateway 路由适配 K8s

Gateway 当前 dev 环境使用 `spring.cloud.discovery.client.simple` 静态实例列表。在 K8s 环境中，有两种方式：

**方案 A（推荐）**：Gateway 也注册到 Nacos，路由使用 `lb://service-name`，由 Nacos 做负载均衡。需新增 `application-k8s.yml`：

```yaml
# data-cloud-gateway application-k8s.yml 关键配置
spring:
  cloud:
    nacos:
      discovery:
        enabled: true
        server-addr: ${NACOS_SERVER_ADDR}
        namespace: ${NACOS_NAMESPACE}
```

**方案 B**：使用 K8s Service DNS 直接路由，不依赖 Nacos 发现：

```yaml
spring:
  cloud:
    gateway:
      server:
        webflux:
          routes:
            - id: service-data
              uri: http://service-data.dib-c1.svc.cluster.local:30003
              predicates:
                - Path=/api/data/**
```

### 3.8 Nginx 前端 + Ingress

```yaml
# k8s/frontend/nginx-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
  namespace: dib-c1
data:
  nginx.conf: |
    # 复用现有 c1-app/nginx.conf 内容，但需修改：
    # 1. proxy_pass http://platform-gateway:20000 
    #    -> proxy_pass http://gateway.dib-c1.svc.cluster.local:20000
    # 2. proxy_pass http://platform-auth-server:9090/sso/
    #    -> proxy_pass http://auth-server.dib-c1.svc.cluster.local:9090/sso/
    # 其余路由规则不变
---
# k8s/frontend/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-frontend
  namespace: dib-c1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx-frontend
  template:
    metadata:
      labels:
        app: nginx-frontend
    spec:
      containers:
        - name: nginx
          image: hub.dibtime.com/dib-c1/c1-frontend:latest
          ports:
            - containerPort: 80
            - containerPort: 8090
          volumeMounts:
            - name: nginx-config
              mountPath: /etc/nginx/nginx.conf
              subPath: nginx.conf
            # 前端静态文件需通过 Dockerfile  COPY 到镜像中
          resources:
            requests:
              cpu: "200m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
      volumes:
        - name: nginx-config
          configMap:
            name: nginx-config
---
# k8s/frontend/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-frontend
  namespace: dib-c1
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 80
      name: http
    - port: 8090
      targetPort: 8090
      name: app
  selector:
    app: nginx-frontend
```

### 3.9 Ingress 入口

```yaml
# k8s/ingress/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: dib-c1-ingress
  namespace: dib-c1
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "200m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
spec:
  ingressClassName: nginx        # 根据实际 Ingress Controller 调整
  rules:
    - host: c1.your-domain.com   # 按实际域名修改
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: nginx-frontend
                port:
                  number: 8090
```

### 3.10 弹性伸缩（HPA，可选）

```yaml
# k8s/hpa/service-data-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: service-data-hpa
  namespace: dib-c1
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: service-data
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## 四、需要新增的 application-k8s.yml 配置文件

每个 web 服务需新增一个 `application-k8s.yml`，将硬编码的 IP 地址替换为环境变量或 K8s DNS。主要改动：

1. **Nacos 地址**：`http://10.0.5.70:8848` -> `${NACOS_SERVER_ADDR:nacos-headless.dib-c1.svc.cluster.local:8848}`
2. **Redis 地址**：`10.0.6.163` -> `${REDIS_HOST}` / `${REDIS_PORT}`
3. **MySQL 地址**：`10.0.6.161:3306` -> `${MYSQL_HOST}:${MYSQL_PORT}`
4. **MinIO 地址**：`10.0.6.163:9000` -> 从环境变量读取
5. **Gateway 路由**：启用 Nacos 发现，移除 `simple.instances` 静态配置

需新增配置文件的模块：
- `data-cloud-auth-server/src/main/resources/application-k8s.yml`
- `data-cloud-auth-resource/data-cloud-auth-resource-web/src/main/resources/application-k8s.yml`
- `data-cloud-mdm/data-cloud-mdm-web/src/main/resources/application-k8s.yml`
- `data-cloud-gateway/src/main/resources/application-k8s.yml`
- `dib-agent-data-dg/dib-agent-data-dg-web/src/main/resources/application-k8s.yml`
- `dib-agent-service-extract/dib-agent-service-extract-web/src/main/resources/application-k8s.yml`
- `dib-agent-service-report/dib-agent-service-report-web/src/main/resources/application-k8s.yml`
- `dib-agent-service-data/dib-agent-service-data-web/src/main/resources/application-k8s.yml`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/resources/application-k8s.yml`

## 五、Dockerfile 调整

现有 Dockerfile 基本可复用，仅需微调：

1. **eureka-server**：基础镜像从 `openjdk:8-jdk` 升级到 `openjdk17`（与其余服务统一，因为 parent 已使用 Java 17）
2. **统一环境变量**：所有 Dockerfile 已使用 `C1_ENV` 环境变量，K8s 中设置 `C1_ENV=k8s` 即可
3. **日志路径**：确保 logback-spring.xml 中的日志输出路径与 K8s volume mount 一致
4. **健康检查端点**：确保各服务的 actuator health 端点可用（已配置 `management.endpoints.web.exposure.include=*`）

## 六、实施步骤

1. **创建 k8s/ 目录结构**，生成所有 YAML 清单文件
2. **为每个 web 服务新增 application-k8s.yml**，将硬编码 IP 改为环境变量引用
3. **构建 Docker 镜像**：`mvn clean package -DskipTests` 后，在各 docker/ 目录执行 `docker build -t hub.dibtime.com/dib-c1/<image-name>:<tag> .`
4. **推送镜像到 Harbor**：`docker push hub.dibtime.com/dib-c1/<image-name>:<tag>`
5. **部署基础设施**：先部署 Nacos（如果 K8s 内没有）、Redis、MySQL 确保可达
6. **部署后端服务**：`kubectl apply -f k8s/namespace.yaml` -> `kubectl apply -f k8s/base/` -> `kubectl apply -f k8s/nacos/` -> `kubectl apply -f k8s/services/`
7. **部署前端**：`kubectl apply -f k8s/frontend/`
8. **配置 Ingress**：`kubectl apply -f k8s/ingress/`
9. **验证**：检查各 Pod 状态、Nacos 注册情况、Gateway 路由转发、前端访问

## 七、注意事项

1. **service-extract 内存需求大**（12-16g），需确保 K8s 节点有足够资源，建议单独调度到高性能节点（使用 nodeSelector 或 tolerations）
2. **数据库连接**：如果 MySQL/Redis 在 K8s 集群外部，需确保 Pod 网络可达（可通过 Service + ExternalName 或 NetworkPolicy 放行）
3. **有状态服务**：Nacos 生产环境建议使用 MySQL 后端存储 + 3 节点集群
4. **镜像仓库认证**：需提前创建 `harbor-registry-secret`：`kubectl create secret docker-registry harbor-registry-secret --docker-server=hub.dibtime.com --docker-username=xxx --docker-password=xxx -n dib-c1`
5. **配置中心**：后续可考虑将 application-k8s.yml 的配置迁移到 Nacos Config，实现配置热更新

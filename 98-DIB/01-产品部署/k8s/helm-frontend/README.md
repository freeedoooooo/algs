# helm-frontend — 微前端独立 Chart 集合

本目录将原先集中在 `../helm-c1-frontend` 的「大 Chart」**按微前端拆分为多个独立的小 Chart**，每个微前端一个目录、一次发布，便于独立升级、回滚与故障隔离。

> 原 `../helm-c1-frontend` 保持不变，可作为整体部署方案继续存在；本目录是**逐应用独立部署**方案。

---

## 一、为什么拆分

原方案用一个 Chart 遍历 `.Values.frontends` 一次性部署全部微前端。拆分后：

| 维度      | 大 Chart（helm-c1-frontend） | 拆分后（helm-frontend） |
|---------|---------------------------|--------------------|
| 发布粒度    | 一次发布全部应用                  | 每个应用独立发布           |
| 升级/回滚   | 整体回滚，影响面大                 | 单应用回滚，互不影响         |
| 故障隔离    | 一个应用配置错误可能影响整体渲染          | 各 Chart 独立，互不干扰    |
| 资源/副本调整 | 需在统一 values 里定位           | 各应用 values 独立、直观   |
| 代价      | 模板单一、无重复                  | 模板有 5 份副本，需保持一致    |

由于这些微前端容器**高度同构**（镜像内共用同一份 nginx.conf、同一 Dockerfile，仅镜像名不同），拆分后各 Chart 的模板结构完全一致，只在
`values.yaml` 中差异化，尽量避免维护漂移。

---

## 二、目录结构

```
helm-frontend/
├── README.md              # 本文档
├── c1-app-portal/         # 门户主应用（网关根路径 / 与 /app-portal/）
│   ├── Chart.yaml
│   ├── values.yaml        # dev 环境
│   ├── values-test.yaml   # test 环境
│   └── templates/frontend.yaml
├── c1-app-data/           # 数据应用（网关 /app-data/）
├── c1-app-nav/            # 导航组件（网关 /app-nav/）
├── c1-app-report/         # 报表应用（网关 /app-report/）
└── c1-app-system/         # 系统管理（网关 /app-system-v2/）
```

每个子目录都是一个**可独立安装的 Helm Chart**，结构一致：

- `Chart.yaml`：`name` 即应用名（= K8s Deployment/Service 名）。
- `values.yaml` / `values-test.yaml`：dev / test 两套环境完整配置。
- `templates/frontend.yaml`：单个应用的 Deployment + Service（ClusterIP）。

---

## 三、关键约定

1. **资源名 = Chart.Name**：Service 名固定为 `c1-app-xxx`，必须与第一层网关 `nginx.conf` 中
   `proxy_pass http://c1-app-xxx/` 的主机名一致，否则路由失败。
2. **Service 类型统一 ClusterIP**：仅供第一层网关内部访问，不对外暴露。
3. **健康检查**：统一使用容器内置 `/healthz`，不依赖任何静态文件（兼容 app-nav 这类无 index.html 的组件库）。
4. **发布名**：与 Chart 名一致（如 `c1-app-data`），环境区分通过 namespace + values 文件实现。
5. **`--server-side=false`**：所有 helm 命令强制携带，避免与 Jenkins `kubectl set image` 产生字段冲突。

---

## 四、部署命令

在 `helm-frontend` 目录下即可执行全部命令（**无需进入各子目录**）。发布名 = Chart 名 = `c1-app-xxx`，5
个微前端命令已全部列出，首次部署直接照抄即可。

### dev 环境（142）

```bash
cd "docs-c1/01_产品部署/k8s/helm-frontend"

helm upgrade --install c1-app-portal ./c1-app-portal -n c1-ns-dev --server-side=false
helm upgrade --install c1-app-data   ./c1-app-data   -n c1-ns-dev --server-side=false
helm upgrade --install c1-app-nav    ./c1-app-nav    -n c1-ns-dev --server-side=false
helm upgrade --install c1-app-report ./c1-app-report -n c1-ns-dev --server-side=false
helm upgrade --install c1-app-system ./c1-app-system -n c1-ns-dev --server-side=false
```

### test 环境（70）

```bash
cd "docs-c1/01_产品部署/k8s/helm-frontend"

helm upgrade --install c1-app-portal ./c1-app-portal --values ./c1-app-portal/values-test.yaml -n c1-ns-test --server-side=false
helm upgrade --install c1-app-data   ./c1-app-data   --values ./c1-app-data/values-test.yaml   -n c1-ns-test --server-side=false
helm upgrade --install c1-app-nav    ./c1-app-nav    --values ./c1-app-nav/values-test.yaml    -n c1-ns-test --server-side=false
helm upgrade --install c1-app-report ./c1-app-report --values ./c1-app-report/values-test.yaml -n c1-ns-test --server-side=false
helm upgrade --install c1-app-system ./c1-app-system --values ./c1-app-system/values-test.yaml -n c1-ns-test --server-side=false
```

> bank / sh 环境接入后，把上面的 `values-test.yaml` 换成 `values-pro-bank.yaml` / `values-pro-sh.yaml`、namespace 换成
`c1-ns-pro-bank` / `c1-ns-pro-sh` 即可。

### 查看 / 回滚 / 卸载

```bash
cd "docs-c1/01_产品部署/k8s/helm-frontend"

# —— 查看 ——
helm list -n c1-ns-dev                      # 已安装的 release
helm history c1-app-report -n c1-ns-dev     # 某 release 的版本历史

# —— 回滚（升级出问题时）——
helm rollback c1-app-report 1 -n c1-ns-dev  # 回滚到指定版本号

# —— 卸载 / 删除（各应用相互独立，可单独卸载）——
helm uninstall c1-app-portal -n c1-ns-dev
helm uninstall c1-app-data   -n c1-ns-dev
helm uninstall c1-app-nav    -n c1-ns-dev
helm uninstall c1-app-report -n c1-ns-dev
helm uninstall c1-app-system -n c1-ns-dev
```

> - 5 个微前端 Chart **相互独立、无先后依赖**，可按需单独部署 / 卸载；但都依赖第一层网关（`../helm-infra/nginx`
    ）做路由分发，网关需先就绪。
> - `helm uninstall` 只删该 Chart 渲染的 Deployment / Service，不动 namespace 与网关；如需保留 release 历史可加
    `--keep-history`。卸载为集群写操作，请由运维确认后手动执行。

### 部署前本地校验

```bash
cd "docs-c1/01_产品部署/k8s/helm-frontend"

# 一次性 lint 全部 5 个 Chart
helm lint ./c1-app-portal ./c1-app-data ./c1-app-nav ./c1-app-report ./c1-app-system

# 渲染抽查（dev / test）
helm template c1-app-report ./c1-app-report
helm template c1-app-report ./c1-app-report --values ./c1-app-report/values-test.yaml
```

---

## 五、关键配置项（各应用 values）

| 配置项                | 说明            | dev 默认值                                 |
|--------------------|---------------|-----------------------------------------|
| `namespace`        | 部署命名空间        | `c1-ns-dev`                             |
| `imageRegistry`    | 镜像仓库前缀        | `10.0.6.183:8088`                       |
| `image.repository` | 镜像名（相对仓库前缀）   | 如 `c1/c1-app-data`                      |
| `image.tag`        | 镜像 tag        | `idc-dev_latest`                        |
| `imagePullPolicy`  | 拉取策略          | `Always`                                |
| `nodeName`         | 调度节点          | dev `worker-5.142` / test `worker-5.70` |
| `replicas`         | 副本数           | `1`                                     |
| `port`             | 容器/Service 端口 | `80`                                    |
| `serviceType`      | Service 类型    | `ClusterIP`                             |
| `resources`        | 资源配额          | 见各 values                               |

---

## 六、多环境说明

| 环境        | values 文件          | namespace    | 节点           |
|-----------|--------------------|--------------|--------------|
| dev (142) | `values.yaml`      | `c1-ns-dev`  | worker-5.142 |
| test (70) | `values-test.yaml` | `c1-ns-test` | worker-5.70  |

> bank / sh 环境如需接入，参照 `values-test.yaml` 在对应应用目录新增 `values-pro-bank.yaml` / `values-pro-sh.yaml`，部署时用
`--values` 指定即可。

---

## 七、部署验证

```bash
# 查看某个应用 Pod（状态 Running 且 READY 1/1）
kubectl get pods -n c1-ns-dev -l app=c1-app-data

# 容器内健康检查（应返回 ok）
kubectl exec -n c1-ns-dev deploy/c1-app-data -- wget -qO- http://127.0.0.1:80/healthz

# 均为 ClusterIP，集群外验证需端口转发
kubectl port-forward -n c1-ns-dev svc/c1-app-data 8080:80
# 浏览器访问 http://localhost:8080/
```

---

## 八、与第一层网关的关系

本目录只负责**第二层微前端容器**的部署。第一层入口网关（路由分发 + 后端 API 代理，剥离 URL 前缀后转发到各 `c1-app-xxx`）仍由
`../helm-c1-frontend`（`gateway.enabled`）或外部 Nginx 承担，本拆分不改动网关职责。

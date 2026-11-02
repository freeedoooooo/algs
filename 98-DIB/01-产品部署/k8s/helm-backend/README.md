# helm-backend — 后端微服务独立 Chart 集合

本目录将原先集中在 `../helm-c1-backend` 的「大 Chart」中的**后端微服务部分**（4 个平台服务 + 5 个业务服务）按服务拆分为多个独立的小
Chart，每个服务一个目录、一次发布，便于独立升级、回滚与故障隔离。

> 原 `../helm-c1-backend` 保持不变，可作为整体部署方案继续存在；本目录 + `../helm-infra` 是**逐服务独立部署**方案。

---

## 一、为什么拆分

原方案用一个 Chart 遍历 `.Values.services` 一次性部署全部后端服务。拆分后：

| 维度      | 大 Chart（helm-c1-backend） | 拆分后（helm-backend） |
|---------|--------------------------|-------------------|
| 发布粒度    | 一次发布全部服务                 | 每个服务独立发布          |
| 升级/回滚   | 整体回滚，影响面大                | 单服务回滚，互不影响        |
| 故障隔离    | 一个服务配置错误可能影响整体渲染         | 各 Chart 独立，互不干扰   |
| 资源/副本调整 | 需在统一 values 里定位          | 各服务 values 独立、直观  |
| 代价      | 模板单一、无重复                 | 模板有 9 份副本，需保持一致   |

由于这些后端服务**高度同构**（同一份通用模板，仅端口/健康检查/资源/额外挂载不同），拆分后各 Chart 的
`templates/backend.yaml` **完全一致**，服务差异全部由 `values.yaml` 驱动，尽量避免维护漂移。

---

## 二、目录结构

```
helm-backend/
├── README.md              # 本文档
├── c1-p-oauth/            # 平台：统一认证（SSO）
├── c1-p-gateway/          # 平台：API 网关
├── c1-p-rbac/             # 平台：权限资源管理
├── c1-p-mdm/              # 平台：主数据管理
├── c1-b-extract/          # 业务：资料提取（高内存）
├── c1-b-report/           # 业务：报告生成
├── c1-b-data/             # 业务：数据资源（高内存）
├── c1-b-rule/             # 业务：规则引擎
└── c1-b-govern/           # 业务：数据治理
```

每个子目录都是一个**可独立安装的 Helm Chart**，结构一致：

- `Chart.yaml`：`name` 即服务名（= K8s Deployment/Service 名）。
- `values.yaml`：dev（142）环境完整配置。
- `values-test.yaml` / `values-pro-bank.yaml` / `values-pro-sh.yaml`：其余 3 套环境**仅覆盖差异项**（namespace /
  nodeName / image.tag），其余继承 `values.yaml`。
- `templates/backend.yaml`：单服务的 Deployment + Service（9 份内容完全相同）。

---

## 三、服务清单（拆分时精确保留原参数）

| 服务           | tier     | 端口    | healthPath                     | prometheus.path                    | resources(req→limit)    | 额外挂载                            |
|--------------|----------|-------|--------------------------------|------------------------------------|-------------------------|---------------------------------|
| c1-p-oauth   | platform | 9090  | `/sso/actuator/health`         | `/sso/actuator/prometheus`         | 100m/512Mi → 500m/1Gi   | 无                               |
| c1-p-gateway | platform | 20000 | `/actuator/health`             | 空（仅 scrape）                        | 100m/512Mi → 500m/1Gi   | 无                               |
| c1-p-rbac    | platform | 20001 | `/api/auth/actuator/health`    | `/api/auth/actuator/prometheus`    | 100m/512Mi → 500m/1Gi   | 无                               |
| c1-p-mdm     | platform | 20002 | `/api/mdm/actuator/health`     | `/api/mdm/actuator/prometheus`     | 100m/512Mi → 500m/1Gi   | 无                               |
| c1-b-extract | business | 30001 | `/api/extract/actuator/health` | `/api/extract/actuator/prometheus` | 250m/3Gi → 2000m/6Gi    | `app-tmp`→`/tmp`（sizeLimit 5Gi） |
| c1-b-report  | business | 30002 | `/api/report/actuator/health`  | `/api/report/actuator/prometheus`  | 250m/1536Mi → 2000m/3Gi | `app-tmp`→`/opt/app/tmp`        |
| c1-b-data    | business | 30003 | `/api/data/actuator/health`    | `/api/data/actuator/prometheus`    | 250m/2Gi → 2000m/4Gi    | 无                               |
| c1-b-rule    | business | 30004 | `/api/rule/actuator/health`    | `/api/rule/actuator/prometheus`    | 250m/1Gi → 2000m/2Gi    | 无                               |
| c1-b-govern  | business | 30005 | `/api/dg/actuator/health`      | `/api/dg/actuator/prometheus`      | 250m/512Mi → 2000m/1Gi  | 无                               |

> 所有服务 `serviceType` 均为 `ClusterIP`、`replicas` 均为 `1`，仅由 `../helm-infra/nginx` 与 Ingress 对外暴露。

---

## 四、前置依赖、部署与卸载

后端服务通过 `envFrom` 注入公共 ConfigMap `c1-configmap-common`，**必须先部署 `../helm-infra/config`**；运行期依赖
Nacos/Redis，建议整体顺序：

```
helm-infra/config → nacos / redis → helm-backend 各服务 → helm-infra/nginx
```

在 `helm-backend` 目录下即可执行全部命令（**无需进入各子目录**）。发布名 = Chart 名 = 服务名（`c1-p-xxx` / `c1-b-xxx`），9
个服务×4 套环境的命令已全部列出，首次部署直接照抄即可。

### dev 环境（142）

```bash
cd "docs-c1/01_产品部署/k8s/helm-backend"

# 平台服务
helm upgrade --install c1-p-oauth   ./c1-p-oauth   -n c1-ns-dev --server-side=false
helm upgrade --install c1-p-gateway ./c1-p-gateway -n c1-ns-dev --server-side=false
helm upgrade --install c1-p-rbac    ./c1-p-rbac    -n c1-ns-dev --server-side=false
helm upgrade --install c1-p-mdm     ./c1-p-mdm     -n c1-ns-dev --server-side=false
# 业务服务
helm upgrade --install c1-b-extract ./c1-b-extract -n c1-ns-dev --server-side=false
helm upgrade --install c1-b-report  ./c1-b-report  -n c1-ns-dev --server-side=false
helm upgrade --install c1-b-data    ./c1-b-data    -n c1-ns-dev --server-side=false
helm upgrade --install c1-b-rule    ./c1-b-rule    -n c1-ns-dev --server-side=false
helm upgrade --install c1-b-govern  ./c1-b-govern  -n c1-ns-dev --server-side=false
```

### test 环境（70）

```bash
cd "docs-c1/01_产品部署/k8s/helm-backend"

helm upgrade --install c1-p-oauth   ./c1-p-oauth   --values ./c1-p-oauth/values-test.yaml   -n c1-ns-test --server-side=false
helm upgrade --install c1-p-gateway ./c1-p-gateway --values ./c1-p-gateway/values-test.yaml -n c1-ns-test --server-side=false
helm upgrade --install c1-p-rbac    ./c1-p-rbac    --values ./c1-p-rbac/values-test.yaml    -n c1-ns-test --server-side=false
helm upgrade --install c1-p-mdm     ./c1-p-mdm     --values ./c1-p-mdm/values-test.yaml     -n c1-ns-test --server-side=false
helm upgrade --install c1-b-extract ./c1-b-extract --values ./c1-b-extract/values-test.yaml -n c1-ns-test --server-side=false
helm upgrade --install c1-b-report  ./c1-b-report  --values ./c1-b-report/values-test.yaml  -n c1-ns-test --server-side=false
helm upgrade --install c1-b-data    ./c1-b-data    --values ./c1-b-data/values-test.yaml    -n c1-ns-test --server-side=false
helm upgrade --install c1-b-rule    ./c1-b-rule    --values ./c1-b-rule/values-test.yaml    -n c1-ns-test --server-side=false
helm upgrade --install c1-b-govern  ./c1-b-govern  --values ./c1-b-govern/values-test.yaml  -n c1-ns-test --server-side=false
```

### pro-bank 环境（101）

```bash
cd "docs-c1/01_产品部署/k8s/helm-backend"

helm upgrade --install c1-p-oauth   ./c1-p-oauth   --values ./c1-p-oauth/values-pro-bank.yaml   -n c1-ns-pro-bank --server-side=false
helm upgrade --install c1-p-gateway ./c1-p-gateway --values ./c1-p-gateway/values-pro-bank.yaml -n c1-ns-pro-bank --server-side=false
helm upgrade --install c1-p-rbac    ./c1-p-rbac    --values ./c1-p-rbac/values-pro-bank.yaml    -n c1-ns-pro-bank --server-side=false
helm upgrade --install c1-p-mdm     ./c1-p-mdm     --values ./c1-p-mdm/values-pro-bank.yaml     -n c1-ns-pro-bank --server-side=false
helm upgrade --install c1-b-extract ./c1-b-extract --values ./c1-b-extract/values-pro-bank.yaml -n c1-ns-pro-bank --server-side=false
helm upgrade --install c1-b-report  ./c1-b-report  --values ./c1-b-report/values-pro-bank.yaml  -n c1-ns-pro-bank --server-side=false
helm upgrade --install c1-b-data    ./c1-b-data    --values ./c1-b-data/values-pro-bank.yaml    -n c1-ns-pro-bank --server-side=false
helm upgrade --install c1-b-rule    ./c1-b-rule    --values ./c1-b-rule/values-pro-bank.yaml    -n c1-ns-pro-bank --server-side=false
helm upgrade --install c1-b-govern  ./c1-b-govern  --values ./c1-b-govern/values-pro-bank.yaml  -n c1-ns-pro-bank --server-side=false
```

### pro-sh 环境（239）

```bash
cd "docs-c1/01_产品部署/k8s/helm-backend"

helm upgrade --install c1-p-oauth   ./c1-p-oauth   --values ./c1-p-oauth/values-pro-sh.yaml   -n c1-ns-pro-sh --server-side=false
helm upgrade --install c1-p-gateway ./c1-p-gateway --values ./c1-p-gateway/values-pro-sh.yaml -n c1-ns-pro-sh --server-side=false
helm upgrade --install c1-p-rbac    ./c1-p-rbac    --values ./c1-p-rbac/values-pro-sh.yaml    -n c1-ns-pro-sh --server-side=false
helm upgrade --install c1-p-mdm     ./c1-p-mdm     --values ./c1-p-mdm/values-pro-sh.yaml     -n c1-ns-pro-sh --server-side=false
helm upgrade --install c1-b-extract ./c1-b-extract --values ./c1-b-extract/values-pro-sh.yaml -n c1-ns-pro-sh --server-side=false
helm upgrade --install c1-b-report  ./c1-b-report  --values ./c1-b-report/values-pro-sh.yaml  -n c1-ns-pro-sh --server-side=false
helm upgrade --install c1-b-data    ./c1-b-data    --values ./c1-b-data/values-pro-sh.yaml    -n c1-ns-pro-sh --server-side=false
helm upgrade --install c1-b-rule    ./c1-b-rule    --values ./c1-b-rule/values-pro-sh.yaml    -n c1-ns-pro-sh --server-side=false
helm upgrade --install c1-b-govern  ./c1-b-govern  --values ./c1-b-govern/values-pro-sh.yaml  -n c1-ns-pro-sh --server-side=false
```

### 查看 / 回滚 / 卸载

```bash
cd "docs-c1/01_产品部署/k8s/helm-backend"

# —— 查看 ——
helm list -n c1-ns-dev                    # 已安装的 release
helm history c1-b-extract -n c1-ns-dev    # 某 release 的版本历史

# —— 回滚（升级出问题时）——
helm rollback c1-b-extract 1 -n c1-ns-dev # 回滚到指定版本号

# —— 卸载 / 删除（各服务相互独立，可单独卸载；下面是 dev，其余环境改 -n 即可）——
helm uninstall c1-p-oauth   -n c1-ns-dev
helm uninstall c1-p-gateway -n c1-ns-dev
helm uninstall c1-p-rbac    -n c1-ns-dev
helm uninstall c1-p-mdm     -n c1-ns-dev
helm uninstall c1-b-extract -n c1-ns-dev
helm uninstall c1-b-report  -n c1-ns-dev
helm uninstall c1-b-data    -n c1-ns-dev
helm uninstall c1-b-rule    -n c1-ns-dev
helm uninstall c1-b-govern  -n c1-ns-dev
```

> - 9 个后端服务 Chart **相互独立**（通过 Nacos 服务发现协作），可单独部署 / 升级 / 回滚 / 卸载；但都 `envFrom` 公共
    ConfigMap `c1-configmap-common`，须先部署 `../helm-infra/config`。
> - `helm uninstall` **只删除该 chart 渲染的资源**（Deployment / Service），不会动 namespace、公共 ConfigMap
    `c1-configmap-common`（属 `../helm-infra/config`）及其他服务。
> - 如需保留 release 历史以便审计，卸载时加 `--keep-history`；卸载同样为集群写操作，请由运维确认后手动执行。

---

## 五、多环境说明

| 环境             | values 文件              | namespace        | 节点           | image.tag             |
|----------------|------------------------|------------------|--------------|-----------------------|
| dev (142)      | `values.yaml`          | `c1-ns-dev`      | worker-5.142 | `idc-dev_latest`      |
| test (70)      | `values-test.yaml`     | `c1-ns-test`     | worker-5.70  | `idc-test_latest`     |
| pro-bank (101) | `values-pro-bank.yaml` | `c1-ns-pro-bank` | worker-5.101 | `idc-pro-bank_latest` |
| pro-sh (239)   | `values-pro-sh.yaml`   | `c1-ns-pro-sh`   | worker-5.239 | `idc-pro-sh_latest`   |

> `values-<env>.yaml` 仅覆盖 namespace / nodeName / image.tag 三项，其余全部继承 `values.yaml`（Helm 深合并）。

---

## 六、关键约定

1. **资源名 = Chart.Name**：Deployment/Service 名固定为 `c1-p-xxx` / `c1-b-xxx`，须与网关、Nacos 服务发现、其他服务调用地址保持一致。
2. **通用模板 + values 驱动**：`templates/backend.yaml` 9 份完全相同，改端口/资源/健康检查只改对应 `values.yaml`。
3. **prometheus 注解**：`prometheus.path` 为空时（如 gateway）模板自动省略 `prometheus.io/path`，仅保留
   `prometheus.io/scrape`。
4. **额外挂载**：`extraVolumeMounts` / `extraVolumes` 为空数组时无额外卷；`extraVolumes` 项含 `sizeLimit` 则渲染带限额的
   emptyDir。
5. **`--server-side=false`**：所有 helm 命令强制携带，避免与 Jenkins `kubectl set image` 产生字段冲突。

---

## 七、部署前本地校验

```bash
cd "docs-c1/01_产品部署/k8s/helm-backend"

# 全部 9 个服务
Get-ChildItem -Directory | ForEach-Object { helm lint $_.FullName }

# 单个服务渲染（含指定环境）
helm template c1-b-extract ./c1-b-extract
helm template c1-p-rbac ./c1-p-rbac --values ./c1-p-rbac/values-test.yaml
```

> 集群写操作请由运维在确认无误后手动执行，本目录仅提供 Chart 与本地只读校验命令。

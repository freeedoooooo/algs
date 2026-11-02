# c1-dataease — DataEase v2.10.9 服务端容器化部署

## 定位

把官方 DataEase v2.10.9 **服务端**（原版镜像，Spring Boot `app.jar`，自带 UI/API/websocket，
容器原生监听 `8100`）+ **专属 MySQL 8.4** 迁入 k8s，两个服务独立容器、独立 PVC，
等价官方 docker-compose 的 `dataease` + `mysql` 两个 service（每个服务独立一个环境）。

与魔改前端（`c1-app-bi` chart，静态 nginx）的关系不变：

```
浏览器 ──> 网关 c1-nginx (helm-infra/nginx)
             ├── /bi/            -> c1-app-bi      (魔改 BI 前端，静态)
             ├── /bi/de2api/     -> c1-dataease:8100/de2api/   (本 chart)
             └── /bi/websocket/  -> c1-dataease:8100/websocket/(本 chart)
```

Service 名固定 `c1-dataease:8100`，**网关 nginx.conf 零改动**。
本 chart 取代 `c1-app-bi` values 里 `dataeaseExternal`（selector-less Service + Endpoints
指向 compose 主机）的外部注册方案，**两者互斥**。

官方镜像事实（v2.10.9 Dockerfile 已核实）：

| 项 | 值 |
| --- | --- |
| 镜像 | `registry.cn-qingdao.aliyuncs.com/dataease/dataease:v2.10.9` |
| 进程 | `run-java.sh` 启动 `/opt/apps/app.jar`（无 nginx，前后端同端口） |
| 监听 | `RUNNING_PORT=8100`，HEALTHCHECK = `nc -zv 127.0.0.1 8100` |
| 配置 | `-Dspring.config.additional-location=/opt/apps/config/`（挂 application.yml） |
| 数据 | `/opt/dataease2.0/{data/*,cache,logs}`；drivers/map 在镜像内不可被 PVC 遮蔽 |
| MySQL | `registry.cn-qingdao.aliyuncs.com/dataease/mysql:8.4.0`（**8.4 不是 8.3**） |
| 建库 | 官方 init.sql 仅建空库 `dataease`；建表由应用首次启动自动完成 |

## 1. 前置：官方镜像落地到 Harbor（离线环境必做）

在任一能跑 docker 的机器（如 70/142 主机）执行：

```bash
# 1) 取离线包（内网 minio）
wget http://10.0.5.178:9000/toubao/dataease/dataease-offline-installer-v2.10.9-ce.tar.gz
tar zxvf dataease-offline-installer-v2.10.9-ce.tar.gz
cd dataease-offline-installer-v2.10.9-ce

# 2) 加载镜像（文件名以 images/ 实际为准）
ls images/
docker load -i images/dataease-*.tar.gz
docker load -i images/mysql-*.tar.gz

# 3) tag + push 到 chart 使用的 Harbor（默认 10.0.6.183:8088，若用 10.0.6.181:8080 同步改 values）
docker tag registry.cn-qingdao.aliyuncs.com/dataease/dataease:v2.10.9  10.0.6.183:8088/c1/dataease:v2.10.9
docker tag registry.cn-qingdao.aliyuncs.com/dataease/mysql:8.4.0       10.0.6.183:8088/c1/dataease-mysql:8.4.0
docker push 10.0.6.183:8088/c1/dataease:v2.10.9
docker push 10.0.6.183:8088/c1/dataease-mysql:8.4.0
```

## 2. 部署（dev 142 为例）

> 部署顺序铁律：**先关外部注册，再装本 chart，最后重启网关**。
> `c1-dataease` Service 重名，先后颠倒会 helm 冲突报错。

```bash
helm="C:/Users/DIB/.workbuddy/binaries/helm/windows-amd64/helm.exe"
kubecfg="--kubeconfig D:/Personal/Documents/C1/04_运维软件/k3s/k3s.yml"

# ① 关闭 c1-app-bi 的外部 DataEase 注册（删除旧的 selector-less Service + Endpoints）
cd 01_产品部署/k8s/helm-frontend/c1-app-bi
$helm upgrade c1-app-bi . $kubecfg -n c1-ns-dev --server-side=false \
    --set dataeaseExternal.enabled=false

# ② 安装本 chart（mysql 独立环境 + dataease 服务端 + c1-dataease Service）
cd ../../helm-infra/dataease
$helm upgrade --install c1-dataease . $kubecfg -n c1-ns-dev --server-side=false

# ③ 重启网关：nginx 启动时才解析 upstream，需让网关 Pod 重建以解析新 Service 的 ClusterIP
#    方式一：Kuboard 界面 -> c1-nginx 部署详情 -> 「重启」
#    方式二：kubectl --kubeconfig D:/Personal/Documents/C1/04_运维软件/k3s/k3s.yml \
#              -n c1-ns-dev rollout restart deployment/c1-nginx
```

test 环境（70）：`helm upgrade --install c1-dataease . --values values-test.yaml
-n c1-ns-test --server-side=false`，前置同上（c1-app-bi 用 `values-test.yaml`
时同样把 `dataeaseExternal.enabled` 置 false）。

## 3. 存量数据迁移（可选，从 compose 主机迁入）

> 全新环境（空库）跳过本节，应用首启自动建表，默认账号 `admin / DataEase@123456`。

以 70 主机现网实例（`/opt/dataease2.0`）为例：

```bash
# —— 源主机（70）——
# 1) 导库（容器名以 docker ps 实际为准，官方为 ${DE_MYSQL_HOST}=mysql-de）
docker exec mysql-de sh -c 'mysqldump -uroot -p"Password123@mysql" --databases dataease \
  --single-transaction --routines --triggers --set-gtid-purged=OFF' > de-mysql.sql
# 2) 打包应用数据（与 chart subPath 一致的 7 个目录）
tar czf de-data.tgz -C /opt/dataease2.0/data \
  static-resource geo appearance exportData plugin font i18n
# 3) 传到任一能执行 kubectl 的机器

# —— k8s 侧 ——
# 4) 按第 2 节装好 chart 且 mysql Pod ready 后，缩容 dataease 应用（只留 mysql，停写）
$helm $kubecfg -n c1-ns-dev upgrade c1-dataease . --set dataease.replicas=0 --reuse-values

# 5) 导库：直接 exec 进 mysql Pod（stdin 管道导入，无需临时容器拼参数）
kubectl $kubecfg -n c1-ns-dev exec -i deploy/c1-dataease-mysql -- \
  sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4' < de-mysql.sql

# 6) 导应用数据文件：临时 helper Pod 挂 data PVC（nodeSelector 与 values 的 nodeName 一致）
cat <<'EOF' | kubectl $kubecfg -n c1-ns-dev apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: de-import
spec:
  nodeSelector:
    node-name: worker-5.142
  containers:
    - name: import
      image: 10.0.6.183:8088/c1/dataease-mysql:8.4.0
      command: ["sh", "-c", "sleep 3600"]
      volumeMounts:
        - name: files
          mountPath: /mnt
  volumes:
    - name: files
      persistentVolumeClaim:
        claimName: c1-dataease-data-pvc
EOF
kubectl $kubecfg -n c1-ns-dev cp de-data.tgz de-import:/mnt/de-data.tgz
kubectl $kubecfg -n c1-ns-dev exec de-import -- sh -c 'cd /mnt && tar xzf de-data.tgz && rm -f de-data.tgz'
kubectl $kubecfg -n c1-ns-dev delete pod de-import
#    说明: de-data.tgz 顶层就是 static-resource/ 等 7 个目录，解到 PVC 根目录后
#    与应用的 subPath 挂载一一对应，无需逐目录处理

# 7) 恢复副本数
$helm $kubecfg -n c1-ns-dev upgrade c1-dataease . --set dataease.replicas=1 --reuse-values
```

迁移后注意：

- **分享链接会失效**（官方迁移已知问题），需在系统里重新生成；
- 旧数据源/应用配置里若有 `www.bidata.com` 域名，在本 chart values 的
  `dataease.hostAliases` 里配 `ip + hostnames`（等价原 compose 的 extra_hosts）；
- 若旧实例改过「系统参数->数据库」指向外部库，先在旧界面改回内置库再导出
  （部署清单既有要求）。

## 4. 验证

```bash
# Pod 全部 Running（dataease 首启建表需几分钟，startupProbe 放宽到 ~10min）
kubectl $kubecfg -n c1-ns-dev get pods -l 'app in (c1-dataease, c1-dataease-mysql)'

# 服务端直连（NodePort）
curl -I http://<节点IP>:30090/            # 200，DataEase 自带 UI
# 网关链路（重点：de2api 代理 + websocket）
curl -s http://c1-dev.dibdata.cn/bi/de2api/sys-request-timeout | head
# 魔改前端 + API 全链路
curl -I http://c1-dev.dibdata.cn/bi/
```

管理员配置入口：`http://<节点IP>:30090`（dev）/ `:30190`（test），登录
`admin / DataEase@123456`（空库全新实例）。

## 5. 常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| dataease Pod `ImagePullBackOff` | 镜像没推到 Harbor：见第 1 节；或 values 里 image 地址与实际 push 地址不一致 |
| init 容器卡 `wait-for-mysql` | mysql 未 ready：查 mysql Pod 日志/`kubectl describe`；PVC 绑定失败多为 nodeSelector 与 local-path 不匹配 |
| dataease 反复重启（首启） | 首次建表慢，startupProbe 已放宽 ~10min；若仍超时查 mysql 慢日志，或临时调大 `failureThreshold` |
| 网关 502 / upstream not found | 未按顺序操作：`c1-dataease` Service 不存在或网关没重启（第 2 节③） |
| `Error: rendered manifests contain a resource that already exists`（Service c1-dataease） | c1-app-bi 的 `dataeaseExternal.enabled` 未先置 false 并 upgrade |
| 分享链接打不开 | 迁移后分享链接失效属官方已知行为，重新生成；并核对 `dataease.originList` 是否含网关域名 |
| 导出/上传报 413 或超大文件失败 | 网关与应用层均已放开 200m/500MB；再大需同步调 `client_max_body_size` 与 multipart 限制 |

## 6. 回退到外部注册方案

若要临时回退到 compose 主机方案：把 `c1-app-bi` 的 `dataeaseExternal.enabled` 置回
`true`（配 ip/port）并 `helm upgrade`，同时 `helm uninstall c1-dataease -n c1-ns-dev`
释放 Service 名，再重启网关。本 chart 的 PVC 数据保留，迁回无损。

## 7. 与 docker-compose 方案的隔离对照（评审 / 新人看这节）

现网 compose 方案（`dataease部署清单.md`：一环境一整机 + `install.sh` + 手工魔改）
与本 chart 的隔离机制逐维度对比：

| 维度 | docker-compose（现网清单） | k8s chart（本目录） |
| --- | --- | --- |
| 进程隔离 | 容器 namespace（dataease 与 mysql 两个容器互不可见） | 同左（Pod 即容器） |
| 网络隔离 | compose 内部 bridge 网络，容器名互访；对外靠端口映射，**3306 要手工开放**（清单魔改①） | Service DNS 集群内互访；mysql=ClusterIP，**外部天然不可达**，导数据走 `kubectl exec` |
| 数据隔离 | bind mount 宿主机目录 `/opt/dataease2.0`，与整机共存亡 | PVC 独立声明（20Gi×2），跟 namespace 走，与节点解耦可迁 |
| 配置 | 登录各主机手工改文件（清单 4 处魔改即手工痕迹，各机已漂移） | ConfigMap + values-\<env\>.yaml，git 版本化，`helm upgrade` 即生效 |
| 故障域 | 整机：宕机 = 该环境 BI 全挂，人肉上机恢复 | Pod 级探针自愈重启；PVC 数据不随 Pod 丢 |
| 多环境 | 每台堡垒机/主机重复：下离线包 → install.sh → 手改 compose/nginx → 迁移重配分享链接 | 镜像 Harbor 推一次共用；新环境 = 拷一份 values + 一条 helm 命令 |
| 升级 | `dectl upgrade`（依赖公网）或手工换镜像，停机替换 | 改 tag 重建，`helm history/rollback` 可回滚 |
| 备份 | `dectl backup` 手工 tar | 同样可 mysqldump（后续可加 CronJob）；local-path 无快照能力 |

清单里 4 处魔改在 k8s 下的归宿：

1. **mysql 补 3306 端口映射** → 不再需要（ClusterIP 只在集群内可达，导入用 `kubectl exec -i`）；
2. **extra_hosts www.bidata.com** → values 的 `dataease.hostAliases`；
3. **宿主机 nginx 反代 /tbpj/bi/de2api/ → IP:8100** → 网关 c1-nginx conf（零改动，Service 名代替硬编码 IP）；
4. **迁移后分享链接失效重配** → 机制相同（访问地址入库），k8s 下迁移低频 + originList 统一配置。

企业生产最小实践（1-4 本 chart 已内置，5-6 建议排期）：

1. 部署物代码化：chart + values 进 git，环境=文件，不登机器手改；
2. 镜像单一来源：Harbor 固定 tag，禁 latest；
3. 最小暴露面：mysql ClusterIP 不对外；NodePort 管理口限内网/防火墙；
4. 变更可回滚：helm release 历史天然留痕；
5. 定期备份：每周 mysqldump（可做 CronJob）+ exportData 目录外同步；
6. 密码收敛 Secret：现沿用 values 明文（与现网清单一致），后续演进。

**结论**：单环境小规模下，"一环境一整机 + compose + 定期 dectl backup" 是可接受的
合规底线（隔离靠容器 + 整机故障域）；多环境统一交付、回滚与收敛暴露面，是迁 k8s
的收益所在。两方案互斥可切换，回退路径见第 6 节。

## 8. Jenkins 流水线要不要建？（结论：不建构建，只留部署按钮）

dataease 用的是**官方原版镜像**，没有代码构建环节，与 Jenkins 里 c1-app-*/c1-b-* 那些
「提交代码 → 构建镜像 → 推 Harbor → 部署」的构建流水线**不是一类东西**。它的生命周期：

| 事件 | 频率 | 动作 |
| --- | --- | --- |
| 镜像入库（load/tag/push） | 每个版本一次 | 手工，见第 1 节 |
| 各环境部署（142/70/…） | 每环境一次 | 一条 helm 命令，见第 2 节 |
| 改配置（originList/资源/副本） | 偶发 | 改 values → 再跑一次部署命令 |
| 升级官方版本 | 官方发版才做 | 新镜像 push 后改 values 的 tag → 部署命令 |

因此：**不建 Jenkins 构建任务**（无源码可构建）。若希望在 Jenkins 界面留个统一按钮
（可选，纯部署任务、秒级完成），新建 **Freestyle 项目** `c1-dataease`：

- 参数化构建过程：Choice 参数 `ENV`，选项 `dev` / `test`；
- 源码管理：Git 拉取本部署仓库（与其他任务同源）；
- 构建步骤 Execute shell：

```bash
#!/bin/bash
set -e
KUBECONF=/path/to/k3s.yml        # Jenkins 节点上 kubeconfig 实际路径
cd helm-infra/dataease           # 仓库内 chart 目录
if [ "$ENV" = "dev" ]; then
  helm upgrade --install c1-dataease . --kubeconfig "$KUBECONF" \
    -n c1-ns-dev --server-side=false
else
  helm upgrade --install c1-dataease . --kubeconfig "$KUBECONF" \
    --values values-test.yaml -n c1-ns-test --server-side=false
fi
```

前提：Jenkins 节点已装 helm、放好 kubeconfig、能拉取本仓库。**存量数据迁移（第 3 节）
与镜像 push（第 1 节）不要塞进 Jenkins**——它们是有风险的一次性手工操作，需要人盯着。

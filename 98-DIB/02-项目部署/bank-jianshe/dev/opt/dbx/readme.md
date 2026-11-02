# DBX 部署说明

DBX 是一款轻量级数据库管理工具，通过 Web 界面连接和管理数据库。

## 环境说明

| 环境 | 部署方式 | 网络 |
|------|----------|------|
| dev  | docker-compose 一键安装 | 可联网拉取镜像 |
| pro（客户生产） | 离线导入镜像 + docker-compose | 内网隔离，无法访问外网 |

## Dev 环境部署

dev 环境网络通畅，可直接使用 docker-compose 一键启动：

```bash
docker compose up -d
```

服务启动后访问：`http://<host>:4224/dbx`

查看运行状态：

```bash
docker compose ps
docker compose logs -f dbx
```

## 生产环境部署（离线）

客户生产环境为内网隔离环境，无法直接从 Docker Hub 或 CNB 镜像仓库拉取镜像，需在具备外网的机器上导出镜像，再通过内网传输方式导入到目标服务器。

### 1. 导出镜像（在有外网的机器上操作）

```bash
# 拉取镜像
docker pull docker.cnb.cool/dbxio.com/dbx:latest

# 导出为 tar 文件
docker save -o dbx-latest.tar docker.cnb.cool/dbxio.com/dbx:latest
```

### 2. 传输镜像文件

将 `dbx-latest.tar` 与 `docker-compose.yml` 通过内网传输方式（U盘、SCP、FTP、内网文件服务器等）拷贝到目标服务器的同一目录下。

### 3. 导入镜像（在目标服务器上操作）

```bash
docker load -i dbx-latest.tar
```

导入完成后，通过以下命令确认镜像存在：

```bash
docker images | grep dbx
```

### 4. 调整 compose 配置

生产环境需将 `docker-compose.yml` 中的 `pull_policy` 改为 `never` 或 `if_not_present`，避免启动时尝试联网拉取镜像：

```yaml
pull_policy: never
```

### 5. 启动服务

```bash
docker compose up -d
```

服务启动后访问：`http://<host>:4224/dbx`

## 服务信息

- **镜像**：`docker.cnb.cool/dbxio.com/dbx:latest`
- **端口**：`4224`
- **访问路径**：`/dbx`（由环境变量 `DBX_PUBLIC_BASE_PATH` 配置）
- **数据卷**：`dbx-data`，挂载到容器 `/app/data`，用于持久化数据库连接配置
- **重启策略**：`unless-stopped`

## 常见问题

### Q1：生产环境启动时报 `pull access denied` 或网络超时

检查 `docker-compose.yml` 中的 `pull_policy` 是否已改为 `never`，并确认镜像已通过 `docker load` 成功导入。

### Q2：如何升级 DBX 版本

- **dev 环境**：执行 `docker compose pull && docker compose up -d` 即可。
- **生产环境**：在有外网的机器上拉取新版本镜像并按上述流程导出、传输、导入，再执行 `docker compose up -d` 重启服务。数据卷 `dbx-data` 会自动保留原有配置。

### Q3：如何备份连接配置

DBX 的连接配置持久化在数据卷 `dbx-data` 中，可通过以下命令备份：

```bash
docker run --rm -v dbx-data:/data -v $(pwd):/backup alpine tar czf /backup/dbx-data-backup.tar.gz -C /data .
```

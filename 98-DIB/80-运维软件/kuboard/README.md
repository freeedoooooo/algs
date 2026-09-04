# Kuboard v4 — K8s 可视化管理

Kuboard 是一个 Kubernetes 管理面板，提供集群导入、工作负载管理、日志查看、资源监控等功能。

## 文件清单

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | Kuboard v4 + MariaDB 数据库 |
| `.env` | 端口、密码等配置 |

## 默认配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 访问端口 | 38000 | 宿主机端口，可在 `.env` 修改 |
| 登录账号 | admin | 固定 |
| 登录密码 | Kuboard12345 | 首次登录后已修改 |
| 数据库密码 | kuboardpwd | MariaDB 密码，可在 `.env` 修改 |

---

## 一、部署 Kuboard

在任意一台有 Docker 的机器上执行（推荐放在 Server 节点 10.0.6.183）：

```bash
# 把 kuboard 目录传到服务器
scp -r kuboard/ root@10.0.6.183:/opt/

# 启动
cd /opt/kuboard/
docker compose up -d

# 查看状态
docker compose ps

# 查看日志（确认启动无报错）
docker compose logs -f
```

启动成功后访问：**http://10.0.6.183:38000**

---

## 二、导入 K3s 集群

### 步骤 1：在 K3s Server 节点创建 ServiceAccount

在 **Server 节点（10.0.6.183）** 上执行：

```bash
# 创建 Kuboard 专用 ServiceAccount
kubectl create sa kuboard-sa -n kube-system

# 绑定集群管理员权限
kubectl create clusterrolebinding kuboard-sa \
  --clusterrole=cluster-admin \
  --serviceaccount=kube-system:kuboard-sa
```

### 步骤 2：获取连接 Token

K8s 1.24+ 不再自动为 ServiceAccount 创建 Secret，需要手动创建：

```bash
# 创建 Token Secret
kubectl -n kube-system apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: kuboard-sa-token
  annotations:
    kubernetes.io/service-account.name: kuboard-sa
type: kubernetes.io/service-account-token
EOF

# 获取 Token（输出一长串字符串，复制备用）
kubectl -n kube-system get secret kuboard-sa-token \
  -o jsonpath='{.data.token}' | base64 -d
echo ""
```

### 步骤 3：在 Kuboard 页面导入集群

1. 打开浏览器访问 **http://10.0.6.183:38000**
2. 使用 `admin` / `Kuboard12345` 登录
3. 点击 **「导入集群」**
4. 填写信息：

| 字段 | 值 |
|------|-----|
| 集群名称 | `c1-idc-test` |
| API Server 地址 | `https://10.0.6.183:6443` |
| 认证方式 | Bearer Token |
| Token | 步骤 2 输出的字符串 |

5. 点击 **「验证」** → 验证通过后 **「保存」**

### 步骤 4：验证连接

导入成功后，在 Kuboard 首页就能看到 `c1-idc-test` 集群，点击进入可以查看：
- `c1-idc-test` 命名空间下的所有 Pod、Deployment、Service
- 实时日志、资源使用情况
- ConfigMap、Secret 等配置

---

## 网络说明

```
浏览器 → http://10.0.6.183:38000 → Kuboard 容器
                                        ↓
                              https://10.0.6.183:6443 → K3s API Server
```

- Kuboard 容器需要能访问 K3s API Server 的 `6443` 端口
- 如果 Kuboard 和 K3s 在同一台机器上，直接填 `https://10.0.6.183:6443`
- 如果在不同机器上，确保网络互通且 K3s Server 防火墙开放 `6443`

---

## 常用运维命令

```bash
# 启动
docker compose up -d

# 停止
docker compose down

# 重启
docker compose restart

# 查看日志
docker compose logs -f kuboard

# 更新到最新版本
docker compose pull
docker compose up -d
```

---

## 常见问题

**Q: Kuboard 容器启动失败，数据库连接不上？**
MariaDB 首次启动需要初始化数据（约 30s），Kuboard 会等待数据库健康检查通过后才启动。如果一直等待，检查：
```bash
docker compose logs db    # 查看数据库初始化日志
```

**Q: 导入集群时验证失败？**
- 检查 API Server 地址是否可达：`curl -k https://10.0.6.183:6443`
- 检查 Token 是否过期或复制不完整
- 确认 K3s 安装时 `--tls-san` 包含了 `10.0.6.183`

**Q: 首次登录密码忘了？**
删除数据目录重新初始化：
```bash
docker compose down
rm -rf kuboard-mariadb-data/
docker compose up -d
```

# 本地访问 Nacos 配置页面指南

> 本文介绍如何从本地开发机通过 `kubectl port-forward` 访问 K3s 集群内的 Nacos Web 管理页面。
> 适用于 Nacos Service 类型为 ClusterIP（默认）的场景。

---

## 一、为什么需要 port-forward？

Nacos 部署后，其 Service 默认类型是 **ClusterIP**——只能在集群内部访问：

```bash
kubectl -n c1-idc-test get svc nacos
# NAME    TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)
# nacos   ClusterIP   10.43.128.96   <none>        8848/TCP,9848/TCP
```

你本地电脑的浏览器直接访问 `10.0.5.142:8848`（Agent 节点 IP）是**不通的**，因为 ClusterIP 是虚拟 IP，只存在于集群网络里。

**解决方案**：用 `kubectl port-forward` 在本地和集群内 Pod 之间建一条临时隧道。

---

## 二、前置条件：配置本地 kubectl

要让本地的 `kubectl` 能操作远程 K3s 集群，需要拿到集群的 **kubeconfig 配置文件**。

### 2.1 从 Server 节点获取 kubeconfig

SSH 登录到 K3s Server 节点（dev6183，10.0.6.183），执行：

```bash
cat /etc/rancher/k3s/k3s.yaml
```

会输出一大段 YAML，类似：

```yaml
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: LS0tLS1CRUdJTi...
    server: https://127.0.0.1:6443    # ← 这里要改
  name: default
contexts:
- context:
    cluster: default
    user: default
  name: default
current-context: default
kind: Config
preferences: {}
users:
- name: default
  user:
    client-certificate-data: LS0tLS1CRU...
    client-key-data: LS0tLS1CRUd...
```

**把整个输出复制下来**。

### 2.2 修改 server 地址（关键！）

拿到的配置里 `server: https://127.0.0.1:6443` 是本地回环地址，**必须改成 Server 节点的实际 IP**：

```yaml
server: https://10.0.6.183:6443    # 改成公司 Server 节点的真实 IP
```

> ⚠️ **不要改证书数据**（`certificate-authority-data`、`client-certificate-data`、`client-key-data` 的长串 Base64 内容），那些是加密认证信息，改了就连不上集群。

> 💡 `name: default` 那些只是配置项的内部标签，不影响功能，不用改。

### 2.3 把配置放到本地电脑

**Windows 系统**：

```powershell
# 创建 .kube 目录（如果不存在）
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.kube"

# 把修改后的 YAML 保存到：C:\Users\你的用户名\.kube\config
# 注意：文件名就是 config，没有扩展名

# 或者直接复制文件
Copy-Item "d:\path\to\k3s.yml" "$env:USERPROFILE\.kube\config"
```

**Linux/Mac 系统**：

```bash
mkdir -p ~/.kube
# 把修改后的内容保存到 ~/.kube/config
```

### 2.4 验证连接

```powershell
kubectl get nodes
```

应该看到公司集群的节点列表：

```text
NAME                  STATUS   ROLES           AGE   VERSION
dev6183               Ready    control-plane   xxd   v1.30.4+k3s1
Bank-AI-Credit-5142   Ready    <none>          xxd   v1.30.4+k3s1
```

如果报错 `Unable to connect to the server`，检查：

- 你电脑能否 ping 通 10.0.6.183（网络是否互通）
- Server 节点的 6443 端口是否开放（防火墙）
- kubeconfig 里的 server 地址是否正确

---

## 三、访问 Nacos 配置页面

### 3.1 执行 port-forward

连接成功后，执行：

```powershell
kubectl -n c1-idc-test port-forward svc/nacos 8848:8848
```

终端会显示：

```text
Forwarding from 127.0.0.1:8848 -> 8848
Forwarding from [::1]:8848 -> 8848
```

### 3.2 浏览器访问

打开浏览器，访问：

```
http://localhost:8848/nacos
```

**默认账号密码**：`nacos` / `nacos`（如果你没改的话）

### 3.3 port-forward 命令详解

```bash
kubectl -n c1-idc-test port-forward svc/nacos 8848:8848
```

| 部分 | 含义 |
|------|------|
| `kubectl` | K8s 命令行工具 |
| `-n c1-idc-test` | 指定命名空间（Nacos 部署在这里） |
| `port-forward` | 子命令：建立一条**本地端口 → 集群内 Pod 端口**的隧道 |
| `svc/nacos` | 目标：`nacos` 这个 Service（kubectl 会自动找到后面的 Pod） |
| `8848:8848` | 端口映射：`本地端口:远端端口` |

**流量路径**：

```text
你的浏览器
    │
    │  http://localhost:8848/nacos
    │
    ▼
你本地电脑的 8848 端口
    │
    │  kubectl 建立的加密隧道（走 K8s API Server）
    │
    ▼
K3s 集群内部
    │
    ▼
nacos Service（ClusterIP）
    │
    ▼
nacos Pod 的 8848 端口
```

### 3.4 注意事项

- **终端不能关**：关掉终端 = 隧道断开
- **临时性**：不是永久暴露，每次需要时重新执行
- **安全性**：只在你本地监听，外部网络访问不到

---

## 四、快速方案（如果网络不通）

如果你本地电脑和公司服务器**不在同一个网段**（比如你在家，服务器在公司机房），连不上 10.0.6.183，那就需要 **SSH 隧道**：

### 4.1 SSH 到 Server 节点

```bash
ssh root@10.0.6.183
```

### 4.2 在 SSH 会话里执行 port-forward

```bash
kubectl -n c1-idc-test port-forward svc/nacos 8848:8848 --address=0.0.0.0
```

（`--address=0.0.0.0` 让端口监听在所有网卡，允许外部访问）

### 4.3 在本地电脑建立 SSH 隧道（新开一个终端）

```bash
ssh -L 8848:localhost:8848 root@10.0.6.183
```

### 4.4 本地浏览器访问

```
http://localhost:8848/nacos
```

---

## 五、其他方式（可选）

### 5.1 改成 NodePort（永久暴露，适合内网）

如果你想让集群内任何机器都能通过节点 IP 访问，可以改 Service 类型：

```bash
kubectl -n c1-idc-test patch svc nacos -p '{"spec":{"type":"NodePort"}}'
```

查看分配的端口：

```bash
kubectl -n c1-idc-test get svc nacos
# 会看到类似：8848:31234/TCP（31234 是自动分配的 NodePort）
```

然后通过任意节点 IP + NodePort 访问：

```
http://10.0.6.183:31234/nacos
http://10.0.5.142:31234/nacos
```

> ⚠️ NodePort 范围是 30000-32767，端口号每次可能不同。

---

## 六、多集群切换（补充）

如果你有多个 K8s 集群，需要在 kubeconfig 里配置多个 context：

```yaml
# ~/.kube/config 里可以有多个 cluster/context/user
clusters:
- cluster:
    server: https://10.0.6.183:6443
  name: company-prod
- cluster:
    server: https://10.0.6.200:6443
  name: company-test

contexts:
- context:
    cluster: company-prod
    user: company-admin
  name: company-prod
- context:
    cluster: company-test
    user: test-admin
  name: company-test

current-context: company-prod   # 默认用这个
```

切换命令：

```bash
kubectl config use-context company-test   # 切到测试集群
kubectl config get-contexts               # 查看所有 context
```

> 💡 每个 K8s 集群有自己独立的 kubeconfig。"Kube 看板（如 Kuboard）相同"不影响 kubectl，kubectl 只认 `~/.kube/config` 里的配置。

---

## 七、常见问题

### Q1: port-forward 报错 `error upgrading connection`

**原因**：kubectl 版本和 K3s 版本不兼容。

**解决**：确保本地 kubectl 版本和集群版本匹配（v1.30.x）。

### Q2: 浏览器访问 `http://localhost:8848/nacos` 无响应

**检查**：

```bash
# 1. 确认 port-forward 在运行
# 终端应该显示 "Forwarding from 127.0.0.1:8848"

# 2. 确认 Nacos Pod 是 Running 状态
kubectl -n c1-idc-test get pod -l app=nacos

# 3. 确认 Service 存在
kubectl -n c1-idc-test get svc nacos
```

### Q3: 忘了 Nacos 密码

**重置密码**（进入 Pod 执行）：

```bash
kubectl -n c1-idc-test exec -it deploy/nacos -- sh
# 进入容器后
curl -X POST "http://localhost:8848/nacos/v1/auth/users?username=nacos&password=nacos"
```

或直接在 MySQL 里改（如果用了外挂 MySQL）：

```sql
USE nacos_config;
UPDATE users SET password = '$2a$10$...' WHERE username = 'nacos';
```

> ⚠️ 密码是 BCrypt 加密的，建议用 Nacos API 重置或查官方文档。

---

## 八、命令速查

```bash
# 获取 kubeconfig（在 Server 节点执行）
cat /etc/rancher/k3s/k3s.yaml

# 验证连接
kubectl get nodes

# 访问 Nacos
kubectl -n c1-idc-test port-forward svc/nacos 8848:8848

# 浏览器访问
# http://localhost:8848/nacos

# 查看 Nacos 日志
kubectl -n c1-idc-test logs -f deploy/nacos

# 重启 Nacos
kubectl -n c1-idc-test rollout restart deploy/nacos
```

## 生产环境部署说明

### linux服务器用户

```
dib
dib@1234A
```

### 安装目录

```
cd /opt/app/
```

### C1-后端安装说明

```
# 以 c1-rule 为例

# 第一步，传安装包，准备好以下2个文件
/opt/app/c1-install/backend/c1-rule/c1-data.jar
/opt/app/c1-install/backend/c1-rule/Dockerfile.jar

# 第二步，构建docker镜像
cd /opt/app/c1-install
./docker-build.sh c1-rule

# 第三步，启动容器
docker-compose up -d c1-rule

# oauth 配置
http://10.5.210.161:8090/tbpj/app/api-oauth/callback,http://www.sipf.com.cn/tbpj/app/api-oauth/callback
```

### C1-前端安装说明

```
# 前端文件路径
/opt/app/c1-client
/opt/app/bi-client

# 迁移脚本
tar -czvf c1-client.tar.gz c1-client
tar -xzvf c1-client.tar.gz

tar -czvf bi-client.tar.gz bi-client
tar -xzvf bi-client.tar.gz
```

### 第三方软件安装说明

```
# 以 nginx 为例，其他 minio、redis 与此同理

# 准备好以下2个文件
/opt/app/nginx/docker-compose.yml
/opt/app/nginx/nginx.conf

# 启动容器
cd /opt/app/nginx
docker-compose up -d
```

### C1地址及账号

```
10.5.210.161:8090/tbpj/app/app-c1/#/
chenlizhen
Sipf@2025
（注意：大写 S）
```

### BI地址及账号

```
# 系统地址及账号
10.5.210.161:8100
admin
DataEase@123456

# 内置MySQL数据库地址及账号
10.5.210.161:3306
root
Password123@mysql
```

### 数据库GBase8s配置及账号

```
# 主库配置
url: jdbc:gbasedbt-sqli://10.5.210.164:9088/c1_tb:sqlmode=oracle;GBASEDBTSERVER=gbase1;DB_LOCALE=zh_CN.utf8;CLIENT_LOCALE=zh_CN.utf8;NEWCODESET=UTF8,utf8,57372;GL_USEGLU=1
username: did
password: Dib@2025032

# 从库，将其中 GBASEDBTSERVER=gbase1 的 gbase1 改为 gbase2）

# 集群模式
# 1、web应用中的数据库配置，使用 .env.db 覆盖
# 2、容器要挂载 /opt/gbase/gbase_hosts
```

### MinIO地址及账号

```
# 登录地址
10.5.210.162:9001
dib
dib@12345

# 迁移脚本
# 登录 uat-minio
cd /opt
sudo tar -czvf minio-data.tar.gz minio
scp "/opt/minio-data.tar.gz" "dib@10.5.210.162:/opt/"
# 登录 pro-minio
tar -xzvf minio-data.tar.gz

# uat-minio
cd /opt/minio/data/c1-bucket
tar -czvf minio-data.tar.gz.2025-11-18 2025-11-18
scp "/opt/minio/data/c1-bucket/minio-data.tar.gz.2025-11-18" "dib@10.5.210.162:/opt/minio/data/c1-bucket"
# pro-minio
tar -xzvf minio-data.tar.gz.2025-11-18
```

### Redis地址及账号

```
10.5.210.166:6739
-
dib@12345
```
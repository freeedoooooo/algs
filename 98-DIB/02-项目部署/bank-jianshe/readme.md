# 部署说明

## 生产环境

```
dev环境部署，除了 opengauss、ocr ，其他的部署与生产完全一致。
```

### Linux 服务器用户

```
root/Internation110
appadmin/dib@1234A
```

### OCR-部署

```
# 切换到 ocr 安装目录
cd /root/simple_ocr

# 执行 ocr 重启脚本
./restart-ocr.sh

```

### C1-安装目录

```
cd /opt/app/
```

### C1-后端安装说明

```
# 以 c1-extract 为例

# 第一步，传安装包，准备好jar
/opt/app/backend/jar/c1-extract.jar

# 第二步，构建docker镜像
cd /opt/app/backend
docker-compose up -d --force-recreate c1-extract
```

### C1-前端安装说明

```
# 前端文件路径
cd /opt/app/frontend/c1-client

# 以后 app-report 为例，替换下面的目录
/opt/app/frontend/c1-client/app-report
```

### 第三方软件安装说明

```
# 以 nginx 为例，其他 minio、redis 与此同理

# 准备好以下2个文件
/opt/nginx/docker-compose.yml
/opt/nginx/nginx.conf

# 启动容器
cd /opt/nginx
docker-compose up -d
```

### C1地址及账号

```
测试地址：http://{ip}:8090/
测试账号：admin/dib@2025
```

### MinIO地址及账号

```
# 登录地址
地址：http://{ip}:9001
账号：dib/dib@12345
```

### Redis地址及账号

```
地址：{ip}:6739
账号：dib@12345
```

### Nacos地址及账号

```
地址：http://{ip}:8848/nacos
账号：c1/c1@2025
```

### opengauss数据库

```
地址：ip:5432/c1
账号: gaussdb
密码: Dib@123456
```

### 服务器更换IP，需要修改的配置

```
1、修改 /etc/hosts 中的 {ip} myhost 的测试IP改为生产IP

2、修改 /opt/app/backend/.env，将以下配置中的测试ip改为生产ip
DIB_OAUTH_SERVER_HOST
DIB_OAUTH_SERVER_HOST_INNER
DIB_OAUTH_CLIENT_HOST
OCR_SERVER
SPRING_DATASOURCE_URL

3、重启以下服务
cd /opt/nginx
docker-compose down
docker-compose up -d

cd /opt/app/backend
docker-compose down
docker-compose up -d

4、配置登录认证跳转地址
将表 oauth_client_details 字段 web_server_redirect_uri 的测试IP改为生产IP

5、配置大模型的接口地址
将表 com_ai_client 字段 api_url 的测试IP给为生产IP
```
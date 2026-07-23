# dataease 安装说明

## 离线安装

```
# 官方地址 https://dataease.io/docs/v2/installation/offline_INSTL_and_UPG/#3
# 从公司内网 minio 下载安装包
wget http://10.0.5.178:9000/toubao/dataease/dataease-offline-installer-v2.10.9-ce.tar.gz

# 解压安装包
tar zxvf dataease-offline-installer-v2.10.9-ce.tar.gz

# 运行安装脚本
/bin/bash install.sh
```

### 修改容器配置-mysql

```
# 配置 docker-compose-mysql.yml
# 开放数据库端口
    container_name: ${DE_MYSQL_HOST}
    # 补充端口映射
    ports:
      - "3306:3306"
    # 补充重启策略
    restart: unless-stopped
```

### 修改容器配置-dataease

```
# 配置 docker-compose.yml
# 解决域名解析问题，方便api配置
services:
  dataease:
    # 补充域名配置
    extra_hosts:
      - "www.bidata.com:<c1服务的ip>"
    # 补充重启策略
    restart: unless-stopped

# 方案2，启动之后，配置 /etc/hosts
docker exec -it dataease sh
vi /etc/hosts
{IP} www.bidata.com
```

### 配置 nginx.conf

```
# 处理BI客户端静态文件和前端路由
location /tbpj/bi/ {
    alias /opt/app/bi-client/;
    try_files $uri $uri/ /index.html;
}

# 代理到 dataease 新的 ip:port
# 处理 BI API 代理
location /tbpj/bi/de2api/ {
    client_max_body_size 200m;
    proxy_pass http://10.0.5.142:8100/de2api/;
}

location /tbpj/bi/websocket/ {
    client_max_body_size 200m;
    proxy_pass http://10.0.5.142:8100/websocket/;
}
```

### 重新配置分享链接

```
因为迁移 dataease 之后，分享链接会失效
```

### 系统配置中，重新配置数据库为内置库

## 备注

### 登录账号密码

```
登录用户名: admin
登录密码: DataEase@123456
```

### 数据库账号密码

```
# 数据库用户名
DE_MYSQL_USER=root
DE_MYSQL_PASSWORD=Password123@mysql
```

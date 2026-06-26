# 产品部署

## 部署准备

```
# 后端服务
/opt/app/c1/docker-compose.yml
/opt/app/c1/.env

# nginx
/opt/app/c1/docker-compose-nginx.yml
/opt/app/nginx.conf

# nacos
/opt/app/c1/docker-compose-nacos.yml

# minio
/opt/app/c1/docker-compose-minio.yml

# redis
/opt/app/c1/docker-compose-redis.yml
```

## 字体安装

```
wget http://10.0.5.178:9000/toubao/uat/font.zip
sudo unzip ./font.zip -d /usr/share/fonts
sudo fc-cache -fv
```

## C1 后端启动

```
cd /opt/app/c1/
docker-compose up -d <service-name>
```

## 第三方软件部署

### nginx

```
cd /opt/app/c1
docker-compose -f docker-compose-nginx.yml down
docker-compose -f docker-compose-nginx.yml up -d
```

### nacos

```
cd /opt/app/c1
docker-compose -f docker-compose-nacos.yml up -d
# 登录ip:8848/nacos，默认用户 nacos/nacos
# 创建默认用户
# username: c1
# password: c1@2025
```

### minio

```
cd /opt/app/c1
docker-compose -f docker-compose-minio.yml up -d
```

### redis

```
cd /opt/app/c1
docker-compose -f docker-compose-redis.yml up -d
```

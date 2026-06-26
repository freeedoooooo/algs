### 离线安装

```
# 官网地址
# wget https://github.com/goharbor/harbor/releases/download/v2.11.0/harbor-offline-installer-v2.11.0.tgz
# 公司内网下载地址
wget http://10.0.5.178:9000/toubao/harbor/harbor-offline-installer-v2.11.0.tgz
tar xzf harbor-offline-installer-v2.11.0.tgz
```

### 修改 harbor.yml

```
# 1、修改hostname
# 2、修改port 80 为 8088
# 3、禁用https
cd harbor
cp harbor.yml.tmpl harbor.yml
vim harbor.yml

# 默认账号 admin/Harbor12345
```

### 修改 /etc/docker/daemon.json

```
# daemon.json
#  "insecure-registries": [
#    "10.0.6.183:8088"
#  ]
```

### 登录

```
docker login 10.0.6.183:8088
```

### 验证推送

```
# 先在web页面创建项目 c1

# 验证推送1
docker tag nginx:1.17.8 10.0.6.183:8088/c1/nginx:1.17.8
docker push 10.0.6.183:8088/c1/nginx:1.17.8

# 验证推送2
docker tag openjdk:8-jdk 10.0.6.183:8088/c1/openjdk:8-jdk
docker push 10.0.6.183:8088/c1/openjdk:8-jdk
```

### 验证代理仓库

```
docker pull 10.0.6.183:8088/proxy-daocloud/openjdk:8-jdk
```

### 最简harbor，仅维护一个注册表

```
docker run -d \
  --name registry \
  -p 5000:5000 \
  -v /opt/registry/data:/var/lib/registry \
  --restart=always \
  registry:2
```
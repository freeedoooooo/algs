#!/bin/bash

# 加载系统环境和配置文件
source /etc/profile           # 加载系统环境变量
export SHELL=/bin/bash        # 设置默认 Shell

cd /opt/www

# MySQL 端口号
readonly MYSQL_PORT=3306
 
# 检查 MySQL 端口是否已通
wait_for_mysql_port() {
  local port=$1
  while true; do
    if nc -z 127.0.0.1 $port > /dev/null 2>&1; then
      echo "检测到 MySQL 服务已启动."
      break
    else
      echo "检测到 MySQL 服务未启动, 等待10重新检测..."
      sleep 10
    fi
  done
}
 
# 调用函数等待 MySQL 端口打开
wait_for_mysql_port $MYSQL_PORT

# 容器列表
readonly CONTAINER_NAME_LIST=(
  "data-cloud-eureka-server"
  "data-cloud-auth-server"
  "data-cloud-gateway"
  "data-cloud-auth-resource"
  "data-cloud-mdm"
  "dib-agent-service-report"
  "dib-agent-service-extract-web"
  "dib-agent-service-data-web"
)

# 逐个重启容器
for container in "${CONTAINER_NAME_LIST[@]}"; do
  ./docker-restart.sh $container
  sleep 3s
done



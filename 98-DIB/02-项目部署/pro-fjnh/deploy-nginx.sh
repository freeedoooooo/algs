#!/bin/bash

# 加载系统环境和配置文件
source /etc/profile           # 加载系统环境变量
export SHELL=/bin/bash        # 设置默认 Shell

# 启用调试模式，打印每条执行的命令
# set -x
# 启用错误检查，如果任何命令失败则退出脚本
set -e

# Docker 容器名称
readonly CONTAINER_NAME="fjnh-nginx"

# 2. 关闭旧容器（如果存在）
echo "关闭旧容器..."
if docker ps -a --format '{{.Names}}' | grep -wq "^${CONTAINER_NAME}$"; then
    docker stop "$CONTAINER_NAME"
    echo "旧容器已关闭"
    docker rm "$CONTAINER_NAME"
    echo "旧容器已删除"
else
    echo "旧容器不存在，无需关闭。"
fi

docker run -d \
    --name ${CONTAINER_NAME} \
    --network host \
    -p 8000:8000 \
    -v /opt/www/nginx.conf:/etc/nginx/nginx.conf \
    -v /opt/www/c1-client:/opt/www/c1-client \
    -v /opt/www/logs:/var/log/nginx \
    nginx:latest


echo "检查容器状态..."
sleep 2
docker ps --filter "name=${CONTAINER_NAME}"

# 需要先安装curl命令
curl -s http://localhost:8000 >/dev/null && echo "服务已正常启动" || echo "服务可能异常，请检查日志"

echo "启动 Nginx 成功！"

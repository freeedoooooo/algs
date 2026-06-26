#!/bin/bash

# 加载系统环境和配置文件
source /etc/profile           # 加载系统环境变量
export SHELL=/bin/bash        # 设置默认 Shell

# 启用调试模式，打印每条执行的命令
# set -x
# 启用错误检查，如果任何命令失败则退出脚本
set -e

# 定义docker的变量
# Docker 容器名称
readonly CONTAINER_NAME="kibana"

echo "容器名称: $CONTAINER_NAME"


# 停止并删除已有容器（如果存在）
if docker ps -a --format '{{.Names}}' | grep -wq ${CONTAINER_NAME}; then
    docker stop ${CONTAINER_NAME}
    echo "停止已存在的容器: ${CONTAINER_NAME}"
    docker rm ${CONTAINER_NAME}
    echo "删除已存在的容器: ${CONTAINER_NAME}"
fi


# 确保目录可访问
mkdir -p /opt/kibana/config
sudo chown -R 1000:1000 /opt/kibana/config
sudo chmod -R 755 /opt/kibana/config

mkdir -p /opt/kibana/data
sudo chown -R 1000:1000 /opt/kibana/data
sudo chmod -R 755 /opt/kibana/data




# 运行一个临时的 Kibana 容器（不挂载任何卷）
docker run --name temp-kibana -d docker.elastic.co/kibana/kibana:8.10.3
# 等待几秒钟让容器启动并准备好文件系统
sleep 5
# 从临时容器中复制默认的 kibana.yml 到宿主机的目录
docker cp temp-kibana:/usr/share/kibana/config/kibana.yml /opt/kibana/config/
# 停止并删除临时容器
docker stop temp-kibana && docker rm temp-kibana




# 如果您之前启用了安全（有密码），需要加上：
# -e "ELASTICSEARCH_USERNAME=elastic" \
# -e "ELASTICSEARCH_PASSWORD=dib@2025" \
# 由于您禁用了安全，所以只需要主机地址
echo "创建，并启动新的容器..."
docker run -d \
  --name kibana \
  --network host \
  --restart=unless-stopped \
  -p 5601:5601 \
  -e "ELASTICSEARCH_HOSTS=http://10.0.5.239:9200" \
  -v /opt/kibana/config:/usr/share/kibana/config \
  -v /opt/kibana/data:/usr/share/kibana/data \
  docker.elastic.co/kibana/kibana:8.10.3


echo "检查容器状态..."
sleep 5
CONTAINER_STATUS=$(docker inspect --format='{{.State.Running}}' "${CONTAINER_NAME}" 2>/dev/null)
if [ -z "${CONTAINER_STATUS}" ]; then
    echo "错误：容器 ${CONTAINER_NAME} 不存在！"
    exit 1
elif [ "${CONTAINER_STATUS}" != "true" ]; then
    echo "错误：容器 ${CONTAINER_NAME} 已停止或未正常运行！"
    docker logs "${CONTAINER_NAME}"
    exit 1
fi

echo "容器 ${CONTAINER_NAME} 正在运行，部署成功！"
echo
#!/bin/bash

# 加载系统环境和配置文件
source /etc/profile
export SHELL=/bin/bash

# 脚本配置
set -e

# 定义常量
readonly CONTAINER_NAME="filebeat"
readonly FILEBEAT_IMAGE="docker.elastic.co/beats/filebeat:8.10.3"
readonly CONFIG_PATH="/opt/filebeat/config"
readonly DATA_PATH="/opt/filebeat/data"

# 检查并清理现有容器
cleanup_container() {
    if docker ps -a --format '{{.Names}}' | grep -wq "${CONTAINER_NAME}"; then
        echo "停止并删除已存在的容器: ${CONTAINER_NAME}"
        docker stop "${CONTAINER_NAME}" >/dev/null
        docker rm "${CONTAINER_NAME}" >/dev/null
    fi
}

# 准备文件目录结构
prepare_directories() {
    echo "设置目录权限..."
    for dir in "${CONFIG_PATH}" "${DATA_PATH}"; do
        mkdir -p "${dir}"
        chown -R 1000:1000 "${dir}"
        chmod -R 755 "${dir}"
    done
}

# 启动容器
start_container() {
    echo "创建并启动新的容器..."
    docker run -d \
      --name="${CONTAINER_NAME}" \
      --network host \
      --user=root \
      --volume="${CONFIG_PATH}/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro" \
      --volume="${DATA_PATH}:/usr/share/filebeat/data" \
      -v /opt/app/backend:/opt/app/backend:ro \
      --restart=unless-stopped \
      "${FILEBEAT_IMAGE}" \
      filebeat -e -strict.perms=false
}


# 验证容器状态
verify_container() {
    echo "检查容器状态..."
    sleep 5

    if ! CONTAINER_STATUS=$(docker inspect --format='{{.State.Running}}' "${CONTAINER_NAME}" 2>/dev/null); then
        echo "错误：容器 ${CONTAINER_NAME} 不存在！"
        exit 1
    fi

    if [ "${CONTAINER_STATUS}" != "true" ]; then
        echo "错误：容器 ${CONTAINER_NAME} 已停止或未正常运行！"
        docker logs "${CONTAINER_NAME}"
        exit 1
    fi

    echo "容器 ${CONTAINER_NAME} 正在运行，部署成功！"
}

# 主函数
main() {
    # 打印执行信息
    echo "容器名称: ${CONTAINER_NAME}"
    prepare_directories
    cleanup_container
    start_container
    verify_container
}

# 执行主函数
main "$@"
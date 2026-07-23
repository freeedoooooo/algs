#!/bin/bash

# 加载系统环境和配置文件
source /etc/profile
export SHELL=/bin/bash

# 脚本配置
set -e

# 定义常量
readonly CONTAINER_NAME="logstash"
readonly DEFAULT_CONFIG_URL="http://10.0.5.178:9000/toubao/elk/logstash.conf"
readonly LOGSTASH_IMAGE="docker.elastic.co/logstash/logstash:8.10.3"
readonly CONFIG_PATH="/opt/logstash/pipeline"

# 使用说明函数
usage() {
    echo "用法: $0 [配置URL]"
    echo "示例:"
    echo "  $0                                   # 使用默认配置URL:${DEFAULT_CONFIG_URL}"
    echo "  $0 http://example.com/logstash.conf  # 使用自定义配置URL"
    exit 1
}

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
    mkdir -p "${CONFIG_PATH}"
    chown -R 1000:1000 "${CONFIG_PATH}"
    chmod -R 755 "${CONFIG_PATH}"
}

# 下载配置文件
download_config() {
    local config_url=$1
    echo "下载配置文件..."
    if ! wget -O "${CONFIG_PATH}/logstash.conf" "${config_url}"; then
        echo "错误: 无法从 ${config_url} 下载配置文件"
        exit 1
    fi
    chown -R 1000:1000 "${CONFIG_PATH}"
    chmod -R 755 "${CONFIG_PATH}"
}

# 启动容器
start_container() {
    echo "创建并启动新的容器..."
    docker run -d \
      --name="${CONTAINER_NAME}" \
      --network host \
      --restart=unless-stopped \
      -p 5044:5044 \
      -v "${CONFIG_PATH}/logstash.conf:/usr/share/logstash/pipeline:ro" \
      "${LOGSTASH_IMAGE}"
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
    # 检查参数
    if [ $# -gt 1 ]; then
        usage
    fi

    # 设置配置URL
    local config_url="${1:-$DEFAULT_CONFIG_URL}"

    # 打印执行信息
    echo "容器名称: ${CONTAINER_NAME}"
    echo "使用配置URL: ${config_url}"

    # 执行流程
    prepare_directories
    download_config "${config_url}"
    cleanup_container
    start_container
    verify_container
}

# 执行主函数
main "$@"
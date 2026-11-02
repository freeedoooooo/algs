#!/bin/bash

# 加载系统环境和配置文件
source /etc/profile           # 加载系统环境变量
export SHELL=/bin/bash        # 设置默认 Shell

# 启用调试模式，打印每条执行的命令
# set -x
# 启用错误检查，如果任何命令失败则退出脚本
set -e


# 显示使用说明和参数说明
USAGE="用法: $0 <容器名称>

示例:
  ./docker-restart.sh dib-agent-service-rule-web
"

# 检查是否传入了 --help 或 -h 参数
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "$USAGE"
    exit 0
fi

# 【步骤1，定义变量】
# 定义服务名
readonly CONTAINER_NAME="$1"

# 校验参数
if [ -z "${CONTAINER_NAME}" ] ; then
    echo "错误：容器名称不能为空！"
    echo
    echo "$USAGE"
    exit 1
fi

# 检查容器是否正在运行
if docker ps -q --filter "name=$CONTAINER_NAME" > /dev/null; then
    echo "容器 $CONTAINER_NAME 正在关闭..."
    # 停止容器
    docker stop $CONTAINER_NAME
    echo "容器 $CONTAINER_NAME 已关闭."
else
    echo "容器 $CONTAINER_NAME 未启动."
fi

# 启动容器
echo "启动容器 $CONTAINER_NAME..."
docker start $CONTAINER_NAME
echo "容器 $CONTAINER_NAME 启动完成."

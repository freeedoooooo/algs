#!/bin/bash

# 加载系统环境和配置文件
source /etc/profile           # 加载系统环境变量
export SHELL=/bin/bash        # 设置默认 Shell

# 启用调试模式，打印每条执行的命令
# set -x
# 启用错误检查，如果任何命令失败则退出脚本
set -e

# 显示使用说明和参数说明
USAGE="用法: $0 <服务名称>

参数说明:
  服务名称   前端模块名称

示例:
  ./deploy-frontend.sh app-c1
"

# 检查是否传入了 --help 或 -h 参数
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "$USAGE"
    exit 0
fi


# 【1. 定义变量】
readonly CLIENT_DIR="/opt/www/c1-client"
readonly SERVICE_NAME="$1"
readonly SERVICE_PATH="${CLIENT_DIR}/${SERVICE_NAME}"
readonly PACKAGE_PATH="${SERVICE_PATH}.zip"
readonly OSS_ENV=pro

# 校验参数
if [ -z "${SERVICE_NAME}" ] ; then
    echo "错误：参数不能为空！"
    echo
    echo "$USAGE"
    exit 1
fi

# 校验是否为合法环境名
case "$SERVICE_NAME" in
    app-c1|app-data|app-nav|app-report|app-system)
        ;;
    *)
        echo "Error: Invalid service name '$SERVICE_NAME'"
        echo "Valid options are: app-c1|app-data|app-nav|app-report|app-system"
        exit 1
        ;;
esac


# 【2. 下载更新】

echo "下载安装包"
MINIO_URL="https://oss.dibdata.cn/fjnh/${OSS_ENV}/${SERVICE_NAME}.zip"
wget -O "${PACKAGE_PATH}" "$MINIO_URL";

echo "删除当前版本"
rm -rf "$CLIENT_DIR/$SERVICE_NAME"

echo "解压部署新版本"
unzip -q -o "${PACKAGE_PATH}" -d "${CLIENT_DIR}"

echo "检查部署状态"
if [ -d "${SERVICE_PATH}" ]; then
   rm -f "${PACKAGE_PATH}"
   echo "部署成功"
else
    echo "部署失败 目录 ${SERVICE_PATH} 不存在"
fi


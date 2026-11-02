#!/bin/bash

# 加载系统环境和配置文件
source /etc/profile           # 加载系统环境变量
export SHELL=/bin/bash        # 设置默认 Shell

# 启用调试模式，打印每条执行的命令
# set -x
# 启用错误检查，如果任何命令失败则退出脚本
set -e


# 显示使用说明和参数说明
USAGE="用法: $0 <环境变量> <服务名称>

参数说明:
  环境变量       Spring Boot 配置文件名，例如: fjnh-uat, fjnh-pro
  服务名称       应用的服务Jar包文件名，以及容器名

示例:
  ./deploy.sh fjnh-uat dib-agent-service-rule-web
"

# 检查是否传入了 --help 或 -h 参数
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "$USAGE"
    exit 0
fi


# 【步骤1，定义变量】
# 定义环境变量
readonly PROFILES_ACTIVE="$1"
# 定义服务名
readonly SERVICE_NAME="$2"

# 校验参数
if [ -z "${SERVICE_NAME}" ] || [ -z "${PROFILES_ACTIVE}" ] ; then
    echo "错误：参数不能为空！"
    echo
    echo "$USAGE"
    exit 1
fi

# 校验是否为合法环境名
case "$PROFILES_ACTIVE" in
    fjnh-uat|fjnh-pro)
        ;;
    *)
        echo "Error: Invalid environment '$ENV_NAME'"
        echo "Valid options are: fjnh-uat, fjnh-pro"
        exit 1
        ;;
esac


# 【步骤2，打包 or 查找对应 JAR 文件】
# 定义本地 JAR 文件路径
readonly LOCAL_JAR_DIR="./jar"

# 创建目录
mkdir -p ${LOCAL_JAR_DIR}

# 先删除旧的 jar
rm -f "${LOCAL_JAR_DIR}/${SERVICE_NAME}"*.jar

# 判断使用哪个环境目录（uat / pro）
if [[ "${PROFILES_ACTIVE}" == *"uat"* ]]; then
    OSS_ENV="fjnh-uat"
else
    OSS_ENV="fjnh-pro"
fi

# 拼接 jar url
JAR_URL="https://oss.dibdata.cn/c1-deploy/${OSS_ENV}/${SERVICE_NAME}.jar"
echo "准备从 MinIO 下载 JAR，OSS 路径：${JAR_URL}"

wget -O ./jar/"${SERVICE_NAME}".jar "${JAR_URL}"

# echo "开始打包工程..."
# mvn clean package -Dmaven.test.skip=true
# echo "工程打包完成！"

# 查找打包的 JAR 文件
LOCAL_JAR_FILE=$(ls "${LOCAL_JAR_DIR}/${SERVICE_NAME}"*.jar 2>/dev/null)
if [ -z "${LOCAL_JAR_FILE}" ]; then
    echo "错误：未找到 JAR 文件！"
    exit 1
fi
echo "找到JAR文件：${LOCAL_JAR_FILE}"



# 【步骤3，构建docker镜像，并启动docker容器】
# 1. 执行同级目录下的 Dockerfile，构建镜像
# 2. 关闭旧容器
# 3. 从新镜像启动新容器
# 4. 将容器中的日志目录挂载到当前目录下的 log 目录

# 定义docker的变量
# Docker 时间戳
readonly TIMESTAMP=$(date +"%Y%m%d-%H%M")
# Docker 容器名称
readonly CONTAINER_NAME="${SERVICE_NAME}"
# Docker 镜像名称 = 容器名称 + 时间戳
readonly IMAGE_NAME="${CONTAINER_NAME}:${TIMESTAMP}"
# 容器中 JAR 文件的目录
readonly CONTAINER_JAR_DIR="/opt/app"

# 定义部署目录
# 日志目录
readonly LOCAL_LOG_DIR="./logs"
# Dockerfile 路径
readonly DOCKERFILE_PATH="./Dockerfile"

echo "容器名称: $CONTAINER_NAME"
echo "镜像名称: $IMAGE_NAME"
echo "环境变量: $PROFILES_ACTIVE"


# 检查 Dockerfile 是否存在
if [ ! -f "${DOCKERFILE_PATH}" ]; then
    echo "错误：Dockerfile 不存在！"
    exit 1
fi

# 创建本地日志目录（如果不存在）
mkdir -p "${LOCAL_LOG_DIR}"

# 1. 构建 Docker 镜像
echo "开始构建 Docker 镜像..."
docker build --build-arg LOCAL_JAR_FILE="${LOCAL_JAR_FILE}" \
             --build-arg CONTAINER_NAME="${CONTAINER_NAME}" \
              -t "$IMAGE_NAME" \
              -f "${DOCKERFILE_PATH}" .


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

# 3. 从新镜像启动新容器
echo "启动新容器..."

# 定义容器启动参数
# 参数说明：
#   -d: 后台运行容器
#   --name: 设置容器名称
#   -v: 挂载日志目录
#   -p: 映射容器端口到主机端口，"${SERVICE_PORT}:${SERVICE_PORT}"
#   -e: 设置环境变量、jar包名等
readonly DOCKER_RUN_OPTS=(
    -d
    --network host
    --name "${CONTAINER_NAME}"
    -v "${LOCAL_LOG_DIR}:${CONTAINER_JAR_DIR}/logs"
    -v "/usr/share/fonts:/usr/share/fonts"
    -e "JAR_FILE_NAME=${CONTAINER_NAME}.jar"
    -e "SPRING_PROFILES_ACTIVE=${PROFILES_ACTIVE}"
    -e "OCR_SERVER=http://pro.fjnh.com:8090/"
)

docker run "${DOCKER_RUN_OPTS[@]}" "${IMAGE_NAME}"
echo "新容器已启动！"

# 4. 检查容器状态
echo "检查容器状态..."
sleep 2

# 使用 docker inspect 获取容器的运行状态
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
echo ""
echo ""

#!/bin/bash
# 脚本：docker-restart-on-boot.sh
# 功能：在系统重启时自动重启 Docker 服务并执行其他脚本

# 定义日志文件路径
LOG_FILE="/opt/www/logs/docker-restart-on-boot.log"

# 确保日志目录存在
mkdir -p /opt/www/logs

# 将所有输出重定向到指定的日志文件
exec > "${LOG_FILE}" 2>&1

# 打印当前日期和时间
echo "Starting docker-restart-on-boot.sh at $(date)"

# 执行 docker-restart-all.sh 脚本
echo "Executing /opt/www/docker-restart-all.sh"
/opt/www/docker-restart-all.sh
if [ $? -eq 0 ]; then
    echo "docker-restart-all.sh executed successfully"
else
    echo "docker-restart-all.sh failed with exit code $?"
fi

# 执行 deploy-nginx.sh 脚本
echo "Executing /opt/www/deploy-nginx.sh"
/opt/www/deploy-nginx.sh
if [ $? -eq 0 ]; then
    echo "deploy-nginx.sh executed successfully"
else
    echo "deploy-nginx.sh failed with exit code $?"
fi

# 打印结束日期和时间
echo "Finished docker-restart-on-boot.sh at $(date)"

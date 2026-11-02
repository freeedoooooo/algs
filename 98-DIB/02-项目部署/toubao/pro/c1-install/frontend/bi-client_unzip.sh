#!/bin/bash

echo " 此脚本将执行以下操作:"
echo "   1. 删除旧目录: /opt/app/bi-client"
echo "   2. 将当前目录下的 app-bi.tar.gz 解压到 /opt/app/bi-client/"
echo

# 检查压缩包是否存在
if [ ! -f "app-bi.tar.gz" ]; then
    echo "错误: 当前目录下未找到 app-bi.tar.gz 文件"
    echo "请确保 app-bi.tar.gz 文件已上传到当前目录"
    exit 1
fi

read -rp "确认要继续吗? (y/N): " confirm
case "${confirm,,}" in
y|yes)
    echo "开始执行..."
    
    # 确保父目录存在
    echo "检查并创建目标目录..."
    if [ ! -d "/opt/app" ]; then
        mkdir -p /opt/app
        echo "已创建目录: /opt/app"
    fi
    
    # 删除旧目录
    echo "删除旧目录 /opt/app/bi-client..."
    rm -rf /opt/app/bi-client
    
    # 解压文件
    echo "解压 app-bi.tar.gz 到 /opt/app/bi-client..."
    tar -xzvf app-bi.tar.gz -C /opt/app/
    
    if [ $? -eq 0 ]; then
        echo "正确解压完成！"
        
        # 显示解压结果
        echo "解压后的文件列表:"
        ls -la /opt/app/bi-client/
    else
        echo "解压失败！"
        exit 1
    fi
    
    echo "操作已完成。"
    ;;
*)
    echo "操作已取消。"
    exit 0
    ;;
esac
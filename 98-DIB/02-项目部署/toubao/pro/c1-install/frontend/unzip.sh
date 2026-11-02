#!/bin/bash

echo "⚠️  此脚本将执行以下操作："
echo "   1. 删除旧目录：/opt/app/c1-client 和 /opt/app/bi-client"
echo "   2. 将当前目录下的 c1-client.tar.gz 和 bi-client.tar.gz 解压到 /opt/app/"
echo

read -rp "❓ 确认要继续吗？(y/N): " confirm
case "${confirm,,}" in
    y|yes)
        echo "✅ 开始执行..."
        rm -rf /opt/app/c1-client
        rm -rf /opt/app/bi-client

        tar -xzvf c1-client.tar.gz -C /opt/app
        tar -xzvf bi-client.tar.gz -C /opt/app

        echo "🎉 所有文件已解压完成！"
        ;;
    *)
        echo "🛑 操作已取消。"
        exit 0
        ;;
esac
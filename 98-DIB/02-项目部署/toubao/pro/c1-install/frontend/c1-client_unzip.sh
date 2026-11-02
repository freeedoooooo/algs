#!/bin/bash

# 功能: 解压gz包到/opt/app/c1-client/(压缩包名字)目录

# 检查参数
if [ $# -ne 1 ]; then
    echo "用法: $0 <gz压缩包路径>"
    echo "示例: $0 /path/to/app-c1.tar.gz"
    exit 1
fi

GZ_FILE="$1"

# 检查文件是否存在
if [ ! -f "$GZ_FILE" ]; then
    echo "错误: 文件不存在 - $GZ_FILE"
    exit 1
fi

# 检查文件格式
if [[ ! "$GZ_FILE" =~ \.tar\.gz$ ]] && [[ ! "$GZ_FILE" =~ \.gz$ ]]; then
    echo "错误: 文件格式不支持，请提供.gz或.tar.gz文件"
    exit 1
fi

# 从文件路径中提取压缩包名称（不带扩展名）
FILENAME=$(basename "$GZ_FILE")
if [[ "$FILENAME" =~ \.tar\.gz$ ]]; then
    DIR_NAME="${FILENAME%.tar.gz}"
elif [[ "$FILENAME" =~ \.gz$ ]]; then
    DIR_NAME="${FILENAME%.gz}"
else
    DIR_NAME="${FILENAME}"
fi

# 目标目录
TARGET_DIR="/opt/app/c1-client/"
TARGET_DIR_NAME="$TARGET_DIR$DIR_NAME"

echo "================================================"
echo "解压脚本开始执行"
echo "压缩包: $GZ_FILE"
echo "目标目录: $TARGET_DIR"
echo "================================================"

# 确认操作
read -p "确认要继续吗? (y/N): " confirm
case "${confirm,,}" in
    y|yes)
        echo "开始执行..."
        ;;
    *)
        echo "操作已取消."
        exit 0
        ;;
esac

# 确保父目录存在
echo "1. 检查并创建目标目录..."
if [ ! -d "$TARGET_DIR" ]; then
    mkdir -p "$TARGET_DIR"
    echo "   已创建目录: $TARGET_DIR"
fi

# 清空目标目录
echo "2. 清理目标目录..."
if [ -d "$TARGET_DIR_NAME" ]; then
    rm -rf "$TARGET_DIR_NAME"
    echo "   已删除旧目录: $TARGET_DIR_NAME"
fi

# 解压文件
echo "3. 开始解压文件..."
if [[ "$GZ_FILE" =~ \.tar\.gz$ ]]; then
    # 解压.tar.gz文件
    tar -xzf "$GZ_FILE" -C "$TARGET_DIR"
    if [ $? -eq 0 ]; then
        echo "   tar.gz解压成功"
    else
        echo "错误: tar.gz解压失败"
        exit 1
    fi
else
    # 解压.gz文件（gzip压缩的单文件）
    # 创建目标目录
    mkdir -p "$TARGET_DIR_NAME"
    # 解压到目标目录中的同名文件
    gunzip -c "$GZ_FILE" > "$TARGET_DIR_NAME/${DIR_NAME}"
    if [ $? -eq 0 ]; then
        echo "   gz解压成功"
    else
        echo "错误: gz解压失败"
        exit 1
    fi
fi

# 显示解压结果
echo "4. 解压结果:"
if [ -d "$TARGET_DIR_NAME" ]; then
    ls -la "$TARGET_DIR_NAME/"
else
    echo "   警告: 目标目录不存在: $TARGET_DIR_NAME"
    ls -la "$TARGET_DIR"
fi

echo "================================================"
echo "解压完成!"
echo "文件已解压到: $TARGET_DIR_NAME"
echo "================================================"
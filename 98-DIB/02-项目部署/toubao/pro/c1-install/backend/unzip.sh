#!/bin/bash

# 遍历当前目录下所有 .zip 文件
for zip_file in *.zip; do
    # 跳过没有匹配的情况（如无 .zip 文件）
    [[ -e "$zip_file" ]] || continue

    # 获取文件名（不含扩展名），例如 c1-data.zip → c1-data
    dir_name="${zip_file%.zip}"

    echo "📦 正在解压 $zip_file 到 ./$dir_name/"

    # 创建目标目录（如果不存在）
    mkdir -p "$dir_name"

    # 解压到该目录
    unzip -q "$zip_file"
done

echo "🎉 所有 ZIP 文件已解压完成！"

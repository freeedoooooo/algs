#!/bin/bash

# ========================================
# 构建 Docker 镜像脚本（模块化版本）
# - 支持构建全部或指定服务
# - 自动校验目录、JAR、Dockerfile
# - 打 latest + 时间戳双标签
# ========================================

set -e

# ======================
# 全局配置
# ======================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 预定义服务列表
ALL_SERVICES=(
    platform-auth-server
    platform-eureka
    platform-gateway
    platform-auth-resource
    platform-mdm
    c1-extract
    c1-report
    c1-rule
    c1-data
    c1-dg
)

# 时间戳（全局统一）
TIMESTAMP=$(date +"%Y%m%d-%H%M")

# ======================
# 工具函数
# ======================

# 检查服务名是否合法
is_valid_service() {
    local service="$1"
    for s in "${ALL_SERVICES[@]}"; do
        if [[ "$s" == "$service" ]]; then
            return 0  # 合法
        fi
    done
    return 1  # 非法
}

# 打印可用服务列表
print_available_services() {
    echo "可用服务:"
    printf '  %s\n' "${ALL_SERVICES[@]}"
}

# 交互式确认（仅用于全量构建）
confirm_full_build() {
    echo "💡 未指定服务，将构建以下全部模块："
    printf '  %s\n' "${ALL_SERVICES[@]}"
    echo

    read -rp "⚠️ 确定要构建以上 ${#ALL_SERVICES[@]} 个服务吗？(y/N): " confirm
    case "${confirm,,}" in
        y|yes) return 0 ;;
        *)     return 1 ;;
    esac
}

# ======================
# 核心构建逻辑
# ======================

# 校验构建目录是否满足要求
validate_build_dir() {
    local service="$1"
    local dir="./backend/$service"

    if [[ ! -d "$dir" ]]; then
        echo "❌ 错误: 目录不存在 '$dir'"
        exit 1
    fi

    if [[ ! -f "$dir/Dockerfile" ]]; then
        echo "❌ 错误: 缺少 Dockerfile ('$dir/Dockerfile')"
        exit 1
    fi

    if [[ ! -f "$dir/${service}.jar" ]]; then
        echo "❌ 错误: 缺少 JAR 文件 ('$dir/${service}.jar')"
        exit 1
    fi
}

# 构建单个服务镜像
build_single_image() {
    local service="$1"
    local dir="./backend/$service"
    local tag_latest="${service}:latest"
    local tag_ts="${service}:${TIMESTAMP}"

    echo "📦 构建服务: $service"
    echo "   标签: $tag_latest, $tag_ts"
    echo "   目录: $dir"

    docker build -t "$tag_latest" -t "$tag_ts" "$dir"
    echo "✅ $service 构建成功！"
    echo
}

# ======================
# 主流程控制
# ======================

main() {
    local target_services=()

    # 1. 解析参数
    if [[ $# -eq 0 ]]; then
        if ! confirm_full_build; then
            echo "🛑 操作已取消。"
            exit 0
        fi
        target_services=("${ALL_SERVICES[@]}")
    else
        # 校验每个参数
        for svc in "$@"; do
            if ! is_valid_service "$svc"; then
                echo "❌ 错误：无效的服务名 '$svc'"
                print_available_services
                exit 1
            fi
        done
        target_services=("$@")
    fi

    # 2. 输出摘要
    echo
    echo "🚀 开始构建服务: ${target_services[*]}"
    echo "🕒 时间戳: $TIMESTAMP"
    echo

    # 3. 逐个构建
    for svc in "${target_services[@]}"; do
        validate_build_dir "$svc"
        build_single_image "$svc"
    done

    echo "🎉 所有镜像构建完成！"
    echo "📌 运行 'docker images' 查看结果"
}

# ======================
# 启动主函数
# ======================

main "$@"
#!/bin/bash

# ========================================
# 批量下载服务 Jar 包（模块化版本）
# - 服务名 = OSS 路径名 = 本地目录名
# - 无参数：交互确认后下载全部
# - 有参数：下载指定服务（需在预定义列表中）
# ========================================

set -e

# ======================
# 全局配置
# ======================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo "已切换到脚本所在目录: $(pwd)"

OSS_BASE_URL="https://oss.dibdata.cn/c1-deploy/pro-toubao/"

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

# ======================
# 工具函数
# ======================

# 检查服务是否在合法列表中
is_valid_service() {
    local service="$1"
    for s in "${ALL_SERVICES[@]}"; do
        if [[ "$s" == "$service" ]]; then
            return 0
        fi
    done
    return 1
}

# 打印可用服务列表
# 打印可用服务列表
print_available_services() {
    echo "可用服务:"
    printf '  %s\n' "${ALL_SERVICES[@]}"
}

# 打印全部服务（用于确认提示）
print_all_services() {
    printf '  %s\n' "${ALL_SERVICES[@]}"
}

# 交互式确认是否下载全部
confirm_download_all() {
    echo "💡 未指定服务，将下载以下全部模块："
    print_all_services
    echo

    read -rp "⚠️ 确定要下载以上 ${#ALL_SERVICES[@]} 个服务吗？(y/N): " confirm
    case "${confirm,,}" in
        y|yes) return 0 ;;
        *)     return 1 ;;
    esac
}

# ======================
# 核心下载逻辑
# ======================

# 下载单个服务的 jar 包
download_single_service() {
    local service="$1"
    local local_dir="./backend/$service"

    local jar_url="$OSS_BASE_URL/$service/$service.jar"
    local jar_local_path="$local_dir/$service.jar"

    local dockerfile_url="$OSS_BASE_URL/$service/Dockerfile"
    local dockerfile_local_path="$local_dir/Dockerfile"

    mkdir -p "$local_dir"
    echo "⬇️ 正在下载 $service"

    echo "   $jar_url: $jar_url"
    echo "   保存为: $jar_local_path"
    wget -O "$jar_local_path" "$jar_url"

    echo "   dockerfile_url: $dockerfile_url"
    echo "   保存为: $dockerfile_local_path"
    wget -O "$dockerfile_local_path" "$dockerfile_url"
}

# 验证并解析命令行参数，返回目标服务列表
resolve_target_services() {
    if [[ $# -eq 0 ]]; then
        if ! confirm_download_all; then
            echo "🛑 操作已取消。"
            exit 0
        fi
        echo "${ALL_SERVICES[@]}"
    else
        # 校验每个参数
        for arg in "$@"; do
            if ! is_valid_service "$arg"; then
                echo "❌ 错误：无效的服务名 '$arg'"
                print_available_services
                exit 1
            fi
        done
        echo "$@"
    fi
}

# ======================
# 主流程
# ======================

main() {
    # 获取目标服务列表（通过函数解析）
    read -ra TARGET_SERVICES <<< "$(resolve_target_services "$@")"

    echo
    echo "✅ 开始处理以下模块：${TARGET_SERVICES[*]}"
    echo

    # 执行下载
    for service in "${TARGET_SERVICES[@]}"; do
        download_single_service "$service"
        echo
    done

    echo "🎉 所有任务已完成。"
}

# ======================
# 启动脚本
# ======================

main "$@"
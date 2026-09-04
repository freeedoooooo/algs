#!/bin/bash
# ============================================================
# DIB 微服务一键部署脚本
# ============================================================
# 用法:
#   bash 06-scripts/deploy-all.sh          # 全量部署
#   bash 06-scripts/deploy-all.sh infra    # 仅部署基础设施
#   bash 06-scripts/deploy-all.sh platform # 仅部署平台服务
#   bash 06-scripts/deploy-all.sh business # 仅部署业务服务
#   bash 06-scripts/deploy-all.sh delete   # 删除所有资源
# ============================================================

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 镜像版本（可通过环境变量覆盖）
export C1_VERSION="${C1_VERSION:-latest}"

# -------------------- 部署函数 --------------------

deploy_base() {
    log_step "部署基础配置..."

    log_info "  创建命名空间..."
    kubectl apply -f "${BASE_DIR}/02-config/namespace.yaml"

    log_info "  应用 ConfigMap..."
    kubectl apply -f "${BASE_DIR}/02-config/configmap.yaml"

    log_info "  应用镜像仓库认证..."
    kubectl apply -f "${BASE_DIR}/02-config/image-pull-secret.yaml"

    log_info "基础配置部署完成"
}

deploy_infra() {
    log_step "部署基础设施 (Nacos + Redis)..."

    log_info "  部署 Nacos..."
    kubectl apply -f "${BASE_DIR}/03-infra/nacos.yaml"

    log_info "  部署 Redis..."
    kubectl apply -f "${BASE_DIR}/03-infra/redis.yaml"

    log_info "等待基础设施就绪..."
    kubectl -n c1-idc-test rollout status deployment/nacos --timeout=120s
    kubectl -n c1-idc-test rollout status deployment/redis --timeout=60s

    log_info "基础设施部署完成"
}

deploy_platform() {
    log_step "部署平台服务..."

    log_info "  部署 auth-server / gateway / auth-resource / mdm..."
    kubectl apply -f "${BASE_DIR}/04-platform/all-services.yaml"

    log_info "等待平台服务就绪（首次启动较慢，请耐心等待）..."
    kubectl -n c1-idc-test rollout status deployment/auth-server --timeout=180s
    kubectl -n c1-idc-test rollout status deployment/gateway --timeout=180s
    kubectl -n c1-idc-test rollout status deployment/auth-resource --timeout=180s
    kubectl -n c1-idc-test rollout status deployment/mdm --timeout=180s

    log_info "平台服务部署完成"
}

deploy_business() {
    log_step "部署业务服务..."

    log_info "  部署 extract / report / data / rule / dg..."
    kubectl apply -f "${BASE_DIR}/05-business/all-services.yaml"

    log_info "等待业务服务就绪..."
    kubectl -n c1-idc-test rollout status deployment/service-extract --timeout=300s
    kubectl -n c1-idc-test rollout status deployment/service-report --timeout=180s
    kubectl -n c1-idc-test rollout status deployment/service-data --timeout=180s
    kubectl -n c1-idc-test rollout status deployment/service-rule --timeout=180s
    kubectl -n c1-idc-test rollout status deployment/data-dg --timeout=180s

    log_info "业务服务部署完成"
}

delete_all() {
    log_warn "即将删除 c1-idc-test 命名空间下的所有资源！"
    read -p "确认删除？(yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "取消删除"
        exit 0
    fi

    log_step "删除业务服务..."
    kubectl delete -f "${BASE_DIR}/05-business/all-services.yaml" --ignore-not-found

    log_step "删除平台服务..."
    kubectl delete -f "${BASE_DIR}/04-platform/all-services.yaml" --ignore-not-found

    log_step "删除基础设施..."
    kubectl delete -f "${BASE_DIR}/03-infra/nacos.yaml" --ignore-not-found
    kubectl delete -f "${BASE_DIR}/03-infra/redis.yaml" --ignore-not-found

    log_step "删除基础配置..."
    kubectl delete -f "${BASE_DIR}/02-config/image-pull-secret.yaml" --ignore-not-found
    kubectl delete -f "${BASE_DIR}/02-config/configmap.yaml" --ignore-not-found
    kubectl delete -f "${BASE_DIR}/02-config/namespace.yaml" --ignore-not-found

    log_info "所有资源已删除"
}

print_summary() {
    echo ""
    echo "============================================"
    echo "  DIB 微服务部署完成"
    echo "============================================"
    echo ""
    echo "  命名空间: c1-idc-test"
    echo "  镜像版本: ${C1_VERSION}"
    echo ""
    echo "  外部访问地址:"
    echo "    Gateway:       http://<NODE_IP>:30000"
    echo "    Auth Server:   http://<NODE_IP>:30090"
    echo ""
    echo "  内部服务地址 (K3s DNS):"
    echo "    Nacos:         http://nacos.c1-idc-test.svc.cluster.local:8848"
    echo "    Redis:         redis.c1-idc-test.svc.cluster.local:6379"
    echo "    Auth Server:   http://auth-server.c1-idc-test.svc.cluster.local:9090"
    echo "    Gateway:       http://gateway.c1-idc-test.svc.cluster.local:20000"
    echo "    Auth Resource: http://auth-resource.c1-idc-test.svc.cluster.local:20001"
    echo "    MDM:           http://mdm.c1-idc-test.svc.cluster.local:20002"
    echo "    Extract:       http://service-extract.c1-idc-test.svc.cluster.local:30001"
    echo "    Report:        http://service-report.c1-idc-test.svc.cluster.local:30002"
    echo "    Data:          http://service-data.c1-idc-test.svc.cluster.local:30003"
    echo "    Rule:          http://service-rule.c1-idc-test.svc.cluster.local:30004"
    echo "    DG:            http://data-dg.c1-idc-test.svc.cluster.local:30005"
    echo ""
    echo "  常用命令:"
    echo "    kubectl -n c1-idc-test get pods           # 查看 Pod 状态"
    echo "    kubectl -n c1-idc-test get svc            # 查看 Service"
    echo "    kubectl -n c1-idc-test logs -f <pod-name> # 查看日志"
    echo "    bash 06-scripts/verify.sh         # 运行健康检查"
    echo ""
    echo "============================================"
}

# -------------------- 主流程 --------------------

main() {
    local target="${1:-all}"

    echo ""
    echo "============================================"
    echo "  DIB 微服务部署脚本"
    echo "  目标: ${target}"
    echo "  镜像版本: ${C1_VERSION}"
    echo "============================================"
    echo ""

    # 检查 kubectl 可用性
    if ! command -v kubectl &>/dev/null; then
        log_error "kubectl 未安装或不在 PATH 中"
        exit 1
    fi

    case "${target}" in
        all)
            deploy_base
            deploy_infra
            deploy_platform
            deploy_business
            print_summary
            ;;
        base)
            deploy_base
            ;;
        infra)
            deploy_infra
            ;;
        platform)
            deploy_platform
            ;;
        business)
            deploy_business
            ;;
        delete)
            delete_all
            ;;
        *)
            log_error "未知目标: ${target}"
            echo "用法: $0 [all|base|infra|platform|business|delete]"
            exit 1
            ;;
    esac
}

main "$@"

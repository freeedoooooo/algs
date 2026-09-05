#!/bin/bash
# ============================================================
# DIB 微服务健康检查验证脚本
# ============================================================
# 用法:
#   bash 06-scripts/verify.sh          # 完整验证
#   bash 06-scripts/verify.sh quick    # 快速检查（仅 Pod 状态）
# ============================================================

set -uo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_ok()    { echo -e "  ${GREEN}[OK]${NC}   $*"; }
log_fail()  { echo -e "  ${RED}[FAIL]${NC} $*"; }
log_warn()  { echo -e "  ${YELLOW}[WARN]${NC} $*"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $*"; }

NAMESPACE="c1-idc-test"
PASS=0
FAIL=0

# -------------------- 检查函数 --------------------

check_pod_status() {
    local name="$1"
    local status
    status=$(kubectl -n "${NAMESPACE}" get pod -l "app=${name}" -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "NotFound")

    if [[ "$status" == "Running" ]]; then
        log_ok "${name}: Pod Running"
        PASS=$((PASS + 1))
    elif [[ "$status" == "Pending" ]]; then
        log_warn "${name}: Pod Pending (可能正在拉取镜像)"
        FAIL=$((FAIL + 1))
    else
        log_fail "${name}: Pod 状态异常 (${status})"
        FAIL=$((FAIL + 1))
    fi
}

check_readiness() {
    local name="$1"
    local ready
    ready=$(kubectl -n "${NAMESPACE}" get pod -l "app=${name}" -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")

    if [[ "$ready" == "True" ]]; then
        log_ok "${name}: Ready"
        PASS=$((PASS + 1))
    else
        log_fail "${name}: Not Ready"
        FAIL=$((FAIL + 1))
    fi
}

check_endpoint() {
    local name="$1"
    local port="$2"
    local path="$3"
    local url="http://${name}.${NAMESPACE}.svc.cluster.local:${port}${path}"

    # 从集群内节点执行
    local http_code
    http_code=$(kubectl -n "${NAMESPACE}" run curl-test --image=curlimages/curl --restart=Never --rm -i --timeout=10s -- curl -s -o /dev/null -w "%{http_code}" "${url}" 2>/dev/null || echo "000")

    if [[ "$http_code" == "200" ]]; then
        log_ok "${name}: HTTP ${http_code} (${path})"
        PASS=$((PASS + 1))
    else
        log_warn "${name}: HTTP ${http_code} (${path}) - 可能需要等待启动完成"
        FAIL=$((FAIL + 1))
    fi
}

check_service() {
    local name="$1"
    local port="$2"
    local cluster_ip
    cluster_ip=$(kubectl -n "${NAMESPACE}" get svc "${name}" -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "None")

    if [[ "$cluster_ip" != "None" && "$cluster_ip" != "" ]]; then
        log_ok "${name}: Service 已创建 (ClusterIP: ${cluster_ip}:${port})"
        PASS=$((PASS + 1))
    else
        log_fail "${name}: Service 未创建"
        FAIL=$((FAIL + 1))
    fi
}

# -------------------- 主流程 --------------------

main() {
    local mode="${1:-full}"

    echo ""
    echo "============================================"
    echo "  DIB 微服务健康检查"
    echo "  命名空间: ${NAMESPACE}"
    echo "  模式: ${mode}"
    echo "============================================"
    echo ""

    # ---------- 1. Pod 状态检查 ----------
    log_step "检查 Pod 状态..."
    echo ""

    # 基础设施
    check_pod_status "nacos"
    check_pod_status "redis"

    # 平台服务
    check_pod_status "c1-p-oauth"
    check_pod_status "c1-p-gateway"
    check_pod_status "c1-p-rbac"
    check_pod_status "c1-p-mdm"

    # 业务服务
    check_pod_status "c1-b-extract"
    check_pod_status "c1-b-report"
    check_pod_status "c1-b-data"
    check_pod_status "c1-b-rule"
    check_pod_status "c1-b-govern"

    echo ""

    # ---------- 2. Ready 状态检查 ----------
    if [[ "$mode" == "full" ]]; then
        log_step "检查 Ready 状态..."
        echo ""

        check_readiness "nacos"
        check_readiness "redis"
        check_readiness "c1-p-oauth"
        check_readiness "c1-p-gateway"
        check_readiness "c1-p-rbac"
        check_readiness "c1-p-mdm"
        check_readiness "c1-b-extract"
        check_readiness "c1-b-report"
        check_readiness "c1-b-data"
        check_readiness "c1-b-rule"
        check_readiness "c1-b-govern"

        echo ""

        # ---------- 3. Service 检查 ----------
        log_step "检查 Service..."
        echo ""

        check_service "nacos" "8848"
        check_service "redis" "6379"
        check_service "c1-p-oauth" "9090"
        check_service "c1-p-gateway" "20000"
        check_service "c1-p-rbac" "20001"
        check_service "c1-p-mdm" "20002"
        check_service "c1-b-extract" "30001"
        check_service "c1-b-report" "30002"
        check_service "c1-b-data" "30003"
        check_service "c1-b-rule" "30004"
        check_service "c1-b-govern" "30005"

        echo ""
    fi

    # ---------- 汇总 ----------
    echo "============================================"
    echo "  检查结果: ${GREEN}${PASS} 通过${NC}, ${RED}${FAIL} 失败${NC}"
    echo "============================================"
    echo ""

    # 显示资源概览
    log_step "资源概览:"
    echo ""
    kubectl -n "${NAMESPACE}" get pods -o wide
    echo ""

    if [[ $FAIL -gt 0 ]]; then
        log_warn "存在未就绪的服务，可尝试:"
        echo "  kubectl -n c1-idc-test describe pod <pod-name>  # 查看详细事件"
        echo "  kubectl -n c1-idc-test logs <pod-name>          # 查看容器日志"
        echo ""
        exit 1
    fi

    log_ok "所有服务运行正常"
}

main "$@"

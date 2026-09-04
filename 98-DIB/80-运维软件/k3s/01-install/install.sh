#!/bin/bash
# ============================================================
# K3s 集群安装脚本
# ============================================================
# 支持两种角色:
#   server  - 控制面节点（必须首先安装，有且仅有一个）
#   agent   - 工作节点（可多个，加入 server 组成集群）
#
# 用法:
#   # 在 server 节点执行:
#   bash install.sh server
#
#   # 在 agent 节点执行（需要 server 的 IP 和 token）:
#   bash install.sh agent --server-ip 10.0.6.100 --token K10xxxxx
#
#   # 卸载:
#   bash install.sh --uninstall
# ============================================================

set -euo pipefail

# -------------------- 配置区 --------------------
# 私有镜像仓库地址（HTTP 协议）
REGISTRY_URL="10.0.6.183:8088"

# K3s 版本
K3S_VERSION="v1.30.4+k3s1"

# K3s 安装脚本下载地址（国内加速）
K3S_INSTALL_URL="https://rancher-mirror.rancher.cn/k3s/k3s-install.sh"

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

# -------------------- 公共函数 --------------------

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "请使用 root 用户执行此脚本"
        exit 1
    fi
}

check_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        log_info "操作系统: ${PRETTY_NAME}"
    else
        log_error "无法识别操作系统版本"
        exit 1
    fi
}

configure_registry() {
    log_info "配置私有镜像仓库: ${REGISTRY_URL}"
    mkdir -p /etc/rancher/k3s

    cat > /etc/rancher/k3s/registries.yaml <<EOF
mirrors:
  "${REGISTRY_URL}":
    endpoint:
      - "http://${REGISTRY_URL}"
EOF

    log_info "registries.yaml 已写入"
}

wait_for_ready() {
    log_info "等待节点就绪..."
    local retries=0
    local max_retries=30
    while [[ $retries -lt $max_retries ]]; do
        if kubectl get nodes 2>/dev/null | grep -q "Ready"; then
            break
        fi
        retries=$((retries + 1))
        echo -n "."
        sleep 2
    done
    echo ""

    if kubectl get nodes 2>/dev/null | grep -q "Ready"; then
        return 0
    else
        return 1
    fi
}

# -------------------- Server 安装 --------------------

install_server() {
    log_step "安装 K3s Server 节点..."

    configure_registry

    export INSTALL_K3S_MIRROR=cn
    export INSTALL_K3S_VERSION="${K3S_VERSION}"

    curl -sfL "${K3S_INSTALL_URL}" | INSTALL_K3S_EXEC="server \
        --disable traefik \
        --write-kubeconfig-mode 644 \
        --node-label role=dib-server \
        --tls-san $(hostname -I | awk '{print $1}') \
        --tls-san $(hostname)" \
    sh -s -

    log_info "K3s Server 安装完成"

    # 配置 kubectl
    mkdir -p ~/.kube
    cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
    chmod 600 ~/.kube/config
    ln -sf /usr/local/bin/kubectl /usr/bin/kubectl 2>/dev/null || true

    # 等待就绪
    if wait_for_ready; then
        log_info "节点状态:"
        kubectl get nodes -o wide
        echo ""
        kubectl cluster-info
    else
        log_error "节点未就绪，请检查: journalctl -u k3s"
        exit 1
    fi

    # 输出 Agent 加入信息
    local server_ip
    server_ip=$(hostname -I | awk '{print $1}')
    local token
    token=$(cat /var/lib/rancher/k3s/server/node-token)

    echo ""
    echo "============================================"
    echo "  K3s Server 安装成功！"
    echo "============================================"
    echo ""
    echo "  Server IP:  ${server_ip}"
    echo "  K3s 版本:   ${K3S_VERSION}"
    echo ""
    echo "  Agent 节点加入命令:"
    echo "  ─────────────────────────────────────────"
    echo "  bash install.sh agent \\"
    echo "    --server-ip ${server_ip} \\"
    echo "    --token ${token}"
    echo "  ─────────────────────────────────────────"
    echo ""
    echo "  将上面的 install.sh 和此命令复制到 Agent 节点执行即可。"
    echo ""
    echo "  Kuboard 连接信息:"
    echo "    API Server: https://${server_ip}:6443"
    echo "    获取 Token: kubectl -n kube-system get secret \\"
    echo "      \$(kubectl -n kube-system get secret | grep kuboard-sa | awk '{print \$1}') \\"
    echo "      -o jsonpath={.data.token} | base64 -d"
    echo ""
    echo "============================================"
}

# -------------------- Agent 安装 --------------------

install_agent() {
    local server_ip=""
    local token=""

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --server-ip)
                server_ip="$2"
                shift 2
                ;;
            --token)
                token="$2"
                shift 2
                ;;
            *)
                log_error "未知参数: $1"
                echo "用法: bash install.sh agent --server-ip <IP> --token <TOKEN>"
                exit 1
                ;;
        esac
    done

    if [[ -z "$server_ip" || -z "$token" ]]; then
        log_error "缺少必要参数"
        echo ""
        echo "用法: bash install.sh agent --server-ip <Server_IP> --token <TOKEN>"
        echo ""
        echo "参数说明:"
        echo "  --server-ip   Server 节点的 IP 地址"
        echo "  --token       Server 节点的 node-token"
        echo "                获取方式: cat /var/lib/rancher/k3s/server/node-token"
        echo ""
        exit 1
    fi

    log_step "安装 K3s Agent 节点..."
    log_info "Server: ${server_ip}"

    configure_registry

    export INSTALL_K3S_MIRROR=cn
    export INSTALL_K3S_VERSION="${K3S_VERSION}"

    curl -sfL "${K3S_INSTALL_URL}" | K3S_URL="https://${server_ip}:6443" \
        K3S_TOKEN="${token}" \
        INSTALL_K3S_EXEC="agent \
        --node-label role=dib-worker" \
    sh -s -

    log_info "K3s Agent 安装完成，正在加入集群..."

    # 等待节点就绪（agent 节点没有 kubectl，通过检查进程判断）
    sleep 5
    if systemctl is-active --quiet k3s-agent; then
        log_info "Agent 节点已成功加入集群"
        echo ""
        echo "============================================"
        echo "  K3s Agent 安装成功！"
        echo "============================================"
        echo ""
        echo "  已加入 Server: ${server_ip}"
        echo ""
        echo "  请在 Server 节点执行以下命令确认:"
        echo "    kubectl get nodes -o wide"
        echo ""
        echo "============================================"
    else
        log_error "Agent 节点启动失败，请检查: journalctl -u k3s-agent"
        exit 1
    fi
}

# -------------------- 卸载 --------------------

uninstall() {
    log_warn "即将卸载 K3s，所有 Pod 和数据将被清除！"
    read -p "确认卸载？(yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "取消卸载"
        exit 0
    fi

    log_info "卸载 K3s..."

    # 尝试卸载 server 或 agent
    if [[ -f /usr/local/bin/k3s-uninstall.sh ]]; then
        /usr/local/bin/k3s-uninstall.sh
    elif [[ -f /usr/local/bin/k3s-agent-uninstall.sh ]]; then
        /usr/local/bin/k3s-agent-uninstall.sh
    else
        log_warn "未找到卸载脚本"
    fi

    # 清理残留
    rm -rf /etc/rancher/k3s
    rm -rf /var/lib/rancher/k3s
    rm -f ~/.kube/config

    log_info "K3s 已卸载"
}

# -------------------- 使用帮助 --------------------

print_usage() {
    echo ""
    echo "============================================"
    echo "  DIB 微服务 K3s 集群安装脚本"
    echo "============================================"
    echo ""
    echo "用法:"
    echo "  bash install.sh server                        # 安装 Server 节点"
    echo "  bash install.sh agent --server-ip IP --token T # 安装 Agent 节点"
    echo "  bash install.sh --uninstall                   # 卸载"
    echo ""
    echo "集群安装步骤:"
    echo "  1. 在 Server 节点执行: bash install.sh server"
    echo "  2. 记录输出中的 Agent 加入命令"
    echo "  3. 将 install.sh 复制到每个 Agent 节点"
    echo "  4. 在 Agent 节点执行第 1 步输出的加入命令"
    echo "  5. 回到 Server 节点执行 kubectl get nodes 确认所有节点就绪"
    echo ""
}

# -------------------- 主流程 --------------------

main() {
    check_root
    check_os

    local role="${1:-}"

    case "${role}" in
        server)
            install_server
            ;;
        agent)
            shift
            install_agent "$@"
            ;;
        --uninstall|-u)
            uninstall
            ;;
        --help|-h|"")
            print_usage
            ;;
        *)
            log_error "未知命令: ${role}"
            print_usage
            exit 1
            ;;
    esac
}

main "$@"

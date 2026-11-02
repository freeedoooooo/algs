#!/bin/bash


# --- 新增开始 ---
# 1. 定义 PATH，确保能找到 gunicorn
export PATH=/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin


# ================= 配置区域 =================
# OCR 后端端口 (避开 Nginx 已占用的 8090)
PORT_NPU0=8088
PORT_NPU1=8089

# 项目路径 (请根据实际情况修改，确保能找到 simple_ocr_server.py)
WORK_DIR="/root/simple_ocr"
# 如果使用虚拟环境，请激活它，例如：source /opt/venv/bin/activate

# 日志文件路径
LOG_NPU0="${WORK_DIR}/simple_ocr_npu0.log"
LOG_NPU1="${WORK_DIR}/simple_ocr_npu1.log"

# ===========================================

echo "=========================================="
echo "开始重启 OCR 双卡负载均衡服务..."
echo "NPU 0 -> Port: ${PORT_NPU0}"
echo "NPU 1 -> Port: ${PORT_NPU1}"
echo "=========================================="

# 1. 停止旧的 OCR 进程
echo "[1/4] 正在清理旧的 gunicorn 进程..."
pkill -f "simple_ocr_server:app"
sleep 2

# 再次检查是否还有残留
if pgrep -f "simple_ocr_server:app" > /dev/null; then
    echo "警告：仍有进程未退出，强制杀死..."
    pkill -9 -f "simple_ocr_server:app"
    sleep 1
fi
echo "清理完成。"

# 2. 启动 NPU 0 服务
echo "[2/4] 正在启动 NPU 0 服务 (Port ${PORT_NPU0})..."
cd ${WORK_DIR}
DEVICE=npu:0 USE_TORCH=False PORT=${PORT_NPU0} nohup gunicorn -w 2 --threads 16 -b 0.0.0.0:${PORT_NPU0} simple_ocr_server:app 2>&1 > ${LOG_NPU0} &
PID0=$!
echo "NPU 0 进程 ID: ${PID0}"

# 3. 启动 NPU 1 服务
echo "[3/4] 正在启动 NPU 1 服务 (Port ${PORT_NPU1})..."
DEVICE=npu:1 USE_TORCH=False PORT=${PORT_NPU1} nohup gunicorn -w 2 --threads 16 -b 0.0.0.0:${PORT_NPU1} simple_ocr_server:app 2>&1 > ${LOG_NPU1} &
PID1=$!
echo "NPU 1 进程 ID: ${PID1}"

# 等待几秒让服务初始化
sleep 5

# 4. 检查端口监听状态
echo "[4/4] 验证端口监听状态..."
if netstat -tlnp | grep -q ":${PORT_NPU0}"; then
    echo "✅ 端口 ${PORT_NPU0} 监听正常"
else
    echo "❌ 端口 ${PORT_NPU0} 启动失败，请检查日志：tail -f ${LOG_NPU0}"
    exit 1
fi

if netstat -tlnp | grep -q ":${PORT_NPU1}"; then
    echo "✅ 端口 ${PORT_NPU1} 监听正常"
else
    echo "❌ 端口 ${PORT_NPU1} 启动失败，请检查日志：tail -f ${LOG_NPU1}"
    exit 1
fi

echo "=========================================="
echo "🎉 OCR 双卡负载均衡服务重启完成!"
echo "访问地址: http://<服务器IP>/api/ocr/<你的接口路径>"
echo "日志查看: tail -f ${LOG_NPU0} 或 tail -f ${LOG_NPU1}"
echo "=========================================="
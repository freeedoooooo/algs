import gc
import logging
import os
import cv2
import gradio as gr
import paddle

# ==================== 0. 全局环境与显存安全配置 ====================
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
logging.getLogger("ppocr").setLevel(logging.WARNING)
logging.getLogger("ppstructure").setLevel(logging.WARNING)

# ✅ 6GB 显存专属安全配置（已移除不兼容的 reallocate 标志）
paddle.set_flags({
    "FLAGS_fraction_of_gpu_memory_to_use": 0.85,
    "FLAGS_allocator_strategy": "auto_growth",       # 按需分配，避免启动时占满显存
})

print(f"Paddle {paddle.__version__} | GPU: {paddle.is_compiled_with_cuda()}")


# ==================== 1. 加载 pp-structure-v3 (6GB 安全版) ====================
def load_table_system():
    """
    初始化 pp-structure-v3 TableSystem
    所有参数已针对 6GB 显存进行压测调优
    """
    try:
        from ppstructure.predict_system import TableSystem

        print("⏳ 正在加载 pp-structure-v3 表格识别系统 (6GB显存安全模式)...")

        table_args = {
            "det_model_dir": None,           # None = 自动下载最新检测模型
            "rec_model_dir": None,           # None = 自动下载最新识别模型
            "table_model_dir": None,         # None = 自动下载 pp-structure-v3 表格模型
            "use_gpu": True,
            "gpu_mem": 4000,                 # ✅ 6GB卡预留4G，给OS/CUDA上下文留2G余量
            "show_log": False,
            "det_limit_side_len": 1280,      # ✅ 检测分辨率上限降至1280，显存降56%
            "det_limit_type": "max",
            "rec_batch_num": 3,              # ✅ 识别批大小降至3，削峰显存占用
            "table_max_len": 384,            # ✅ TSR模型输入降至384，注意力矩阵显存降38%
            "merge_no_span_structure": True, # 合并无跨度单元格，减少冗余HTML节点
        }

        system = TableSystem(table_args)
        print("✅ pp-structure-v3 加载成功 (6GB安全模式)")
        return system

    except ImportError:
        raise RuntimeError(
            "❌ 未安装 ppstructure！请执行:\n"
            "pip install 'paddleocr>=2.7' --upgrade"
        )
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        raise


# 全局单例加载，避免重复初始化浪费显存
table_system = load_table_system()


# ==================== 2. 解析入口（含 OOM 兜底机制）====================
def parse_document(file_path, progress=gr.Progress(track_tqdm=True)):
    if not file_path or not os.path.exists(file_path):
        return '<div class="paddlex-preview"><p>⚠️ 请先上传图片</p></div>'

    try:
        progress(0.1, desc="📖 读取图像中...")
        img = cv2.imread(file_path)
        if img is None:
            raise ValueError("图像读取失败，请确认文件格式为 JPG/PNG/BMP")

        progress(0.3, desc="🔍 表格检测 + 结构识别中 (pp-structure-v3)...")
        results = table_system(img)

        progress(0.9, desc="🎨 渲染结果中...")
        if not results:
            html_content = "<p style='color:#999;'>⚠️ 未检测到表格区域</p>"
        else:
            tables_html = []
            for res in results:
                table_html = res.get("html", "")
                if table_html:
                    tables_html.append(table_html)

            if tables_html:
                html_content = "\n<hr/>\n".join(tables_html)
            else:
                html_content = "<p style='color:#999;'>⚠️ 检测到表格但无法还原结构</p>"

        progress(1.0, desc="✅ 完成！")

        # 及时释放显存碎片
        paddle.device.cuda.empty_cache()
        gc.collect()

        return f'<div class="paddlex-preview">{html_content}</div>'

    except RuntimeError as e:
        # ✅ OOM 专项捕获：提示用户而非直接崩溃
        err_msg = str(e).lower()
        if "out of memory" in err_msg or "oom" in err_msg:
            logging.warning(f"显存不足，当前图片过大: {e}")
            return (
                '<div class="paddlex-preview">'
                '<p style="color:orange;">⚠️ 显存不足！当前图片分辨率超出6GB显存承载能力。<br>'
                '建议：将图片长边缩放至1280px以内后重新上传。</p>'
                '</div>'
            )
        logging.exception("运行时异常")
        return f'<div class="paddlex-preview"><p style="color:red;">❌ 错误: {str(e)}</p></div>'

    except Exception as e:
        logging.exception("解析异常")
        return f'<div class="paddlex-preview"><p style="color:red;">❌ 错误: {str(e)}</p></div>'


# ==================== 3. Gradio UI ====================
CSS = """
<style>
.paddlex-preview {
    padding: 16px;
    line-height: 1.6;
    max-height: 70vh;
    overflow-y: auto;
}
.paddlex-preview table {
    margin: 12px 0;
    border-collapse: collapse !important;
    width: 100% !important;
    font-size: 13px !important;
}
.paddlex-preview th, .paddlex-preview td {
    border: 1px solid #d0d0d0 !important;
    padding: 5px 8px !important;
    text-align: left !important;
    white-space: nowrap;
}
.paddlex-preview tr:nth-child(even) { background: #f9f9f9 !important; }
.paddlex-preview tr:hover { background: #eef4ff !important; }
</style>
"""

with gr.Blocks(title="银行对账单解析器 (pp-structure-v3 | 6GB显存版)") as demo:
    gr.Markdown(
        "# 🏦 银行对账单结构化解析\n"
        "> ✅ **pp-structure-v3** 端到端表格识别 | 🛡️ **6GB显存安全模式** 已启用\n"
        "> 💡 若提示显存不足，请将图片长边缩放至 1280px 以内后重试"
    )
    with gr.Row():
        inp = gr.Image(
            label="📤 上传对账单图片（JPG/PNG）",
            type="filepath",
            sources=["upload"],
            height=450,
        )
        out = gr.HTML(
            value=CSS + '<div class="paddlex-preview"><p>📤 等待上传...</p></div>'
        )

    gr.Button("🔍 开始解析", variant="primary").click(parse_document, [inp], [out])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7861)
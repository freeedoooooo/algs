import gc
import logging
import os
import re

import gradio as gr
import numpy as np
import paddle

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
logging.getLogger("paddlex").setLevel(logging.WARNING)

# 8GB 显存安全配置
paddle.set_flags({"FLAGS_fraction_of_gpu_memory_to_use": 0.85})
print(f"Paddle {paddle.__version__} | GPU: {paddle.is_compiled_with_cuda()}")


# ==================== 加载基础 OCR 产线 ====================
def load_ocr_pipeline():
    try:
        from paddlex import create_pipeline

        print("⏳ 正在加载基础 OCR 产线 (PaddleX 3.x)...")
        pipeline = create_pipeline(
            pipeline="OCR",
            device="gpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
        )
        print("✅ OCR 产线加载成功")
        return pipeline
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        raise


ocr_pipeline = load_ocr_pipeline()


# ==================== 核心：基于坐标的表格重建算法 ====================
def rebuild_table_from_ocr(ocr_result):
    """适配 PaddleX 3.x OCR 返回结构的表格重建（修复 NumPy 布尔歧义）"""
    items = []

    # 1. 安全获取第一个结果
    if hasattr(ocr_result, "__iter__") and not isinstance(ocr_result, dict):
        res = next(iter(ocr_result))
    else:
        res = ocr_result

    # 🔑 2. 兼容 PaddleX 3.x 字段（避免对 ndarray 使用 or 运算符）
    boxes, texts = None, None
    if isinstance(res, dict):
        # 按优先级逐个检查，不使用 or 连接
        for key in ("rec_boxes", "dt_polys"):
            val = res.get(key)
            if val is not None and len(val) > 0:
                boxes = val
                break
        for key in ("rec_texts", "rec_text"):
            val = res.get(key)
            if val is not None and len(val) > 0:
                texts = val
                break
        # 兜底旧版嵌套结构
        if boxes is None or texts is None:
            rec_res = res.get("rec_res", {})
            if isinstance(rec_res, dict):
                if boxes is None:
                    boxes = rec_res.get("boxes")
                if texts is None:
                    texts = rec_res.get("texts")
    else:
        for attr in ("rec_boxes", "dt_polys"):
            val = getattr(res, attr, None)
            if val is not None and len(val) > 0:
                boxes = val
                break
        for attr in ("rec_texts", "rec_text"):
            val = getattr(res, attr, None)
            if val is not None and len(val) > 0:
                texts = val
                break

    # 统一转为 Python list，避免后续 NumPy 索引问题
    if isinstance(boxes, np.ndarray):
        boxes = boxes.tolist()
    if isinstance(texts, np.ndarray):
        texts = texts.tolist()

    if not boxes or not texts or len(boxes) != len(texts):
        box_len = len(boxes) if boxes is not None else 0
        text_len = len(texts) if texts is not None else 0
        return (
            f"<p style='color:#999;'>⚠️ 字段解析失败: boxes={box_len}, texts={text_len}<br>"
            "请检查控制台打印的原始返回结构</p>"
        )

    # 3. 提取坐标与文本
    for box, text in zip(boxes, texts):
        txt = str(text).strip()
        if not txt:
            continue
        try:
            if isinstance(box, (list, tuple)) and len(box) == 4:
                if isinstance(box[0], (list, tuple)):
                    y_center = sum(p[1] for p in box) / 4
                    x_start = min(p[0] for p in box)
                else:
                    y_center = (box[1] + box[3]) / 2
                    x_start = box[0]
            else:
                continue
            items.append({"y": y_center, "x": x_start, "text": txt})
        except (TypeError, IndexError, ValueError):
            continue

    if not items:
        return "<p style='color:#999;'>⚠️ 有效文字提取为空</p>"

    # 4. 动态行聚类
    items.sort(key=lambda i: i["y"])
    avg_height = 20
    rows = []
    current_row = [items[0]]

    for item in items[1:]:
        tolerance = max(10, avg_height * 0.6)
        if abs(item["y"] - current_row[-1]["y"]) < tolerance:
            current_row.append(item)
            ys = [i["y"] for i in current_row]
            avg_height = (max(ys) - min(ys)) / max(len(ys) - 1, 1) or 20
        else:
            rows.append(sorted(current_row, key=lambda i: i["x"]))
            current_row = [item]
            avg_height = 20
    rows.append(sorted(current_row, key=lambda i: i["x"]))

    # 5. 生成 HTML 表格
    html = [
        '<table border="1" cellspacing="0" cellpadding="6" '
        'style="border-collapse:collapse;width:100%;font-size:14px;">'
    ]
    for row in rows:
        html.append("<tr>")
        for cell in row:
            txt = cell["text"]
            if re.match(r"^0[\d,]*\.\d+$", txt):
                clean = txt.replace(",", "").lstrip("0")
                if clean.startswith("."):
                    clean = "0" + clean
                txt = f"<b>{clean}</b>"
            html.append(f"<td>{txt}</td>")
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)


# ==================== 解析入口 ====================
def parse_document(file_path, progress=gr.Progress(track_tqdm=True)):
    if not file_path or not os.path.exists(file_path):
        return '<div class="paddlex-preview"><p>⚠️ 请先上传文件</p></div>'

    try:
        progress(0.2, desc="🔍 OCR 识别中...")
        result = ocr_pipeline.predict(file_path)
        progress(0.8, desc="📊 重建表格结构中...")
        table_html = rebuild_table_from_ocr(result)
        progress(1.0, desc="✅ 完成！")

        paddle.device.cuda.empty_cache()
        gc.collect()
        return f'<div class="paddlex-preview">{table_html}</div>'

    except Exception as e:
        logging.exception("解析异常")
        return f'<div class="paddlex-preview"><p style="color:red;">❌ 错误: {str(e)}</p></div>'


# ==================== UI ====================
CSS = """
<style>
.paddlex-preview { padding: 16px; line-height: 1.6; }
.paddlex-preview table { margin: 10px 0; }
.paddlex-preview th, .paddlex-preview td {
    border: 1px solid #ccc; padding: 6px 10px; text-align: left;
}
.paddlex-preview tr:nth-child(even) { background: #fafafa; }
</style>
"""

with gr.Blocks(title="银行对账单解析器") as demo:
    gr.Markdown(
        "# 🏦 银行对账单结构化解析\n"
        "> 基于 PaddleX 3.x OCR + 动态坐标聚类算法，专治弱边框表格"
    )
    with gr.Row():
        inp = gr.File(
            label="上传图片/PDF", file_types=["image", ".pdf"], type="filepath"
        )
        out = gr.HTML(
            value=CSS + '<div class="paddlex-preview"><p>📤 等待上传...</p></div>'
        )
    gr.Button("🔍 开始解析", variant="primary").click(parse_document, [inp], [out])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7861)
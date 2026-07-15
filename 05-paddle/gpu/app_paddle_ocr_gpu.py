import logging
import os

import gradio as gr
import numpy as np
from PIL import ImageDraw, ImageFont
from paddleocr import PaddleOCR

# 屏蔽检查 & 日志
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
logging.getLogger("paddleocr").setLevel(logging.INFO)

# 👇 2.9.x 经典 API
ocr = PaddleOCR(
    use_gpu=True,                          # 👈 2.9.x 用 use_gpu
    enable_mkldnn=False,                   # GPU 下关闭 oneDNN
    use_angle_cls=True,                    # 👈 2.9.x 用 use_angle_cls
    lang="ch",                             # 👈 2.9.x 支持 lang 参数
    det_model_dir=None,                    # None = 自动下载 PP-OCRv4
    rec_model_dir=None,
    cls_model_dir=None,
    det_db_thresh=0.35,
    det_db_box_thresh=0.15,
    det_db_unclip_ratio=1.5,
    det_limit_side_len=1280,
    show_log=True,
)

import paddle
print(f"PaddlePaddle GPU 可用: {paddle.device.is_compiled_with_cuda()}")
print(f"当前设备: {paddle.device.get_device()}")


def draw_ocr_boxes(image, ocr_result):
    """在原图上绘制 OCR 检测框和识别文本"""
    img = image.copy()
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("msyh.ttc", size=max(12, int(min(img.size) * 0.03)))
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                                      size=max(12, int(min(img.size) * 0.03)))
        except Exception:
            font = ImageFont.load_default()

    txt_lines = []
    info_lines = []
    md_lines = ["## 📄 OCR 识别结果\n"]

    # 👇 2.9.x 返回格式: List[List[ [box, (text, score)] ]]
    for page in ocr_result:
        if page is None:
            continue
        for line in page:
            box = line[0]
            text, score = line[1]

            points = [(int(p[0]), int(p[1])) for p in box]
            draw.polygon(points, outline="#FF4444", width=2)
            label = f"{text} ({score:.2f})"
            x, y = points[0][0], max(0, points[0][1] - 20)
            draw.text((x, y), label, fill="#FF4444", font=font)

            txt_lines.append(text)
            info_lines.append(f"{text} (置信度: {score:.4f})")
            md_lines.append(f"- **{text}** _(置信度: {score:.2f})_")

    return img, "\n".join(txt_lines), "\n".join(info_lines), "\n".join(md_lines)


def recognize_image(image):
    if image is None:
        return None, "", "请上传图片", "### ⚠️ 请先上传图片"

    result = ocr.ocr(np.array(image), cls=True)  # 👈 2.9.x 用 ocr() 方法
    annotated_img, full_text, detail_info, md_content = draw_ocr_boxes(image, result)

    return (
        annotated_img,
        full_text,
        detail_info if detail_info else "未识别到文字",
        md_content if md_content.strip() else "### ⚠️ 未识别到文字"
    )


with gr.Blocks(title="PaddleOCR 可视化测试") as demo:
    gr.Markdown("# 📝 PaddleOCR 可视化识别测试\n上传图片后，左侧显示带检测框的结果图，右侧显示识别文本")

    with gr.Row():
        img_input = gr.Image(type="pil", label="📤 上传原图")
        img_output = gr.Image(type="pil", label="🖼️ OCR 结果可视化", elem_classes=["output-image"])

    with gr.Row():
        text_output = gr.Textbox(label="识别文本", lines=8)
        detail_output = gr.Textbox(label="详细信息(含置信度)", lines=8)

    md_output = gr.Markdown(value="### 📭 等待上传图片...")

    btn = gr.Button("🔍 开始识别", variant="primary", size="lg")
    btn.click(
        fn=recognize_image,
        inputs=img_input,
        outputs=[img_output, text_output, detail_output, md_output]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        theme=gr.themes.Default(),
        css="""
            .output-image img { object-fit: contain !important; max-height: 600px; }
        """
    )
import os
import logging
import gradio as gr
from paddleocr import PaddleOCR
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 屏蔽检查 & 日志
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
logging.getLogger("paddleocr").setLevel(logging.WARNING)

ocr = PaddleOCR(
    use_textline_orientation=True,
    lang="ch",
    # 🔧 核心修改：指定移动端/服务器端模型
    text_detection_model_name="PP-OCRv4_mobile_det",     # 识别模型换为 mobile
    text_recognition_model_name="PP-OCRv4_mobile_rec"    # 检测模型换为 mobile
)

def draw_ocr_boxes(image, ocr_result):
    """在原图上绘制 OCR 检测框和识别文本"""
    img = image.copy()
    draw = ImageDraw.Draw(img)

    # 尝试加载中文字体，失败则用默认字体
    try:
        font = ImageFont.truetype("msyh.ttc", size=max(12, int(min(img.size) * 0.03)))
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", size=max(12, int(min(img.size) * 0.03)))
        except Exception:
            font = ImageFont.load_default()

    txt_lines = []
    info_lines = []

    for res in ocr_result:
        # 兼容 3.x 返回结构
        if hasattr(res, 'dt_polys') and hasattr(res, 'rec_texts'):
            boxes = res.dt_polys
            texts = res.rec_texts
            scores = res.rec_scores
        elif isinstance(res, dict):
            boxes = res.get('dt_polys', [])
            texts = res.get('rec_texts', [])
            scores = res.get('rec_scores', [])
        else:
            continue

        for box, text, score in zip(boxes, texts, scores):
            # box 格式: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            points = [(int(p[0]), int(p[1])) for p in box]
            # 绘制四边形检测框
            draw.polygon(points, outline="#FF4444", width=2)
            # 在框上方绘制文本标签
            label = f"{text} ({score:.2f})"
            x, y = points[0][0], max(0, points[0][1] - 20)
            draw.text((x, y), label, fill="#FF4444", font=font)

            txt_lines.append(text)
            info_lines.append(f"{text} (置信度: {score:.4f})")

    return img, "\n".join(txt_lines), "\n".join(info_lines)


def recognize_image(image):
    if image is None:
        return None, "", "请上传图片"

    result = ocr.predict(np.array(image))
    annotated_img, full_text, detail_info = draw_ocr_boxes(image, result)

    return annotated_img, full_text, detail_info if detail_info else "未识别到文字"


with gr.Blocks(title="PaddleOCR 可视化测试", css="""
    .output-image img { object-fit: contain !important; max-height: 600px; }
""") as demo:
    gr.Markdown("# 📝 PaddleOCR 可视化识别测试\n上传图片后，左侧显示带检测框的结果图，右侧显示识别文本")

    with gr.Row():
        img_input = gr.Image(type="pil", label="📤 上传原图")
        img_output = gr.Image(type="pil", label="🖼️ OCR 结果可视化", elem_classes=["output-image"])

    with gr.Row():
        text_output = gr.Textbox(label="识别文本", lines=8)
        detail_output = gr.Textbox(label="详细信息(含置信度)", lines=8)

    btn = gr.Button("🔍 开始识别", variant="primary", size="lg")
    btn.click(
        fn=recognize_image,
        inputs=img_input,
        outputs=[img_output, text_output, detail_output]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
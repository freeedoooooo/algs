import os
import logging
import gradio as gr
from paddleocr import PaddleOCR
import numpy as np

# 屏蔽模型源检查 & 日志
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
logging.getLogger("paddleocr").setLevel(logging.WARNING)

# 新版初始化：方向分类在初始化时配置，调用时不再传 cls
ocr = PaddleOCR(
    use_textline_orientation=True,
    lang="ch"
)

def recognize_image(image):
    if image is None:
        return "", "请上传图片"

    # 🔧 修复: 去掉 cls=True，改用 predict()
    result = ocr.predict(np.array(image))

    txt_lines = []
    info_lines = []

    # 🔧 适配 3.x 返回结构
    # 3.x predict() 返回生成器/列表，每个元素是单张图片的结果对象
    for res in result:
        # res 可能是 dict 或自定义对象，兼容两种访问方式
        if hasattr(res, 'rec_texts'):
            texts = res.rec_texts
            scores = res.rec_scores
        elif isinstance(res, dict):
            texts = res.get('rec_texts', [])
            scores = res.get('rec_scores', [])
        else:
            # 兜底：尝试按旧版嵌套列表解析
            try:
                for line in res:
                    box, (text, confidence) = line
                    txt_lines.append(text)
                    info_lines.append(f"{text} (置信度: {confidence:.4f})")
                continue
            except Exception:
                continue

        for text, score in zip(texts, scores):
            txt_lines.append(text)
            info_lines.append(f"{text} (置信度: {score:.4f})")

    full_text = "\n".join(txt_lines)
    detail_info = "\n".join(info_lines)

    return full_text, detail_info if detail_info else "未识别到文字"


with gr.Blocks(title="PaddleOCR Web 测试") as demo:
    gr.Markdown("# 📝 PaddleOCR 在线识别测试")
    with gr.Row():
        img_input = gr.Image(type="pil", label="上传图片")
        with gr.Column():
            text_output = gr.Textbox(label="识别文本", lines=10)
            detail_output = gr.Textbox(label="详细信息(含置信度)", lines=10)

    btn = gr.Button("🔍 开始识别", variant="primary")
    btn.click(fn=recognize_image, inputs=img_input, outputs=[text_output, detail_output])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
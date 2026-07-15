import os

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import logging
import numpy as np
import gradio as gr
from PIL import Image

logging.getLogger("paddlex").setLevel(logging.INFO)


def get_available_pipeline():
    from paddlex import create_pipeline

    candidates = [
        "layout_parsing",
        "PP-StructureV3",
        "doc_parsing",
    ]

    last_error = None
    for name in candidates:
        # 👇 修改1: 将 device 改为 gpu，并增加 GPU 优先的参数组合
        param_variants = [
            {
                "device": "gpu",                          # 👈 cpu → gpu
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
            },
            {"device": "gpu"},                            # 👈 cpu → gpu
        ]

        for params in param_variants:
            try:
                print(f"🔍 正在尝试: {name} | 参数: {list(params.keys())}")
                pipeline = create_pipeline(pipeline=name, **params)
                print(f"✅ 成功加载流水线: {name} (GPU)")
                return pipeline, name
            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    continue
                raise
            except Exception as e:
                last_error = e
                print(f"⚠️ '{name}' 不可用: {str(e)[:300]}")
                break

    raise RuntimeError(
        f"❌ 所有候选流水线均不可用！\n最后一条错误: {last_error}\n"
        f"请运行: python -c \"from paddlex import create_pipeline; create_pipeline('__INVALID__')\" 查看可用列表"
    )


doc_parser, used_pipeline_name = get_available_pipeline()


def extract_markdown(result):
    """从 PaddleX 解析结果中提取 Markdown 内容"""
    md_parts = []
    results = list(result) if hasattr(result, '__iter__') else [result]

    for res in results:
        if hasattr(res, 'markdown') and res.markdown:
            md_parts.append(str(res.markdown))
            continue
        if hasattr(res, 'res_dict') and isinstance(res.res_dict, dict):
            md_val = res.res_dict.get('markdown', '')
            if md_val:
                md_parts.append(str(md_val))
                continue
        if hasattr(res, 'rec_text') and res.rec_text:
            texts = res.rec_text if isinstance(res.rec_text, list) else [res.rec_text]
            md_parts.append("\n".join(str(t) for t in texts if t))

    return "\n\n".join(part for part in md_parts if part.strip())


def parse_document(file_input, progress=gr.Progress(track_tqdm=True)):
    """支持图片和 PDF 文件解析"""
    if file_input is None:
        return None, "### ⚠️ 请先上传文件或图片"

    progress(0, desc="⏳ 正在预处理...")

    preview_image = None
    input_data = None

    if isinstance(file_input, Image.Image):
        preview_image = file_input
        input_data = np.array(file_input)
    elif isinstance(file_input, np.ndarray):
        preview_image = Image.fromarray(file_input)
        input_data = file_input
    elif isinstance(file_input, str) and os.path.exists(file_input):
        input_data = file_input
        try:
            preview_image = Image.open(file_input)
        except Exception:
            pass
    else:
        return None, "### ❌ 不支持的输入格式"

    try:
        # 👇 修改2: 更新进度条提示文案
        progress(0.1, desc="🔍 正在解析文档（GPU加速中）...")
        result = doc_parser.predict(input_data)

        progress(0.5, desc="📝 正在提取 Markdown...")
        md_content = extract_markdown(result)

        progress(1.0, desc="✅ 完成！")

    except Exception as e:
        return preview_image, f"### ❌ 解析失败\n```{str(e)}```"

    if not md_content.strip():
        md_content = "### 🔍 未提取到结构化内容\n可能原因：\n1. 图片清晰度不足\n2. 当前流水线不支持该版式\n3. 请尝试更换为 `layout_parsing` 流水线"

    return preview_image, md_content


with gr.Blocks(title="文档转 Markdown 工具") as demo:
    # 👇 修改3: 标题显示 GPU 而非 CPU
    gr.Markdown(f"# 📑 文档/图片 → Markdown 转换\n当前流水线: `{used_pipeline_name}` | 设备: **GPU**")

    with gr.Row(equal_height=True):
        with gr.Column(scale=1):
            file_input = gr.File(
                label="📁 上传文档 (图片/PDF)",
                file_types=["image", ".pdf"],
                type="filepath"
            )
        with gr.Column(scale=1):
            img_preview = gr.Image(type="pil", label="🖼️ 原图预览", interactive=False)

    md_output = gr.Markdown(
        value="### 📭 等待上传...\n支持表格、标题、列表、公式的结构化还原",
        label="还原后的 Markdown"
    )

    btn = gr.Button("🔍 开始解析", variant="primary", size="lg")

    btn.click(
        fn=parse_document,
        inputs=[file_input],
        outputs=[img_preview, md_output]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7861, theme=gr.themes.Default())
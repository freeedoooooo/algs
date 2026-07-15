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
        "PP-StructureV2",
        "doc_parsing",
        "document_parse",
        "ocr",
    ]

    last_error = None
    for name in candidates:
        param_variants = [
            {
                "device": "cpu",
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
            },
            {"device": "cpu"},
        ]

        for params in param_variants:
            try:
                print(f"🔍 正在尝试: {name} | 参数: {list(params.keys())}")
                pipeline = create_pipeline(pipeline=name, **params)
                print(f"✅ 成功加载流水线: {name}")
                return pipeline, name
            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    print(f"⚠️ 参数不兼容，尝试下一组...")
                    last_error = e
                    continue
                raise
            except Exception as e:
                last_error = e
                err_msg = str(e)
                print(f"⚠️ '{name}' 不可用: {err_msg[:300]}")
                break

    raise RuntimeError(
        f"❌ 所有候选流水线均不可用！\n"
        f"最后一条错误: {last_error}\n\n"
        f"请手动执行以下命令获取完整可用列表：\n"
        f"  python -c \"from paddlex import create_pipeline; create_pipeline('__INVALID__')\"\n"
        f"然后将输出中 Available pipelines 里的正确名称添加到 candidates 列表首位。"
    )


doc_parser, used_pipeline_name = get_available_pipeline()


def parse_document(image):
    if image is None:
        return None, "### ⚠️ 请先上传图片"

    # ✅ PaddleX layout_parsing 只接受 numpy.ndarray 或 str
    if isinstance(image, Image.Image):
        image_np = np.array(image)
    else:
        image_np = image

    try:
        result = doc_parser.predict(image_np)
    except Exception as e:
        return image, f"### ❌ 解析失败\n```{str(e)}```"

    md_content = ""
    results = list(result) if hasattr(result, '__iter__') else [result]

    for res in results:
        # ✅ 新增：针对 LayoutParsingResult 的专属解析
        # 1. 尝试 rec_text（识别文本拼接）
        if hasattr(res, 'rec_text') and res.rec_text:
            if isinstance(res.rec_text, list):
                md_content = "\n".join(str(t) for t in res.rec_text if t)
            else:
                md_content = str(res.rec_text)
            if md_content.strip():
                break

        # 2. 尝试 markdown / md 属性
        for attr in ('markdown', 'md', 'text'):
            val = getattr(res, attr, None)
            if val and str(val).strip():
                md_content = str(val)
                break
        if md_content.strip():
            break

        # 3. 尝试 res_dict 嵌套结构
        if hasattr(res, 'res_dict') and isinstance(res.res_dict, dict):
            for key in ('markdown', 'md', 'rec_text', 'text'):
                val = res.res_dict.get(key)
                if val:
                    md_content = "\n".join(val) if isinstance(val, list) else str(val)
                    if md_content.strip():
                        break
        if md_content.strip():
            break

        # 4. 字典格式兜底
        if isinstance(res, dict):
            for key in ('markdown', 'md', 'rec_text', 'text'):
                val = res.get(key)
                if val:
                    md_content = "\n".join(val) if isinstance(val, list) else str(val)
                    if md_content.strip():
                        break
        if md_content.strip():
            break

    # ✅ 关键调试：如果仍未提取到内容，打印对象完整结构辅助定位
    if not md_content.strip() and results:
        res_obj = results[0]
        debug_info = []
        debug_info.append(f"类型: {type(res_obj)}")
        debug_info.append(f"属性列表: {[a for a in dir(res_obj) if not a.startswith('_')]}")
        if hasattr(res_obj, 'res_dict'):
            debug_info.append(f"res_dict keys: {list(res_obj.res_dict.keys()) if isinstance(res_obj.res_dict, dict) else type(res_obj.res_dict)}")
        if hasattr(res_obj, 'json'):
            try:
                debug_info.append(f"json片段: {str(res_obj.json)[:500]}")
            except Exception:
                pass

        md_content = (
            f"### 🔍 未自动提取到 Markdown，请检查以下对象结构：\n"
            f"当前流水线: `{used_pipeline_name}` | 设备: CPU\n\n"
            f"```\n" + "\n".join(debug_info) + "\n```"
        )

    return image, md_content


with gr.Blocks(title="CPU文档结构化解析") as demo:
    gr.Markdown(f"# 📑 CPU 文档排版/表格还原\n当前流水线: `{used_pipeline_name}` | 设备: CPU")

    with gr.Row(equal_height=True):
        img_input = gr.Image(type="pil", label="📤 上传文档图片")
        img_preview = gr.Image(type="pil", label="🖼️ 原图预览", interactive=False)

    md_output = gr.Markdown(
        value="### 📭 等待上传...\n支持表格、标题、列表的结构化还原",
        label="还原后的 Markdown"
    )

    btn = gr.Button("🔍 开始解析", variant="primary", size="lg")
    btn.click(fn=parse_document, inputs=img_input, outputs=[img_preview, md_output])

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        theme=gr.themes.Default()
    )
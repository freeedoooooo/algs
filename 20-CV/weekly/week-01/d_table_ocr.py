"""
第1周 · 模块D：表格识别 PP-StructureV3（可直接运行）

普通 OCR 只给"一行行文字"，表格需要结构识别（还原行列关系），输出 HTML。

用法（在 week-01 目录下）：
    python d_table_ocr.py                      # 用配置区 INPUT_IMAGE 指定的图片
    python d_table_ocr.py input/你的表格.png     # 命令行临时指定（优先级高于 INPUT_IMAGE）

调试要改的路径都在文件顶部的【配置区】，不用往下翻代码。

跑完会生成 output/table_out.html，用浏览器打开看还原效果。

版本说明（paddleocr 3.7 / paddlex 3.x）：
    旧的 PPStructure 已在 3.x 移除，改用 PPStructureV3。
    - 输出用 .predict()，结果是 list[PPStructureV3Result]（dict 结构）
    - 用 result.save_to_html(路径) 直接导出表格 HTML

关于首次运行的下载：
    表格识别是"多模型流水线"：版面检测 + 表格分类 + 有线/无线表格结构识别 + 单元格检测。
    其中大部分模型你本地没缓存，首次运行会自动下载（一次性，之后复用）。
    这里强制走百度云 BOS 模型源 + 跳过连通性检查，避免像 PP-OCRv6 那样卡在 HuggingFace。
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_IMAGE = 'input/test2.jpg'             # 输入图片（含表格的图）
OUT_HTML = 'output/table_out_d.html'        # 表格还原结果，浏览器打开看效果
# ==========================================================================

import os
import re
import sys
import time

# ⚠️ 必须在 import paddleocr 之前设置：模型走百度云源、跳过连通性检查（国内不卡 HF）
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

from paddleocr import PPStructureV3  # noqa: E402

# 输入：命令行指定 > 配置区 INPUT_IMAGE（文件不存在时自动退回 input/test2.jpg）
if len(sys.argv) > 1:
    IMAGE = sys.argv[1]
else:
    IMAGE = INPUT_IMAGE
    if not os.path.exists(IMAGE) and os.path.exists('input/test2.jpg'):
        IMAGE = 'input/test2.jpg'
        print(f'>> 配置区的 {INPUT_IMAGE} 不存在，先用 input/test2.jpg 演示')

if not os.path.exists(IMAGE):
    sys.exit(
        f'找不到图片：{os.path.abspath(IMAGE)}\n'
        f'改文件顶部的 INPUT_IMAGE，或用命令行指定：python d_table_ocr.py 你的图片.png'
    )

# ---------- 1) 初始化（加载流水线里的多个模型） ----------
print('>> 初始化 PPStructureV3（表格识别流水线），首次加载/下载模型可能较慢…')
t0 = time.perf_counter()
engine = PPStructureV3(
    use_formula_recognition=False,   # 关掉公式识别（本示例不需要，少下载几个模型）
    use_chart_recognition=False,     # 关掉图表识别
    use_seal_recognition=False,      # 关掉印章识别
    use_region_detection=False,      # 关掉区域检测
    use_table_recognition=True,      # 只保留表格识别
    # 文本检测/识别用移动端模型：CPU 上比 server 快一个数量级（表格 OCR 文字量不大，精度够用）
    text_detection_model_name='PP-OCRv4_mobile_det',
    text_recognition_model_name='PP-OCRv4_mobile_rec',
)
t1 = time.perf_counter()
print(f'>> 流水线加载耗时：{t1 - t0:.2f}s')

# ---------- 2) 推理 ----------
print(f'>> 开始识别：{IMAGE}')
result = engine.predict(IMAGE)
t2 = time.perf_counter()
print(f'>> 推理耗时：{t2 - t1:.2f}s')

def ensure_readable_html(path):
    """
    给 paddlex 导出的 HTML 片段补上编码声明。

    坑点（你遇到的"日志正常但浏览器乱码"）：
        save_to_html 写文件时确实是 utf-8（字节没错），
        但内容只是 `<html><body><table>...` 这种片段，没有 <meta charset>。
        浏览器在中文 Windows 上默认按 GBK 解码 → 中文乱码。
        补上 `<meta charset="utf-8">` 后浏览器才知道该用 utf-8 读。
    """
    with open(path, encoding='utf-8') as f:
        frag = f.read()

    # 已经有 charset 声明就不用管了
    if re.search(r'<meta[^>]+charset', frag, flags=re.I):
        return False

    # 去掉片段自带的 <html>/<body> 外层标签，避免嵌套成 <html><html>
    inner = re.sub(r'^\s*<html[^>]*>|</html>\s*$', '', frag, flags=re.I)
    inner = re.sub(r'^\s*<body[^>]*>|</body>\s*$', '', inner, flags=re.I)

    doc = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-CN">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        '  <title>表格识别结果</title>\n'
        '  <style>\n'
        '    body { font-family: "Microsoft YaHei", sans-serif; margin: 24px; }\n'
        '    table { border-collapse: collapse; width: 100%; }\n'
        '    td, th { border: 1px solid #999; padding: 6px 10px; }\n'
        '  </style>\n'
        '</head>\n'
        '<body>\n'
        f'{inner}\n'
        '</body>\n'
        '</html>\n'
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc)
    return True


# ---------- 3) 打印各内容块 + 导出 HTML ----------
os.makedirs('output', exist_ok=True)
for i, res in enumerate(result):
    data = res.json if hasattr(res, 'json') else res
    # 3.x 的 res.json 是 {'res': {...}} 嵌套结构，真正的字段在里面
    if isinstance(data, dict) and isinstance(data.get('res'), dict):
        data = data['res']
    blocks = data.get('parsing_res_list', []) if isinstance(data, dict) else []
    print(f'>> 第 {i + 1} 个输入，识别到 {len(blocks)} 个内容块：')
    for b in blocks:
        label = b.get('block_label', '?')
        content = str(b.get('block_content', '')).replace('\n', ' ')
        print(f'   [{label}] {content[:60]}')
    # 直接导出 HTML（表格会还原成 <table>）
    res.save_to_html(OUT_HTML)
    # 补编码声明，否则浏览器按 GBK 解码会显示乱码
    if ensure_readable_html(OUT_HTML):
        print('>> 已为 HTML 补充 <meta charset="utf-8"> 与表格样式')

print(f'\n>> 已保存 {OUT_HTML}，用浏览器打开查看表格还原效果')
print(f'>> 总耗时：{t2 - t0:.2f}s（加载 {t1 - t0:.2f}s + 推理 {t2 - t1:.2f}s）')

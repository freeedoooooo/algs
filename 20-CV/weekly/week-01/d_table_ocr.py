"""
第1周 · 模块D：表格识别 PP-StructureV3（可直接运行，也可以被别的脚本 import）

普通 OCR 只给"一行行文字"，表格需要结构识别（还原行列关系），输出 HTML。

用法（在 week-01 目录下）：
    conda activate paddle
    python d_table_ocr.py                      # 用配置区 INPUT_IMAGE 指定的图片
    python d_table_ocr.py input/你的表格.png     # 命令行临时指定（优先级高于 INPUT_IMAGE）

调试要改的路径都在文件顶部的【配置区】，不用往下翻代码。

【产物】两层隔离，一眼看出「哪个脚本、哪个输入」的产物：
    output/d_table_ocr/<输入文件名去后缀>/
        d_table_out.html     表格还原结果（多个结果会自动加编号，不互相覆盖）
例如输入 input/test2.jpg → output/d_table_ocr/test2/d_table_out.html。
脚本会自动补 <meta charset="utf-8">，中文不会乱码。

版本说明（paddleocr 3.7 / paddlex 3.x）：
    旧的 PPStructure 已在 3.x 移除，改用 PPStructureV3。
    - 输出用 .predict()，结果是 list[PPStructureV3Result]（dict 结构）
    - 用 result.save_to_html(路径) 直接导出表格 HTML
    - 结果多一层：真正的内容块在 res.json['res']['parsing_res_list']

关于首次运行的下载：
    表格识别是"多模型流水线"：版面检测 + 表格分类 + 有线/无线表格结构识别 + 单元格检测。
    其中大部分模型你本地没缓存，首次运行会自动下载（一次性，之后复用）。
    这里强制走百度云 BOS 模型源 + 跳过连通性检查，避免像 PP-OCRv6 那样卡在 HuggingFace。
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_IMAGE = 'input/test2.jpg'             # 输入图片（含表格的图）
# ↓ 产物隔离规则：output/<脚本名>/<输入文件名>/
#   OUT_DIR 是本脚本专属目录，和 b / c / weekend_pipeline 的产物互不干扰；
#   OUT_HTML 只是「文件名」，运行时会拼到 OUT_DIR/<输入文件名>/ 里。
OUT_DIR = 'output/d_table_ocr'              # 本脚本的产物总目录
OUT_HTML = 'd_table_out.html'               # 表格还原结果，浏览器打开看效果
# ==========================================================================

import os
import re
import sys
import time

# ↓ 必须在任何 paddleocr / paddlex 被导入之前设置：模型走百度云源、跳过连通性检查。
# setdefault = 只给默认值，不覆盖你在终端里自己 set 过的配置。
# 本文件把真正的 paddle import 放进了 build_engine()（懒加载），
# 所以这两行一定会在它之前执行，时序是安全的。
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')


def show(path):
    """日志专用：把 Windows 的反斜杠显示成 /，实际读写路径不变。"""
    return str(path).replace(os.sep, '/') if path else path


def case_dir(input_path):
    """
    按输入文件名算出专属产物目录：OUT_DIR/<输入文件名去后缀>/。

    os.path.basename 去掉前面的目录只留文件名，splitext 再去掉后缀，
    os.path.join 用当前系统的分隔符拼路径（Windows 是反斜杠，别自己手写）。
    """
    stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(OUT_DIR, stem)


def build_engine():
    """创建 PP-StructureV3 流水线。函数被调用时才 import 并加载那一堆模型。"""
    from paddleocr import PPStructureV3

    return PPStructureV3(
        use_formula_recognition=False,   # 关掉公式识别（本示例不需要，少下载几个模型）
        use_chart_recognition=False,     # 关掉图表识别
        use_seal_recognition=False,      # 关掉印章识别
        use_region_detection=False,      # 关掉区域检测
        use_table_recognition=True,      # 只保留表格识别
        # 文本检测/识别用移动端模型：CPU 上比 server 快一个数量级（表格 OCR 文字量不大，精度够用）
        text_detection_model_name='PP-OCRv4_mobile_det',
        text_recognition_model_name='PP-OCRv4_mobile_rec',
    )


def parse_blocks(res):
    """
    从一个结果对象里取出内容块列表，兼容不同版本的返回结构。

    3.7.0 的 res.json 是 {'res': {...}} 嵌套结构，parsing_res_list 藏在里面一层。
    """
    data = res.json if hasattr(res, 'json') else res
    if isinstance(data, dict) and isinstance(data.get('res'), dict):
        data = data['res']
    if not isinstance(data, dict):
        return []
    return data.get('parsing_res_list', []) or []


def ensure_readable_html(path):
    """
    给 paddlex 导出的 HTML 片段补上编码声明，返回 True 表示确实补过。

    坑点（第1周遇到的"日志正常但浏览器乱码"）：
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

    # 去掉片段自带的 <!DOCTYPE> / <html> / <body> 外层标签，避免嵌套成 <html><html>。
    # 正则前的 r 是「原始字符串」：反斜杠按字面保留，不当转义符处理。
    frag = re.sub(r'^\s*<!DOCTYPE[^>]*>', '', frag, flags=re.I)
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


def list_available_images():
    """输入文件不存在时，列出 input/ 下可用的图片，省得去猜文件名。"""
    folder = 'input'
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder)
                  if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')))


def main():
    # 命令行指定 > 配置区 INPUT_IMAGE（找不到就明确报错，不再偷偷换成别的图）
    image = sys.argv[1] if len(sys.argv) > 1 else INPUT_IMAGE
    if not os.path.exists(image):
        candidates = list_available_images()
        msg = [f'找不到图片：{os.path.abspath(image)}',
               '改文件顶部的 INPUT_IMAGE，或用命令行指定：python d_table_ocr.py 你的图片.png']
        if candidates:
            msg.append('input/ 下现有图片：')
            msg.extend(f'   python d_table_ocr.py input/{f}' for f in candidates[:8])
        sys.exit('\n'.join(msg))

    # ---- 1) 初始化（加载流水线里的多个模型） ----
    print(f'>> 产物目录：{show(case_dir(image))}')
    print('>> 初始化 PPStructureV3（表格识别流水线），首次加载/下载模型可能较慢…')
    t0 = time.perf_counter()
    engine = build_engine()
    t1 = time.perf_counter()
    print(f'>> 流水线加载耗时：{t1 - t0:.2f}s')

    # ---- 2) 推理 ----
    print(f'>> 开始识别：{image}')
    try:
        result = engine.predict(image)
    except Exception as e:
        sys.exit(f'>> 识别失败：{e}\n（若是模型下载中断，重跑一次通常会续传；也可检查 ~/.paddlex/official_models/）')
    t2 = time.perf_counter()
    print(f'>> 推理耗时：{t2 - t1:.2f}s')

    # ---- 3) 打印各内容块 ----
    for i, res in enumerate(result):
        blocks = parse_blocks(res)
        print(f'>> 第 {i + 1} 个输入，识别到 {len(blocks)} 个内容块：')
        for b in blocks:
            label = b.get('block_label', '?')
            content = str(b.get('block_content', '')).replace('\n', ' ')
            print(f'   [{label}] {content[:60]}')

    # ---- 4) 导出 HTML 并补编码声明 ----
    # 产物目录 = 脚本专属目录 / 输入文件名；不再写死 output/ 根目录。
    out_dir = case_dir(image)
    os.makedirs(out_dir, exist_ok=True)
    stem, ext = os.path.splitext(OUT_HTML)
    saved = []
    for i, res in enumerate(result):
        # 多个输入时给每个结果单独命名，避免后面的覆盖前面的
        name = OUT_HTML if len(result) == 1 else f'{stem}_{i}{ext}'
        path = os.path.join(out_dir, name)
        res.save_to_html(path)
        if ensure_readable_html(path):
            print(f'>> 已为 {show(path)} 补充 <meta charset="utf-8"> 与表格样式')
        saved.append(path)

    print(f'\n>> 已保存 {", ".join(show(p) for p in saved)}，用浏览器打开查看表格还原效果')
    print(f'>> 总耗时：{t2 - t0:.2f}s（加载 {t1 - t0:.2f}s + 推理 {t2 - t1:.2f}s）')


# 只有直接运行本文件时才执行 main()。
# 之前这个文件把所有代码写在模块顶层，一 import 就会立刻跑一遍识别，
# 导致 weekend_pipeline.py 不敢复用它；现在可以安全 import 了。
if __name__ == '__main__':
    main()

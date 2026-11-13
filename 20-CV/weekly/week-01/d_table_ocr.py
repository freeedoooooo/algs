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
        d_table_out.html         单页输入：表格还原结果
        d_table_out_2.html …     PDF 多页输入：数字 = PDF 页码（1 起），只生成含表格的页
        d_table_out_2_table_3.html  一页多张表时按表名再分文件，不互相覆盖
例如输入 input/test2.jpg → output/d_table_ocr/test2/d_table_out.html。
脚本会自动补 <meta charset="utf-8">，中文不会乱码；
没有表格的页只在日志里说明，不生成空 HTML。

版本说明（paddleocr 3.7 / paddlex 3.x）：
    旧的 PPStructure 已在 3.x 移除，改用 PPStructureV3。
    - 输出用 .predict()，结果是 list[PPStructureV3Result]（dict 结构）
    - 用 result.html / 安全封装导出表格 HTML（见下面 export_html 的说明）
    - 结果多一层：真正的内容块在 res.json['res']['parsing_res_list']

【输入是 PDF 时的坑（11-13 修）】
    predict(一个 5 页的 PDF) 会返回 5 个结果，一页一个。但并不是每页都有表格：
    test3_image.pdf 的第 3~5 页是证书扫描图，只有 [image]/[header]/[figure_title] 块。
    paddlex 3.7.0 的 save_to_html() 内部写的是 html[list(html.keys())[0]]，
    而这一页没有表格时 _to_html() 返回空字典 {} → 直接 IndexError。
    所以本脚本不再直接调 save_to_html()：先用 res.html 判断有没有表格，
    空则再从 [table] 内容块兜底；两者都空就跳过这一页（这是正常情况，不是错误）。
    一页有多张表时，save_to_html() 又只会写第一张并打 warning，
    这里改成每张表各写一个文件，不会悄悄丢表格。

【页码基准（11-13 定稿）】全仓统一从 1 起，和 PDF 阅读器一致：
    PDF 第 2 页 → `d_table_out_2.html`，日志写「第 2 个输入」。
    `enumerate(result, 1)` 直接给出 1 起序号，不再做 +1 换算。
    重跑时 clear_old_html() 先清掉旧编号的文件，避免新旧两套编号并存。

关于首次运行的下载：
    表格识别是"多模型流水线"：版面检测 + 表格分类 + 有线/无线表格结构识别 + 单元格检测。
    其中大部分模型你本地没缓存，首次运行会自动下载（一次性，之后复用）。
    这里强制走百度云 BOS 模型源 + 跳过连通性检查，避免像 PP-OCRv6 那样卡在 HuggingFace。
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_IMAGE = 'input/test3_image.pdf'             # 输入图片或 PDF（多页 PDF 会一页一个结果）
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
    给导出的 HTML 片段补上编码声明，返回 True 表示确实补过。

    坑点（第1周遇到的"日志正常但浏览器乱码"）：
        写入字节本身是 utf-8（无论走 paddlex 的 save_to_html 还是本脚本自己写），
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


def export_html(res, path):
    """
    把一个结果的表格写成 HTML 文件，返回「实际写出的文件路径列表」。
    这一页没有表格就返回空列表 []（调用方据此跳过，不生成空文件）。

    为什么不直接 res.save_to_html(path)（paddlex 3.7.0 的两个坑）：
      1) 它内部是 `html[list(html.keys())[0]]`。而「这一页没识别出表格」时
         _to_html() 返回空字典 {}，取 [0] 就直接 IndexError —— 本次报错的原因。
         输入是 PDF 时一页一个结果，证书扫描页必然命中它，不是识别失败。
      2) 一页有多张表时，它只写第一张并打一条 warning，会悄悄丢数据。

    所以这里改成自己写：
      - 先读公开的 res.html（dict：表名 → HTML 片段），空则从内容块兜底；
      - 兜底：parse_blocks() 里的 [table] 块，其 block_content 已经是还原好的
        <table> HTML（3.7.0 有些结果 table_res_list 为空但内容块里有表格）；
      - 多张表 → 每张单独一个文件，文件名带表名，绝不互相覆盖。
    写文件用 encoding='utf-8'，和 paddlex 的 HtmlWriter 完全一致；
    之后照样交给 ensure_readable_html() 补 charset 和样式。
    """
    # 先取官方 HTML 字典；万一取不到也不能让整条流水线崩，用 try/except 兜住。
    try:
        html = res.html or {}
    except Exception as e:
        print(f'   >> 读取 res.html 失败（{type(e).__name__}: {e}），改用内容块兜底')
        html = {}

    if not html:
        # 字典推导式：遍历内容块，只留 label 含 table 且 content 非空的块。
        # enumerate 给每张表一个序号，避免多个块生成同名文件。
        html = {f'block_{n}': str(b.get('block_content'))
                for n, b in enumerate(parse_blocks(res))
                if 'table' in str(b.get('block_label', '')).lower()
                and b.get('block_content')}

    html = {k: v for k, v in html.items() if v}   # 过滤空内容，别写出 0 字节文件
    if not html:
        return []

    stem, ext = os.path.splitext(path)
    saved = []
    for key, frag in html.items():
        # 只有一张表就用原文件名；多张表按 key 加后缀。
        p = path if len(html) == 1 else f'{stem}_{key}{ext}'
        with open(p, 'w', encoding='utf-8') as f:
            f.write(frag)
        saved.append(p)
    return saved


def clear_old_html(out_dir):
    """
    重跑前清掉本 case 上一次生成的表格 HTML。

    页码统一成 1 起之后，旧的 `d_table_out_1.html`（旧规则里是第 2 页）
    如果留着，会和新的 `d_table_out_2.html` 同时存在，反而更乱。
    只删本脚本自己生成的、名字符合规则的文件：
    d_table_out.html / d_table_out_2.html / d_table_out_2_table_3.html。
    不递归、不碰目录里其它文件；这些结果每次重跑都会重新生成。
    """
    if not os.path.isdir(out_dir):
        return
    removed = 0
    for name in os.listdir(out_dir):
        if not re.fullmatch(r'd_table_out(?:_\d+)?(?:_table_.+)?\.html', name):
            continue
        try:
            os.remove(os.path.join(out_dir, name))
            removed += 1
        except OSError:
            pass
    if removed:
        print(f'>> 重跑前清掉 {removed} 个旧编号 HTML → {show(out_dir)}')


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
    print(f'>> 开始识别：{show(image)}')
    try:
        result = engine.predict(image)
    except Exception as e:
        sys.exit(f'>> 识别失败：{e}\n（若是模型下载中断，重跑一次通常会续传；也可检查 ~/.paddlex/official_models/）')
    t2 = time.perf_counter()
    print(f'>> 推理耗时：{t2 - t1:.2f}s')

    # ---- 3) 打印各内容块 ----
    for i, res in enumerate(result, 1):
        blocks = parse_blocks(res)
        print(f'>> 第 {i} 个输入，识别到 {len(blocks)} 个内容块：')
        for b in blocks:
            label = b.get('block_label', '?')
            content = str(b.get('block_content', '')).replace('\n', ' ')
            print(f'   [{label}] {content[:60]}')

    # ---- 4) 导出 HTML 并补编码声明 ----
    # 产物目录 = 脚本专属目录 / 输入文件名；不再写死 output/ 根目录。
    out_dir = case_dir(image)
    os.makedirs(out_dir, exist_ok=True)
    clear_old_html(out_dir)     # 重跑时先清掉旧编号的文件，保证只有一套页码
    stem, ext = os.path.splitext(OUT_HTML)
    saved = []
    skipped = []
    for i, res in enumerate(result, 1):
        # 多个输入时按 PDF 页码（1 起）命名，避免后面的覆盖前面的
        name = OUT_HTML if len(result) == 1 else f'{stem}_{i}{ext}'
        path = os.path.join(out_dir, name)
        paths = export_html(res, path)
        if not paths:
            # PDF 里的证书扫描页没有表格，属正常情况；不写空 HTML，也不让 paddlex 抛异常。
            skipped.append(i)
            print(f'>> 第 {i} 个输入：没有识别到表格，跳过 HTML 导出')
            continue
        for p in paths:
            if ensure_readable_html(p):
                print(f'>> 已为 {show(p)} 补充 <meta charset="utf-8"> 与表格样式')
            saved.append(p)

    if saved:
        print(f'\n>> 已保存 {len(saved)} 个 HTML：{", ".join(show(p) for p in saved)}')
        print('   用浏览器打开查看表格还原效果')
    else:
        print('\n>> 本次所有页都没有识别出表格，因此没有 HTML 文件；'
              '各页内容块见上面的日志（可用 input/test2.jpg 试单张表格图）')
    if skipped:
        print(f'>> 无表格、未生成 HTML 的输入序号：{", ".join(str(n) for n in skipped)}')
    print(f'>> 总耗时：{time.perf_counter() - t0:.2f}s'
          f'（加载 {t1 - t0:.2f}s + 推理 {t2 - t1:.2f}s + 导出）')


# 只有直接运行本文件时才执行 main()。
# 之前这个文件把所有代码写在模块顶层，一 import 就会立刻跑一遍识别，
# 导致 weekend_pipeline.py 不敢复用它；现在可以安全 import 了。
if __name__ == '__main__':
    main()

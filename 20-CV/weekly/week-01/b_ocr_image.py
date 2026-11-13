"""
第1周 · 模块B：PaddleOCR 识别一张图片（可直接运行，也可以被别的脚本 import）

用法（在 week-01 目录下）：
    conda activate paddle
    python b_ocr_image.py                      # 用配置区 INPUT_IMAGE 指定的图片
    python b_ocr_image.py input/你的图片.png     # 命令行临时指定（优先级高于 INPUT_IMAGE）

调试要改的路径都在文件顶部的【配置区】，不用往下翻代码。

【产物】两层隔离，一眼看出「哪个脚本、哪个输入」的产物：
    output/b_ocr_image/<输入文件名去后缀>/
        b_ocr_result.txt      每行文字 + 置信度
        b_ocr_boxes.png       原图上叠加识别框，一眼看出哪里认出来了、哪里漏了
        b_ocr_report.html     离线对照报告（左图右文字），浏览器直接打开，不用起服务
例如输入 input/test2.jpg → output/b_ocr_image/test2/。
换一张图跑，结果自动进另一个目录，不会覆盖上一次的。
HTML 把图片用 base64 内嵌进去了，所以单独把 HTML 拷走也能正常显示。
不想要可视化就把配置区的 MAKE_VIS 改成 False。

说明：
    OCR = 文字检测（找文字在哪）+ 文字识别（读出来）。
    本周当黑盒 API 用即可，原理留到 P4。

版本说明（paddleocr 3.7.0）：
    - 3.x 把 .ocr(cls=True) 改成了 .predict()，返回 dict 结构（rec_texts / rec_scores / rec_polys）。
    - 默认模型是 PP-OCRv6（需联网下载）。这里显式指定本地已缓存的
      PP-OCRv4_mobile_det / PP-OCRv4_mobile_rec，免下载、CPU 上快。
      想用默认 v6 就把配置区两个 MODEL 改成 None 再删掉构造参数。
    - use_angle_cls 已废弃，用 use_textline_orientation 代替。
    - 显式指定模型名时不要再传 lang / ocr_version，否则 3.7.0 会打印
      "will be ignored" 警告；语言能力已由所选识别模型决定。

关于识别框坐标（本机 3.7.0 实测，week-02 踩过）：
    PaddleOCR 默认会做「整页方向分类 + UVDoc 去扭曲」，此时 rec_polys / dt_polys
    是【矫正后图像】的坐标，画回原图会整体错位。所以画框前必须关掉这两项，
    即配置区 USE_DOC_PREPROCESS = False。代价是某些特殊图（亮字暗底的终端截图）
    识别质量会下降；只取文字、不画框时可以改回 True 换取质量。

关于"一张图很慢"：
    单张耗时 = 模型加载（仅进程内第一次） + 推理。
    第一次加载模型要好几秒（含 oneDNN 预热），之后同进程每张图只剩推理。
    想更快：① 换移动端模型（配置区已经是 mobile）；
           ② det 侧减小 text_det_limit_side_len；③ paddle.set_num_threads(物理核数)。
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_IMAGE = 'input/test2.jpg'             # 输入图片
# ↓ 产物隔离规则：output/<脚本名>/<输入文件名>/
#   OUT_DIR 是本脚本专属目录，和 c / d / weekend_pipeline 的产物互不干扰。
#   下面三项只是「文件名」，运行时会拼到 OUT_DIR/<输入文件名>/ 里，
#   所以换一张图跑不会覆盖上一次的结果。
OUT_DIR = 'output/b_ocr_image'              # 本脚本的产物总目录
OUT_TXT = 'b_ocr_result.txt'                # 纯文本结果；不想落盘就改成 None
OUT_BOX_PNG = 'b_ocr_boxes.png'             # 原图 + 识别框
OUT_REPORT_HTML = 'b_ocr_report.html'       # 离线对照报告，浏览器直接打开
DET_MODEL = 'PP-OCRv4_mobile_det'           # 文本检测模型（找文字在哪）
REC_MODEL = 'PP-OCRv4_mobile_rec'           # 文本识别模型（读出来）
USE_DOC_PREPROCESS = False                  # False = 坐标对齐原图（画框必须）；True = 只取文字时可能更准
LOW_SCORE = 0.8                             # 低于此置信度的行在报告里标橙红色
MAKE_VIS = True                             # 是否生成带框 PNG + HTML 报告
# 模型说明：没 GPU 时 server 大模型在 CPU 上极慢（实测单张 104s vs mobile 3.8s），
#           追求最高精度且能忍慢，再换成 PP-OCRv5_server_det / PP-OCRv5_server_rec
# ==========================================================================

import os
import sys
import time
import base64
import html as html_lib

# ↓ 必须在任何 paddleocr / paddlex 被导入之前设置（见 week-01/d_table_ocr.py 的说明）：
#   BOS = 百度对象存储，国内下载模型比 HuggingFace 稳；
#   DISABLE_MODEL_SOURCE_CHECK = 跳过启动时的连通性探测，避免网络不通时干等。
# setdefault 表示「给个默认值，但不覆盖你在终端里自己 set 过的配置」。
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

# 注意：这里【故意不】在模块顶层 import paddleocr。
# 一是保证上面两行环境变量先设置好（paddle 在被导入那一刻会读走并"快照"）；
# 二是别的文件 import 本模块做复用时，不会连带花几秒钟加载模型（懒加载）。
# 真正的 import 写在下面的 build_ocr() 里。


def show(path):
    """日志专用：把 Windows 的反斜杠显示成 /，实际读写路径不变。"""
    return str(path).replace(os.sep, '/') if path else path


def case_dir(input_path):
    """
    按输入文件名算出专属产物目录：OUT_DIR/<输入文件名去后缀>/。

    os.path.splitext('input/test2.jpg') → ('input/test2', '.jpg')，取 [0] 得到不带后缀的部分；
    os.path.basename 先去掉前面的目录，只留文件名。
    这样 test2.jpg 和 test1.jpg 的产物自然分到两个目录，谁也不会覆盖谁。
    """
    stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(OUT_DIR, stem)


def build_ocr():
    """创建并返回 OCR 引擎。函数被调用时才 import + 加载模型。"""
    from paddleocr import PaddleOCR  # 局部 import，时序安全且启动更快

    kwargs = dict(
        text_detection_model_name=DET_MODEL,
        text_recognition_model_name=REC_MODEL,
        use_textline_orientation=True,   # 3.x 名称，替代已废弃的 use_angle_cls
        # 不传 lang：显式指定模型名时会被忽略并报警告。
    )
    if not USE_DOC_PREPROCESS:
        # 关掉整页方向分类 + UVDoc 去扭曲，让 rec_polys 基于原始图片坐标系。
        # 开着也能识别文字，只是框画回原图会错位（week-02 实测过）。
        kwargs['use_doc_orientation_classify'] = False
        kwargs['use_doc_unwarping'] = False
    return PaddleOCR(**kwargs)


def recognize(ocr, image_path):
    """
    跑一次识别，返回「行记录」组成的列表。

    每条记录是一个 dict：{'text': 文字, 'score': 置信度, 'box': 四点坐标或 None}
    统一成这种结构后，打印、存文本、画框都读同一份数据，不会各取各的。
    """
    rows = []
    # predict() 返回列表：每张输入图对应一个结果对象（这里只有一张，但按通用写法遍历）。
    for res in ocr.predict(image_path):
        texts = res['rec_texts']                    # list[str]   每行文字
        scores = res['rec_scores']                  # list[float] 对应置信度
        # rec_polys 是每行文字的四点框；个别模型只有 dt_polys，做个兜底。
        # 注意不能写 `if polys`（numpy 数组这样判断会报"真值不明确"），要用 len。
        polys = res.get('rec_polys')
        if polys is None or len(polys) == 0:
            polys = res.get('dt_polys')
        if polys is None:
            polys = []
        for i, (text, score) in enumerate(zip(texts, scores)):
            box = polys[i] if i < len(polys) else None
            rows.append({
                'text': str(text),
                'score': float(score),
                # numpy 坐标转成普通 Python 的列表，后面画图和序列化都方便
                'box': [[float(p[0]), float(p[1])] for p in box] if box is not None else None,
            })
    return rows


def save_text(rows, path):
    """把识别结果写成纯文本，每行「文字 + 制表符 + 置信度」。"""
    if not path:                     # 配置区设成 None / '' 就跳过
        return
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(f"{r['text']}\t置信度={r['score']:.2f}" for r in rows))
    print(f'>> 文字结果已保存：{show(path)}')


def save_visualization(image_path, rows, out_dir):
    """
    生成 ① 带框 PNG ② 自包含的离线 HTML 对照报告。

    out_dir 是本次输入专属的目录，OUT_BOX_PNG / OUT_REPORT_HTML 只是文件名，
    要用 os.path.join 拼上去 —— 这正是「不同输入不混在一起」的实现点。

    这部分是「脚手架」，不是本周要学的 OCR 原理 —— 它只负责把坐标画出来，
    让你能直观看到「原图有字但没框 = 漏检」，这是只看 JSON/TXT 看不出来的。
    week-02 的 vis_ocr_result.py 是它的批量加强版。
    """
    from PIL import Image, ImageDraw   # 只在需要画图时才导入

    os.makedirs(out_dir, exist_ok=True)
    box_png = os.path.join(out_dir, OUT_BOX_PNG)
    report_html = os.path.join(out_dir, OUT_REPORT_HTML)

    # ---- ① 在原图副本上画识别框 ----
    img = Image.open(image_path).convert('RGB')
    draw = ImageDraw.Draw(img)
    for i, row in enumerate(rows):
        # 低置信度用橙红，正常用绿色；中国习惯里红=需要注意，这里沿用醒目配色
        color = (214, 76, 48) if row['score'] < LOW_SCORE else (24, 150, 92)
        box = row['box']
        if box:
            pts = [(p[0], p[1]) for p in box]
            # draw.line 首尾相连画成闭合四边形
            draw.line(pts + [pts[0]], fill=color, width=2)
            # 左上角放行号标签，方便和右侧表格对上；两位数标签要按字数算宽度
            label = str(i + 1)
            lx = min(p[0] for p in pts)
            ly = min(p[1] for p in pts)
            top = max(0, ly - 18)
            width = 9 * len(label) + 8
            draw.rectangle([lx, top, lx + width, top + 16], fill=color)
            draw.text((lx + 4, top + 2), label, fill=(255, 255, 255))
    img.save(box_png)

    # ---- ② 生成 HTML：图片用 base64 内嵌，拷到任何地方都能显示 ----
    with open(box_png, 'rb') as f:
        data_uri = 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')

    # html.escape 把文字里的 < > & 转义，避免识别结果被浏览器当成 HTML 标签
    lines = []
    for i, row in enumerate(rows):
        warn = ' low' if row['score'] < LOW_SCORE else ''
        pct = max(0, min(100, row['score'] * 100))
        lines.append(
            f'<tr class="{warn.strip()}">'
            f'<td class="no">{i + 1}</td>'
            f'<td class="txt">{html_lib.escape(row["text"])}</td>'
            f'<td class="sc">{row["score"]:.2f}</td>'
            f'<td class="bar"><span style="width:{pct:.0f}%"></span></td>'
            f'</tr>'
        )
    low_count = sum(1 for r in rows if r['score'] < LOW_SCORE)
    doc = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '<meta charset="utf-8">\n<title>OCR 识别结果对照</title>\n'
        '<style>\n'
        'body{font-family:"Microsoft YaHei",sans-serif;margin:20px;color:#222;'
        'background:#fff}\n'
        'h2{font-size:16px;font-weight:500;margin:0 0 12px}\n'
        '.meta{color:#666;font-size:13px;margin-bottom:16px}\n'
        '.wrap{display:flex;gap:20px;align-items:flex-start}\n'
        '.left{flex:1;min-width:0}\n'
        '.left img{width:100%;border:1px solid #ddd;border-radius:6px}\n'
        '.right{flex:1;min-width:0}\n'
        'table{border-collapse:collapse;width:100%;font-size:13px}\n'
        'td{border-bottom:1px solid #eee;padding:6px 8px;vertical-align:top}\n'
        'td.no{color:#888;width:32px}\ntd.sc{width:52px;font-family:monospace}\n'
        'td.bar{width:90px}\n'
        '.bar span{display:block;height:8px;background:#18965c;border-radius:4px}\n'
        'tr.low td.txt,tr.low td.sc{color:#d64c30}\n'
        'tr.low .bar span{background:#d64c30}\n'
        '</style>\n</head>\n<body>\n'
        f'<h2>OCR 识别结果对照 · {html_lib.escape(os.path.basename(image_path))}</h2>\n'
        f'<div class="meta">共 {len(rows)} 行，其中 {low_count} 行置信度低于 {LOW_SCORE:.2f}（标橙红）。'
        '原图上「有字却没有框」的地方就是漏检。</div>\n'
        '<div class="wrap">\n'
        f'<div class="left"><img src="{data_uri}" alt="带识别框的原图"></div>\n'
        '<div class="right"><table>\n'
        + '\n'.join(lines)
        + '\n</table></div>\n</div>\n</body>\n</html>\n'
    )
    with open(report_html, 'w', encoding='utf-8') as f:
        f.write(doc)
    print(f'>> 带框图已保存：{show(box_png)}')
    print(f'>> 对照报告已保存：{show(report_html)}（浏览器直接打开）')


def main():
    # 命令行参数 > 配置区 INPUT_IMAGE
    image = sys.argv[1] if len(sys.argv) > 1 else INPUT_IMAGE
    if not os.path.exists(image):
        sys.exit(
            f'找不到图片：{os.path.abspath(image)}\n'
            f'改文件顶部的 INPUT_IMAGE，或用命令行指定：python b_ocr_image.py 你的图片.png'
        )

    print(f'>> 目标图片：{image}')
    print(f'>> 初始化 PaddleOCR（det={DET_MODEL}, rec={REC_MODEL}），首次加载稍慢…')
    t0 = time.perf_counter()
    ocr = build_ocr()
    t1 = time.perf_counter()
    print(f'>> 模型加载耗时：{t1 - t0:.2f}s')

    rows = recognize(ocr, image)
    t2 = time.perf_counter()
    print(f'>> 推理耗时：{t2 - t1:.2f}s，共识别 {len(rows)} 行')

    for row in rows:
        print(f"{row['text']}  置信度={row['score']:.2f}")

    # ---- 产物目录：脚本名 + 输入文件名 两层隔离 ----
    out_dir = case_dir(image)
    os.makedirs(out_dir, exist_ok=True)
    print(f'>> 产物目录：{show(out_dir)}')

    save_text(rows, os.path.join(out_dir, OUT_TXT) if OUT_TXT else None)
    if MAKE_VIS:
        if USE_DOC_PREPROCESS:
            print('>> 警告：USE_DOC_PREPROCESS=True 时坐标基于矫正后图像，画出的框会错位')
        save_visualization(image, rows, out_dir)
    t3 = time.perf_counter()

    low_count = sum(1 for r in rows if r['score'] < LOW_SCORE)
    print(f'>> 低置信度（< {LOW_SCORE:.2f}）行数：{low_count}')
    print(f'>> 总耗时：{t3 - t0:.2f}s（加载 {t1 - t0:.2f}s + 推理 {t2 - t1:.2f}s '
          f'+ 产物 {t3 - t2:.2f}s）')
    print('>> 提示：模型加载只在进程内第一次发生；同进程连跑多张图，后续每张只剩推理时间。')


# 只有直接运行本文件时才执行 main()。
# 这样别的文件可以 `from b_ocr_image import recognize, build_ocr` 复用，
# 不会顺带把整张图识别一遍（第1周笔记里记过这个待办）。
if __name__ == '__main__':
    main()

"""
第2周 · OCR 结果与原图对照可视化

【谁在调用我】（11-13 补）
两种情况用的是同一个函数 build_report()：
    ① a_batch_ocr.py 跑完自动调用（在 main() 里「用到才 import」，属于懒加载）；
       这样即使报告生成失败，已经落盘的 result.json / result.txt 也不会白跑。
    ② 直接 python vis_ocr_result.py 独立运行，只重画报告、不重跑 OCR，
       结果从各 case 目录的 result.json 读回来。
所以我是这三个模块里唯一「既被 import、又带 main() 能独立跑」的一个。

【解决什么问题】
result.json 里只有文字和坐标，读起来不直观：
看不出「哪个框框住了哪行字」，也看不出「哪一块压根没被检测到」。
本脚本把已有的 boxes / texts / scores 还原到原图上，产出一份可离线打开的
对照报告，并把每个 case 的图片产物放回它自己的目录：

    output/a_batch_ocr/index.html                 报告（跨 case，放根）
    output/a_batch_ocr/<输入名>/source.<ext>      输入副本（图片=原图 / PDF=首页渲染图 / CSV=原始文本）
    output/a_batch_ocr/<输入名>/boxes.png         原图 + 彩色识别框 + 行号（纯文本没有图，不生成）

报告的每张卡片：
      左边 = 原图，识别框以 SVG 叠加在图上，鼠标悬停会互相高亮
      右边 = 逐行文字 + 置信度条，低置信度行标橙红色
      下方 = 标准答案对照（若有）、PDF / CSV 的「直读结果」
      顶部 = 全部 case 的汇总指标，可一键只筛「有问题的 case」
   11-13 新增：PDF / CSV 卡片右侧下面多一块「直读结果」——
      直接读文本层（或纯文本）抽出的表格、策略与质量指标、抽取诊断、原文，
      同一个 PDF 因此能并排比较「像素 OCR 读出来的字」和「文本层无损抽出的表」。

【与第1周一致的产物隔离】
每个输入一个目录，报告只在根目录放跨 case 的汇总。
卡片标题下方有链接直接跳到该 case 的 result.json，排查时不用翻大 JSON。

【重要】可视化不会重新跑 OCR，只是把已有结果画出来，所以瞬间完成、不加载模型。

【用法】在 week-02 目录下：
    python a_batch_ocr.py                # 正常批量识别，跑完会自动调用本脚本
    python vis_ocr_result.py             # 只重新生成报告（改了样式时用）
    python vis_ocr_result.py ../week-01/input   # 临时指定别的原图目录

【为什么用 HTML 而不是弹窗】
HTML 是纯文本产物，可以反复打开、Ctrl+F 搜文字、Ctrl+S 保存、发给别人，
不依赖任何 GUI 库，也不需要起本地服务。注意文件头必须写 <meta charset="utf-8">，
否则中文会乱码（第1周 d_table_ocr.py 踩过这个坑）。

【输入副本为什么复制进 case 目录】
报告用相对路径 <case 目录>/source.<ext> 引用图片；CSV 这类纯文本也留一份原始文件，
让每个 case 目录自包含、整目录搬走不会丢输入。
一开始用的是 ../../input/xxx.png，本地双击能显示，但通过静态服务 / 预览面板打开时
目录会被重映射，跳出目录的路径一律 404，整页只剩空框。
把副本放进报告所在目录的子目录后，file:// 双击、静态服务、整个
a_batch_ocr/ 目录拷走，三种方式都能显示（代价只是多一份可再生的副本）。
"""

# =========================== 配置区：调试只改这里 ===========================
OUT_ROOT = 'output/a_batch_ocr'         # 与 a_batch_ocr.py 共用的产物根（脚本一层隔离）
IMAGE_DIR = 'input'                     # 原图目录（必须与跑 OCR 时一致）
MANIFEST = 'input/samples_manifest.json'  # 样本说明书；缺条目不影响分组
# 下面只写「文件名 / 子目录名」，具体路径由 OUT_ROOT/<case 目录>/ 拼出来。
RESULT_JSON = 'result.json'             # 独立运行时从各 case 目录读回这个文件
SUMMARY_JSON = 'batch_summary.json'     # 跨 case 汇总表（模型信息从这里取）
SOURCE_BASENAME = 'source'              # 原图副本主文件名（扩展名沿用原图）
BOXES_NAME = 'boxes.png'                # 带框 PNG
REPORT_NAME = 'index.html'              # 报告落在 OUT_ROOT 根目录
LOW_SCORE = 0.8                          # 低于此值标为「可疑」，与 a_batch_ocr.py 一致
COLOR_OK = (34, 150, 90)                 # 正常行的框：绿
COLOR_LOW = (222, 92, 40)                # 可疑行的框：橙红
# ==========================================================================

import os
import sys
import json
import html
import shutil
from urllib.parse import quote            # 把文件名转成 URL 安全的写法

from PIL import Image, ImageDraw

import case_naming as naming   # 命名 / 分组 / 排序规则的唯一真相源


# --------------------------------------------------------------------------
# 一、小工具函数
# --------------------------------------------------------------------------

def read_json(path, fallback=None):
    """读 JSON 文件；文件不存在或内容损坏时返回 fallback，不让整个脚本崩掉。"""
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f'!! 读取 {path} 失败（按「无此文件」处理）：{e}')
        return fallback


def normalize_box(box):
    """
    把一条坐标整理成 [(x, y), ...] 的点列表。

    JSON 里的 boxes 来自 numpy 数组，通常是 4 个点 [[x,y],[x,y],[x,y],[x,y]]；
    但不同版本也可能给 2 点矩形或别的形状，所以这里做兼容并过滤非法值。
    """
    points = []
    for p in box:
        # p 可能是 list / tuple / numpy 数组，只要能取出前两个数即可
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            return None
        points.append((x, y))
    return points if len(points) >= 3 else None     # 至少要 3 点才能画多边形


def copy_source(src_path, case_abs, case_rel):
    """
    把输入文件复制一份进**这个 case 自己的目录**，返回报告里可用的相对路径。

    图片分支复制原图，PDF 分支复制首页渲染图（框就画在这张图上），
    CSV / 纯文本分支复制原始文本 —— 三类都留副本，是为了让每个 case 目录
    自包含：整个目录搬走后，输入、结果、报告引用还在一起，不会丢原始素材。

    为什么不用 ../../input/xxx.png：本地双击能显示，但静态服务 / 预览面板会把
    HTML 映射到一个新目录，任何跳出该目录的相对路径都会 404，报告就只剩空框。
    把副本放进「报告所在目录 / <case 目录>」里，file://、静态服务、整个
    a_batch_ocr/ 拷走，三种打开方式都能显示。
    quote 负责处理目录名 / 文件名里的空格与中文。
    """
    os.makedirs(case_abs, exist_ok=True)
    ext = os.path.splitext(src_path)[1].lower() or '.png'
    filename = SOURCE_BASENAME + ext
    shutil.copy2(src_path, os.path.join(case_abs, filename))
    return f'{quote(case_rel, safe="")}/{quote(filename, safe="")}'


def esc(text):
    """HTML 转义：识别出来的文字里若含 < & " 等符号，不转义会破坏页面结构。"""
    return html.escape(str(text), quote=True)


def norm_text(text):
    """
    粗略比对用的归一化：去空白、统一全角/半角冒号、去掉货币符号与常见标点。
    只用来「大致估计哪几行没被认出来」，不是准确率计算。
    """
    table = str.maketrans({'：': ':', '，': ',', '（': '(', '）': ')',
                           '¥': '', '￥': '', '　': ''})
    return ''.join(str(text).translate(table).split()).lower()


def rough_misses(expect_lines, texts):
    """返回「标准答案里没在识别结果中出现」的行（粗略估计，仅供筛选 bad case）。"""
    joined = norm_text(''.join(texts))
    return [line for line in expect_lines if norm_text(line) not in joined]


# --------------------------------------------------------------------------
# 二、画带框 PNG
# --------------------------------------------------------------------------

def draw_boxes_png(image_path, rec, out_path):
    """
    在原图上把每行文字的四点框画出来，左上角标行号。返回 (宽, 高)。
    框的颜色 = 置信度：正常绿、可疑橙红，一眼就能扫出哪几行不可靠。
    """
    img = Image.open(image_path).convert('RGB')
    draw = ImageDraw.Draw(img)
    width, height = img.size

    for i, box in enumerate(rec.get('boxes') or []):
        points = normalize_box(box)
        if not points:
            continue
        scores = rec.get('scores') or []
        score = scores[i] if i < len(scores) else 1.0
        color = COLOR_LOW if score < LOW_SCORE else COLOR_OK

        # 首尾相连：最后一个点再连回第一个点，框才闭合
        draw.line(points + [points[0]], fill=color, width=3, joint='curve')

        # 在框左上角画一个小色块 + 行号，方便和右侧表格对上。
        # 色块宽度按位数算，否则第 10 行以后两位数会被裁掉。
        lx = min(p[0] for p in points)
        ly = min(p[1] for p in points)
        label = str(i + 1)
        tag_w = 10 + 8 * len(label)
        box_left, box_top = lx, max(0, ly - 18)
        draw.rectangle([box_left, box_top, box_left + tag_w, box_top + 16], fill=color)
        draw.text((box_left + 5, box_top + 2), label, fill=(255, 255, 255))

    img.save(out_path)
    return width, height


# --------------------------------------------------------------------------
# 三、生成 HTML 对照报告
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#f4f6f9;--card:#fff;--ink:#1f2430;--muted:#6b7280;--line:#e3e7ee;
      --accent:#2563eb;--low:#de5c28;--ok:#22965a;}
*{box-sizing:border-box}
body{margin:0;padding:28px;background:var(--bg);color:var(--ink);
     font:14px/1.6 "Microsoft YaHei","Segoe UI",Arial,sans-serif}
header{max-width:1500px;margin:0 auto 20px}
h1{margin:0 0 6px;font-size:24px}
.sub{color:var(--muted);font-size:13px;margin-bottom:16px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;
      padding:10px 16px;min-width:130px}
.stat b{display:block;font-size:22px;line-height:1.2}
.stat span{color:var(--muted);font-size:12px}
button{border:1px solid var(--line);background:var(--card);border-radius:8px;
       padding:8px 14px;cursor:pointer;color:var(--ink)}
button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.card{max-width:1500px;margin:0 auto 22px;background:var(--card);
      border:1px solid var(--line);border-radius:12px;overflow:hidden}
.card-head{padding:14px 18px;border-bottom:1px solid var(--line)}
.card-head h2{margin:0;font-size:17px;display:inline-block}
.tag{display:inline-block;margin-left:10px;padding:2px 9px;border-radius:20px;
     background:#eef2ff;color:#3730a3;font-size:12px;vertical-align:2px}
.desc{color:var(--muted);font-size:13px;margin-top:4px}
.metrics{display:flex;gap:18px;flex-wrap:wrap;margin-top:8px;font-size:13px}
.metrics em{font-style:normal;color:var(--muted)}
.metrics b{font-weight:600}
.grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(330px,.85fr)}
.stage{position:relative;background:#eceff3;padding:14px;border-right:1px solid var(--line)}
.stage img{display:block;width:100%;height:auto}
.stage svg{position:absolute;left:14px;top:14px;width:calc(100% - 28px);
           height:calc(100% - 28px);pointer-events:none}
.box{fill:rgba(37,99,235,.06);stroke:var(--accent);stroke-width:2;
     vector-effect:non-scaling-stroke}
.box.low{fill:rgba(222,92,40,.10);stroke:var(--low)}
.box.hl{fill:rgba(37,99,235,.30);stroke-width:4}
.pane{padding:14px 16px;max-height:620px;overflow:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:500;border-bottom:1px solid var(--line);
   padding:6px 6px;position:sticky;top:0;background:var(--card)}
td{border-bottom:1px solid #f0f2f6;padding:7px 6px;vertical-align:middle}
tr[data-idx]{cursor:default}
tr[data-idx].hl,tr[data-idx]:hover{background:#eef4ff}
tr.low td.txt{color:var(--low)}
.num{width:34px;color:var(--muted)}
.txt{word-break:break-all}
.score{width:118px;white-space:nowrap}
.bar{display:inline-block;width:64px;height:7px;background:#e9edf3;border-radius:5px;
     overflow:hidden;vertical-align:middle;margin-right:5px}
.bar i{display:block;height:100%;background:var(--ok)}
tr.low .bar i{background:var(--low)}
details{margin-top:12px;border-top:1px dashed var(--line);padding-top:8px}
summary{cursor:pointer;color:var(--accent);font-size:13px}
details ul{margin:8px 0 0;padding-left:22px;color:var(--muted);font-size:12px}
details li.miss{color:var(--low)}
.tag-real{background:#fff2e6;color:#8a4b0a}
.extract{margin-top:14px;border-top:1px dashed var(--line);padding-top:10px}
.extract h3{font-size:13px;font-weight:500;margin:0 0 6px}
.extract .note{font-size:12px;color:var(--muted);margin:0 0 8px;line-height:1.5}
.tablewrap{max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.extract table{font-size:12px;width:auto;min-width:100%}
.extract th,.extract td{border:1px solid var(--line);padding:4px 7px;
  white-space:nowrap;position:static;background:none;color:var(--ink);font-weight:400}
.extract thead th{background:#f2f5fa;font-weight:500;position:sticky;top:0}
.extract table tr.low td{color:var(--ink)}
.extract table tr.first td{background:#f7f9fc}
.plain pre{white-space:pre-wrap;word-break:break-all;font-size:12px;
  background:#f7f9fc;padding:9px;border-radius:8px;margin:6px 0 0}
.empty{color:var(--muted);padding:20px}
a{color:var(--accent)}
@media(max-width:900px){.grid{grid-template-columns:1fr}.stage{border-right:0}}
"""

JS = """
// 鼠标悬停：表格行 <-> 图上的框 双向高亮。
// data-card 用来区分「第几张图」，data-idx 用来区分「这张图里的第几行」，
// 否则不同图片的 1、2、3 号会串在一起。
document.querySelectorAll('[data-card][data-idx]').forEach(function(el){
  el.addEventListener('mouseenter', function(){
    var c = el.getAttribute('data-card'), i = el.getAttribute('data-idx');
    document.querySelectorAll('[data-card="'+c+'"][data-idx="'+i+'"]')
            .forEach(function(x){ x.classList.add('hl'); });
  });
  el.addEventListener('mouseleave', function(){
    document.querySelectorAll('.hl').forEach(function(x){ x.classList.remove('hl'); });
  });
});
// 一键只看「有问题」的图：有低置信度行、识别失败、或标准答案有未命中行。
var onlyProblem = false;
document.getElementById('filterBtn').addEventListener('click', function(){
  onlyProblem = !onlyProblem;
  this.classList.toggle('on', onlyProblem);
  this.textContent = onlyProblem ? '显示全部图片' : '只看有问题的图';
  document.querySelectorAll('.card').forEach(function(card){
    card.style.display = (onlyProblem && card.getAttribute('data-problem') !== '1')
                         ? 'none' : '';
  });
});
"""


def build_extract_html(rec):
    """
    渲染「文本层 / 纯文本直读」区域：抽出的表格 + 抽取诊断 + 原文。
    图片分支没有这段，直接返回空字符串。

    这是 11-13 新增的对比重点：同一个 PDF 卡片里，
    上面的表格是「把页面当图片 OCR 读出来的字」，下面这段是「直接读文本层」，
    一个带识别误差、一个字符无损，放在一起才看得出差别。
    """
    kind = rec.get('kind', 'image')
    if kind == 'image':
        return ''
    tables = rec.get('tables') or []
    diag = rec.get('diagnostics') or {}
    parts = [f'<div class="extract"><h3>直读结果（{esc(kind)}）：{len(tables)} 张表</h3>']

    if kind == 'pdf':
        note = (f'共 {rec.get("pages", 1)} 页 · '
                + ('有文本层，表格直接抽取、未加载表格模型'
                   if rec.get('text_layer') else '无文本层，表格只能走 OCR / 结构模型'))
        if rec.get('cropbox_limited'):
            note += ' · 预览图已按 MediaBox 整页渲染（含阅读器里看不到的内容）'
    else:
        note = f'纯文本按 {rec.get("encoding", "?")} 解码 · 不跑 OCR'
    parts.append(f'<p class="note">{esc(note)}</p>')

    if not tables:
        parts.append('<p class="note">没有抽到表格，见下方诊断</p>')
    for idx, t in enumerate(tables, 1):
        rows = t.get('rows') or []
        head = (f'第 {t.get("page", 1)} 页 · {t.get("strategy", "?")} 策略 · '
                f'{t.get("n_rows", 0)}×{t.get("n_cols", 0)} · '
                f'填充率 {t.get("fill_ratio", 0)}'
                + (' · 低置信度，建议人工核对' if t.get('low_confidence') else ''))
        parts.append(f'<p class="note"><b>表 {idx}</b>　{esc(head)}　'
                     f'· 按原始抽取顺序平铺，首行可能是页眉</p>')
        if not rows:
            continue
        # 不做「第一行当表头」的假设：pdfplumber 的 text/explicit 策略常把
        # 页眉也切进表格，真正的表头可能在第 2、3 行。这里如实平铺最不容易误导。
        body = ''.join(
            f'<tr class="{"first" if j == 0 else ""}">'
            + ''.join(f'<td>{esc(c)}</td>' for c in r) + '</tr>'
            for j, r in enumerate(rows)
        )
        parts.append(f'<div class="tablewrap"><table><tbody>{body}</tbody></table></div>')

    if rec.get('plain_text'):
        parts.append('<div class="plain"><p class="note"><b>原文</b></p>'
                     f'<pre>{esc(rec["plain_text"])}</pre></div>')

    notes = list(diag.get('pages') or []) + list(diag.get('notes') or [])
    if notes:
        li = ''.join(f'<li>{esc(n)}</li>' for n in notes)
        parts.append(f'<details><summary>抽取诊断（{len(notes)} 条）</summary>'
                     f'<ul>{li}</ul></details>')
    parts.append('</div>')
    return ''.join(parts)


def build_card(rec, card_no, image_dir, out_root, manifest_map):
    """生成一张图对应的 HTML 卡片；图片产物写进这个 case 自己的目录。"""
    name = rec.get('file', '(未知文件)')
    info = manifest_map.get(name, {})
    category = info.get('category', '自定义 / 未登记')
    distortion = info.get('distortion',
                          '新增 case：未登记退化说明（不影响识别，可手工补进说明书）')
    # 分组统一交给 case_naming：manifest 有登记就信登记，没登记就按编号推断。
    # 这样 108_real_xxx.jpg 刚丢进来、还没写进说明书，也不会被误当成合成样本。
    group = naming.case_group(name, info.get('group'))
    group_label = '真实 case' if group == 'real' else '合成样本'
    case_rel = rec.get('out_dir') or naming.case_dir_name(name)
    case_abs = os.path.join(out_root, case_rel)
    case_href = quote(case_rel, safe='')
    image_path = os.path.join(image_dir, name)
    kind = rec.get('kind', 'image')
    preview = rec.get('preview_image')
    # PDF 的框是画在「首页渲染图」上的，左侧必须显示同一张图，否则坐标对不上。
    display_image = (preview if kind == 'pdf' and preview and os.path.isfile(preview)
                     else image_path)

    # ---- 左侧：原图 / PDF 首页渲染图 + SVG 框（CSV 没有图像）----
    if kind == 'csv':
        left = ('<div class="stage empty">CSV / 纯文本输入：没有图像可显示，'
                '右侧直接看解析出的表格与原文</div>')
        # 纯文本没有像素可画，但原始输入照样留一份副本：这样把整个 case 目录
        # 拷走时，输入 / 结果 / 报告引用都在一起，和图片、PDF 分支保持一致。
        src_rel = copy_source(image_path, case_abs, case_rel)
        extra = (f'纯文本分支，不跑 OCR · '
                 f'<a href="{src_rel}" target="_blank">查看原始文件</a>')
    elif os.path.isfile(display_image):
        # 原图副本和带框 PNG 都放进 <OUT_ROOT>/<case>/，报告用相对路径引用。
        src = copy_source(display_image, case_abs, case_rel)
        png_href = f'{case_href}/{BOXES_NAME}'
        w, h = draw_boxes_png(display_image, rec, os.path.join(case_abs, BOXES_NAME))
        polys = []
        for i, box in enumerate(rec.get('boxes') or []):
            pts = normalize_box(box)
            if not pts:
                continue
            scores = rec.get('scores') or []
            score = scores[i] if i < len(scores) else 1.0
            texts = rec.get('texts') or []
            tip = texts[i] if i < len(texts) else ''
            point_str = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
            cls = 'box low' if score < LOW_SCORE else 'box'
            polys.append(
                f'<polygon class="{cls}" data-card="{card_no}" data-idx="{i}" '
                f'points="{point_str}"><title>#{i + 1} {esc(tip)} (score={score:.2f})'
                f'</title></polygon>'
            )
        left = (
            f'<div class="stage"><img src="{src}" alt="{esc(name)}">'
            f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'{"".join(polys)}</svg></div>'
        )
        extra = (
            f'<a href="{src}" target="_blank">查看原图副本</a> · '
            f'<a href="{png_href}" target="_blank">查看带框 PNG</a>'
        )
    else:
        left = f'<div class="stage empty">找不到预览图：{esc(display_image)}</div>'
        extra = '（重新跑一次 python a_batch_ocr.py 生成 PDF 首页渲染图）'

    # 每个 case 的结果单独成文件，卡片上给一个直达链接，排查时不用翻大 JSON。
    extra += (f' · <a href="{case_href}/{quote(RESULT_JSON, safe="")}" '
              f'target="_blank">本 case 的 {RESULT_JSON}</a>')

    # ---- 右侧：逐行文字表格 ----
    rows = []
    texts = rec.get('texts') or []
    scores = rec.get('scores') or []
    for i, text in enumerate(texts):
        score = scores[i] if i < len(scores) else 0.0
        low = score < LOW_SCORE
        rows.append(
            f'<tr data-card="{card_no}" data-idx="{i}" class="{"low" if low else ""}">'
            f'<td class="num">{i + 1}</td>'
            f'<td class="txt">{esc(text) or "(空)"}</td>'
            f'<td class="score"><span class="bar"><i style="width:{score * 100:.0f}%"></i>'
            f'</span>{score:.2f}</td></tr>'
        )
    if rec.get('error'):
        rows.append(f'<tr><td colspan="3" style="color:var(--low)">'
                    f'识别失败：{esc(rec["error"])}</td></tr>')
    if not rows:
        hint = ('该输入没有 OCR 文字（纯文本 / 无文本层），见下方直读结果'
                if kind != 'image' else '没有识别到任何文字（整图漏检）')
        rows.append(f'<tr><td colspan="3" class="empty">{hint}</td></tr>')

    # ---- 标准答案对照（只有合成样本才有）----
    expect = info.get('expect_lines')
    details = ''
    if expect:
        misses = rough_misses(expect, texts)
        li = ''.join(
            f'<li class="{"miss" if line in misses else ""}">'
            f'{"✗ 未命中" if line in misses else "✓ 命中"}　{esc(line)}</li>'
            for line in expect
        )
        details = (
            f'<details><summary>标准答案对照：命中 {len(expect) - len(misses)}'
            f' / {len(expect)} 行（粗略估计，仅供筛选）</summary>'
            f'<ul>{li}</ul><p style="font-size:12px;color:var(--muted)">'
            f'判定方式是「归一化后做子串匹配」：OCR 把全角冒号认成半角、'
            f'多加空格、拆成两行都会算未命中，所以这个数字<b>不等于准确率</b>。'
            f'</p></details>'
        )

    low_lines = rec.get('low_score_lines', 0)
    tables = rec.get('tables') or []
    if kind == 'image':
        # 图片分支：低置信 / 识别失败 / 整图漏检 / 标准答案未命中，都算「有问题」
        problem = 1 if (low_lines or rec.get('error') or not texts
                        or (expect and rough_misses(expect, texts))) else 0
    else:
        # 非图片分支的 OCR 结果不代表成败：只有「有文本层却一张表都没抽到」
        # 才算问题。扫描件 PDF 本来就没有文本层，不该被误标。
        problem = 1 if (rec.get('error')
                        or (kind == 'pdf' and rec.get('text_layer') and not tables)
                        or (kind == 'csv' and not tables)) else 0
    table_metric = (f'<span><em>直读表格</em> <b>{len(tables)}</b></span>'
                    if kind != 'image' else '')
    head = (
        f'<div class="card-head"><h2>{esc(name)}</h2>'
        f'<span class="tag">{esc(category)}</span>'
        f'<span class="tag {"tag-real" if group == "real" else ""}">'
        f'{group_label}</span>'
        f'<div class="desc">退化 / 来源：{esc(distortion)}　·　{extra}</div>'
        f'<div class="metrics">'
        f'<span><em>识别行数</em> <b>{rec.get("lines", 0)}</b></span>'
        f'<span><em>平均置信度</em> <b>{rec.get("avg_score", 0):.2f}</b></span>'
        f'<span><em>可疑行</em> <b style="color:{"var(--low)" if low_lines else "var(--ok)"}">'
        f'{low_lines}</b></span>'
        f'{table_metric}'
        f'<span><em>耗时</em> <b>{rec.get("elapsed", 0)}s</b></span>'
        f'</div></div>'
    )
    right = (
        f'<div class="pane"><table><thead><tr><th>#</th><th>识别文字</th>'
        f'<th>置信度</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
        f'{details}{build_extract_html(rec)}</div>'
    )
    return (
        f'<section class="card" data-problem="{problem}">{head}'
        f'<div class="grid">{left}{right}</div></section>'
    )


def build_report(records, image_dir=IMAGE_DIR, out_root=OUT_ROOT,
                 manifest_path=MANIFEST, summary_path=None):
    """
    对外主函数：a_batch_ocr.py 跑完会调用它；独立运行时 main() 也会调用它。
    返回生成的 HTML 绝对路径，方便调用方打印出来。

    out_root 是「脚本一层」的产物根（报告放根，各 case 的图片放子目录）。
    summary_path 用来取模型信息；不传就默认读 out_root/batch_summary.json。
    """
    os.makedirs(out_root, exist_ok=True)
    if summary_path is None:
        summary_path = os.path.join(out_root, SUMMARY_JSON)

    manifest = read_json(manifest_path, {}) or {}
    manifest_map = {
        item['file']: item for item in (manifest.get('samples') or [])
        if isinstance(item, dict) and item.get('file')
    }

    cards = [
        build_card(rec, i, image_dir, out_root, manifest_map)
        for i, rec in enumerate(records)
    ]

    total_lines = sum(rec.get('lines', 0) for rec in records)
    total_low = sum(rec.get('low_score_lines', 0) for rec in records)
    scores = [rec.get('avg_score', 0) for rec in records if rec.get('lines', 0)]
    avg = sum(scores) / len(scores) if scores else 0.0
    total_time = sum(rec.get('elapsed', 0) for rec in records)
    total_tables = sum(len(rec.get('tables') or []) for rec in records)
    # 真实 case 的统计也走命名规则：manifest 没登记的新 case 照样算进来。
    real_count = sum(
        1 for rec in records
        if naming.is_real_case(rec.get('file', ''),
                               manifest_map.get(rec.get('file', ''), {}).get('group'))
    )
    problem_count = sum(1 for c in cards if 'data-problem="1"' in c)
    model = (read_json(summary_path, {}) or {}).get('model', {})

    stats = (
        f'<div class="stats">'
        f'<div class="stat"><b>{len(records)}</b><span>case 数</span></div>'
        f'<div class="stat"><b>{real_count}</b><span>真实 case（101~ 起编号）</span></div>'
        f'<div class="stat"><b>{total_lines}</b><span>识别总行数</span></div>'
        f'<div class="stat"><b>{avg:.2f}</b><span>平均置信度</span></div>'
        f'<div class="stat"><b style="color:var(--low)">{total_low}</b>'
        f'<span>可疑行（&lt; {LOW_SCORE}）</span></div>'
        f'<div class="stat"><b>{total_tables}</b><span>直读表格</span></div>'
        f'<div class="stat"><b>{problem_count}</b><span>有问题的 case</span></div>'
        f'<div class="stat"><b>{total_time:.1f}s</b><span>识别总耗时</span></div>'
        f'</div>'
    )

    # 注意 <meta charset="utf-8"> 必须在 <head> 最前面，否则中文会乱码
    doc = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>OCR / 文本层提取 对照报告</title>\n'
        f'<style>{CSS}</style>\n</head>\n<body>\n'
        '<header><h1>OCR / 文本层提取 对照报告</h1>'
        f'<div class="sub">模型：{esc(model.get("det", "?"))} + '
        f'{esc(model.get("rec", "?"))}　·　'
        '左图彩色框 = OCR 检测到的文字行（绿=正常，橙红=低置信度），'
        '鼠标移到右侧任意一行，左图对应框会高亮。'
        'PDF / CSV 卡片下方另有「直读结果」：直接读文本层或纯文本抽出的表格，'
        '字符无损、不经过模型，可和上面的 OCR 文字对照看。'
        '01~18 是合成样本；101~ 起编号的 1xx_real_* 是真实 case，恒排最后。'
        '每个 case 的 result.json、带框 PNG、原图副本都在同名目录里，'
        '卡片上可直接点开该 case 的结果。</div>\n'
        f'{stats}'
        '<button id="filterBtn" type="button">只看有问题的图</button>\n'
        '</header>\n'
        + '\n'.join(cards) +
        f'\n<script>{JS}</script>\n</body>\n</html>\n'
    )

    out_html = os.path.join(out_root, REPORT_NAME)
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(doc)
    return os.path.abspath(out_html)


def collect_records(out_root):
    """
    独立运行（只重画报告）时，把各个 case 目录里的 result.json 读回来。

    以前是读一个 output/batch_ocr_results.json 大文件；现在结果按 case 拆开了，
    所以改成「遍历子目录 → 各读一个」再按命名规则排序，顺序和批量跑时一致。
    """
    if not os.path.isdir(out_root):
        return []
    found = []
    for rel in os.listdir(out_root):
        path = os.path.join(out_root, rel, RESULT_JSON)
        rec = read_json(path)
        if isinstance(rec, dict) and rec.get('file'):
            rec.setdefault('out_dir', rel)
            found.append(rec)
    found.sort(key=lambda r: naming.case_sort_key(r['file']))
    return found


def main():
    # 命令行第一个参数可临时覆盖原图目录（例如指向 ../week-01/input）
    image_dir = sys.argv[1] if len(sys.argv) > 1 else IMAGE_DIR
    records = collect_records(OUT_ROOT)
    if not records:
        sys.exit(f'找不到各 case 的 {RESULT_JSON}：{os.path.abspath(OUT_ROOT)}\n'
                 f'请先运行：python a_batch_ocr.py')

    out = build_report(records, image_dir=image_dir, out_root=OUT_ROOT,
                       manifest_path=MANIFEST,
                       summary_path=os.path.join(OUT_ROOT, SUMMARY_JSON))
    print(f'>> 产物根目录：{os.path.abspath(OUT_ROOT)}')
    print(f'>> 用浏览器打开对照报告：{out}')
    print(f'>> 每个 case 的 {BOXES_NAME} / {SOURCE_BASENAME}.* 就在它自己的目录里')


if __name__ == '__main__':
    main()

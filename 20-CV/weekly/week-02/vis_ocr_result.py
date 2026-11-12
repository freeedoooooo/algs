"""
第2周 · OCR 结果与原图对照可视化

【解决什么问题】
batch_ocr_results.json 里只有文字和坐标，读起来不直观：
看不出「哪个框框住了哪行字」，也看不出「哪一块压根没被检测到」。
本脚本把 JSON 里已有的 boxes / texts / scores 还原到原图上，产出两样东西：

1. output/vis/*_boxes.png   原图 + 彩色识别框 + 行号（单张图，可直接贴进笔记）
2. output/vis/index.html    一份可离线打开的对照报告：
      左边 = 原图，识别框以 SVG 叠加在图上，鼠标悬停会互相高亮
      右边 = 逐行文字 + 置信度条，低置信度行标橙红色
      下方 = 该图的标准答案（若有）与「粗略未命中行数」，方便挑 bad case
      顶部 = 全部图片的汇总指标，可一键只筛「有问题的图」

【重要】可视化不会重新跑 OCR，只是把已有结果画出来，所以瞬间完成、不加载模型。

【用法】在 week-02 目录下：
    python a_batch_ocr.py                # 正常批量识别，跑完会自动调用本脚本
    python vis_ocr_result.py             # 只重新生成报告（改了样式 / 换了 JSON 时用）
    python vis_ocr_result.py ../week-01/input   # 临时指定别的原图目录

【为什么用 HTML 而不是弹窗】
HTML 是纯文本产物，可以反复打开、Ctrl+F 搜文字、Ctrl+S 保存、发给别人，
不依赖任何 GUI 库，也不需要起本地服务。注意文件头必须写 <meta charset="utf-8">，
否则中文会乱码（第1周 d_table_ocr.py 踩过这个坑）。
"""

# =========================== 配置区：调试只改这里 ===========================
RESULT_JSON = 'output/batch_ocr_results.json'   # 批量识别的结果
IMAGE_DIR = 'input'                             # 原图目录（必须与跑 OCR 时一致）
MANIFEST = 'input/samples_manifest.json'        # 样本说明书，不存在就跳过标准答案
VIS_DIR = 'output/vis'                          # 可视化产物目录
LOW_SCORE = 0.8                                 # 低于此值标为「可疑」，与 a_batch_ocr.py 保持一致
COLOR_OK = (34, 150, 90)                        # 正常行的框：绿
COLOR_LOW = (222, 92, 40)                       # 可疑行的框：橙红
# ==========================================================================

import os
import sys
import json
import html
from urllib.parse import quote            # 把路径转成 URL 安全的写法

from PIL import Image, ImageDraw


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


def image_rel_src(image_path, vis_dir):
    """
    算出从 HTML 文件（在 vis_dir 里）看向原图的相对路径。

    例如 vis_dir=output/vis、原图=input/01_clear.png，结果是 ../../input/01_clear.png。
    用相对路径的好处：整个 week-02 目录拷到别处，报告里的图依然能显示。
    Windows 的 \\ 必须换成 /，否则浏览器不认；quote 负责处理空格与中文。
    """
    rel = os.path.relpath(os.path.abspath(image_path), os.path.abspath(vis_dir))
    return quote(rel.replace(os.sep, '/'), safe='/')


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


def build_card(rec, card_no, image_dir, vis_dir, manifest_map):
    """生成一张图对应的 HTML 卡片。"""
    name = rec.get('file', '(未知文件)')
    info = manifest_map.get(name, {})
    category = info.get('category', '真实/自定义')
    distortion = info.get('distortion', '未提供退化说明')
    image_path = os.path.join(image_dir, name)
    stem = os.path.splitext(name)[0]

    # ---- 左侧：原图 + SVG 框 ----
    if os.path.isfile(image_path):
        png_name = f'{stem}_boxes.png'
        w, h = draw_boxes_png(image_path, rec, os.path.join(vis_dir, png_name))
        src = image_rel_src(image_path, vis_dir)
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
            f'<a href="{src}" target="_blank">查看原图</a> · '
            f'<a href="{esc(png_name)}" target="_blank">查看带框 PNG</a>'
        )
    else:
        left = f'<div class="stage empty">找不到原图：{esc(image_path)}</div>'
        extra = '（把原图放回该目录后，重新运行本脚本即可显示）'

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
        rows.append('<tr><td colspan="3" class="empty">没有识别到任何文字（整图漏检）</td></tr>')

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
    problem = 1 if (low_lines or rec.get('error') or not texts
                    or (expect and rough_misses(expect, texts))) else 0
    head = (
        f'<div class="card-head"><h2>{esc(name)}</h2>'
        f'<span class="tag">{esc(category)}</span>'
        f'<div class="desc">退化 / 来源：{esc(distortion)}　·　{extra}</div>'
        f'<div class="metrics">'
        f'<span><em>识别行数</em> <b>{rec.get("lines", 0)}</b></span>'
        f'<span><em>平均置信度</em> <b>{rec.get("avg_score", 0):.2f}</b></span>'
        f'<span><em>可疑行</em> <b style="color:{"var(--low)" if low_lines else "var(--ok)"}">'
        f'{low_lines}</b></span>'
        f'<span><em>耗时</em> <b>{rec.get("elapsed", 0)}s</b></span>'
        f'</div></div>'
    )
    right = (
        f'<div class="pane"><table><thead><tr><th>#</th><th>识别文字</th>'
        f'<th>置信度</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
        f'{details}</div>'
    )
    return (
        f'<section class="card" data-problem="{problem}">{head}'
        f'<div class="grid">{left}{right}</div></section>'
    )


def build_report(records, image_dir=IMAGE_DIR, vis_dir=VIS_DIR,
                 manifest_path=MANIFEST, result_json=RESULT_JSON):
    """
    对外主函数：a_batch_ocr.py 跑完会调用它；独立运行时 main() 也会调用它。
    返回生成的 HTML 绝对路径，方便调用方打印出来。
    """
    os.makedirs(vis_dir, exist_ok=True)

    manifest = read_json(manifest_path, {}) or {}
    manifest_map = {
        item['file']: item for item in (manifest.get('samples') or [])
        if isinstance(item, dict) and item.get('file')
    }

    cards = [
        build_card(rec, i, image_dir, vis_dir, manifest_map)
        for i, rec in enumerate(records)
    ]

    total_lines = sum(rec.get('lines', 0) for rec in records)
    total_low = sum(rec.get('low_score_lines', 0) for rec in records)
    scores = [rec.get('avg_score', 0) for rec in records if rec.get('lines', 0)]
    avg = sum(scores) / len(scores) if scores else 0.0
    total_time = sum(rec.get('elapsed', 0) for rec in records)
    problem_count = sum(1 for c in cards if 'data-problem="1"' in c)
    model = (read_json(result_json, {}) or {}).get('model', {})

    stats = (
        f'<div class="stats">'
        f'<div class="stat"><b>{len(records)}</b><span>图片数</span></div>'
        f'<div class="stat"><b>{total_lines}</b><span>识别总行数</span></div>'
        f'<div class="stat"><b>{avg:.2f}</b><span>平均置信度</span></div>'
        f'<div class="stat"><b style="color:var(--low)">{total_low}</b>'
        f'<span>可疑行（&lt; {LOW_SCORE}）</span></div>'
        f'<div class="stat"><b>{problem_count}</b><span>有问题的图</span></div>'
        f'<div class="stat"><b>{total_time:.1f}s</b><span>识别总耗时</span></div>'
        f'</div>'
    )

    # 注意 <meta charset="utf-8"> 必须在 <head> 最前面，否则中文会乱码
    doc = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>OCR 结果与原图对照报告</title>\n'
        f'<style>{CSS}</style>\n</head>\n<body>\n'
        '<header><h1>OCR 结果与原图对照报告</h1>'
        f'<div class="sub">模型：{esc(model.get("det", "?"))} + '
        f'{esc(model.get("rec", "?"))}　·　'
        '左图彩色框 = 检测到的文字行（绿=正常，橙红=低置信度）；'
        '鼠标移到右侧任意一行，左图对应框会高亮。'
        '没框到的地方就是漏检。</div>\n'
        f'{stats}'
        '<button id="filterBtn" type="button">只看有问题的图</button>\n'
        '</header>\n'
        + '\n'.join(cards) +
        f'\n<script>{JS}</script>\n</body>\n</html>\n'
    )

    out_html = os.path.join(vis_dir, 'index.html')
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(doc)
    return os.path.abspath(out_html)


def main():
    # 命令行第一个参数可临时覆盖原图目录（例如指向 ../week-01/input）
    image_dir = sys.argv[1] if len(sys.argv) > 1 else IMAGE_DIR
    payload = read_json(RESULT_JSON)
    if payload is None:
        sys.exit(f'找不到识别结果：{os.path.abspath(RESULT_JSON)}\n'
                 f'请先运行：python a_batch_ocr.py')
    # 兼容两种结构：批量脚本写的 {records:[...]}，或直接一个列表
    records = payload.get('records', []) if isinstance(payload, dict) else payload
    if not records:
        sys.exit('结果文件里没有记录，先跑一次批量识别。')

    out = build_report(records, image_dir=image_dir)
    print(f'>> 可视化产物目录：{os.path.abspath(VIS_DIR)}')
    print(f'>> 用浏览器打开对照报告：{out}')
    print('>> 每张图另有一份 *_boxes.png（原图 + 识别框），可直接贴进 bad_cases/notes.md')


if __name__ == '__main__':
    main()

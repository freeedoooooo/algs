"""
extract_report/cards.py — 卡片渲染的薄层：准备数据 + 选模板。

HTML 结构全部在 templates/*.html（Jinja2，autoescape 默认开启），
样式在 assets/report.css，交互在 assets/report.js。本文件只做：
  · 从 pageRec / 文件信封里挑出渲染所需的数据（坐标 rect、行、表格、文档块）
  · 生成自包含 data URI（CSV / Markdown 下载）
  · 调 render() 产出 HTML 片段（Markup，供上层模板安全内嵌）
"""
import io
import os
import csv
import json
import base64
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from .. import config
from .. import viewmodel

_ENV = Environment(
    loader=FileSystemLoader(config.TEMPLATES_DIR),
    autoescape=True, trim_blocks=True, lstrip_blocks=True,
    finalize=lambda v: '' if v is None else v)
_ENV.filters.update(
    f0=lambda v: '{:.0f}'.format(v), f1=lambda v: '{:.1f}'.format(v),
    f2=lambda v: '{:.2f}'.format(v), f4=lambda v: '{:.4f}'.format(v))


def file_url(rel):
    # 报告 HTML 就放在 case 目录里、与产物同级：一律相对路径。
    # file:// 直开与 /files/<case>/对照报告.html 在线打开都成立。
    return quote(rel, safe='/')


_ENV.globals['file_url'] = file_url


def render(tpl, **ctx):
    return Markup(_ENV.get_template(tpl).render(**ctx))


def csv_data_uri(headers, rows):
    """自包含 CSV：预览面板 / iframe 里相对路径取不到本地文件时也能下载。"""
    buf = io.StringIO(newline='')
    w = csv.writer(buf)
    if headers:
        w.writerow(headers)
    w.writerows(rows)
    payload = ('\ufeff' + buf.getvalue()).encode('utf-8')
    return ('data:text/csv;charset=utf-8;base64,'
            + base64.b64encode(payload).decode())


def md_data_uri(text):
    payload = text.encode('utf-8')
    return ('data:text/markdown;charset=utf-8;base64,'
            + base64.b64encode(payload).decode())


def _cell_rects(rec, space):
    """某坐标空间下的单元格 rect 数据，与表格 data-cell 一一对应。"""
    out = []
    for ti, t in enumerate(rec.get('structured_tables') or []):
        coord = t.get('coord') or {}
        if coord.get('space') != space or not coord.get('exact'):
            continue
        cells = t.get('cells') or []
        headers = t.get('headers') or []
        rows = t.get('rows') or []
        for r, row in enumerate(cells):
            for c, b in enumerate(row):
                if not b or len(b) < 4:
                    continue
                text = ''
                if r == 0 and c < len(headers):
                    text = headers[c]
                elif r - 1 < len(rows) and c < len(rows[r - 1]):
                    text = rows[r - 1][c]
                out.append({'off': ti != 0, 'ti': ti, 'r': r, 'c': c,
                            'x': b[0], 'y': b[1],
                            'w': max(0.0, b[2] - b[0]),
                            'h': max(0.0, b[3] - b[1]), 'text': text})
    return out


def _stitch_rects(stitched, page_no, space):
    """跨页合并表中「属于本页、本空间」的单元格 rect（页感知回溯叠在该页图上）。"""
    if not stitched or page_no is None:
        return []
    out = []
    for si, t in enumerate(stitched):
        for r, row in enumerate(t.get('cells') or []):
            for c, cell in enumerate(row):
                if not cell or cell.get('page') != page_no \
                        or cell.get('space') != space:
                    continue
                b = cell.get('bbox')
                if not b or len(b) < 4:
                    continue
                out.append({'si': si, 'r': r, 'c': c, 'x': b[0], 'y': b[1],
                            'w': max(0.0, b[2] - b[0]),
                            'h': max(0.0, b[3] - b[1])})
    return out


def image_views(rec, card_no, stitched=None, page_no=None, pager=''):
    """左图区：每个 view 各自一个 .imgwrap，保证 img+svg 1:1。
    pager（多页文件的翻页组件）悬浮在本 stage 底缘——锚定「看源文件」视图而非整页底部。"""
    # CSV / TXT 也留了 source.<ext> 副本，但那不是图片，不能当 <img> 渲染
    if not rec.get('image_size') or rec.get('kind') == 'csv':
        return render('image_views.html', empty=True, pager=pager)
    w, h = rec.get('image_size') or [0, 0]
    polys = []
    for i, box in enumerate(rec.get('boxes') or []):
        pts = [(float(p[0]), float(p[1])) for p in box]
        if len(pts) < 3:
            continue
        score = (rec.get('scores') or [1.0])[i]
        polys.append({
            'low': score < config.LOW_SCORE, 'idx': i,
            'points': ' '.join('{:.1f},{:.1f}'.format(x, y) for x, y in pts),
            'tip': (rec.get('texts') or [''])[i], 'score': score})
    tspace = rec.get('text_space') or 'source'
    if tspace == 'rectified' and not rec.get('rectified'):
        tspace = 'source'
    rect = None
    if rec.get('rectified'):
        rw, rh = rec.get('rectified_size') or [0, 0]
        rect = {'src': file_url(rec['rectified']), 'rw': rw, 'rh': rh,
                'rar': (rw / rh) if rh else 1.5,
                'cells': _cell_rects(rec, 'rectified'),
                'stitch': _stitch_rects(stitched, page_no, 'rectified')}
    return render('image_views.html', empty=False, pager=pager, card=card_no,
                  src=file_url(rec['source']), w=w, h=h,
                  ar=(w / h) if h else 1.5, page_no=page_no,
                  polys_src=polys if tspace == 'source' else [],
                  polys_rect=polys if tspace == 'rectified' else [],
                  cell_src=_cell_rects(rec, 'source'),
                  stitch_src=_stitch_rects(stitched, page_no, 'source'),
                  rect=rect)


def text_pane(rec, card_no):
    texts = rec.get('texts') or []
    scores = rec.get('scores') or []
    rows = []
    for i, text in enumerate(texts):
        s = scores[i] if i < len(scores) else 1.0
        rows.append({'idx': i, 'text': text, 's': s,
                     'low': s < config.LOW_SCORE,
                     'width': max(0, min(100, s * 100))})
    plain = rec.get('plain_text') or ''
    pctx = None
    if plain:
        pctx = {'aid': 'aux-plain-{}'.format(card_no), 'n': len(plain),
                'text': plain[:20000]}
    # 页头瘦身：可疑行数 / 带框图 原在页头，现整合进文字 tab 头
    n_low = rec.get('low_score_lines') or sum(1 for r in rows if r['low'])
    boxes = file_url(rec['boxes_png']) if rec.get('boxes_png') else None
    return render('text_pane.html', card=card_no, n=len(texts), rows=rows,
                  tspace=rec.get('text_space') or 'source', plain=pctx,
                  n_low=n_low, boxes=boxes)


def tables_section(rec, card_no, stitched=None):
    tables = rec.get('structured_tables') or []
    # 被并入跨页合并表的逐页表 (page, 表下标) → 合并表下标。一个文件可有多条链。
    merged = {}
    for si, st in enumerate(stitched or []):
        for part in st.get('parts') or []:
            merged[(part.get('page'), part.get('tbl'))] = si
    # 同为 space='source'，文本层 PDF 与「关闭矫正的表格模型」来源不同，
    # 标签要说清是字符 bbox 还是模型框，别让用户把近似坐标当精确看。
    src_label = ('预览图（字符 bbox）'
                 if rec.get('table_route') == 'text_layer'
                 else '原图（模型框）')
    spaces = []
    for t in tables:
        sp = (t.get('coord') or {}).get('space', 'none')
        label = {'source': src_label,
                 'rectified': '矫正图',
                 'none': '无图像载体'}.get(sp, sp)
        if label not in spaces:
            spaces.append(label)
    tctx = []
    for idx, t in enumerate(tables, 1):
        ti = idx - 1
        headers = t.get('headers') or []
        rows = t.get('rows') or []
        si = merged.get((rec.get('page', 1), ti))
        tctx.append({
            'ti': ti, 'idx': idx, 'hidden': ti != 0,
            'space': (t.get('coord') or {}).get('space') or 'none',
            'headers': headers, 'rows': rows,
            'csv_file': t.get('csv_file', 'table_{}.csv'.format(idx)),
            'csv_uri': csv_data_uri(headers, rows),
            'page': t.get('page', 1), 'source': t.get('source', '?'),
            'strategy': t.get('strategy', '?'),
            'n_rows': t.get('n_rows', 0), 'n_cols': t.get('n_cols', 0),
            'fill_ratio': t.get('fill_ratio', 0), 'title': t.get('title'),
            'merge_si': si,
            'merge_pages': ('、'.join(str(p) for p in
                                     (stitched[si].get('source_pages') or []))
                            if si is not None else '')})
    return render('tables.html', card=card_no,
                  route=rec.get('table_route', '-'), n=len(tables),
                  notes=rec.get('notes') or [],
                  has_coord=any((t.get('coord') or {}).get('exact')
                                for t in tables),
                  spaces=' / '.join(spaces), tables=tctx)


def _table_union(t):
    """全部单元格 bbox 的并集；无有效坐标返回 None。"""
    xs1, ys1, xs2, ys2 = [], [], [], []
    for row in t.get('cells') or []:
        for b in row:
            if b and len(b) >= 4:
                xs1.append(b[0])
                ys1.append(b[1])
                xs2.append(b[2])
                ys2.append(b[3])
    if not xs1:
        return None
    return [min(xs1), min(ys1), max(xs2), max(ys2)]


def _doc_blocks_ysort(rec):
    """无 layout 语义时的回退：OCR 行与 source 空间表格按 y 穿插，其余表格置底。

    落在表格并集框内的 OCR 行被过滤（内容由表格块承载，避免重复）。
    返回 [{'kind':'line','idx':i} | {'kind':'table','ti':i,'trailing':bool}]
    """
    texts = rec.get('texts') or []
    boxes = rec.get('boxes') or []
    tables = rec.get('structured_tables') or []
    unions = {}
    for ti, t in enumerate(tables):
        coord = t.get('coord') or {}
        if coord.get('space') == 'source' and coord.get('exact'):
            u = _table_union(t)
            if u:
                unions[ti] = u
    items = []
    for i in range(len(texts)):
        pts = boxes[i] if i < len(boxes) else []
        ys = [float(p[1]) for p in pts] or [0.0]
        xs = [float(p[0]) for p in pts] or [0.0]
        cy, cx = sum(ys) / len(ys), sum(xs) / len(xs)
        if any(u[0] <= cx <= u[2] and u[1] <= cy <= u[3]
               for u in unions.values()):
            continue
        items.append((min(ys), 0, {'kind': 'line', 'idx': i}))
    trailing = []
    for ti in range(len(tables)):
        if ti in unions:
            items.append((unions[ti][1], 1, {'kind': 'table', 'ti': ti}))
        else:
            trailing.append({'kind': 'table', 'ti': ti, 'trailing': True})
    items.sort(key=lambda x: (x[0], x[1]))
    return [it[2] for it in items] + trailing


_TITLE_LABELS = {'doc_title', 'paragraph_title', 'title'}
_VISUAL_LABELS = {'image', 'chart', 'formula', 'seal', 'figure'}


def _line_center(boxes, i):
    pts = boxes[i] if i < len(boxes) else []
    ys = [float(p[1]) for p in pts] or [0.0]
    xs = [float(p[0]) for p in pts] or [0.0]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _in_bbox(cx, cy, bbox):
    if not bbox or len(bbox) < 4:
        return False
    return bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]


def _doc_blocks_layout(rec):
    """有 layout 语义时直读：官方阅读顺序 + 标题角色 + 表格块。

    文字仍落到行级（data-idx 复用既有回溯通路）：每个文本块收集落在其
    block_bbox 内的投影行；表格块按出现顺序映射 structured_tables。
    返回 [{'kind':'head'|'para','lines':[idx]} | {'kind':'table','ti':i}]
    """
    texts = rec.get('texts') or []
    boxes = rec.get('boxes') or []
    tables = rec.get('structured_tables') or []
    layout = rec.get('layout') or []
    centers = [_line_center(boxes, i) for i in range(len(texts))]
    assigned = set()
    out = []
    ti = 0
    for lb in layout:
        label = str(lb.get('label') or '').lower()
        bbox = lb.get('bbox')
        inside = [i for i in range(len(texts))
                  if i not in assigned and _in_bbox(*centers[i], bbox)]
        if 'table' in label:
            assigned.update(inside)
            if ti < len(tables):
                out.append({'kind': 'table', 'ti': ti})
            ti += 1
            continue
        if label in _VISUAL_LABELS:
            assigned.update(inside)
            continue
        if not inside:
            continue
        assigned.update(inside)
        inside.sort(key=lambda i: (centers[i][1], centers[i][0]))
        out.append({'kind': 'head' if label in _TITLE_LABELS else 'para',
                    'lines': inside})
    stray = [i for i in range(len(texts)) if i not in assigned]
    if stray:
        stray.sort(key=lambda i: (centers[i][1], centers[i][0]))
        out.append({'kind': 'para', 'lines': stray})
    return out


def doc_blocks(rec):
    if rec.get('layout'):
        return _doc_blocks_layout(rec)
    return _doc_blocks_ysort(rec)


def _block_lines(rec, b):
    """块 → 行下标列表（兼容旧 'line' 与新 'head'/'para'）。"""
    if b['kind'] == 'line':
        return [b['idx']]
    return b.get('lines') or []


def _md_cell(v):
    return str(v or '').replace('|', '\\|').replace('\n', ' ')


def blocks_markdown(rec, blocks):
    """与文档视图同序的纯 Markdown（坐标信息丢弃，供下载）。"""
    texts = rec.get('texts') or []
    tables = rec.get('structured_tables') or []
    parts = []
    if not texts and rec.get('plain_text'):
        parts.append(rec['plain_text'].strip())
    for b in blocks:
        if b['kind'] in ('line', 'head', 'para'):
            idxs = _block_lines(rec, b)
            txt = '\n'.join(texts[i] for i in idxs if i < len(texts))
            if not txt:
                continue
            if b['kind'] == 'head':
                txt = '## ' + txt.replace('\n', ' ')
            parts.append(txt)
            continue
        t = tables[b['ti']]
        if t.get('title'):
            parts.append('**{}**'.format(t['title']))
        headers = t.get('headers') or []
        rows = t.get('rows') or []
        width = len(headers) or max((len(r) for r in rows), default=0)
        if not width:
            continue
        head = list(headers) + [''] * (width - len(headers))
        lines = ['| ' + ' | '.join(_md_cell(c) for c in head) + ' |',
                 '| ' + ' | '.join(['---'] * width) + ' |']
        for r in rows:
            r = list(r) + [''] * (width - len(r))
            lines.append('| ' + ' | '.join(_md_cell(c) for c in r[:width])
                         + ' |')
        parts.append('\n'.join(lines))
    return '\n\n'.join(p for p in parts if p) + '\n'


def md_pane(rec, card_no):
    texts = rec.get('texts') or []
    scores = rec.get('scores') or []
    tables = rec.get('structured_tables') or []
    blocks = doc_blocks(rec)
    items = []
    if not texts and rec.get('plain_text'):
        lines = [ln for ln in rec['plain_text'].splitlines() if ln.strip()]
        if lines:
            items.append({'kind': 'plain', 'lines': lines})
    for b in blocks:
        if b['kind'] in ('line', 'head', 'para'):
            lines = []
            for i in _block_lines(rec, b):
                if i >= len(texts):
                    continue
                s = scores[i] if i < len(scores) else 1.0
                lines.append({'idx': i, 'low': s < config.LOW_SCORE,
                              'text': texts[i]})
            if lines:
                items.append({'kind': 'lines', 'head': b['kind'] == 'head',
                              'lines': lines})
            continue
        ti = b['ti']
        t = tables[ti]
        space = (t.get('coord') or {}).get('space') or 'none'
        items.append({'kind': 'table', 'ti': ti, 'space': space,
                      'trailing': b.get('trailing'),
                      'trailing_label': {'rectified': '矫正图',
                                         'none': '无图像载体'}.get(space, space),
                      'title': t.get('title'),
                      'headers': t.get('headers') or [],
                      'rows': t.get('rows') or []})
    stem = os.path.splitext(rec.get('file', 'doc'))[0]
    n_line = sum(len(_block_lines(rec, b)) for b in blocks
                 if b['kind'] in ('line', 'head', 'para'))
    order_tip = ('按官方版面顺序组织（标题/段落/表格）'
                 if rec.get('layout') else '表格按 y 坐标穿插进文字流')
    return render('md_pane.html', card=card_no, n_line=n_line,
                  n_tbl=len(tables),
                  dl_uri=md_data_uri(blocks_markdown(rec, blocks)),
                  stem=stem, order_tip=order_tip,
                  tspace=rec.get('text_space') or 'source', items=items)


def json_section(rec, href=None, label='result.json', opened=True):
    # 展示落盘形态（ppstruct 剥掉派生投影），渲染时美化。
    # href 给出时带下载链接（单页=整份信封，与下载一致）；多页页卡片只展示本页切片。
    text = json.dumps(viewmodel.disk_view(rec), ensure_ascii=False, indent=2)
    return render('json_panel.html', opened=opened, label=label,
                  href=href, text=text)


def _render_card(pg, card_no, file_rec, single=True, page_no=None,
                 stitched=None, title_suffix='', hidden=False, pager=''):
    """渲染一个页卡片（单页文件=整张卡片；多页文件=其中一页）。复用既有全部区块。"""
    labels = {'image': '图片', 'pdf': 'PDF', 'csv': '纯文本'}
    has_stitch = (not single) and bool(stitched)
    # 多页：本页 JSON 与整份信封 JSON 各占一个独立 tab；整份信封紧凑嵌在
    # filecard 的 <script type="application/json">（全报告仅一份），首次打开
    # tab 时才美化（report.js loadFileJson）——不逐页内联（平方级膨胀），
    # 也不 fetch（file:// 直开时浏览器禁止 fetch 本地文件）。
    if single:
        json_html = json_section(file_rec, href=file_url(config.RESULT_JSON))
    else:
        json_html = json_section(
            pg, label='本页 JSON · pages[{}]'.format((page_no or 1) - 1))
    return render(
        'card.html', card=card_no, single=single, page_no=page_no,
        hidden=hidden, textspace=pg.get('text_space') or 'source',
        name=pg.get('file', '(未知)'), title_suffix=title_suffix,
        kind_label=labels.get(pg.get('kind'), pg.get('kind', '?')),
        image_views=image_views(pg, card_no, stitched, page_no, pager),
        n_text=pg.get('lines', 0),
        n_tbl=len(pg.get('structured_tables') or []),
        has_stitch=has_stitch, n_stitch=len(stitched or []),
        json_label='JSON' if single else '本页 JSON',
        text_html=text_pane(pg, card_no),
        tables_html=tables_section(pg, card_no, stitched),
        md_html=md_pane(pg, card_no),
        stitch_html=stitch_content(file_rec, card_no) if has_stitch else '',
        json_html=json_html,
        result_href=quote(config.RESULT_JSON, safe=''))


def stitch_content(file_rec, card_no):
    """跨页合并表内容（渲染进每个页卡片的「跨页合并」tab）。

    每格带 data-page/data-space，悬停自动切到该格所在页并高亮（页感知回溯）。
    一个文件可有多条跨页链 → 多个 stitchtab 子页签。card_no 用所在页卡片的编号，
    与该页图上 _stitch_rects 的 data-card 一致。
    """
    stitched = file_rec.get('stitched_tables') or []
    tctx = []
    for si, t in enumerate(stitched):
        headers = t.get('headers') or []
        rows = t.get('rows') or []
        csv_file = t.get('csv_file', 'stitched_{}.csv'.format(si + 1))
        rec_pages = [str(pp['page']) for pp in (t.get('parts') or [])
                     if pp.get('header_recovered')]
        tctx.append({
            'si': si, 'hidden': si != 0, 'headers': headers, 'rows': rows,
            'cells': t.get('cells') or [], 'csv_file': csv_file,
            'csv_uri': csv_data_uri(headers, rows),
            'n_rows': t.get('n_rows', 0), 'n_cols': t.get('n_cols', 0),
            'source_pages': '、'.join(str(p) for p in
                                     t.get('source_pages') or []),
            'rec_pages': '、'.join(rec_pages), 'title': t.get('title')})
    return render('stitch.html', card=card_no, n=len(stitched), stitched=tctx)


def _filejson_src(file_rec):
    """整份信封的紧凑 JSON（嵌入 <script type="application/json">，全报告仅一份）。
    `</` 转义成 `<\\/`（JSON 合法转义），防文字内容里的 </script> 提前闭合标签。"""
    text = json.dumps(viewmodel.disk_view(file_rec), ensure_ascii=False,
                      separators=(',', ':'))
    return text.replace('</', '<\\/')


def _multi_card(file_rec, idx):
    pages = file_rec.get('pages') or []
    stitched = file_rec.get('stitched_tables') or []
    labels = {'image': '图片', 'pdf': 'PDF', 'csv': '纯文本'}
    # 翻页组件（窗口式页码）渲染进每个页卡片的 stage，只显示激活页那组；
    # 页码窗口 / 首末页 / 跳页由 report.js renderPager 按 data-pages 动态生成。
    page_nums = [p.get('page') for p in pages]
    pager = render('pager.html', idx=idx, n=len(pages),
                   nums=','.join(str(x) for x in page_nums),
                   first=page_nums[0] if page_nums else 1)
    cards_html = [
        _render_card(p, '{}p{}'.format(idx, p.get('page')), file_rec,
                     single=False, page_no=p.get('page'), stitched=stitched,
                     hidden=(i > 0), pager=pager)
        for i, p in enumerate(pages)]
    return render('filecard.html', idx=idx,
                  name=file_rec.get('file', '(未知)'),
                  kind_label=labels.get(file_rec.get('kind'), '?'),
                  n_pages=len(pages), n_stitch=len(stitched),
                  filejson=Markup(_filejson_src(file_rec)), cards=cards_html)


def card(file_rec, idx):
    pages = file_rec.get('pages') or []
    if len(pages) <= 1:
        pg = pages[0] if pages else {}
        return _render_card(pg, idx, file_rec, single=True)
    return _multi_card(file_rec, idx)
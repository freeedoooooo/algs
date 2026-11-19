"""
report/cards.py — 卡片各区块的 HTML 渲染（只管结构，样式在 assets/report.css）。

每个文件一张卡片：
    图片区（原图 / 矫正图） · 文字内容 · 表格内容 · 完整 JSON
"""
import io
import os
import csv
import json
import html
import base64
from urllib.parse import quote

from .. import config
from .. import viewmodel


def esc(v):
    return html.escape(str(v if v is not None else ''), quote=True)


def file_url(case, rel):
    return '/files/{}/{}'.format(quote(case, safe=''),
                                 quote(rel, safe='/'))


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


def build_cell_rects(rec, card_no, space):
    """生成某个坐标空间下的 <rect>，与表格 data-cell 一一对应。"""
    out = []
    for ti, t in enumerate(rec.get('structured_tables') or []):
        coord = t.get('coord') or {}
        if coord.get('space') != space or not coord.get('exact'):
            continue
        cells = t.get('cells') or []
        headers = t.get('headers') or []
        rows = t.get('rows') or []
        off = '' if ti == 0 else ' off'
        for r, row in enumerate(cells):
            for c, b in enumerate(row):
                if not b or len(b) < 4:
                    continue
                text = ''
                if r == 0 and c < len(headers):
                    text = headers[c]
                elif r - 1 < len(rows) and c < len(rows[r - 1]):
                    text = rows[r - 1][c]
                w, h = max(0.0, b[2] - b[0]), max(0.0, b[3] - b[1])
                out.append(
                    '<rect class="cellbox{}" data-card="{}" data-tbl="{}" '
                    'data-cell="{}_{}" x="{:.1f}" y="{:.1f}" '
                    'width="{:.1f}" height="{:.1f}">'
                    '<title>表 {} · 行 {} 列 {} · {}</title></rect>'.format(
                        off, card_no, ti, r, c, b[0], b[1], w, h,
                        ti + 1, r, c + 1, esc(text)))
    return ''.join(out)


def build_stitch_rects(stitched, card_no, page_no, space):
    """跨页合并表中「属于本页、本空间」的单元格 rect（页感知回溯叠在该页图上）。"""
    if not stitched or page_no is None:
        return ''
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
                w, h = max(0.0, b[2] - b[0]), max(0.0, b[3] - b[1])
                out.append(
                    '<rect class="stitchbox" data-card="{}" data-stitch="{}" '
                    'data-cell="{}_{}" data-page="{}" x="{:.1f}" y="{:.1f}" '
                    'width="{:.1f}" height="{:.1f}">'
                    '<title>跨页表 {} · 行 {} 列 {} · 第 {} 页</title></rect>'
                    .format(card_no, si, r, c, page_no, b[0], b[1], w, h,
                            si + 1, r, c + 1, page_no))
    return ''.join(out)


def image_views(rec, card_no, stitched=None, page_no=None, pagetabs=''):
    """左图区：每个 view 各自一个 .imgwrap，保证 img+svg 1:1。
    pagetabs（多页文件的页签）悬浮在本 stage 右缘——锚定「看源文件」视图而非整页右侧。"""
    # CSV / TXT 也留了 source.<ext> 副本，但那不是图片，不能当 <img> 渲染
    if not rec.get('image_size') or rec.get('kind') == 'csv':
        return ('<div class="stage empty">{}纯文本输入：没有图像可显示，'
                '右侧是解析出的文字与表格</div>'.format(pagetabs))
    src = file_url(rec['case'], rec['source'])
    w, h = rec.get('image_size') or [0, 0]
    polys = []
    for i, box in enumerate(rec.get('boxes') or []):
        pts = [(float(p[0]), float(p[1])) for p in box]
        if len(pts) < 3:
            continue
        score = (rec.get('scores') or [1.0])[i]
        tip = (rec.get('texts') or [''])[i]
        cls = 'box low' if score < config.LOW_SCORE else 'box'
        points = ' '.join('{:.1f},{:.1f}'.format(x, y) for x, y in pts)
        polys.append(
            '<polygon class="{}" data-card="{}" data-idx="{}" points="{}">'
            '<title>#{} {} (score={:.2f})</title></polygon>'.format(
                cls, card_no, i, points, i + 1, esc(tip), score))
    tspace = rec.get('text_space') or 'source'
    if tspace == 'rectified' and not rec.get('rectified'):
        tspace = 'source'
    polys_src = ''.join(polys) if tspace == 'source' else ''
    polys_rect = ''.join(polys) if tspace == 'rectified' else ''
    cell_src = build_cell_rects(rec, card_no, 'source')
    stitch_src = build_stitch_rects(stitched, card_no, page_no, 'source')
    cell_svg = ('<svg class="cellsvg" viewBox="0 0 {} {}" '
                'preserveAspectRatio="none">{}{}</svg>'.format(
                    w, h, cell_src, stitch_src)
                ) if (cell_src or stitch_src) else ''

    # 默认隐藏常显识别框（stage 带 noboxes）；按钮初始即「显示叠加框」+on，
    # 与 report.js 切换逻辑一致。悬停文字行的 .hl / 钉住 .pin 高亮不受影响。
    boxbtn = ('<button type="button" class="boxtoggle on" data-card="{}">'
              '显示叠加框</button>'.format(card_no))
    rect_view, viewbtns = '', ''
    if rec.get('rectified'):
        rsrc = file_url(rec['case'], rec['rectified'])
        rw, rh = rec.get('rectified_size') or [0, 0]
        rar = (rw / rh) if rh else 1.5
        rect_cells = build_cell_rects(rec, card_no, 'rectified')
        stitch_rect = build_stitch_rects(stitched, card_no, page_no, 'rectified')
        rect_view = (
            '<div class="view" data-card="{}" data-view="rect" '
            'data-space="rectified" hidden>'
            '<div class="imgwrap" style="--ar:{:.4f}"><img src="{}" alt="矫正图" '
            'title="点击放大查看"><svg class="cellsvg" viewBox="0 0 {} {}" '
            'preserveAspectRatio="none">{}{}{}</svg>{}</div></div>'.format(
                card_no, rar, rsrc, rw, rh, rect_cells, polys_rect,
                stitch_rect, boxbtn))
        viewbtns = (
            '<button type="button" class="viewbtn on" data-card="{}" '
            'data-view="orig" title="原始上传图（矫正路线下无叠加框，仅作对照）">'
            '原图</button>'
            '<button type="button" class="viewbtn" data-card="{}" '
            'data-view="rect" title="单元格 / 文字框的坐标基准图">矫正图</button>'
            .format(card_no, card_no))
    viewbar = ('<div class="viewbar">{}</div>'.format(viewbtns)
               if viewbtns else '')
    ar = (w / h) if h else 1.5
    # 多页：stage 右侧留一条窄 gutter 给页签圆点，图不再被按钮盖住右缘；
    # 单页无页签，不留 gutter，图铺满。
    stage_cls = 'stage noboxes' + (' has-pages' if pagetabs else '')
    return (
        '<div class="{}">{}{}<div class="views">{}'
        '<div class="view" data-card="{}" data-view="orig" data-space="source">'
        '<div class="imgwrap" style="--ar:{:.4f}"><img src="{}" alt="原图" '
        'title="点击放大查看">'
        '<svg viewBox="0 0 {} {}" preserveAspectRatio="none">{}</svg>{}{}'
        '</div></div>{}</div></div>'.format(
            stage_cls, pagetabs, viewbar, '', card_no, ar, src, w, h,
            polys_src, cell_svg, boxbtn, rect_view))


def text_pane(rec, card_no):
    texts = rec.get('texts') or []
    scores = rec.get('scores') or []
    tspace = rec.get('text_space') or 'source'
    if texts:
        rows = []
        for i, text in enumerate(texts):
            s = scores[i] if i < len(scores) else 1.0
            low = s < config.LOW_SCORE
            rows.append(
                '<tr data-card="{}" data-idx="{}" data-space="{}" class="{}">'
                '<td class="num">{}</td><td class="txt">{}</td>'
                '<td class="score"><span class="bar"><i style="width:{:.0f}%"></i>'
                '</span>{:.2f}</td></tr>'.format(
                    card_no, i, esc(tspace), 'low' if low else '', i + 1,
                    esc(text), max(0, min(100, s * 100)), s))
        main = ('<div class="scrollbox"><table><thead><tr><th>#</th>'
                '<th>识别文字</th><th>置信度</th></tr></thead>'
                '<tbody>{}</tbody></table></div>'.format(''.join(rows)))
    else:
        main = '<div class="empty">无 OCR 文字行</div>'
    plain = rec.get('plain_text') or ''
    aux_btn = aux_src = ''
    if plain:
        aid = 'aux-plain-{}'.format(card_no)
        aux_btn = ('<button type="button" class="auxbtn" data-aux="{}" '
                   'data-title="纯文本原文（{} 字符）">文本原文</button>'
                   .format(aid, len(plain)))
        aux_src = ('<div class="aux-src" id="{}" hidden><pre>{}</pre></div>'
                   .format(aid, esc(plain[:20000])))
    return (
        '<details class="panel" open>'
        '<summary class="panel-head"><span class="panel-title">文字内容</span>'
        '<span class="cnt">{} 行</span><span class="spacer"></span>{}</summary>'
        '<div class="panel-body">{}{}</div></details>'.format(
            len(texts), aux_btn, main, aux_src))


def tables_section(rec, card_no, stitched=None):
    tables = rec.get('structured_tables') or []
    notes = rec.get('notes') or []
    route = esc(rec.get('table_route', '-'))
    # 被并入跨页合并表的逐页表 (page, 表下标) → 合并表下标。
    # 这些表下载给「完整合并表」，未合并的保持各自 CSV。一个文件可有多条链。
    merged = {}
    for si, st in enumerate(stitched or []):
        for part in st.get('parts') or []:
            merged[(part.get('page'), part.get('tbl'))] = si
    aux_btn = aux_src = ''
    if notes:
        aid = 'aux-diag-{}'.format(card_no)
        aux_btn = ('<button type="button" class="auxbtn" data-aux="{}" '
                   'data-title="提取诊断（{} 条）">提取诊断 {}</button>'
                   .format(aid, len(notes), len(notes)))
        aux_src = ('<div class="aux-src" id="{}" hidden><ul>{}</ul></div>'
                   .format(aid, ''.join('<li>{}</li>'.format(esc(n))
                                        for n in notes)))
    if not tables:
        return (
            '<details class="panel" open>'
            '<summary class="panel-head">'
            '<span class="panel-title">表格内容</span>'
            '<span class="cnt">0 张</span><span class="meta">路线：{}</span>'
            '<span class="spacer"></span>{}</summary>'
            '<div class="panel-body"><div class="empty">'
            '未检测到表格，路线 {}</div>{}</div></details>'
            .format(route, aux_btn, route, aux_src))

    has_coord = any((t.get('coord') or {}).get('exact') for t in tables)
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
    head = ('<summary class="panel-head">'
            '<span class="panel-title">表格内容</span>'
            '<span class="cnt">{} 张</span><span class="meta">路线：{}</span>'
            '<span class="spacer"></span>'.format(len(tables), route))
    if has_coord:
        head += ('<button type="button" class="allcells" data-card="{}">'
                 '显示整表网格</button>'.format(card_no))
    head += aux_btn + '</summary>'
    parts = ['<div class="panel-body">',
             '<p class="note">坐标宿主：{} '
             '<span class="hint" tabindex="0" data-tip="悬停高亮单格，点击钉住（再点取消）。">?</span>'
             '</p>'.format(esc(' / '.join(spaces)))]
    if len(tables) > 1:
        tabs = ''.join(
            '<button type="button" class="tbltab{}" data-card="{}" '
            'data-tbl="{}">表 {} · {}×{}</button>'.format(
                ' on' if i == 0 else '', card_no, i, i + 1,
                t.get('n_rows', 0), t.get('n_cols', 0))
            for i, t in enumerate(tables))
        parts.append('<div class="tbltabs">{}</div>'.format(tabs))

    for idx, t in enumerate(tables, 1):
        ti = idx - 1
        space = (t.get('coord') or {}).get('space') or 'none'
        headers = t.get('headers') or []
        rows = t.get('rows') or []
        si = merged.get((rec.get('page', 1), ti))
        if si is not None:
            st = stitched[si]
            dl_headers = st.get('headers') or []
            dl_rows = st.get('rows') or []
            csv_file = st.get('csv_file', 'stitched_{}.csv'.format(si + 1))
            dl_label = '下载完整合并表'
            badge = '<span class="tag merge">跨页合并 {}</span>'.format(si + 1)
            merge_note = (
                '<p class="note">本页是「跨页合并表 {}」的一段（来源页 {}）；'
                '下载给完整合并表，不另存碎片。</p>'.format(
                    si + 1, esc('、'.join(str(p) for p in st.get('source_pages') or []))))
        else:
            dl_headers, dl_rows = headers, rows
            csv_file = t.get('csv_file', 'table_{}.csv'.format(idx))
            dl_label = '下载 CSV'
            badge = merge_note = ''
        parts.append('<div class="tblpane" data-card="{}" data-tbl="{}" '
                     'data-space="{}"{}>'.format(
                         card_no, ti, esc(space), '' if ti == 0 else ' hidden'))
        parts.append(
            '<div class="tbl-bar"><b>表 {}</b>{}'
            '<span class="meta">第 {} 页 · {} · {} · {} 行 × {} 列 · 填充率 {}</span>'
            '<a class="btn" href="{}" download="{}">{}</a>'
            '<a class="btn ghost" href="{}" target="_blank">打开 {}</a></div>'
            .format(idx, badge, t.get('page', 1), esc(t.get('source', '?')),
                    esc(t.get('strategy', '?')), t.get('n_rows', 0),
                    t.get('n_cols', 0), t.get('fill_ratio', 0),
                    csv_data_uri(dl_headers, dl_rows), esc(csv_file), dl_label,
                    file_url(rec['case'], csv_file), esc(csv_file)))
        parts.append(merge_note)
        if t.get('title'):
            parts.append('<p class="note">标题：{}</p>'.format(esc(t['title'])))
        thead = ''
        if headers:
            thead = '<thead><tr>{}</tr></thead>'.format(''.join(
                '<th class="cell" data-card="{}" data-tbl="{}" '
                'data-cell="0_{}">{}</th>'.format(card_no, ti, c, esc(v))
                for c, v in enumerate(headers)))
        body = ''.join(
            '<tr>{}</tr>'.format(''.join(
                '<td class="cell" data-card="{}" data-tbl="{}" '
                'data-cell="{}_{}">{}</td>'.format(
                    card_no, ti, r, c, esc(v))
                for c, v in enumerate(row)))
            for r, row in enumerate(rows, 1))
        parts.append('<div class="tablewrap scrollbox"><table>{0}<tbody>{1}</tbody>'
                     '</table></div></div>'.format(thead, body))
    parts.append(aux_src)
    parts.append('</div>')
    return '<details class="panel" open>' + head + ''.join(parts) + '</details>'


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


def md_data_uri(text):
    payload = text.encode('utf-8')
    return ('data:text/markdown;charset=utf-8;base64,'
            + base64.b64encode(payload).decode())


def md_pane(rec, card_no):
    texts = rec.get('texts') or []
    scores = rec.get('scores') or []
    tables = rec.get('structured_tables') or []
    tspace = rec.get('text_space') or 'source'
    blocks = doc_blocks(rec)
    body = []
    if not texts and rec.get('plain_text'):
        for ln in rec['plain_text'].splitlines():
            if ln.strip():
                body.append('<p class="mdline">{}</p>'.format(esc(ln)))
    for b in blocks:
        if b['kind'] in ('line', 'head', 'para'):
            head = ' mdhead' if b['kind'] == 'head' else ''
            for i in _block_lines(rec, b):
                if i >= len(texts):
                    continue
                s = scores[i] if i < len(scores) else 1.0
                low = ' low' if s < config.LOW_SCORE else ''
                body.append(
                    '<p class="mdline{}{}" data-card="{}" data-idx="{}" '
                    'data-space="{}">{}</p>'
                    .format(head, low, card_no, i, esc(tspace), esc(texts[i])))
            continue
        ti = b['ti']
        t = tables[ti]
        space = (t.get('coord') or {}).get('space') or 'none'
        body.append('<div class="mdtbl" data-space="{}">'.format(esc(space)))
        if b.get('trailing'):
            label = {'rectified': '矫正图',
                     'none': '无图像载体'}.get(space, space)
            body.append('<p class="note">表 {}（坐标：{}，无法按位置穿插，置底显示）'
                        '</p>'.format(ti + 1, esc(label)))
        if t.get('title'):
            body.append('<p class="mdtbl-title">{}</p>'.format(esc(t['title'])))
        headers = t.get('headers') or []
        rows = t.get('rows') or []
        thead = ''
        if headers:
            thead = '<thead><tr>{}</tr></thead>'.format(''.join(
                '<th class="cell" data-card="{}" data-tbl="{}" '
                'data-cell="0_{}">{}</th>'.format(card_no, ti, c, esc(v))
                for c, v in enumerate(headers)))
        tbody = ''.join(
            '<tr>{}</tr>'.format(''.join(
                '<td class="cell" data-card="{}" data-tbl="{}" '
                'data-cell="{}_{}">{}</td>'.format(card_no, ti, r, c, esc(v))
                for c, v in enumerate(row)))
            for r, row in enumerate(rows, 1))
        body.append('<div class="tablewrap"><table>{}<tbody>{}</tbody>'
                    '</table></div></div>'.format(thead, tbody))
    if not body:
        body.append('<div class="empty">无文档内容</div>')
    stem = os.path.splitext(rec.get('file', 'doc'))[0]
    dl = ('<a class="btn" href="{}" download="{}.md" '
          'onclick="event.stopPropagation()">下载 Markdown</a>'
          .format(md_data_uri(blocks_markdown(rec, blocks)), esc(stem)))
    n_line = sum(len(_block_lines(rec, b)) for b in blocks
                 if b['kind'] in ('line', 'head', 'para'))
    order_tip = ('按官方版面顺序组织（标题/段落/表格）'
                 if rec.get('layout') else '表格按 y 坐标穿插进文字流')
    return (
        '<details class="panel" open>'
        '<summary class="panel-head"><span class="panel-title">文档视图</span>'
        '<span class="cnt">{} 行 · {} 表</span>'
        '<span class="spacer"></span>{}</summary>'
        '<div class="panel-body">'
        '<p class="note">悬停文字回溯左图识别框；悬停单元格回溯单格，点击钉住。'
        '<span class="hint" tabindex="0" data-tip="{}；'
        '矫正图空间的内容点击后会自动切换左图视图。">?</span></p>'
        '<div class="mdview scrollbox">{}</div></div></details>'.format(
            n_line, len(tables), dl, order_tip, ''.join(body)))


def json_section(rec, href=None, label='result.json', opened=True):
    # 展示落盘形态（ppstruct 剥掉派生投影），渲染时美化。
    # href 给出时带下载链接（单页=整份信封，与下载一致）；多页页卡片只展示本页切片。
    text = json.dumps(viewmodel.disk_view(rec), ensure_ascii=False, indent=2)
    dl = ('<a class="btn ghost" href="{}" target="_blank" '
          'onclick="event.stopPropagation()">下载</a>'.format(href)
          if href else '')
    return (
        '<details class="panel"{}>'
        '<summary class="panel-head"><span class="panel-title">完整 JSON</span>'
        '<span class="meta">{}</span><span class="spacer"></span>{}'
        '<button type="button" class="copyjson btn ghost" '
        'onclick="event.stopPropagation()">复制 JSON</button></summary>'
        '<div class="panel-body"><pre class="jsonpre">{}</pre></div>'
        '</details>'.format(' open' if opened else '', esc(label), dl, esc(text)))


def _render_card(pg, card_no, file_rec, single=True, page_no=None,
                 stitched=None, title_suffix='', hidden=False, pagetabs=''):
    """渲染一个页卡片（单页文件=整张卡片；多页文件=其中一页）。复用既有全部区块。"""
    name = pg.get('file', '(未知)')
    labels = {'image': '图片', 'pdf': 'PDF', 'csv': '纯文本'}
    img_links = []
    if pg.get('source'):
        img_links.append('<a href="{}" target="_blank">原图</a>'.format(
            file_url(pg['case'], pg['source'])))
    if pg.get('boxes_png'):
        img_links.append('<a href="{}" target="_blank">带框图</a>'.format(
            file_url(pg['case'], pg['boxes_png'])))
    if pg.get('rectified'):
        img_links.append('<a href="{}" target="_blank">矫正图</a>'.format(
            file_url(pg['case'], pg['rectified'])))
    json_link = '<a href="{}" target="_blank">result.json</a>'.format(
        file_url(file_rec['case'], config.RESULT_JSON))
    kind_label = labels.get(pg.get('kind'), pg.get('kind', '?'))
    route_label = esc(pg.get('table_route', '-'))
    # 页头右侧保留信息：图链接 + result.json（单页/多页都只此一处，不重复）。
    # 指标只留 行数/表格；可疑行仅 >0 时以琥珀色警示；置信度/耗时属诊断，不进页头。
    desc_html = '<div class="desc">{}</div>'.format(
        ' · '.join(img_links + [json_link]))
    low = pg.get('low_score_lines', 0)
    metrics_html = (
        '<div class="metrics">'
        '<span>行数 <b>{}</b></span>'
        '<span>表格 <b>{}</b></span>'
        '{}</div>'.format(
            pg.get('lines', 0), len(pg.get('structured_tables') or []),
            '<span class="warn">可疑 <b>{}</b></span>'.format(low) if low else ''))
    if single:
        head = (
            '<div class="card-head"><div class="fh-left">'
            '<h2 id="case-{}" title="{}">{}{}</h2>'
            '<span class="tag">{}</span></div>'
            '<div class="fh-right"><span class="tag">路线 {}</span>'
            '{}{}</div></div>'.format(
                card_no, esc(name), esc(name), esc(title_suffix),
                kind_label, route_label, metrics_html, desc_html))
    else:
        # 多页：页头整合进 filecard 的单一头，本页只留「页相关片段」模板（inert），
        # 切页时由 report.js 注入右侧 .pagehead-slot —— 不再每页各渲染一个可见页头。
        head = (
            '<template class="pagehead-tpl" data-page="{}">'
            '<span class="tag">第 {} 页</span><span class="tag">路线 {}</span>'
            '{}{}</template>'.format(
                page_no, page_no, route_label, metrics_html, desc_html))
    n_text = pg.get('lines', 0)
    n_tbl = len(pg.get('structured_tables') or [])
    has_stitch = (not single) and bool(stitched)
    stitch_btn = (
        '<button type="button" class="ctab stitch" data-card="{}" '
        'data-tab="stitch">跨页合并 {}</button>'.format(card_no, len(stitched))
        if has_stitch else '')
    tabs = (
        '<div class="ctabs" data-card="{}">'
        '<button type="button" class="ctab on" data-card="{}" data-tab="text">'
        '文字 {}</button>'
        '<button type="button" class="ctab" data-card="{}" data-tab="tables">'
        '表格 {}</button>'
        '<button type="button" class="ctab" data-card="{}" data-tab="md">'
        '文档</button>'
        '{}'
        '<button type="button" class="ctab" data-card="{}" data-tab="json">'
        'JSON</button></div>'.format(
            card_no, card_no, n_text, card_no, n_tbl, card_no,
            stitch_btn, card_no))
    if single:
        json_html = json_section(
            file_rec, href=file_url(file_rec['case'], config.RESULT_JSON))
    else:
        json_html = json_section(
            pg, href=None, label='本页 JSON · pages[{}]'.format(
                (page_no or 1) - 1))
    stitch_panel_html = (
        '<div class="tabpanel" data-card="{}" data-tab="stitch" hidden>{}</div>'
        .format(card_no, stitch_content(file_rec, card_no))
        if has_stitch else '')
    content = (
        '<div class="contentcol">{}'
        '<div class="tabpanel" data-card="{}" data-tab="text">{}</div>'
        '<div class="tabpanel" data-card="{}" data-tab="tables" hidden>{}</div>'
        '<div class="tabpanel" data-card="{}" data-tab="md" hidden>{}</div>'
        '{}'
        '<div class="tabpanel" data-card="{}" data-tab="json" hidden>{}</div>'
        '</div>'.format(
            tabs, card_no, text_pane(pg, card_no),
            card_no, tables_section(pg, card_no, stitched),
            card_no, md_pane(pg, card_no),
            stitch_panel_html, card_no, json_html))
    page_attr = '' if single else ' data-page="{}"'.format(page_no)
    hidden_attr = ' hidden' if hidden else ''
    return (
        '<section class="card" data-card="{}"{}{} data-textspace="{}">{}'
        '<div class="grid">{}{}</div></section>'.format(
            card_no, page_attr, hidden_attr, esc(pg.get('text_space') or 'source'),
            head, image_views(pg, card_no, stitched, page_no, pagetabs), content))


def stitch_content(file_rec, card_no):
    """跨页合并表内容（渲染进每个页卡片的「跨页合并」tab）。

    每格带 data-page/data-space，悬停自动切到该格所在页并高亮（页感知回溯）。
    一个文件可有多条跨页链 → 多个 stitchtab 子页签。card_no 用所在页卡片的编号，
    与该页图上 build_stitch_rects 的 data-card 一致。
    """
    stitched = file_rec.get('stitched_tables') or []
    if not stitched:
        return '<div class="empty">本文件没有可合并的跨页续表</div>'
    parts = ['<div class="panel-body">',
             '<p class="note">相邻页续表已合并（丢重复表头、数据顺接）。'
             '悬停单元格自动切到它所在页的图并高亮，点击钉住。'
             '<span class="hint" tabindex="0" data-tip="合并判据：相邻页 + 同列数 '
             '+ 列边界对齐 + 表头相同（空白归一化）；不满足则保持各页独立，不强行合并。'
             '一个文件可有多条跨页链，用下方子页签切换。">?</span>'
             '</p>']
    if len(stitched) > 1:
        tabs = ''.join(
            '<button type="button" class="stitchtab{}" data-card="{}" '
            'data-stitch="{}">合并表 {} · {}×{}</button>'.format(
                ' on' if i == 0 else '', card_no, i, i + 1,
                t.get('n_rows', 0), t.get('n_cols', 0))
            for i, t in enumerate(stitched))
        parts.append('<div class="tbltabs">{}</div>'.format(tabs))
    for si, t in enumerate(stitched):
        headers = t.get('headers') or []
        rows = t.get('rows') or []
        cells = t.get('cells') or []
        csv_file = t.get('csv_file', 'stitched_{}.csv'.format(si + 1))
        parts.append('<div class="stitchpane" data-card="{}" data-stitch="{}"{}>'
                     .format(card_no, si, '' if si == 0 else ' hidden'))
        parts.append(
            '<div class="tbl-bar"><b>跨页合并表 {}</b>'
            '<span class="meta">来源页 {} · {} 行 × {} 列</span>'
            '<a class="btn" href="{}" download="{}">下载完整 CSV</a>'
            '<a class="btn ghost" href="{}" target="_blank">打开 {}</a></div>'
            .format(si + 1, esc('、'.join(str(p) for p in t.get('source_pages') or [])),
                    t.get('n_rows', 0), t.get('n_cols', 0),
                    csv_data_uri(headers, rows), esc(csv_file),
                    file_url(file_rec['case'], csv_file), esc(csv_file)))
        if t.get('title'):
            parts.append('<p class="note">标题：{}</p>'.format(esc(t['title'])))

        def cell_attr(r, c):
            cell = (cells[r][c] if r < len(cells) and c < len(cells[r]) else None)
            pno = (cell or {}).get('page')
            space = (cell or {}).get('space') or 'source'
            return ' data-page="{}" data-space="{}"'.format(
                pno if pno is not None else '', esc(space))

        thead = ''
        if headers:
            thead = '<thead><tr>{}</tr></thead>'.format(''.join(
                '<th class="scell" data-card="{}" data-stitch="{}" '
                'data-cell="0_{}"{}>{}</th>'.format(
                    card_no, si, c, cell_attr(0, c), esc(v))
                for c, v in enumerate(headers)))
        body = ''.join(
            '<tr>{}</tr>'.format(''.join(
                '<td class="scell" data-card="{}" data-stitch="{}" '
                'data-cell="{}_{}"{}>{}</td>'.format(
                    card_no, si, r, c, cell_attr(r, c), esc(v))
                for c, v in enumerate(row)))
            for r, row in enumerate(rows, 1))
        parts.append('<div class="tablewrap scrollbox"><table>{}<tbody>{}</tbody>'
                     '</table></div></div>'.format(thead, body))
    # 整份信封 JSON 收进跨页 tab（默认收起），不再在文件底部单列占版面
    parts.append(json_section(
        file_rec, href=file_url(file_rec['case'], config.RESULT_JSON),
        label='整份 result.json（含 stitched_tables）', opened=False))
    parts.append('</div>')
    return (
        '<details class="panel" open>'
        '<summary class="panel-head"><span class="panel-title">跨页合并表</span>'
        '<span class="cnt">{}</span><span class="spacer"></span></summary>'
        '{}</details>'.format(len(stitched), ''.join(parts)))


def _multi_card(file_rec, idx):
    pages = file_rec.get('pages') or []
    stitched = file_rec.get('stitched_tables') or []
    name = file_rec.get('file', '(未知)')
    labels = {'image': '图片', 'pdf': 'PDF', 'csv': '纯文本'}
    # 单一整合页头（单行）：左=标题+类型+页数+跨页合并标签；右=.pagehead-slot，
    # 切页时由 JS 注入当前页的 第N页/路线/行数/表格/可疑/链接（含整份 result.json）。
    head = (
        '<div class="card-head filehead"><div class="fh-left">'
        '<h2 id="case-{}" title="{}">{}</h2>'
        '<span class="tag">{}</span><span class="tag">{} 页</span>{}</div>'
        '<div class="fh-right pagehead-slot"></div></div>'.format(
            idx, esc(name), esc(name), labels.get(file_rec.get('kind'), '?'),
            len(pages),
            '<span class="tag merge">跨页合并 {}</span>'.format(len(stitched))
            if stitched else ''))
    # 页签渲染进每个页卡片的 stage（悬浮在「看源文件」视图右缘），只显示激活页那组。
    pagetabs = '<div class="pagetabs">{}</div>'.format(''.join(
        '<button type="button" class="pagetab{}" data-file="{}" data-page="{}"'
        ' title="第 {} 页">{}</button>'.format(
            ' on' if i == 0 else '', idx, p.get('page'),
            p.get('page'), p.get('page'))
        for i, p in enumerate(pages)))
    cards_html = ''.join(
        _render_card(p, '{}p{}'.format(idx, p.get('page')), file_rec,
                     single=False, page_no=p.get('page'), stitched=stitched,
                     hidden=(i > 0), pagetabs=pagetabs)
        for i, p in enumerate(pages))
    return (
        '<section class="filecard" data-file="{}">{}{}</section>'.format(
            idx, head, cards_html))


def card(file_rec, idx):
    pages = file_rec.get('pages') or []
    if len(pages) <= 1:
        pg = pages[0] if pages else {}
        return _render_card(pg, idx, file_rec, single=True)
    return _multi_card(file_rec, idx)

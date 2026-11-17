"""
report/cards.py — 卡片各区块的 HTML 渲染（只管结构，样式在 assets/report.css）。

每个文件一张卡片：
    图片区（原图 / 矫正图） · 提取内容 · 表格内容 · 完整 JSON
"""
import io
import csv
import json
import html
import base64
from urllib.parse import quote

from .. import config


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


def image_views(rec, card_no):
    """左图区：每个 view 各自一个 .imgwrap，保证 img+svg 1:1。"""
    # CSV / TXT 也留了 source.<ext> 副本，但那不是图片，不能当 <img> 渲染
    if not rec.get('image_size') or rec.get('kind') == 'csv':
        return ('<div class="stage empty">纯文本输入：没有图像可显示，'
                '右侧是解析出的文字与表格</div>')
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
    cell_src = build_cell_rects(rec, card_no, 'source')
    cell_svg = ('<svg class="cellsvg" viewBox="0 0 {} {}" '
                'preserveAspectRatio="none">{}</svg>'.format(w, h, cell_src)
                ) if cell_src else ''

    rect_view, viewbar = '', ''
    if rec.get('rectified'):
        rsrc = file_url(rec['case'], rec['rectified'])
        rw, rh = rec.get('rectified_size') or [0, 0]
        rar = (rw / rh) if rh else 1.5
        rect_cells = build_cell_rects(rec, card_no, 'rectified')
        rect_view = (
            '<div class="view" data-card="{}" data-view="rect" hidden>'
            '<div class="imgwrap" style="--ar:{:.4f}"><img src="{}" alt="矫正图" '
            'title="点击放大查看"><svg class="cellsvg" viewBox="0 0 {} {}" '
            'preserveAspectRatio="none">{}</svg></div></div>'.format(
                card_no, rar, rsrc, rw, rh, rect_cells))
        viewbar = (
            '<div class="viewbar">'
            '<button type="button" class="viewbtn on" data-card="{}" '
            'data-view="orig">原图</button>'
            '<button type="button" class="viewbtn" data-card="{}" '
            'data-view="rect">矫正图（单元格坐标基准）</button></div>'.format(
                card_no, card_no))
    ar = (w / h) if h else 1.5
    return (
        '<div class="stage">{}<div class="views">{}'
        '<div class="view" data-card="{}" data-view="orig">'
        '<div class="imgwrap" style="--ar:{:.4f}"><img src="{}" alt="原图" '
        'title="点击放大查看">'
        '<svg viewBox="0 0 {} {}" preserveAspectRatio="none">{}</svg>{}'
        '</div></div>{}</div></div>'.format(
            viewbar, '', card_no, ar, src, w, h,
            ''.join(polys), cell_svg, rect_view))


def text_pane(rec, card_no):
    texts = rec.get('texts') or []
    scores = rec.get('scores') or []
    if texts:
        rows = []
        for i, text in enumerate(texts):
            s = scores[i] if i < len(scores) else 1.0
            low = s < config.LOW_SCORE
            rows.append(
                '<tr data-card="{}" data-idx="{}" class="{}">'
                '<td class="num">{}</td><td class="txt">{}</td>'
                '<td class="score"><span class="bar"><i style="width:{:.0f}%"></i>'
                '</span>{:.2f}</td></tr>'.format(
                    card_no, i, 'low' if low else '', i + 1, esc(text),
                    max(0, min(100, s * 100)), s))
        body = ('<table><thead><tr><th>#</th><th>识别文字</th>'
                '<th>置信度</th></tr></thead><tbody>{}</tbody></table>'
                .format(''.join(rows)))
    else:
        body = '<div class="empty">没有 OCR 文字行（纯文本输入或未检测到文字）</div>'
    plain = rec.get('plain_text') or ''
    extra = ''
    if plain:
        extra = ('<details><summary>文本层原文 / 纯文本全文（{} 字符）</summary>'
                 '<pre>{}</pre></details>'.format(len(plain),
                                                  esc(plain[:20000])))
    return ('<div class="pane"><h3 class="pane-title">提取内容</h3>{}{}</div>'
            .format(body, extra))


def tables_section(rec, card_no):
    tables = rec.get('structured_tables') or []
    notes = rec.get('notes') or []
    if not tables:
        diag = ''
        if notes:
            diag = ('<details><summary>提取诊断（{} 条）</summary><ul>{}</ul>'
                    '</details>'.format(
                        len(notes),
                        ''.join('<li>{}</li>'.format(esc(n)) for n in notes)))
        return ('<div class="sec"><h3>表格内容</h3>'
                '<p class="note">本文件未检测到结构化表格。提取路线：{}</p>'
                '{}</div>'.format(esc(rec.get('table_route', '-')), diag))

    has_coord = any((t.get('coord') or {}).get('exact') for t in tables)
    # 同为 space='source'，文本层 PDF 与「关闭矫正的表格模型」来源不同，
    # 标签要说清是字符 bbox 还是模型框，别让用户把近似坐标当精确看。
    src_label = ('预览图（PDF 文本层字符 bbox，精确）'
                 if rec.get('table_route') == 'text_layer'
                 else '原图（矫正关闭，模型单元格框 1:1 精确）')
    spaces = []
    for t in tables:
        s = (t.get('coord') or {}).get('space', 'none')
        label = {'source': src_label,
                 'rectified': '矫正图（转正 + 去扭曲，1:1 精确）',
                 'none': '无图像载体'}.get(s, s)
        if label not in spaces:
            spaces.append(label)
    parts = ['<div class="sec"><div class="sec-head"><h3>表格内容</h3>',
             '<span class="cnt">{} 张</span>'.format(len(tables)),
             '<span class="note">路线：{}</span><span class="spacer"></span>'
             .format(esc(rec.get('table_route', '-')))]
    if has_coord:
        parts.append('<button type="button" class="allcells" data-card="{}">'
                     '显示整表网格</button>'.format(card_no))
    parts.append('</div>')
    parts.append('<p class="note">坐标宿主：{} '
                 '<span class="hint" tabindex="0" data-tip="悬停表格单元格：图上只高亮这一格；'
                 '点击：钉住该格（再点取消）；旋转扫描件点击时会自动切到矫正图。">?</span>'
                 '</p>'.format(esc(' / '.join(spaces))))
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
        csv_file = t.get('csv_file', 'table_{}.csv'.format(idx))
        parts.append('<div class="tblpane" data-card="{}" data-tbl="{}" '
                     'data-space="{}"{}>'.format(
                         card_no, ti, esc(space), '' if ti == 0 else ' hidden'))
        parts.append(
            '<div class="tbl-bar"><b>表 {}</b>'
            '<span class="meta">第 {} 页 · {} · {} · {} 行 × {} 列 · 填充率 {}</span>'
            '<a class="btn" href="{}" download="{}">下载 CSV</a>'
            '<a class="btn ghost" href="{}" target="_blank">打开 {}</a></div>'
            .format(idx, t.get('page', 1), esc(t.get('source', '?')),
                    esc(t.get('strategy', '?')), t.get('n_rows', 0),
                    t.get('n_cols', 0), t.get('fill_ratio', 0),
                    csv_data_uri(headers, rows), esc(csv_file),
                    file_url(rec['case'], csv_file), esc(csv_file)))
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
        parts.append('<div class="tablewrap"><table>{0}<tbody>{1}</tbody>'
                     '</table></div></div>'.format(thead, body))
    if notes:
        parts.append('<details><summary>提取诊断（{} 条）</summary><ul>{}</ul>'
                     '</details>'.format(
                         len(notes),
                         ''.join('<li>{}</li>'.format(esc(n)) for n in notes)))
    parts.append('</div>')
    return ''.join(parts)


def json_section(rec):
    text = json.dumps(rec, ensure_ascii=False, indent=2)
    href = file_url(rec['case'], config.RESULT_JSON)
    return (
        '<div class="sec"><details><summary>完整 JSON（result.json）　·　'
        '<a href="{}" target="_blank" onclick="event.stopPropagation()">下载</a>'
        '　·　<button type="button" class="copyjson jsontoggle" '
        'onclick="event.stopPropagation()">复制 JSON</button></summary>'
        '<pre class="jsonpre">{}</pre></details></div>'.format(
            href, esc(text)))


def card(rec, card_no):
    name = rec.get('file', '(未知)')
    labels = {'image': '图片', 'pdf': 'PDF', 'csv': '纯文本'}
    links = []
    if rec.get('source'):
        links.append('<a href="{}" target="_blank">原图副本</a>'.format(
            file_url(rec['case'], rec['source'])))
    if rec.get('boxes_png'):
        links.append('<a href="{}" target="_blank">带框 PNG</a>'.format(
            file_url(rec['case'], rec['boxes_png'])))
    if rec.get('rectified'):
        links.append('<a href="{}" target="_blank">矫正图</a>'.format(
            file_url(rec['case'], rec['rectified'])))
    links.append('<a href="{}" target="_blank">result.json</a>'.format(
        file_url(rec['case'], config.RESULT_JSON)))
    head = (
        '<div class="card-head"><h2 id="case-{}">{}</h2>'
        '<span class="tag">{}</span><span class="tag">路线 {}</span>'
        '<div class="desc">{}</div>'
        '<div class="metrics">'
        '<span>识别行数 <b>{}</b></span>'
        '<span>平均置信度 <b>{:.2f}</b></span>'
        '<span>可疑行 <b>{}</b></span>'
        '<span>结构化表格 <b>{}</b></span>'
        '<span>耗时 <b>{}s</b></span></div></div>'.format(
            card_no, esc(name),
            labels.get(rec.get('kind'), rec.get('kind', '?')),
            esc(rec.get('table_route', '-')), ' · '.join(links),
            rec.get('lines', 0), rec.get('avg_score', 0),
            rec.get('low_score_lines', 0),
            len(rec.get('structured_tables') or []), rec.get('elapsed', 0)))
    n_text = rec.get('lines', 0)
    n_tbl = len(rec.get('structured_tables') or [])
    tabs = (
        '<div class="ctabs" data-card="{}">'
        '<button type="button" class="ctab on" data-card="{}" data-tab="text">'
        '文字行 {}</button>'
        '<button type="button" class="ctab" data-card="{}" data-tab="tables">'
        '表格 {}</button>'
        '<button type="button" class="ctab" data-card="{}" data-tab="json">'
        'JSON</button></div>'.format(
            card_no, card_no, n_text, card_no, n_tbl, card_no))
    content = (
        '<div class="contentcol">{}'
        '<div class="tabpanel" data-card="{}" data-tab="text">{}</div>'
        '<div class="tabpanel" data-card="{}" data-tab="tables" hidden>{}</div>'
        '<div class="tabpanel" data-card="{}" data-tab="json" hidden>{}</div>'
        '</div>'.format(
            tabs, card_no, text_pane(rec, card_no),
            card_no, tables_section(rec, card_no),
            card_no, json_section(rec)))
    return (
        '<section class="card" data-card="{}">{}'
        '<div class="grid">{}{}</div></section>'.format(
            card_no, head, image_views(rec, card_no), content))

"""
pipeline/structure.py — 把 raw 表整理成「有表头、每格带 bbox」的结构化表。

cells[r][c] 与「表头 1 行 + 数据 n 行」严格同形状，
报告里的 <td data-cell="r_c"> 才能直接索引，不用再换算。
"""
import os
import re
import csv
from decimal import Decimal, InvalidOperation


def align_cell_grid(rows, grid):
    if not grid:
        return []
    width = max((len(r) for r in rows), default=0)
    out = [g[:width] + [None] * max(0, width - len(g))
           for g in grid][:len(rows)]
    while len(out) < len(rows):
        out.append([None] * width)
    return out


def split_header(rows):
    """返回 (标题行, 表头, 数据行, 表头在原 rows 里的下标)。"""
    if not rows:
        return [], [], [], 0
    width = max(len(r) for r in rows)
    rows = [list(r) + [''] * (width - len(r)) for r in rows]
    idx = 0
    for i, row in enumerate(rows[:6]):
        filled = sum(1 for c in row if str(c).strip())
        if filled >= 3 and filled == width:
            idx = i
            break
    # 表头前的「碎片标签行」（如 108 单独一行的 余额/摘要）并入表头对应列，
    # 而不是误当成表格标题。真实标题通常是单个跨列长单元格，不满足此条件。
    headers = list(rows[idx])
    title_rows = []
    for r in rows[:idx]:
        cells = [(c, str(v).strip()) for c, v in enumerate(r) if str(v).strip()]
        label_like = (len(cells) >= 2 and
                      all(len(v) <= 8 and not any(ch.isdigit() for ch in v)
                          for _, v in cells))
        if label_like:
            for c, v in cells:
                if c < len(headers):
                    headers[c] = v
        else:
            title_rows.append(r)
    return title_rows, headers, rows[idx + 1:], idx


# ---- 多行表头块（复杂财报表）：R1..Rn 全是标签、无数据，叶子列名散落在不同层 ----
# 老路径（split_header 单行表头）逐字段不变；仅当识别到「跨多列合并单元格 + 连续
# 多行纯标签」时才走这里，把整块展平成一行列名，同时保留 header_chain 供跨页判定。
_NL_WS = re.compile(r'\s*\n\s*')
_NUM_DATA = re.compile(r'\d{5,}|\d+\.\d{1,2}')

# 通用启发式阈值（与具体文档无关，集中在此便于调整）：
# 表头块最多扫前 6 行；跨列合并至少覆盖 3 列才算层级表头；
# 断行标签尾巴 ≤6 字、前驱 ≥8 字且不以中文编号/括号开头。
_HEADER_SCAN_ROWS = 6
_MIN_SPAN_COLS = 3
_TAIL_MAX_LEN = 6
_HEAD_MIN_LEN = 8
_LABEL_START_RE = re.compile(r'^[（(一二三四五六七八九十\d]')


def _flat_cell(v):
    """窄列折行：竖排单字/断行数字/折行标签。只去换行两侧空白，保留普通空格。"""
    return _NL_WS.sub('', str(v or ''))


def _col_edges(grid):
    """从单元格 bbox 左缘聚类出列边界；跨列合并格只贡献一个左缘。"""
    xs = set()
    for row in grid or []:
        for b in row:
            if b and len(b) >= 4:
                xs.add(round(float(b[0]), 1))
    merged = []
    for x in sorted(xs):
        if not merged or x - merged[-1] > 2:
            merged.append(x)
    return merged


def _header_block(rows, grid):
    """返回 (h1, chain, edges) 或 None。h1 = 表头块行数，chain = 逐行非空标签。"""
    if not rows:
        return None
    edges = _col_edges(grid)
    if len(edges) < 3:
        return None
    h1, chain = 0, []
    for ri, r in enumerate(rows[:_HEADER_SCAN_ROWS]):
        cells = [_flat_cell(c) for c in r]
        nonempty = [c for c in cells if c.strip()]
        if not nonempty or any(_NUM_DATA.search(c) for c in nonempty):
            break
        if ri:
            # 无跨列合并、且非空格含首列 → 是数据行（续表首行常是纯标签尾巴），停
            wide = any(b and len(b) >= 4 and
                       sum(1 for x in edges
                           if float(b[0]) - 2 <= x < float(b[2]) - 2)
                       >= _MIN_SPAN_COLS
                       for b in (grid[ri] if ri < len(grid) else []))
            if not wide and any(c.strip() for c in cells[:1]):
                break
        h1 += 1
        chain.append(nonempty)
    if h1 < 2:
        return None
    span_found = any(
        b and len(b) >= 4 and
        sum(1 for x in edges if float(b[0]) - 2 <= x < float(b[2]) - 2)
        >= _MIN_SPAN_COLS
        for ri in range(h1) for b in (grid[ri] if ri < len(grid) else []))
    return (h1, chain, edges) if span_found else None


def _flatten_header(rows, grid, h1, edges):
    """按 span 覆盖列收集各层标签；跨过半数的分组标签让位给下层叶子。"""
    width = len(edges)
    labels = [[] for _ in range(width)]
    head_grid = [None] * width
    for ri in range(h1):
        row = rows[ri]
        grow = grid[ri] if ri < len(grid) else []
        for ci in range(min(width, len(row))):
            b = grow[ci] if ci < len(grow) else None
            if not b or len(b) < 4:
                continue
            x0, x1 = float(b[0]), float(b[2])
            cov = [j for j, x in enumerate(edges) if x0 - 2 <= x < x1 - 2]
            txt = _flat_cell(row[ci]).strip()
            if not cov or not txt:
                continue
            for j in cov:
                labels[j].append((len(cov), txt))
                if head_grid[j] is None or ri == h1 - 1:
                    head_grid[j] = list(b)
    headers = []
    for j in range(width):
        cand = labels[j]
        if not cand:
            headers.append('')
            continue
        narrow = [t for span, t in cand if span * 2 <= width]
        chosen, seen = [], set()
        for t in (narrow or [t for _span, t in cand]):
            if t not in seen:
                seen.add(t)
                chosen.append(t)
        headers.append('/'.join(chosen))
    return headers, head_grid


def _label_only(row):
    """仅首列有短标签、其余全空 —— 跨页断行标签的形态。"""
    vals = [str(c or '').strip() for c in row]
    return bool(vals[0]) and not any(vals[1:]) and len(vals[0]) <= 24


# 勾稽列名模式（可选校验）：表头命中这些语义才做合计核对，找不到就跳过，
# 不参与任何提取决策。按项目覆盖即可适配其它语种/命名，不写死某张表的列名。
_RECON_LABELS = ('sub', 'minor', 'total')
_RECON_PATTERNS = {
    'sub': re.compile(r'小计|subtotal', re.I),
    'minor': re.compile(r'少数股东|minority', re.I),
    'total': re.compile(r'合计|总计|total', re.I),
}


def _reconcile(headers, rows):
    """按列名模式找 小计 / 附加 / 合计 三列，核对 合计 = 小计 + 附加。
    只记差异，不改数值；未识别到三列时返回 None（不影响链路）。"""
    pos = {}
    for i, h in enumerate(headers or []):
        for key in _RECON_LABELS:
            if key not in pos and _RECON_PATTERNS[key].search(str(h or '')):
                pos[key] = i
    if len(pos) < 3:
        return None

    def num(s):
        s = str(s or '').replace(',', '').strip()
        if not s or s == '-':
            return None
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    fails = []
    for ri, row in enumerate(rows):
        vals = [num(row[pos[k]]) if pos[k] < len(row) else None
                for k in ('sub', 'minor', 'total')]
        if any(v is None for v in vals):
            continue
        if abs(vals[2] - (vals[0] + vals[1])) > Decimal('0.02'):
            fails.append({'row': ri, 'expect': str(vals[0] + vals[1]),
                          'actual': str(vals[2])})
    return {'checked': True, 'fails': fails}


def structure_table(raw, index):
    raw_rows = [list(r) for r in (raw.get('rows') or [])]
    rows = [[re.sub(r'\s+', ' ', str(c or '')).strip()
             for c in r] for r in raw_rows]
    grid = align_cell_grid(rows, raw.get('cell_grid') or [])
    block = _header_block(raw_rows, grid)
    if block:
        # 复杂表头块：整块展平成一行，数据从块后开始；竖排单字/断行数字在此拼回。
        h1, chain, edges = block
        headers, head_grid = _flatten_header(raw_rows, grid, h1, edges)
        data = [[_flat_cell(c) for c in r] for r in raw_rows[h1:]]
        data_grid = grid[h1:]
        title_rows, hidx = [], 0
        keep = [i for i, r in enumerate(data) if any(r)]
        data = [data[i] for i in keep]
        data_grid = [data_grid[i] for i in keep] if data_grid else []
        width = len(headers)
        cells = ([head_grid] + data_grid) if grid else []
        title = ' / '.join(c for row in chain[:1] for c in row
                           if c and _NUM_DATA.search(c))
    else:
        title_rows, headers, data, hidx = split_header(rows)
        head_grid = grid[hidx] if grid else []
        data_grid = grid[hidx + 1:] if grid else []
        keep = [i for i, r in enumerate(data) if any(r)]
        data = [data[i] for i in keep]
        data_grid = [data_grid[i] for i in keep] if data_grid else []
        width = len(headers) if headers else max((len(r) for r in data), default=0)
        cells = ([head_grid] + data_grid) if grid else []
        title = ' / '.join(c for r in title_rows for c in r if c)
    total = len(data) * width
    filled = sum(1 for r in data for c in r if c)
    coord = dict(raw.get('coord') or {'space': 'none', 'exact': False,
                                      'note': '无坐标'})
    coord['grid_rows'] = len(cells)
    coord['grid_cols'] = width
    return {
        'page': raw.get('page', 1),
        'source': raw.get('source', '?'),
        'strategy': raw.get('strategy', '?'),
        'title': title,
        'headers': headers,
        'rows': data,
        'cells': cells,
        'coord': coord,
        'n_rows': len(data),
        'n_cols': width,
        'fill_ratio': round(filled / total, 3) if total else 0.0,
        'low_confidence': (filled / total if total else 0) < 0.20,
        'csv_file': 'table_{}.csv'.format(index),
        'header_rows': h1 if block else 1,
        'header_chain': chain if block else [],
        'col_edges': edges if block else [],
    }


def structure_all(raw_tables):
    return [structure_table(t, i) for i, t in enumerate(raw_tables, 1)]


def export_csvs(structured, case_abs):
    """每张表一份 UTF-8 BOM 的 CSV，第一行固定是表头。"""
    for t in structured:
        path = os.path.join(case_abs, t['csv_file'])
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            if t['headers']:
                w.writerow(t['headers'])
            w.writerows(t['rows'])


# ---- 跨页表拼接：相邻页续表合并成一张逻辑表 ----
# 确定性优先，两条通路：
#   repeat    —— 同列数 + 列 x 对齐 + 表头逐字重复：丢后续页重复表头、数据顺接（原严格通路）。
#   headerless—— 续页无重复表头（首行数据被误标表头）+ 末尾空列被裁：列位置子集对齐 +
#                续页贴顶 + 首行像数据 → 回收首行作数据、按主表布局补齐空列。
# 判据不满足一律不合并（宁可不拼，不误拼）。合并表每个单元格保留 {bbox, page, space}，
# 报告据此做「页感知回溯」：悬停某格自动切到它所在页的图并高亮。

def _col_left_edges(t):
    """取首个有效坐标行的各列左缘 x0（缺格为 None），用于列对齐判断。"""
    for row in t.get('cells') or []:
        if sum(1 for b in row if b and len(b) >= 4) >= 2:
            return [(b[0] if b and len(b) >= 4 else None) for b in row]
    return []


def _cols_aligned(a, b, tol=12.0):
    ea, eb = _col_left_edges(a), _col_left_edges(b)
    pairs = [(ea[i], eb[i]) for i in range(min(len(ea), len(eb)))
             if ea[i] is not None and eb[i] is not None]
    if len(pairs) < 2:
        return False
    return all(abs(x - y) <= tol for x, y in pairs)


def _norm_header(h):
    return [re.sub(r'\s+', ' ', str(c or '')).strip() for c in (h or [])]


# 通用数据形态（不写死任何 case）：长数字串 / YYYYMMDD 日期 / 带小数点金额。
_DATA_RE = re.compile(
    r'\d{6,}|(?:19|20)\d{2}(?:0[1-9]|1[2])(?:0[1-9]|[12]\d|3[01])|\d+\.\d{1,2}')


def _col_xs(t):
    """每列左缘 x0：跨所有坐标行取首个非 None，比单行更完整（缺格列也能定位）。"""
    xs = []
    for row in t.get('cells') or []:
        while len(xs) < len(row):
            xs.append(None)
        for j, b in enumerate(row):
            if xs[j] is None and b and len(b) >= 4:
                xs[j] = b[0]
    return xs


def _col_map(a, b, tol=12.0):
    """续页列 → 主表列 的保序单射 x 匹配（贪心双指针）。

    优先用表头块解析出的真实列边界 col_edges（无合并格污染）；老表无此字段
    时回退 _col_xs。允许续页缺主表若干列（被裁的空列）。
    返回 {cont_col: master_col}；匹配对 <2 → None。
    """
    ea = a.get('col_edges') or _col_xs(a)
    eb = b.get('col_edges') or _col_xs(b)
    if not ea or not eb or any(x is None for x in eb):
        return None
    cmap, i = {}, 0
    for j, x in enumerate(eb):
        while i < len(ea) and (ea[i] is None or ea[i] < x - tol):
            i += 1
        if i >= len(ea) or ea[i] is None or abs(ea[i] - x) > tol:
            return None
        cmap[j] = i
        i += 1
    return cmap if len(cmap) >= 2 else None


def _table_y0(t):
    for row in t.get('cells') or []:
        ys = [b[1] for b in row if b and len(b) >= 4]
        if ys:
            return min(ys)
    return None


def _table_y1(t):
    ys = [b[3] for row in (t.get('cells') or [])
          for b in row if b and len(b) >= 4]
    return max(ys) if ys else None


# 跨页续表的物理特征：前驱表被页底切断、续表从页面上部接着排。
# 用这两个相对位置替代「贴顶百分比调参」；与 DPI、纸张尺寸无关。
_PREV_BOTTOM_RATIO = 0.75
_CONT_TOP_RATIO = 0.35
_LEGACY_TOP_RATIO = 0.10


def _data_like(row, master_headers, cmap):
    """首行是否像数据：≥1 格命中数据形态，且对应主表头是非数字标签。"""
    for j, v in enumerate(row):
        s = str(v or '').strip()
        if not s or not _DATA_RE.search(s):
            continue
        i = cmap.get(j)
        if i is None or i >= len(master_headers):
            continue
        lab = str(master_headers[i] or '').strip()
        if lab and not re.search(r'\d', lab):
            return True
    return False


def _header_subset(m, b):
    """b 的表头块是否为 m 表头块的前缀子集（续页只保留高层标签）。

    本例主表 4 行表头块，续页只剩前 2 行（期别 + 归属分组），逐行做集合包含；
    行数必须严格更少，否则交给 repeat 通路。
    """
    ma, mb = m.get('header_chain') or [], b.get('header_chain') or []
    if not ma or not mb or len(mb) >= len(ma):
        return False
    for i, row in enumerate(mb):
        if not set(row).issubset(set(ma[i])):
            return False
    return True


def _continues(a, b, page_h=None, master=None):
    """b 是否为 a 的跨页续表。返回 (模式, 列映射) 或 None。

    repeat     —— 原严格通路：同列数 + 列对齐 + 表头逐字相同，恒等映射。
    partial    —— 多行表头块续页：表头块是主表的前缀子集（叶子列名缺失），
                  列位置子集对齐 + 续页贴顶；继承主表扁平表头。
    headerless —— 原通路：子集对齐 + 贴顶 + 首行像数据（无表头）。
    master 为链首主表；partial/headerless 一律以 master 为参照。
    """
    if (a.get('coord') or {}).get('space') != (b.get('coord') or {}).get('space'):
        return None
    if not (a.get('coord') or {}).get('exact'):
        return None
    ha, hb = _norm_header(a.get('headers')), _norm_header(b.get('headers'))
    if (a.get('n_cols') and a.get('n_cols') == b.get('n_cols')
            and _cols_aligned(a, b) and ha and hb and ha == hb):
        n = b.get('n_cols') or len(hb)
        return 'repeat', {j: j for j in range(n)}
    m = master if master is not None else a
    cmap = _col_map(m, b)
    if cmap is None:
        return None
    y0 = _table_y0(b)
    if not page_h or y0 is None:
        return None
    subset = _header_subset(m, b)
    if subset:
        # 多行表头块续页：前驱表贴页底 + 续表从页面上部起，才认定是被切断的表。
        y1 = _table_y1(a)
        if (y1 is not None and y1 >= _PREV_BOTTOM_RATIO * page_h
                and y0 <= _CONT_TOP_RATIO * page_h):
            return 'partial', cmap
        return None
    if y0 > _LEGACY_TOP_RATIO * page_h:
        return None
    mh = _norm_header(m.get('headers'))
    if not hb or not _data_like(hb, mh, cmap):
        return None
    return 'headerless', cmap


def _annotate_cells(grid_rows, page, space):
    return [[{'bbox': (list(b) if b and len(b) >= 4 else None),
              'page': page, 'space': space} for b in row]
            for row in grid_rows]


def _pad_row(row, cmap, width, fill):
    out = [fill] * width
    for j, v in enumerate(row):
        i = cmap.get(j)
        if i is not None and i < width:
            out[i] = v
    return out


def _build_stitched(chain, si):
    p0, _ti0, a0, _m0, _c0 = chain[0]
    space = (a0.get('coord') or {}).get('space') or 'source'
    headers = list(a0.get('headers') or [])
    width = a0.get('n_cols') or len(headers)
    rows = [_pad_row(r, {j: j for j in range(width)}, width, '')
            for r in (a0.get('rows') or [])]
    row_pages = [p0] * len(rows)
    a0_cells = a0.get('cells') or []
    cells = _annotate_cells(a0_cells[:1], p0, space)          # 表头行
    cells += _annotate_cells(a0_cells[1:1 + len(rows)], p0, space)
    parts = [{'page': p0, 'tbl': _ti0, 'header_dropped': False,
              'header_recovered': False, 'n_rows': len(rows)}]
    for p, ti, b, mode, cmap in chain[1:]:
        b_rows = b.get('rows') or []
        b_cells = b.get('cells') or []
        if mode == 'headerless':
            # 无重复表头：被误标成 headers 的首行其实是数据，回收进数据行
            br = [list(b.get('headers') or [])] + [list(r) for r in b_rows]
            bc = b_cells[:1 + len(b_rows)]
            dropped, recovered, inherited = False, True, False
        elif mode == 'partial':
            # 多行表头块续页：残缺表头继承主表，续页表头行整块丢弃
            br = [list(r) for r in b_rows]
            bc = b_cells[1:1 + len(br)]
            dropped, recovered, inherited = True, False, True
        else:
            br = [list(r) for r in b_rows]
            bc = b_cells[1:1 + len(br)]                       # 丢重复表头行
            dropped, recovered, inherited = True, False, False
        bc = list(bc) + [[] for _ in range(max(0, len(br) - len(bc)))]
        # 跨页断行标签：上一页末行首列是半截标签、本页首行是它的尾巴 → 拼回一行
        if br and rows and _label_only(rows[-1]) and _label_only(br[0]):
            tail = str(br[0][0]).strip()
            if (len(str(rows[-1][0]).strip()) >= _HEAD_MIN_LEN
                    and len(tail) <= _TAIL_MAX_LEN
                    and not _LABEL_START_RE.match(tail)):
                rows[-1][0] = str(rows[-1][0]).rstrip() + tail
                br, bc = br[1:], bc[1:]
        for r, crow in zip(br, bc):
            rows.append(_pad_row(r, cmap, width, ''))
            cells += _annotate_cells(
                [_pad_row(crow, cmap, width, None)], p, space)
        row_pages += [p] * len(br)
        parts.append({'page': p, 'tbl': ti, 'header_dropped': dropped,
                      'header_recovered': recovered, 'n_rows': len(br),
                      'header_inherited': inherited, 'label_merged': inherited and
                      bool(b_rows) and len(br) < len(b_rows)})
    out = {
        'id': si,
        'title': a0.get('title', ''),
        'headers': headers,
        'rows': rows,
        'row_pages': row_pages,
        'cells': cells,
        'n_rows': len(rows),
        'n_cols': width,
        'source_pages': [p for p, _t, _b, _m, _c in chain],
        'parts': parts,
        'coord': {'mixed': True, 'space': 'per-cell', 'exact': True},
        'csv_file': 'stitched_{}.csv'.format(si),
    }
    checks = _reconcile(headers, rows)
    if checks:
        out['checks'] = checks
    return out


def stitch_tables(pages):
    """pages（按页排序的 pageRec 列表）→ 跨页合并表列表（仅含 >=2 页的续表）。

    只从每页最后一张表起链，接下一页第一张表，逐页延伸；已被合并的表不再重复起链。
    页高（image_size[1]）传进判据供「续页贴顶」闸使用。
    """
    by_page = {pg.get('page'): (pg.get('structured_tables') or [])
               for pg in pages}
    heights = {pg.get('page'): (pg.get('image_size') or [0, 0])[1]
               for pg in pages}
    used, stitched = set(), []
    for p in sorted(k for k in by_page if k is not None):
        tabs = by_page[p]
        if not tabs:
            continue
        ai = len(tabs) - 1
        if (p, ai) in used:
            continue
        chain = [(p, ai, tabs[ai], None, None)]
        master = tabs[ai]
        cur, np = tabs[ai], p + 1
        while by_page.get(np):
            b = by_page[np][0]
            res = None if (np, 0) in used else _continues(
                cur, b, heights.get(np), master)
            if res is None:
                break
            mode, cmap = res
            chain.append((np, 0, b, mode, cmap))
            used.add((np, 0))
            cur, np = b, np + 1
        if len(chain) >= 2:
            used.add((p, ai))
            stitched.append(_build_stitched(chain, len(stitched) + 1))
    return stitched

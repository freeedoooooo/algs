"""
pipeline/resplit.py — 图片路线的「人工列边界」后处理（确定性重切）。

模型（PPStructureV3）把相邻两列看成一格时（108 摘要+余额），本模块沿用户
给的竖线把黏连格切开，再对每个子格裁剪重 OCR，让文字按列归位。
只治结构（谁归哪格），不治识别（字符级错字仍靠识别模型本身）。

坐标空间：与 cell_grid 一致。v1 仅支持 doc_unwarp=off（space=source），
此时单元格框就是原图像素，裁剪原图即可；on 时框在矫正图空间，由 runner 拦截。

四步，全部确定性规则：
  ① 筛线：只保留落在该表 x 范围内部的竖线（一页多表互不影响）
  ② 切格：bbox 被竖线穿过的格子切成 k 个子格，y 不变；没被切的格子原样保留
  ③ 重 OCR：每个子格从原图 crop 出来单独识别（检测器只看到一列，天然分开，
     顺带解决「OCR 行本身跨列」的问题），文字按 y 排序拼接
  ④ 补齐：逐行切分后宽度不齐的（整行宽标题行）交给下游 align_cell_grid
     补齐到最大宽度、split_header 单独处理标题行，不做全局 x 聚类（会被宽格桥接）
"""
import cv2

from . import engines

_MARGIN = 2          # 竖线须严格穿过格子内部（离边 >2px）才切，避免擦边误切


def _log(emit, level, msg):
    if emit:
        emit(level, 'table', msg)


def _table_x_range(table):
    xs = [c[0] for row in (table.get('cell_grid') or []) for c in row if c]
    xe = [c[2] for row in (table.get('cell_grid') or []) for c in row if c]
    if not xs:
        return None
    return min(xs), max(xe)


def _cuts_for(box, lines):
    x0, _, x1, _ = box
    return [L for L in lines if x0 + _MARGIN < L < x1 - _MARGIN]


def _sub_boxes(box, cuts):
    x0, y0, x1, y1 = box
    edges = [x0] + cuts + [x1]
    return [[edges[i], y0, edges[i + 1], y1] for i in range(len(edges) - 1)]


def _ocr_crop(img, box, det_thresh, box_thresh):
    """crop 子格单独识别，返回按 y 排序拼接的文字。"""
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    h, w = img.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return ''
    crop = img[y0:y1, x0:x1]
    kw = {}
    if det_thresh is not None:
        kw['text_det_thresh'] = float(det_thresh)
    if box_thresh is not None:
        kw['text_det_box_thresh'] = float(box_thresh)
    lines = []
    for res in engines.ocr().predict(crop, **kw):
        texts = res.get('rec_texts') or []
        polys = res.get('rec_polys') or res.get('dt_polys') or []
        for i, t in enumerate(texts):
            cy = 0.0
            if i < len(polys) and len(polys[i]):
                cy = sum(p[1] for p in polys[i]) / len(polys[i])
            lines.append((cy, str(t)))
    lines.sort(key=lambda p: p[0])
    return ' '.join(t for _, t in lines).strip()


def _resplit_table(table, lines, img, det_thresh, box_thresh, emit, idx):
    rng = _table_x_range(table)
    if not rng:
        _log(emit, 'warn', '表 {} 无单元格坐标，跳过人工列边界重切'.format(idx))
        return table
    inner = [L for L in lines if rng[0] + _MARGIN < L < rng[1] - _MARGIN]
    if not inner:
        return table

    rows = table.get('rows') or []
    grid = table.get('cell_grid') or []
    new_rows, new_grid = [], []
    n_split = n_sub = 0
    for r, row in enumerate(rows):
        grow = grid[r] if r < len(grid) else []
        out_row, out_grid = [], []
        for c, text in enumerate(row):
            box = grow[c] if c < len(grow) else None
            cuts = _cuts_for(box, inner) if box else []
            if not cuts:
                out_row.append(text)
                out_grid.append(box)
                continue
            n_split += 1
            for sb in _sub_boxes(box, cuts):
                txt = _ocr_crop(img, sb, det_thresh, box_thresh)
                out_row.append(txt)
                out_grid.append(sb)
                n_sub += 1
        new_rows.append(out_row)
        new_grid.append(out_grid)

    if not n_split:
        return table

    # 逐行切分后各行宽度可能不齐（标题行整行宽），不做全局 x 聚类（会被宽格
    # 桥接合并），直接交给下游 structure.align_cell_grid 补齐到最大宽度、
    # split_header 单独处理标题行。108 各数据行切后宽度一致，补齐即对齐。
    width = max((len(r) for r in new_rows), default=0)
    _log(emit, 'info', '表 {} 沿人工列边界切开 {} 个黏连格 → {} 个子格重 OCR，'
         ' {} 列'.format(idx, n_split, n_sub, width))
    out = dict(table)
    out['rows'] = new_rows
    out['cell_grid'] = new_grid
    return out


def resplit(raw_tables, lines, img_path, det_thresh=None, box_thresh=None,
            emit=None):
    """入口：返回重切后的 raw_tables（不改动入参）。lines 为空原样返回。"""
    if not lines or not raw_tables:
        return raw_tables
    img = cv2.imread(img_path)
    if img is None:
        _log(emit, 'warn', '读不到原图，跳过人工列边界重切')
        return raw_tables
    return [
        _resplit_table(t, lines, img, det_thresh, box_thresh, emit, i)
        for i, t in enumerate(raw_tables, 1)
    ]
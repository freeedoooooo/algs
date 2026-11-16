"""
pipeline/table_model.py — 图片 / 扫描件的表格路线。

先用长直线预筛，命中网格才加载 PPStructureV3；
从结果里同时取表格 HTML、cell_box_list 和矫正图 output_img。

★ 坐标方案（用户选定的「矫正图视图」）：
  cell_box_list 本就基于 doc_preprocessor_res["output_img"]（转正 + 去扭曲图），
  把它另存为 pages/rectified.png，框 1:1 叠上去，零几何变换。
  不做 UVDoc 逆变换 —— 它是非线性形变且不暴露变换场；
  关掉它又会损失表格文字质量（week-02 实测 12/50 个单元格退化）。
"""
import os
import re
from html.parser import HTMLParser

import cv2
import numpy as np
from PIL import Image

from .. import config
from . import engines


class _TableParser(HTMLParser):
    """文字网格 + 每格对应的原始 <td> 序号（用来配 cell_box_list）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.box_tables = [], []
        self._table = self._boxtable = None
        self._row = self._boxrow = None
        self._buf = None
        self._colspan = 1
        self._td_index = 0
        self._cur_box = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self._table, self._boxtable, self._td_index = [], [], 0
        elif tag == 'tr' and self._table is not None:
            self._row, self._boxrow = [], []
        elif tag in ('td', 'th') and self._row is not None:
            self._buf = []
            self._cur_box = self._td_index
            self._td_index += 1
            try:
                self._colspan = max(1, int(dict(attrs).get('colspan', 1)))
            except (TypeError, ValueError):
                self._colspan = 1
        elif tag == 'br' and self._buf is not None:
            self._buf.append(' ')

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._buf is not None:
            cell = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
            # colspan 展开的格子共享同一个框序号
            self._row.extend([cell] + [''] * (self._colspan - 1))
            self._boxrow.extend([self._cur_box] * self._colspan)
            self._buf, self._colspan, self._cur_box = None, 1, None
        elif tag == 'tr' and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._boxtable.append(self._boxrow)
            self._row = self._boxrow = None
        elif tag == 'table' and self._table is not None:
            self.tables.append(self._table)
            self.box_tables.append(self._boxtable)
            self._table = self._boxtable = None


def parse_table_html_with_boxes(html_text):
    if not html_text or '<table' not in str(html_text).lower():
        return [], []
    parser = _TableParser()
    try:
        parser.feed(str(html_text))
        parser.close()
    except Exception:
        return [], []
    return parser.tables, parser.box_tables


def grid_score(image_path):
    """形态学 + 霍夫，数长横线 / 长竖线；异常时当无网格跳过。"""
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0, 0
        h, w = img.shape[:2]
        k = config.GRID_RESIZE_MAX / max(h, w)
        if k < 1:
            img = cv2.resize(img, None, fx=k, fy=k)
        bw = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 15, 8)
        hk = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30))
        args = dict(rho=1, theta=np.pi / 180, threshold=60,
                    minLineLength=config.GRID_LINE_MIN_LEN, maxLineGap=8)
        hl = cv2.HoughLinesP(cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk), **args)
        vl = cv2.HoughLinesP(cv2.morphologyEx(bw, cv2.MORPH_OPEN, vk), **args)
        return (0 if hl is None else len(hl), 0 if vl is None else len(vl))
    except Exception:
        return 0, 0


def _html_blocks(res):
    html_map = getattr(res, 'html', None) or {}
    blocks = [v for v in html_map.values()
              if v and '<table' in str(v).lower()]
    if blocks:
        return blocks
    # res.html 为空是正常情况（这页没表格），从解析块兜底
    data = res.json if hasattr(res, 'json') else res
    if isinstance(data, dict) and isinstance(data.get('res'), dict):
        data = data['res']
    out = []
    if isinstance(data, dict):
        for b in data.get('parsing_res_list', []) or []:
            if 'table' not in str(b.get('block_label', '')).lower():
                continue
            content = str(b.get('block_content', '') or '')
            if '<table' in content.lower():
                out.append(content)
    return out


def _cell_boxes(res):
    try:
        data = res.json
        d = data.get('res', data) if isinstance(data, dict) else {}
        return [list(t.get('cell_box_list') or [])
                for t in (d.get('table_res_list') or [])]
    except Exception:
        return []


def _save_rectified(res, case_abs):
    try:
        out = res['doc_preprocessor_res']['output_img']   # ndarray, BGR
        im = Image.fromarray(out[:, :, ::-1])             # BGR → RGB
        path = os.path.join(case_abs, 'pages', config.RECTIFIED_NAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        im.save(path)
        return [im.size[0], im.size[1]]
    except Exception:
        return None


def tables(image_path, case_abs, min_h=None, min_v=None):
    """返回 (raw_tables, notes, rectified_size)；预筛门槛可由页面参数覆盖。"""
    mh = config.GRID_MIN_H if min_h is None else int(min_h)
    mv = config.GRID_MIN_V if min_v is None else int(min_v)
    nh, nv = grid_score(image_path)
    if nh < mh or nv < mv:
        return [], ['长直线预筛未命中（横 {} / 竖 {}，门槛 {}/{}），跳过表格模型'
                    .format(nh, nv, mh, mv)], None
    notes = ['长直线预筛命中（横 {} / 竖 {}，门槛 {}/{}），启用 PPStructureV3'
             .format(nh, nv, mh, mv)]
    raw, rect_size = [], None
    for pno, res in enumerate(engines.structure().predict(image_path), 1):
        htmls = _html_blocks(res)
        boxes_by_table = _cell_boxes(res)
        parsed = []
        for ti, html_text in enumerate(htmls):
            tables_html, box_tables = parse_table_html_with_boxes(html_text)
            boxes = boxes_by_table[ti] if ti < len(boxes_by_table) else []
            for rows, brows in zip(tables_html, box_tables):
                if rows:
                    parsed.append((rows, brows, boxes))
        if not parsed:
            continue
        # 只有真的抽到表才落盘矫正图
        rect_size = _save_rectified(res, case_abs)
        if rect_size:
            notes.append('第 {} 页：已保存矫正图 pages/{}（{}×{}），单元格框 1:1 叠加'
                         .format(pno, config.RECTIFIED_NAME,
                                 rect_size[0], rect_size[1]))
        for rows, brows, boxes in parsed:
            grid = [[
                [round(float(v), 1) for v in list(boxes[bi])[:4]]
                if bi is not None and bi < len(boxes) and len(boxes[bi]) >= 4
                else None for bi in br
            ] for br in brows]
            raw.append({
                'page': pno, 'rows': rows, 'cell_grid': grid,
                'strategy': 'table_model', 'source': 'PPStructureV3',
                'coord': {
                    'space': 'rectified',
                    'image': 'pages/' + config.RECTIFIED_NAME,
                    'origin': 'PPStructureV3', 'exact': bool(rect_size),
                    'note': '单元格框取自模型矫正图，1:1 叠加；UVDoc 保持开启',
                },
            })
    if not raw:
        notes.append('表格模型未还原出表格（有网格线但不是标准表格）')
    return raw, notes, rect_size

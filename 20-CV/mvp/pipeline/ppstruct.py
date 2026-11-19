"""
pipeline/ppstruct.py — 图片 / 扫描件的「单次推理」路线（升级后主路线）。

一次 PPStructureV3 推理，官方 JSON 为唯一事实源：
  · 官方 JSON（裁死字段）→ rec['parsing']   唯一事实源，落盘
  · table_res_list      → _TableParser → raw 表（下游 resplit/structure 零改动）
  · doc_preprocessor    → rectified.png（仅 unwarp=on）

文字投影 texts/scores/boxes 与版面 layout **不在这里算、也不落盘**：
它们由 viewmodel.hydrate() 在渲染期从 parsing 现算（官方 overall_ocr_res /
parsing_res_list 的薄视图）。parsing 经 _slim_parsing 裁掉代码从不读取的
死字段（table_ocr_pred / rec_boxes / rec_polys 重复 / layout_det_res /
参数回显 / 本机 input_path），保留官方语义源。

坐标空间：内部 OCR 与 cell_box 都基于矫正图。unwarp=on → text_space='rectified'；
off 时矫正图与原图逐像素一致 → text_space='source'。与 cell_grid 的 coord.space 一致。
"""
import os
import re
import time
from html.parser import HTMLParser

from PIL import Image

from .. import config
from . import engines
from .ocr import det_kwargs


def _plain(v):
    """官方结果 → 可 JSON 序列化；丢掉图像 ndarray（output_img 单独落盘）。"""
    if hasattr(v, 'tolist'):
        return _plain(v.tolist())
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()
                if k not in ('output_img', 'img')}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def _inner(res):
    data = res.json if hasattr(res, 'json') else res
    if isinstance(data, dict) and isinstance(data.get('res'), dict):
        return data['res']
    return data if isinstance(data, dict) else {}


def _slim_parsing(p):
    """裁掉官方 JSON 里代码从不读取的死字段 / 自我重复 / 参数回显 / 本机路径。

    保留语义源：parsing_res_list、overall_ocr_res.{rec_texts,rec_scores,dt_polys}、
    table_res_list.{pred_html,cell_box_list}、width/height、doc_preprocessor_res.angle。
    这些正是 viewmodel.hydrate 派生投影 / layout 与 raw 表溯源所需的全部。
    """
    for k in ('input_path', 'model_settings', 'page_index', 'page_count',
              'layout_det_res'):
        p.pop(k, None)
    o = p.get('overall_ocr_res')
    if isinstance(o, dict):
        for k in ('input_path', 'page_index', 'model_settings', 'rec_polys',
                  'rec_boxes', 'textline_orientation_angles', 'text_det_params',
                  'text_type', 'text_rec_score_thresh', 'return_word_box'):
            o.pop(k, None)
    for t in p.get('table_res_list') or []:
        if isinstance(t, dict):
            t.pop('table_ocr_pred', None)
    d = p.get('doc_preprocessor_res')
    if isinstance(d, dict):
        for k in ('input_path', 'page_index', 'model_settings'):
            d.pop(k, None)
    return p


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


def _html_blocks(res):
    html_map = getattr(res, 'html', None) or {}
    blocks = [v for v in html_map.values()
              if v and '<table' in str(v).lower()]
    if blocks:
        return blocks
    out = []
    for b in _inner(res).get('parsing_res_list', []) or []:
        if 'table' not in str(b.get('block_label', '')).lower():
            continue
        content = str(b.get('block_content', '') or '')
        if '<table' in content.lower():
            out.append(content)
    return out


def _cell_boxes(res):
    try:
        return [list(t.get('cell_box_list') or [])
                for t in (_inner(res).get('table_res_list') or [])]
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


def _coord(use_unwarp, rect_size):
    if use_unwarp:
        return {
            'space': 'rectified',
            'image': 'pages/' + config.RECTIFIED_NAME,
            'origin': 'PPStructureV3', 'exact': bool(rect_size),
            'note': '单元格框取自模型矫正图，1:1 叠加；UVDoc 保持开启',
        }
    return {
        'space': 'source',
        'origin': 'PPStructureV3', 'exact': True,
        'note': '文档矫正关闭（电子版平整截图），矫正图与原图逐像素一致，'
                '单元格框直接叠在 source 图上',
    }


def extract(img_path, case_abs, use_unwarp=True, params=None, emit=None):
    """单次推理，返回 parsing（裁死字段）/raw/notes/rect_size/text_space/elapsed。

    投影与 layout 不在此计算——由 viewmodel.hydrate 渲染期从 parsing 派生。
    """
    t0 = time.perf_counter()
    notes = []

    def note(level, msg):
        notes.append(msg)
        if emit:
            emit(level, 'model', msg)

    note('info', '加载 PPStructureV3 并单次推理（文档矫正={}，首次约 20~40s）…'
         .format('开' if use_unwarp else '关'))
    parsing = None
    raw, rect_size = [], None
    for pno, res in enumerate(
            engines.structure(use_unwarp).predict(
                img_path, **det_kwargs(params)), 1):
        inner = _inner(res)
        parsing = _slim_parsing(_plain(inner))

        htmls = _html_blocks(res)
        boxes_by_table = _cell_boxes(res)
        parsed = []
        for ti, html_text in enumerate(htmls):
            tables_html, box_tables = parse_table_html_with_boxes(html_text)
            tb = boxes_by_table[ti] if ti < len(boxes_by_table) else []
            for rows, brows in zip(tables_html, box_tables):
                if rows:
                    parsed.append((rows, brows, tb))
        if not parsed:
            continue
        if use_unwarp:
            rect_size = _save_rectified(res, case_abs)
            if rect_size:
                note('ok', '第 {} 页：已保存矫正图 pages/{}（{}×{}），框 1:1 叠加'
                     .format(pno, config.RECTIFIED_NAME,
                             rect_size[0], rect_size[1]))
        else:
            note('ok', '第 {} 页：文档矫正已关闭，框基于原图（space=source），'
                 '坐标 1:1 精确'.format(pno))
        coord = _coord(use_unwarp, rect_size)
        for rows, brows, tb in parsed:
            grid = [[
                [round(float(v), 1) for v in list(tb[bi])[:4]]
                if bi is not None and bi < len(tb) and len(tb[bi]) >= 4
                else None for bi in br
            ] for br in brows]
            raw.append({
                'page': pno, 'rows': rows, 'cell_grid': grid,
                'strategy': 'ppstruct', 'source': 'PPStructureV3',
                'coord': coord,
            })
    if not raw:
        note('warn', '表格模型未还原出表格（parsing_res_list 无 table 块）')
    else:
        note('ok', '单次推理还原出 {} 张表'.format(len(raw)))
    elapsed = round(time.perf_counter() - t0, 2)
    return {
        'parsing': parsing,
        'text_space': 'rectified' if use_unwarp else 'source',
        'elapsed': elapsed,
        'raw': raw,
        'notes': notes,
        'rect_size': rect_size,
    }
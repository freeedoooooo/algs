"""
adapter/base.py — c1-structure 标准契约 + 适配入口（纯函数，不加载模型）。

c1-structure/1 契约（extract.json）：
  信封  schema / case / file{name,kind,encoding,page_count} / params /
        pages:[page…] / stitched_tables:[跨页合并表…]
  page  index(1起) / size[w,h] / rectified_size / image / rectified_image /
        boxes_image / space(source|rectified，文字坐标空间) /
        route(model|text_layer|skipped) / text_layer / cropbox_limited /
        plain_text / elapsed / notes / texts:[{text,score,box}] /
        blocks:[{role,bbox,text}] / tables:[表…] /
        stats{lines,avg_score,low_score_lines}
  表    领域资产语义保留：headers / rows / cells(与表头+数据同形的 bbox 网格) /
        coord{space,exact,…} / n_rows / n_cols / fill_ratio / csv_file / title；
        source / strategy 已中性化（model / text_layer / csv / explicit / lines / text）。
  坐标  texts[].box 为四点 polygon（旋转行框不失真）；表格 cells 为 [x0,y0,x1,y1]。
        像素基准 = 该页 image（space=source）或 rectified_image（space=rectified）。

引擎名（PPStructureV3 / pdfplumber / PaddleOCR）不出本包：
source/strategy/coord.origin/notes 全部中性化；原始结构只落 raw/（前端 403）。
"""
SCHEMA = 'c1-structure/1'
RECORDS_SCHEMA = 'c1-structure-records/1'

# 引擎名 → 中性词（notes / coord.note 展示净化；raw 与运行日志保留原名供运维）
_ENGINE_WORDS = (
    ('PPStructureV3', '表格模型'),
    ('PP-OCRv4', 'OCR 模型'),
    ('PaddleOCR', 'OCR 模型'),
    ('pdfplumber', '文本层解析'),
)

_SOURCE_MAP = {'PPStructureV3': 'model', 'pdfplumber': 'text_layer', 'csv': 'csv'}
_STRATEGY_MAP = {'ppstruct': 'model', 'csv.reader': 'csv'}
_ROUTE_MAP = {'ppstruct': 'model'}

_TITLE_LABELS = {'doc_title', 'paragraph_title', 'title'}
_FIGURE_LABELS = {'image', 'chart', 'figure'}


def sanitize(text):
    for a, b in _ENGINE_WORDS:
        text = str(text).replace(a, b)
    return text


def block_role(label):
    """官方版面标签 → c1-structure 角色（title/text/table/figure/formula/seal）。"""
    lab = str(label or '').lower()
    if 'table' in lab:
        return 'table'
    if lab in _TITLE_LABELS:
        return 'title'
    if lab in _FIGURE_LABELS:
        return 'figure'
    if lab == 'formula':
        return 'formula'
    if lab == 'seal':
        return 'seal'
    return 'text'


def hydrate(rec):
    """就地补全 ppstruct 页的派生投影（原 viewmodel.hydrate，迁移后唯一实现）。

    runner 在画带框图 / 拼接之前调用；adapt() 假定投影已就绪。幂等。
    """
    from . import paddle
    for pg in rec.get('pages') or []:
        if pg.get('parsing'):
            paddle.derive(pg)
    return rec


def _page_shell(pg):
    return {
        'index': pg.get('page', 1),
        'size': pg.get('image_size'),
        'rectified_size': pg.get('rectified_size'),
        'image': pg.get('source'),
        'rectified_image': pg.get('rectified'),
        'boxes_image': pg.get('boxes_png'),
        'space': pg.get('text_space') or 'source',
        'route': _ROUTE_MAP.get(pg.get('table_route'), pg.get('table_route')),
        'text_layer': bool(pg.get('text_layer')),
        'cropbox_limited': bool(pg.get('cropbox_limited')),
        'plain_text': pg.get('plain_text') or '',
        'elapsed': pg.get('elapsed') or 0.0,
        'notes': [sanitize(n) for n in pg.get('notes') or []],
        'stats': {
            'lines': pg.get('lines', 0),
            'avg_score': pg.get('avg_score', 0.0),
            'low_score_lines': pg.get('low_score_lines', 0),
        },
    }


def _texts(pg):
    texts = pg.get('texts') or []
    scores = pg.get('scores') or []
    boxes = pg.get('boxes') or []
    return [{'text': t,
             'score': scores[i] if i < len(scores) else 1.0,
             'box': boxes[i] if i < len(boxes) else []}
            for i, t in enumerate(texts)]


def _table(t):
    """领域表 → c1-structure 表：语义保留，来源中性化，coord.origin 剥掉。"""
    out = {k: t.get(k) for k in (
        'page', 'title', 'headers', 'rows', 'cells',
        'n_rows', 'n_cols', 'fill_ratio', 'low_confidence', 'csv_file')}
    coord = dict(t.get('coord') or {})
    coord.pop('origin', None)
    if coord.get('note'):
        coord['note'] = sanitize(coord['note'])
    out['coord'] = coord
    out['source'] = _SOURCE_MAP.get(t.get('source'), 'model')
    out['strategy'] = _STRATEGY_MAP.get(t.get('strategy'), t.get('strategy'))
    return out


def _blocks(layout):
    return [{'role': block_role(b.get('label')),
             'bbox': b.get('bbox'), 'text': b.get('content')}
            for b in layout or []]


def adapt(rec):
    """内部文件信封（已 hydrate）→ c1-structure。纯函数，不改输入。"""
    from . import paddle, pdfplumber, plain
    kind = rec.get('kind')
    pages = []
    for pg in rec.get('pages') or []:
        if kind == 'csv':
            pages.append(plain.page(pg))
        elif pg.get('parsing'):
            pages.append(paddle.page(pg))
        else:
            pages.append(pdfplumber.page(pg))
    return {
        'schema': SCHEMA,
        'file': {'name': rec.get('file'), 'kind': kind,
                 'encoding': rec.get('encoding') or '',
                 'page_count': rec.get('page_count', 1)},
        'params': rec.get('params_snapshot') or {},
        'pages': pages,
        'stitched_tables': rec.get('stitched_tables') or [],
    }
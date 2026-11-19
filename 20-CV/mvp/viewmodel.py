"""
mvp/viewmodel.py — 官方 parsing 与报告视图之间的纯函数桥（不加载模型、不触发重 import）。

存储原则（彻底清理后）：
  result.json 是「文件信封」：file/case/kind/encoding/params_snapshot/page_count
  + pages:[pageRec…] + stitched_tables。每个 pageRec 只存该页的官方 parsing（裁死字段）
  + structured_tables + 页级元信息。文字投影 texts/scores/boxes、版面 layout、
  行数/均值/低置信数都是**渲染期派生视图**，由 hydrate() 从 parsing 现算、不落盘
  （ppstruct 路线）——官方 JSON 是唯一事实源。文本层 PDF / CSV 路线没有 parsing，
  其 OCR 投影是该页唯一文字记录，直接存储。

hydrate() 另把文件上下文（case/file/kind）注入每个 pageRec，供报告渲染取用；
disk_view() 落盘时剥掉派生键与注入的上下文，保证 pageRec 落盘形态纯净、无重复。
单页文件同样走信封（pages 长度为 1），无双形态、无兼容 shim。
"""
from . import config

# 渲染期从 parsing 派生、不重复落盘的键（仅 ppstruct 路线剥掉）
DERIVED = ('texts', 'scores', 'boxes', 'layout',
           'lines', 'avg_score', 'low_score_lines')
# hydrate 注入页级的文件上下文（渲染便利），落盘时剥掉避免逐页重复
CONTEXT = ('case', 'file', 'kind')


def _derive_page(page):
    """有 parsing（ppstruct）→ 从官方 overall_ocr_res / parsing_res_list 现算投影。"""
    p = page.get('parsing')
    if not p:
        return page
    o = p.get('overall_ocr_res') or {}
    texts = list(o.get('rec_texts') or [])
    full = [float(s) for s in (o.get('rec_scores') or [])]
    page['texts'] = texts
    page['scores'] = [round(s, 4) for s in full]
    page['boxes'] = [list(poly) for poly in (o.get('dt_polys') or [])]
    page['lines'] = len(texts)
    page['avg_score'] = round(sum(full) / len(full), 4) if full else 0.0
    page['low_score_lines'] = sum(1 for s in full if s < config.LOW_SCORE)
    page['layout'] = [{
        'label': b.get('block_label'),
        'content': b.get('block_content'),
        'bbox': b.get('block_bbox'),
    } for b in (p.get('parsing_res_list') or [])]
    return page


def hydrate(rec):
    """就地补全报告所需的派生视图 + 文件上下文。幂等。

    文件信封（含 pages）→ 逐页注入 case/file/kind 并派生投影；
    直接传入单个 pageRec（测试便利）→ 就地派生。
    """
    pages = rec.get('pages')
    if pages is None:
        return _derive_page(rec)
    ctx = {'case': rec.get('case'), 'file': rec.get('file'),
           'kind': rec.get('kind')}
    for pg in pages:
        for k, v in ctx.items():
            pg.setdefault(k, v)
        _derive_page(pg)
    return rec


def _disk_page(page):
    out = {k: v for k, v in page.items() if k not in CONTEXT}
    if out.get('parsing'):
        out = {k: v for k, v in out.items() if k not in DERIVED}
    return out


def disk_view(rec):
    """落盘形态：逐页剥掉注入上下文 + 派生键（parsing 已是其唯一源）。"""
    pages = rec.get('pages')
    if pages is None:
        return _disk_page(rec)
    out = {k: v for k, v in rec.items() if k != 'pages'}
    out['pages'] = [_disk_page(p) for p in pages]
    return out
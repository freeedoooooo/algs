"""
adapter/paddle.py — PPStructureV3 路线适配（全仓唯一认识官方 parsing 结构的模块）。

derive()：官方 overall_ocr_res / parsing_res_list → 派生投影（原 viewmodel 逻辑，
迁移后在提取期一次算好，渲染期不再现算）。page()：内部页 → c1-structure 页。
"""
from .. import config
from . import base


def derive(page):
    """从官方 parsing 现算投影 texts/scores/boxes + 版面 + 统计（就地、幂等）。"""
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


def page(pg):
    out = base._page_shell(pg)
    out['texts'] = base._texts(pg)
    out['blocks'] = base._blocks(pg.get('layout'))
    out['tables'] = [base._table(t) for t in pg.get('structured_tables') or []]
    return out
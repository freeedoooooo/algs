"""
mvp/viewmodel.py — 官方 parsing 与报告视图之间的纯函数桥（不加载模型、不触发重 import）。

存储原则（彻底清理后）：
  result.json 只存「官方 parsing（裁死字段）+ structured_tables + 应用元信息」。
  文字投影 texts/scores/boxes、版面 layout、行数/均值/低置信数都是**渲染期派生视图**，
  由 hydrate() 从 parsing 现算，不落盘（ppstruct 路线）——官方 JSON 是唯一事实源。
  文本层 PDF / CSV 路线没有 parsing，其 OCR 投影是唯一文字记录，直接存储。

disk_view() 给出落盘形态：ppstruct 路线剥掉派生键，避免与 parsing 重复存储。
"""
from . import config

# 渲染期从 parsing 派生、不重复落盘的键（仅 ppstruct 路线剥掉）
DERIVED = ('texts', 'scores', 'boxes', 'layout',
           'lines', 'avg_score', 'low_score_lines')


def hydrate(rec):
    """就地补全报告所需的派生视图。

    有 parsing（ppstruct 路线）→ 从官方 overall_ocr_res / parsing_res_list 现算；
    无 parsing（文本层 / CSV）→ 投影已存储，原样返回。幂等。
    """
    p = rec.get('parsing')
    if not p:
        return rec
    o = p.get('overall_ocr_res') or {}
    texts = list(o.get('rec_texts') or [])
    full = [float(s) for s in (o.get('rec_scores') or [])]
    rec['texts'] = texts
    rec['scores'] = [round(s, 4) for s in full]
    rec['boxes'] = [list(poly) for poly in (o.get('dt_polys') or [])]
    rec['lines'] = len(texts)
    rec['avg_score'] = round(sum(full) / len(full), 4) if full else 0.0
    rec['low_score_lines'] = sum(1 for s in full if s < config.LOW_SCORE)
    rec['layout'] = [{
        'label': b.get('block_label'),
        'content': b.get('block_content'),
        'bbox': b.get('block_bbox'),
    } for b in (p.get('parsing_res_list') or [])]
    return rec


def disk_view(rec):
    """落盘形态：ppstruct 路线剥掉派生键（parsing 已是其唯一源）；其余原样。"""
    if rec.get('parsing'):
        return {k: v for k, v in rec.items() if k not in DERIVED}
    return rec
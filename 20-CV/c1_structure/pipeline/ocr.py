"""
pipeline/ocr.py — 逐行文字 / 置信度 / 四点框，以及带框 PNG。

坐标基准是喂进去的那张图（原图 / PDF 首页渲染图）的像素坐标，
与报告左图 1:1 对应。
"""
import time

from PIL import Image, ImageDraw

from .. import config
from . import engines


def to_plain(value):
    if hasattr(value, 'tolist'):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [to_plain(x) for x in value]
    return value


def det_kwargs(params):
    """页面检测参数 → predict 级 text_det_* kwargs（缺省/None 跳过）。

    OCR / 重切 re-OCR / 表格模型三处共用，保证同一组旋钮在全链路生效。
    全是 predict 级参数：按次覆盖、不重建模型，单例复用不受影响。
    """
    p = params or {}
    kw = {}
    for key, name, cast in (
            ('det_thresh', 'text_det_thresh', float),
            ('box_thresh', 'text_det_box_thresh', float),
            ('det_unclip', 'text_det_unclip_ratio', float),
            ('det_limit_side_len', 'text_det_limit_side_len', int),
            ('det_limit_type', 'text_det_limit_type', str)):
        v = p.get(key)
        if v is not None and v != '':
            kw[name] = cast(v)
    return kw


def recognize(img_path, params=None):
    """
    返回一段可直接合并进 rec 的 dict。

    检测参数是 predict 级：按次覆盖、不重建模型，所以不同文件能用不同值，
    单例复用不受影响（这正是它们适合放页面的原因）。
    """
    t0 = time.perf_counter()
    texts, scores, boxes = [], [], []
    kw = det_kwargs(params)
    for res in engines.ocr().predict(img_path, **kw):
        texts.extend(res['rec_texts'])
        scores.extend(float(s) for s in res['rec_scores'])
        polys = res.get('rec_polys') or res.get('dt_polys') or []
        boxes.extend(to_plain(b) for b in polys)
    return {
        'texts': texts,
        'scores': [round(s, 4) for s in scores],
        'boxes': boxes,
        'lines': len(texts),
        'avg_score': round(sum(scores) / len(scores), 4) if scores else 0.0,
        'low_score_lines': sum(1 for s in scores if s < config.LOW_SCORE),
        'elapsed': round(time.perf_counter() - t0, 2),
    }


def draw_boxes_png(img_path, rec, out_path):
    """把识别框烘焙进一张 PNG，供单独打开核对（尖角细线，与报告 SVG 一致）。"""
    im = Image.open(img_path).convert('RGB')
    draw = ImageDraw.Draw(im)
    for box, score in zip(rec['boxes'], rec['scores']):
        pts = [(float(p[0]), float(p[1])) for p in box]
        if len(pts) < 3:
            continue
        color = ((222, 92, 40) if score < config.LOW_SCORE
                 else (34, 150, 90))
        draw.line(pts + [pts[0]], fill=color, width=2)
    im.save(out_path)
    return im.size

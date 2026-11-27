"""kv 算子：非表格文档的“标签 + 值”定位。

输入来自 page.texts[{text,score,box}]（四点 polygon）或 page.blocks[{role,bbox,text}]，
不依赖表格识别。先按标签文本找锚点行，再按方向取旁边的值，最后用 regex 兜底。
返回双锚点：值行在前、标签行在后，血缘能证明值来自哪个标签旁边。
"""
import re

from .._common import as_text, box_to_bbox, make_anchor
from ..registry import register
from ..spatial import item_in_region


def _label_span(text, label):
    label = label or {}
    mode = label.get('match') or 'contains'
    pattern = as_text(label.get('text') if label.get('text') is not None
                      else label.get('pattern'))
    if not pattern:
        return None
    if mode == 'exact':
        return (0, len(pattern)) if text.strip() == pattern.strip() else None
    if mode == 'regex':
        m = re.search(pattern, text)
        return m.span() if m else None
    i = text.find(pattern)
    return (i, i + len(pattern)) if i >= 0 else None


def _value_of(text, cfg):
    pattern = cfg.get('regex')
    if pattern:
        m = re.search(str(pattern), text)
        if not m:
            return None
        try:
            return m.group(cfg.get('group', 0))
        except (IndexError, TypeError):
            return None
    return text.strip() or None


def _items(ctx, args):
    """展平候选文本行/版面块，附带页信息与归一化 bbox。"""
    doc = ctx.get('doc') or {}
    pages = doc.get('pages') or []
    want = args.get('page')
    if want is not None:
        pages = [pg for pg in pages if pg.get('index') == want]
    elif ctx.get('page_only') and ctx.get('page'):
        # one_per_page 策略：每页一条记录，kv 只在本页找标签，避免跨页串值
        cur = ctx['page'].get('index')
        pages = [pg for pg in pages if pg.get('index') == cur]
    source = args.get('source') or 'texts'
    out = []
    for pg in pages:
        items = (pg.get('texts') or []) if source == 'texts' \
            else (pg.get('blocks') or [])
        for it in items:
            raw = it.get('box') if source == 'texts' else it.get('bbox')
            if not item_in_region(raw, pg, args.get('region')):
                continue
            out.append({'page': pg.get('index'), 'space': pg.get('space'),
                        'text': as_text(it.get('text')),
                        'bbox': box_to_bbox(raw)})
    return out


def _by_direction(label, items, cfg):
    """按 right / below 找候选 (gap, item)，过远者丢弃。"""
    direction = cfg.get('direction') or 'right'
    max_gap = cfg.get('max_gap')
    lb = label['bbox']
    if not lb:
        return []
    out = []
    for it in items:
        if it is label or not it['bbox']:
            continue
        cb = it['bbox']
        if direction == 'right':
            if cb[0] < lb[2]:
                continue
            if min(cb[3], lb[3]) - max(cb[1], lb[1]) <= 0:
                continue
            gap = cb[0] - lb[2]
        elif direction == 'below':
            if cb[1] < lb[3]:
                continue
            if min(cb[2], lb[2]) - max(cb[0], lb[0]) <= 0:
                continue
            gap = cb[1] - lb[3]
        else:
            continue
        if max_gap is not None and gap > float(max_gap):
            continue
        out.append((gap, it))
    return sorted(out, key=lambda x: x[0])


@register('kv', kind='source')
def op_kv(ctx, args, value, anchors):
    """按 label 找锚点行，按 direction 取值；返回 [值锚点, 标签锚点]。"""
    args = args or {}
    vcfg = args.get('value') or {}
    items = _items(ctx, args)
    hit = None
    for it in items:
        span = _label_span(it['text'], args.get('label'))
        if span is not None:
            hit = (it, span)
            break
    if hit is None:
        return '', [], {'issues': ['kv_label_not_found']}

    label, span = hit
    label_anchor = make_anchor(label['page'], label['space'],
                               label['bbox'], label['text'])
    direction = vcfg.get('direction') or 'right'

    if direction == 'inline':
        tail = label['text'][span[1]:].replace('：', ':')
        if ':' in tail:
            tail = tail.split(':', 1)[1]
        found = _value_of(tail, vcfg)
        if not found:
            return '', [label_anchor], {'issues': ['kv_value_not_found']}
        return found, [make_anchor(label['page'], label['space'],
                                   label['bbox'], found), label_anchor], {}

    for _gap, it in _by_direction(label, items, vcfg):
        found = _value_of(it['text'], vcfg)
        if not found:
            continue
        return (found,
                [make_anchor(it['page'], it['space'], it['bbox'], found),
                 label_anchor], {})
    return '', [label_anchor], {'issues': ['kv_value_not_found']}

"""变换族算子：trim / cut / replace / regex / number / date。

一律透传上游锚点并标 derived；不取值、不新增锚点，不碰入库期 transform。
"""
import datetime
import re

from .._common import as_text
from ..registry import register


@register('trim')
def op_trim(ctx, args, value, anchors):
    return as_text(value).strip(), anchors, {'derived': True}


@register('cut')
def op_cut(ctx, args, value, anchors):
    args = args or {}
    text = as_text(value)
    begin = args.get('begin', 0)
    end = args.get('end', len(text))
    return text[begin:end], anchors, {'derived': True}


@register('replace')
def op_replace(ctx, args, value, anchors):
    args = args or {}
    text = as_text(value)
    out = re.sub(str(args.get('pattern') or ''),
                 str(args.get('repl') or ''), text)
    return out, anchors, {'derived': True}


@register('regex')
def op_regex(ctx, args, value, anchors):
    args = args or {}
    m = re.search(str(args.get('pattern') or ''), as_text(value))
    if not m:
        return '', anchors, {'derived': True, 'issues': ['regex_no_match']}
    try:
        return m.group(args.get('group', 0)), anchors, {'derived': True}
    except (IndexError, TypeError):
        return '', anchors, {'derived': True, 'issues': ['regex_bad_group']}


@register('number')
def op_number(ctx, args, value, anchors):
    args = args or {}
    text = as_text(value)
    for ch in str(args.get('strip') or ''):
        text = text.replace(ch, '')
    text = text.strip()
    try:
        num = float(text)
    except ValueError:
        return '', anchors, {'derived': True, 'issues': ['number_parse_failed']}
    return (int(num) if num.is_integer() else num), anchors, {'derived': True}


@register('date')
def op_date(ctx, args, value, anchors):
    args = args or {}
    text = as_text(value)
    try:
        dt = datetime.datetime.strptime(text, str(args.get('format') or '%Y-%m-%d'))
    except ValueError:
        return text, anchors, {'derived': True, 'issues': ['date_parse_failed']}
    return dt.strftime(str(args.get('out') or '%Y-%m-%d')), anchors, {'derived': True}

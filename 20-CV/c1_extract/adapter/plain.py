"""
adapter/plain.py — CSV / TXT / MD 纯文本路线适配（无 OCR、无图像载体）。
"""
from . import base


def page(pg):
    out = base._page_shell(pg)
    out['texts'] = []
    out['blocks'] = []
    out['tables'] = [base._table(t) for t in pg.get('structured_tables') or []]
    return out
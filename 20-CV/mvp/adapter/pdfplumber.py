"""
adapter/pdfplumber.py — 文本层 PDF 路线适配。

该路线文字投影来自整页 OCR（已是中性并行数组），表格来自文本层直读；
无版面语义（blocks 空）。原始 find_tables 快照只落 raw/pdfplumber.json。
"""
from . import base


def page(pg):
    out = base._page_shell(pg)
    out['texts'] = base._texts(pg)
    out['blocks'] = []
    out['tables'] = [base._table(t) for t in pg.get('structured_tables') or []]
    return out
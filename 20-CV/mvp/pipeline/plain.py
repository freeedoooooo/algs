"""
pipeline/plain.py — CSV / TXT / MD 纯文本直读，不加载任何模型。
"""
import io
import csv

import config


def read_text(path):
    raw = open(path, 'rb').read()
    for enc in config.TEXT_ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace'), 'utf-8(replace)'


def tables(text, ext):
    if ext != '.csv':
        return []
    rows = [r for r in csv.reader(io.StringIO(text))
            if any(c.strip() for c in r)]
    if not rows:
        return []
    return [{
        'page': 1, 'rows': rows, 'cell_grid': [],
        'strategy': 'csv.reader', 'source': 'csv',
        'coord': {'space': 'none', 'origin': 'csv', 'exact': False,
                  'note': '纯文本输入，没有图像载体'},
    }]

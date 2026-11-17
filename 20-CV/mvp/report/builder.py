"""
report/builder.py — 组装最终 index.html。

源码里 CSS / JS / lightbox 都是 assets/ 下的独立文件（方便维护、IDE 高亮），
但生成报告时把它们**内联**进 HTML —— 产出的 index.html 仍是自包含的，
整个 output/ 目录拷走、用 file:// 打开也能正常显示与交互。
"""
import os

from .. import config
from .. import params as params_mod
from . import cards


def _param_block(params):
    """报告页头的参数快照：折叠区，按优先级列出本次每个参数与说明。"""
    if not params:
        return ''
    rows = params_mod.describe(params)
    trs = ''.join(
        '<tr><td>{} <span class="hint" tabindex="0" data-tip="{}">?</span></td>'
        '<td><code>{}</code></td></tr>'
        .format(cards.esc(r['label']), cards.esc(r['help']),
                cards.esc(r['value']))
        for r in rows)
    return (
        '<details class="paramsnap"><summary>本次参数快照（{} 项，按优先级）'
        '</summary><table><thead><tr><th>参数</th><th>本次值</th>'
        '</tr></thead><tbody>{}</tbody></table></details>\n'
        .format(len(rows), trs))


def _asset(name):
    path = os.path.join(config.ASSETS_DIR, name)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def build(records, out_path, params=None):
    nav = ''.join(
        '<a href="#case-{}">{}</a>'.format(i, cards.esc(r.get('file', '?')))
        for i, r in enumerate(records))
    total_lines = sum(r.get('lines', 0) for r in records)
    total_tables = sum(len(r.get('structured_tables') or []) for r in records)

    header = (
        '<header><h1>CV 提取 MVP · 对照报告</h1>'
        '<div class="sub">共 {} 个文件 · {} 行识别文字 · {} 张结构化表格　|　'
        '左图吸顶 ↔ 右侧「文字行 / 表格 / JSON」切换；表格单元格可单格定位（图始终可见）；'
        '点击图片全屏放大；右下角「取 x 坐标」可量人工列边界（点图取 x、复制填 column_lines）'
        '</div><div class="nav"><a href="/">← 继续上传</a>{}</div>'
        '{}</header>\n'
        .format(len(records), total_lines, total_tables, nav,
                _param_block(params)))
    body = '\n'.join(cards.card(r, i) for i, r in enumerate(records))

    doc = (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>CV 提取 MVP · 对照报告</title>\n'
        '<style>\n' + _asset('hint.css') + '\n' + _asset('report.css')
        + '\n</style>\n</head><body>\n'
        + header
        + '<div class="wrap">\n' + body + '\n</div>\n'
        + _asset('lightbox.html') + '\n'
        + '<script>\n' + _asset('hint.js') + '\n' + _asset('report.js')
        + '\n</script>\n'
        + '</body></html>\n')

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    return os.path.abspath(out_path)

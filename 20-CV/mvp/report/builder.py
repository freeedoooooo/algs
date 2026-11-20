"""
report/builder.py — 组装提取报告（每个 case 一份独立自包含 HTML）。

模板只有一份：CSS / JS / lightbox 都是 assets/ 下的独立文件（方便维护、IDE 高亮），
生成报告时把它们**内联**进 HTML —— 产出的 提取报告.html 仍是自包含的。
报告直接落在该 case 的 output/<批次戳_文件名>/ 目录里，与 result.json /
图片 / CSV 同级，每次上传各自独立、互不覆盖。
"""
import os

from .. import config
from .. import params as params_mod
from .. import viewmodel
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
    # 磁盘 result.json 只存官方 parsing（ppstruct 路线），渲染前派生投影/layout
    records = [viewmodel.hydrate(r) for r in records]
    nav = ''.join(
        '<a href="#case-{}">{}</a>'.format(i, cards.esc(r.get('file', '?')))
        for i, r in enumerate(records))
    total_lines = sum(p.get('lines', 0)
                      for r in records for p in (r.get('pages') or []))
    total_tables = sum(len(p.get('structured_tables') or [])
                       for r in records for p in (r.get('pages') or []))
    total_stitch = sum(len(r.get('stitched_tables') or []) for r in records)

    header = (
        '<header><h1>C1 提取 · 提取报告</h1>'
        '<div class="sub">共 {} 个文件 · {} 行识别文字 · {} 张结构化表格 · {} 张跨页合并'
        '<span class="hint" tabindex="0" data-tip="左图吸顶，右侧页签切换；悬停/点击表格单元格定位；点击图片放大。多页文件用翻页组件切换，跨页合并表悬停自动切页。">?</span>'
        '</div><div class="nav">{}</div>'
        '{}</header>\n'
        .format(len(records), total_lines, total_tables, total_stitch, nav,
                _param_block(params)))
    body = '\n'.join(cards.card(r, i) for i, r in enumerate(records))

    doc = (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>C1 提取 · 提取报告</title>\n'
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

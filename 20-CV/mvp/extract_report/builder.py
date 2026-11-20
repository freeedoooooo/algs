"""
extract_report/builder.py — 组装对照报告（每个 case 一份独立自包含 HTML）。

结构模板在 templates/report.html；CSS / JS / lightbox 是 assets/ 下的独立文件
（方便维护、IDE 高亮），生成报告时把它们**内联**进 HTML —— 产出的
对照报告.html 仍是自包含的。报告直接落在该 case 的 output/<批次戳_文件名>/
目录里，与 result.json / 图片 / CSV 同级，每次上传各自独立、互不覆盖。
一份报告只含一个文件，多文件批次由上传页顶部的文件页签切换各自的报告。
"""
import os

from markupsafe import Markup

from .. import config
from .. import params as params_mod
from .. import viewmodel
from . import cards


def _param_block(params):
    """报告页头的参数快照：折叠区，按优先级列出本次每个参数与说明。"""
    if not params:
        return ''
    rows = params_mod.describe(params)
    return cards.render('paramsnap.html', rows=rows, n=len(rows))


def _asset(name):
    path = os.path.join(config.ASSETS_DIR, name)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def build(records, out_path, params=None):
    # 磁盘 result.json 只存官方 parsing（ppstruct 路线），渲染前派生投影/layout
    records = [viewmodel.hydrate(r) for r in records]
    total_lines = sum(p.get('lines', 0)
                      for r in records for p in (r.get('pages') or []))
    total_tables = sum(len(p.get('structured_tables') or [])
                       for r in records for p in (r.get('pages') or []))
    total_stitch = sum(len(r.get('stitched_tables') or []) for r in records)

    # 一份报告只含一个文件：页头不再列文件导航/文件数，只留本份的总量统计。
    # 内联资源与已渲染片段是可信内容，以 Markup 传入（模板其余部分 autoescape）。
    doc = cards.render(
        'report.html',
        total_lines=total_lines, total_tables=total_tables,
        total_stitch=total_stitch, paramsnap=Markup(_param_block(params)),
        hint_css=Markup(_asset('hint.css')),
        report_css=Markup(_asset('report.css')),
        lightbox=Markup(_asset('lightbox.html')),
        hint_js=Markup(_asset('hint.js')),
        report_js=Markup(_asset('report.js')),
        body=Markup('\n'.join(cards.card(r, i)
                              for i, r in enumerate(records))))

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    return os.path.abspath(out_path)
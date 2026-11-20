"""
extract_report/builder.py — 组装对照报告（每个 case 一份独立自包含 HTML）。

结构模板在 templates/report.html；CSS / JS / lightbox 是 assets/ 下的独立文件
（方便维护、IDE 高亮），生成报告时把它们**内联**进 HTML —— 产出的
对照报告.html 仍是自包含的。报告直接落在该 case 的 output/<批次戳_文件名>/
目录里，与 extract.json / 图片 / CSV 同级，每次上传各自独立、互不覆盖。
一份报告只含一个文件，多文件批次由上传页顶部的文件页签切换各自的报告。

消费契约 = cvdoc（extract.json 同形态）：派生视图已由 adapter 预生成，
渲染期不再现算任何内容数据。
"""
import os

from markupsafe import Markup

from .. import config
from .. import params as params_mod
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
    # records 已是 cvdoc（adapter 产物）：投影/统计预生成，直接消费。
    total_lines = sum((p.get('stats') or {}).get('lines', 0)
                      for r in records for p in (r.get('pages') or []))
    total_tables = sum(len(p.get('tables') or [])
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
    _write_markdown(records, os.path.dirname(out_path) or '.')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    return os.path.abspath(out_path)


def _write_markdown(records, case_dir):
    """文档 Markdown 预生成落 output/<case>/（与报告同级），统一「内容先落盘」策略。

    单页一份 <stem>.md，多页每页一份 <stem>_p<页码>.md；命名与渲染下载链接
    共用 cards.md_filename。在线文档视图已内联进报告 HTML，此处只补可下载文件。
    """
    for r in records:
        fname = (r.get('file') or {}).get('name', 'doc')
        pages = r.get('pages') or []
        single = len(pages) <= 1
        for pg in pages:
            page_no = None if single else pg.get('index')
            md_name = cards.md_filename(fname, page_no, single)
            text = cards.blocks_markdown(pg, cards.doc_blocks(pg))
            with open(os.path.join(case_dir, md_name), 'w',
                      encoding='utf-8') as f:
                f.write(text)
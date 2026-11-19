"""
mvp/params.py — 调试参数的唯一真相源：schema（顺序=优先级）+ 校验 + 快照。

设计要点：
  · SCHEMA 里 order 从小到大 = 页面上的显示顺序 = 重要/优先级顺序。
  · 默认值全部引用 config 常量，不在这里重复写数字（避免两处改不全）。
  · normalize() 把页面传来的字符串转成有类型的 dict，越界的钳制、非法的回退，
    并把警告一起返回（不因为一个填错的参数让整批失败）。
  · describe() 给报告页头渲染「本次参数快照」，让每个批次自己解释用了什么参数。
"""
import re

from . import config

# ---- 文字检测阈值：PaddleOCR 3.x 的 predict() 默认值（c_try_params.py 实测）----
DET_DEFAULT = 0.3
BOX_DEFAULT = 0.6
# ---- 检测框外扩 / 检测分辨率：3.7 paddlex configs/pipelines/OCR.yaml 默认 ----
UNCLIP_DEFAULT = 1.5
LIMIT_SIDE_DEFAULT = 64
LIMIT_TYPE_DEFAULT = 'min'

# ---- 参数 schema：order 即页面优先级顺序 ----
SCHEMA = [
    dict(key='page', label='PDF 页码', type='str', default='',
         order=1, group='① 先看哪一页',
         help='留空（默认）= 提取全部页，多页 PDF 自动启用分页与跨页合并。\n'
              '填页码（1 起）= 只提取该页。\n'
              'all / 全部 / * 等同留空。图片 / 纯文本始终单页。'),
    dict(key='table_strategy', label='表格策略首选', type='select',
         default='auto', options=['auto', 'lines', 'text'],
         order=2, group='② 表格能不能抽到',
         help='仅「有文本层的电子 PDF」生效；扫描件 / 图片走模型，不看此项。\n'
              'auto：自动回退（推荐）。依次试 人工/自动列边界 → 真实框线 → '
              '文字对齐，取第一个抽出表的。\n'
              'lines：强制按 PDF 真实框线切。适合框线完整、或一页多表。\n'
              'text：强制按文字列对齐切。适合无线框表（只有横线 / 空格对齐）。\n'
              '人工列边界：填下方 column_lines 即可，auto 会自动优先用，'
              '无需单独选策略。'),
    dict(key='column_lines', label='人工列边界（x 坐标）', type='str', default='',
         order=3, group='② 表格能不能抽到',
         help='竖线 x 坐标，逗号/空格分隔，需 ≥1 个且递增。'
              '图片/扫描件用原图像素（仅 doc_unwarp=off 生效），单条即可切开黏连格；'
              '文本层 PDF 用点坐标。留空则 PDF 自动推断、图片不重切。'),
    dict(key='det_thresh', label='文字检测阈值', type='float',
         default=DET_DEFAULT, min=0.05, max=0.95, step=0.05,
         order=6, group='④ 文字识别',
         help='调低救漏检、可能增误检。默认 0.3，按次覆盖不重建模型。'),
    dict(key='box_thresh', label='文字框阈值', type='float',
         default=BOX_DEFAULT, min=0.05, max=0.95, step=0.05,
         order=7, group='④ 文字识别',
         help='默认 0.6，漏检严重试 0.4。'),
    dict(key='det_unclip', label='检测框外扩比例', type='float',
         default=UNCLIP_DEFAULT, min=1.0, max=3.0, step=0.1,
         order=8, group='④ 文字识别',
         help='DBNet 框外扩系数。调大救被切边的字，但易把相邻字并进同框。默认 1.5。'),
    dict(key='det_limit_side_len', label='检测分辨率边长', type='int',
         default=LIMIT_SIDE_DEFAULT, min=32, max=4000, step=32,
         order=9, group='④ 文字识别',
         help='配合下一项：min 时调大=放大图救小字；max 时调小=缩小提速。默认 64。'),
    dict(key='det_limit_type', label='检测分辨率方向', type='select',
         default=LIMIT_TYPE_DEFAULT, options=['min', 'max'],
         order=10, group='④ 文字识别',
         help='min：短边不低于边长（放大图，救小字）。\n'
              'max：长边不超过边长（缩小图，提速）。\n'
              '配合「检测分辨率边长」使用。默认 min。'),
    dict(key='dpi', label='PDF 渲染 DPI', type='int',
         default=config.PDF_DPI, min=72, max=400, step=10,
         order=11, group='⑤ 渲染精度',
         help='小字/密集表调高到 150~200；越高越慢。'),
    dict(key='doc_unwarp', label='文档矫正(UVDoc)', type='select',
         default='on', options=['on', 'off'],
         order=12, group='⑥ 坐标回溯',
         help='on：方向分类 + UVDoc 去扭曲，适合旋转/弯曲扫描件（框叠矫正图）。\n'
              'off：关闭预处理，适合平整电子截图，框 1:1 叠原图。\n'
              '仅影响表格模型；人工列边界重切只在 off 生效。'),
]

_BY_KEY = {p['key']: p for p in SCHEMA}


def defaults():
    """返回类型正确的默认参数 dict。"""
    return {p['key']: p['default'] for p in SCHEMA}


def public_schema():
    """给上传页渲染表单用的 schema（去掉内部字段，带上 group/order）。"""
    keys = ('key', 'label', 'type', 'default', 'min', 'max', 'step',
            'options', 'order', 'group', 'help')
    return [{k: p[k] for k in keys if k in p} for p in SCHEMA]


def parse_lines(value):
    """'12,80 150' / [12,80] → [12.0,80.0,150.0]；非法返回 None（纯示例，非配置）。"""
    if value is None or value == '' or value == []:
        return None
    try:
        toks = re.split(r'[,，\s;；]+', str(value).strip()) if isinstance(value, str) \
            else [str(x) for x in value]
        nums = [float(t) for t in toks if t != '']
    except (TypeError, ValueError):
        return None
    if len(nums) < 1 or any(nums[i] >= nums[i + 1] for i in range(len(nums) - 1)):
        return None                      # 至少 1 条且递增；图片切一刀只需单条 x
    return nums


def parse_page(value):
    """''/all/全部/* → 'all'（默认全部页）；1~500 正整数 → 规范字符串；非法 → None。"""
    s = str(value if value is not None else '').strip().lower()
    if s in ('', 'all', '全部', '*'):
        return 'all'
    try:
        n = int(s)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 500:
        return None
    return str(n)


def normalize(raw):
    """
    校验并归一化页面参数 → (params, warnings)。

    params 保证含全部 SCHEMA 键且类型正确；column_lines 额外解析成
    params['_column_lines']（list[float] 或 None）。非法值回退默认并记警告。
    """
    raw = raw if isinstance(raw, dict) else {}
    out, warns = {}, []
    for p in SCHEMA:
        key, typ, val = p['key'], p['type'], raw.get(p['key'], p['default'])
        if typ in ('int', 'float'):
            try:
                val = int(val) if typ == 'int' else float(val)
            except (TypeError, ValueError):
                warns.append('{}「{}」不是数字，已用默认值 {}'.format(
                    p['label'], val, p['default']))
                val = p['default']
            for bound, ok in (('min', lambda a, b: a >= b),
                              ('max', lambda a, b: a <= b)):
                if bound in p and not ok(val, p[bound]):
                    warns.append('{}「{}」超出范围，已钳制到 {}'.format(
                        p['label'], val, p[bound]))
                    val = p[bound]
                    break
        elif typ == 'select':
            if val not in p['options']:
                warns.append('{}「{}」不在可选项内，已用 {}'.format(
                    p['label'], val, p['default']))
                val = p['default']
        else:
            val = '' if val is None else str(val).strip()[:500]
        out[key] = val
    lines_raw = out.get('column_lines', '')
    parsed = parse_lines(lines_raw)
    if lines_raw and parsed is None:
        warns.append('人工列边界「{}」无法解析（需 ≥1 个递增数字），已忽略'
                     .format(lines_raw[:80]))
    out['_column_lines'] = parsed
    page_raw = out.get('page', '')
    page = parse_page(page_raw)
    if page is None:
        warns.append('PDF 页码「{}」无法解析（需正整数或留空/all），已提取全部页'
                     .format(str(page_raw)[:40]))
        page = 'all'
    out['page'] = page
    return out, warns


def describe(params):
    """报告页头用：按 order 返回 [{label, value, help, group}]。"""
    rows = []
    for p in SCHEMA:
        val = params.get(p['key'], p['default'])
        if p['key'] == 'page':
            shown = '全部页' if val in ('all', '') else '第 {} 页'.format(val)
        elif p['key'] == 'column_lines':
            lines = params.get('_column_lines') or []
            shown = (', '.join('{:g}'.format(x) for x in lines)
                     if lines else '（留空）')
        elif p['key'] == 'table_strategy':
            shown = {'auto': 'auto', 'lines': 'lines',
                     'text': 'text'}.get(val, str(val))
        elif p['key'] == 'doc_unwarp':
            shown = ('on' if val == 'on'
                     else 'off')
        else:
            shown = str(val)
        rows.append({'label': p['label'], 'value': shown,
                     'help': p['help'], 'group': p['group'], 'order': p['order']})
    rows.sort(key=lambda r: r['order'])
    return rows

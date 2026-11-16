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

# ---- 参数 schema：order 即页面优先级顺序 ----
# type: int / float / str / select；select 必须有 options。
SCHEMA = [
    dict(key='page', label='PDF 页码', type='int', default=1, min=1, max=500,
         order=1, group='① 先看哪一页',
         help='多页 PDF 只处理这一页（渲染 + OCR + 表格都取它）。'
              '跨页 badcase 用它逐页定位，不用一次跑完整份。'),
    dict(key='table_strategy', label='表格策略首选', type='select',
         default='auto', options=['auto', 'explicit', 'lines', 'default', 'text'],
         order=2, group='② 表格能不能抽到',
         help='auto=按优先级自动回退；text=强制按文字对齐（无线框表）；'
              'lines=按矢量线；default=pdfplumber 默认。'),
    dict(key='column_lines', label='人工列边界（x 坐标）', type='str', default='',
         order=3, group='② 表格能不能抽到',
         help='逗号/空格分隔的竖线 x 坐标，如 17,112,175,265。'
              '填了就覆盖 config 里的固定版式模板；只对「有横线没竖线」的流水表有意义。'),
    dict(key='grid_min_h', label='预筛·最少横线', type='int',
         default=config.GRID_MIN_H, min=0, max=200,
         order=4, group='③ 扫描件进不进模型',
         help='扫描图的长直线预筛门槛。该进表格模型却没进，就调低；'
              '误把证件框当表格就调高。'),
    dict(key='grid_min_v', label='预筛·最少竖线', type='int',
         default=config.GRID_MIN_V, min=0, max=200,
         order=5, group='③ 扫描件进不进模型',
         help='同上，竖线数门槛。两个都调 0 = 跳过预筛、强制走表格模型。'),
    dict(key='det_thresh', label='文字检测阈值', type='float',
         default=DET_DEFAULT, min=0.05, max=0.95, step=0.05,
         order=6, group='④ 文字识别',
         help='调低救漏检但可能引入误检（PaddleOCR 3.x 默认 0.3）。'
              'predict 时按次覆盖，不重建模型。'),
    dict(key='box_thresh', label='文字框阈值', type='float',
         default=BOX_DEFAULT, min=0.05, max=0.95, step=0.05,
         order=7, group='④ 文字识别',
         help='与检测阈值配合，默认 0.6。漏检严重时试 0.4。'),
    dict(key='dpi', label='PDF 渲染 DPI', type='int',
         default=config.PDF_DPI, min=72, max=400, step=10,
         order=8, group='⑤ 渲染精度',
         help='小字 / 密集表格调高到 150~200 更清晰；越高图越大、OCR 越慢。'),
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
    """'17,112 175' / [17,112] → [17.0,112.0,175.0]；非法返回 None。"""
    if value is None or value == '' or value == []:
        return None
    try:
        toks = re.split(r'[,，\s;；]+', str(value).strip()) if isinstance(value, str) \
            else [str(x) for x in value]
        nums = [float(t) for t in toks if t != '']
    except (TypeError, ValueError):
        return None
    if len(nums) < 2 or any(nums[i] >= nums[i + 1] for i in range(len(nums) - 1)):
        return None                      # 至少要 2 条且递增，否则不是合法列边界
    return nums


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
        warns.append('人工列边界「{}」无法解析（需 ≥2 个递增数字），已忽略'
                     .format(lines_raw[:80]))
    out['_column_lines'] = parsed
    return out, warns


def describe(params):
    """报告页头用：按 order 返回 [{label, value, help, group}]。"""
    rows = []
    for p in SCHEMA:
        val = params.get(p['key'], p['default'])
        if p['key'] == 'page':
            shown = '第 {} 页'.format(val)
        elif p['key'] == 'column_lines':
            lines = params.get('_column_lines') or []
            shown = (', '.join('{:g}'.format(x) for x in lines)
                     if lines else '（留空：内置模板 / 自动推断）')
        elif p['key'] == 'table_strategy':
            shown = {'auto': 'auto（自动回退）', 'explicit': 'explicit',
                     'lines': 'lines', 'default': 'default',
                     'text': 'text（强制文字对齐）'}.get(val, str(val))
        else:
            shown = str(val)
        rows.append({'label': p['label'], 'value': shown,
                     'help': p['help'], 'group': p['group'], 'order': p['order']})
    rows.sort(key=lambda r: r['order'])
    return rows

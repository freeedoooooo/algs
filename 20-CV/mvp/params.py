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
SCHEMA = [
    dict(key='page', label='PDF 页码', type='int', default=1, min=1, max=500,
         order=1, group='① 先看哪一页',
         help='多页 PDF 只处理这一页。'),
    dict(key='table_strategy', label='表格策略首选', type='select',
         default='auto', options=['auto', 'explicit', 'lines', 'default', 'text'],
         order=2, group='② 表格能不能抽到',
         help='auto=自动回退；text=文字对齐（无线框表）；'
              'lines=矢量线；default=pdfplumber 默认。'),
    dict(key='column_lines', label='人工列边界（x 坐标）', type='str', default='',
         order=3, group='② 表格能不能抽到',
         help='竖线 x 坐标，逗号/空格分隔，需 ≥1 个且递增。'
              '图片/扫描件用原图像素（仅 doc_unwarp=off 生效），单条即可切开黏连格；'
              '文本层 PDF 用点坐标。留空则 PDF 自动推断、图片不重切。'),
    dict(key='grid_min_h', label='预筛·最少横线', type='int',
         default=config.GRID_MIN_H, min=0, max=200,
         order=4, group='③ 扫描件进不进模型',
         help='长直线预筛门槛：漏检表格调低，误检调高。'),
    dict(key='grid_min_v', label='预筛·最少竖线', type='int',
         default=config.GRID_MIN_V, min=0, max=200,
         order=5, group='③ 扫描件进不进模型',
         help='竖线数门槛。两者都 0 = 跳过预筛、强制走表格模型。'),
    dict(key='det_thresh', label='文字检测阈值', type='float',
         default=DET_DEFAULT, min=0.05, max=0.95, step=0.05,
         order=6, group='④ 文字识别',
         help='调低救漏检、可能增误检。默认 0.3，按次覆盖不重建模型。'),
    dict(key='box_thresh', label='文字框阈值', type='float',
         default=BOX_DEFAULT, min=0.05, max=0.95, step=0.05,
         order=7, group='④ 文字识别',
         help='默认 0.6，漏检严重试 0.4。'),
    dict(key='dpi', label='PDF 渲染 DPI', type='int',
         default=config.PDF_DPI, min=72, max=400, step=10,
         order=8, group='⑤ 渲染精度',
         help='小字/密集表调高到 150~200；越高越慢。'),
    dict(key='doc_unwarp', label='文档矫正(UVDoc)', type='select',
         default='on', options=['on', 'off'],
         order=9, group='⑥ 坐标回溯',
         help='on=方向分类+UVDoc 去扭曲，适合旋转/弯曲扫描件（框叠矫正图）；'
              'off=关闭预处理，适合平整电子截图，框 1:1 叠原图。仅影响表格模型。'),
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
                     if lines else '（留空）')
        elif p['key'] == 'table_strategy':
            shown = {'auto': 'auto', 'explicit': 'explicit',
                     'lines': 'lines', 'default': 'default',
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

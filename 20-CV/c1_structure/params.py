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

# ---- 识别模型档位（仅快照标签，不切换引擎）----
# 引擎实际模型名仍由 config.DET_MODEL / config.REC_MODEL 决定（pipeline/engines.py）。
# 这里给上传页一个可选档位，值只进参数快照与报告表头，便于追溯"本次按什么模型配置解析"。
MODEL_OPTIONS = ['PP-OCRv4-mobile', 'PP-OCRv4-server',
                 'PP-OCRv5-mobile', 'PP-OCRv5-server']


def _default_model_tier():
    """从当前服务配置推导默认档位，保证"默认=现在配置的模型"。"""
    det = (config.DET_MODEL or '').lower()
    ver = 'v5' if 'v5' in det else 'v4'
    size = 'server' if 'server' in det else 'mobile'
    tier = 'PP-{}-{}'.format(ver, size)
    return tier if tier in MODEL_OPTIONS else MODEL_OPTIONS[0]


# ---- 参数 schema：order 即页面优先级顺序 ----
SCHEMA = [
    dict(key='model', label='识别模型', type='select',
         default=_default_model_tier(), options=MODEL_OPTIONS,
         order=0, group='⓪ 模型',
         help='记录本次使用的识别模型档位到报告参数快照，便于追溯。\n'
              '默认档位跟随服务当前配置（PP-OCRv4-mobile）。\n'
              '注意：实际识别引擎使用服务配置的模型，切换档位不会改变引擎行为。'),
    dict(key='page', label='PDF 页码', type='str', default='',
         order=1, group='① 页面范围',
         help='留空（默认）：解析全部页，多页 PDF 自动启用分页与跨页合并。\n'
              '填写页码（从 1 开始）：仅解析该页。\n'
              '填写 all / 全部 / * 等同留空。图片与纯文本始终为单页。'),
    dict(key='table_strategy', label='表格识别策略', type='select',
         default='auto', options=['auto', 'lines', 'text'],
         order=2, group='② 表格识别',
         help='仅对有文本层的电子 PDF 生效；扫描件与图片由模型识别，不受此项影响。\n'
              'auto：依次尝试多种策略，取第一个成功抽出表格的结果（推荐）。\n'
              'lines：按 PDF 真实框线切分，适合框线完整或一页多表。\n'
              'text：按文字列对齐切分，适合无框线表格。\n'
              '填写「人工列边界」后，auto 会优先使用，无需单独选择策略。'),
    dict(key='column_lines', label='人工列边界（x 坐标）', type='str', default='',
         order=3, group='② 表格识别',
         help='竖线 x 坐标列表，以逗号或空格分隔，至少 1 个且递增。\n'
              '图片/扫描件使用原图像素坐标（仅 doc_unwarp 为 off 时生效），可用于拆分粘连的单元格。\n'
              '有文本层的 PDF 使用点（pt）坐标。留空时：PDF 自动推断，图片不重新切分。'),
    dict(key='det_thresh', label='文字检测阈值', type='float',
         default=DET_DEFAULT, min=0.05, max=0.95, step=0.05,
         order=6, group='③ 文字识别',
         help='调低可减少漏检，但可能增加误检。\n默认 0.3；按次覆盖，不会重新加载模型。'),
    dict(key='box_thresh', label='文字框阈值', type='float',
         default=BOX_DEFAULT, min=0.05, max=0.95, step=0.05,
         order=7, group='③ 文字识别',
         help='默认 0.6；漏检较多时可尝试 0.4。'),
    dict(key='det_unclip', label='检测框外扩比例', type='float',
         default=UNCLIP_DEFAULT, min=1.0, max=3.0, step=0.1,
         order=8, group='③ 文字识别',
         help='检测框外扩系数。调大可修复边缘被裁切的文字，但相邻文字可能并入同一框。\n默认 1.5。'),
    dict(key='det_limit_side_len', label='检测分辨率边长', type='int',
         default=LIMIT_SIDE_DEFAULT, min=32, max=4000, step=32,
         order=9, group='③ 文字识别',
         help='与下一项「检测分辨率方向」配合使用：\n'
              '方向为 min 时调大相当于放大图像，有利于识别小字；\n'
              '方向为 max 时调小相当于缩小图像，可提升速度。\n默认 64。'),
    dict(key='det_limit_type', label='检测分辨率方向', type='select',
         default=LIMIT_TYPE_DEFAULT, options=['min', 'max'],
         order=10, group='③ 文字识别',
         help='min：图像短边不低于该边长（放大图像，有利于识别小字）。\n'
              'max：图像长边不超过该边长（缩小图像，可提升速度）。\n'
              '与「检测分辨率边长」配合使用。默认 min。'),
    dict(key='dpi', label='PDF 渲染 DPI', type='int',
         default=config.PDF_DPI, min=72, max=400, step=10,
         order=11, group='④ 渲染精度',
         help='小字或密集表格可调高至 150~200；数值越高，处理耗时越长。'),
    dict(key='doc_unwarp', label='文档矫正（UVDoc）', type='select',
         default='on', options=['on', 'off'],
         order=12, group='⑤ 坐标回溯',
         help='on：执行方向分类与 UVDoc 扭曲矫正，适用于旋转、弯曲的扫描件（检测框叠加在矫正图上）。\n'
              'off：关闭预处理，适用于平整的电子截图（检测框按 1:1 叠加在原图上）。\n'
              '仅影响表格识别；人工列边界重新切分仅在 off 时生效。'),
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
        warns.append('PDF 页码「{}」无法解析（需正整数或留空/all），已解析全部页'
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

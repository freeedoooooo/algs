"""
pipeline/runner.py — 单文件提取的统一入口（编排各子模块）。

按后缀分流：
    图片        → PPStructureV3 单次推理（官方 parsing / 表格 / 矫正图）
    PDF 有文本层 → 渲染首页 + pdfplumber 直读表格（带 bbox）+ 整页 OCR 作文字源
    PDF 无文本层 → 同图片路线（单次推理）
    CSV / TXT   → 直读文本，不跑 OCR
所有坐标统一以「报告左图」的像素为准，两套空间用 coord.space / text_space 区分。

result.json 只存官方 parsing（裁死字段）+ structured_tables + 元信息；文字投影 /
layout 由 viewmodel.hydrate 渲染期派生、紧凑落盘时剥掉（文本层/CSV 无 parsing，
其 OCR 投影直接存储）。raw 表是中间态，不落盘。
"""
import os
import json
import shutil

from PIL import Image

from .. import config
from .. import viewmodel
from . import ocr as ocr_mod
from . import pdf as pdf_mod
from . import plain as plain_mod
from . import ppstruct as pp_mod
from . import resplit as resplit_mod
from . import structure as struct_mod


def _blank_rec(name, case_rel):
    return {
        'file': name, 'case': case_rel, 'kind': '', 'source': None,
        'rectified': None, 'image_size': None, 'rectified_size': None,
        'boxes_png': None, 'pages': 1, 'text_layer': False,
        'cropbox_limited': False, 'encoding': '', 'plain_text': '',
        'texts': [], 'scores': [], 'boxes': [], 'lines': 0,
        'avg_score': 0.0, 'low_score_lines': 0, 'elapsed': 0.0,
        'parsing': None, 'layout': [], 'text_space': 'source',
        'structured_tables': [],
        'table_route': 'skipped', 'notes': [],
        'page': 1, 'params_snapshot': {},
    }


def _maybe_resplit(raw, img_path, params, use_unwarp, log):
    """图片/扫描路线：填了人工列边界才重切；on 时坐标空间不一致，warn 跳过。"""
    lines = params.get('_column_lines')
    if not lines or not raw:
        return raw
    if use_unwarp:
        log('warn', 'table', '人工列边界仅支持 doc_unwarp=off'
            '（单元格框须与原图同空间），本次已跳过重切')
        return raw
    return resplit_mod.resplit(raw, lines, img_path, params=params, emit=log)


def _pp_route(rec, img_path, case_abs, params, use_unwarp, log, emit):
    """图片/扫描路线：PPStructureV3 单次推理，官方 parsing 为源，返回 raw 表。

    投影 texts/scores/boxes 与 layout 不在此存储——extract_one 末尾由
    viewmodel.hydrate 从 parsing 渲染期派生（落盘时剥掉，避免重复）。
    """
    res = pp_mod.extract(img_path, case_abs, use_unwarp=use_unwarp,
                         params=params, emit=emit)
    rec['parsing'] = res['parsing']
    rec['text_space'] = res['text_space']
    rec['elapsed'] = res['elapsed']
    rec['rectified_size'] = res['rect_size']
    if res['rect_size'] and use_unwarp:
        rec['rectified'] = 'pages/' + config.RECTIFIED_NAME
    raw = _maybe_resplit(res['raw'], img_path, params, use_unwarp, log)
    rec['table_route'] = 'ppstruct' if raw else 'skipped'
    if not emit:
        for n in res['notes']:
            log('info', 'model', n)
    rec['notes'].extend(res['notes'])
    return raw


def extract_one(src_path, case_abs, case_rel, params=None, emit=None):
    """
    处理一个文件，写产物到 case_abs，返回完整 rec dict。

    params 是本批调试参数；emit 是可选的日志回调 (level, stage, msg)，
    由 app 注入 —— 提取层只认回调，不 import Web 层。
    """
    os.makedirs(case_abs, exist_ok=True)
    name = os.path.basename(src_path)
    ext = os.path.splitext(name)[1].lower()
    rec = _blank_rec(name, case_rel)
    params = params or {}

    def log(level, stage, msg):
        if emit:
            emit(level, stage, msg, case=name)

    page = params.get('page') or 1
    dpi = params.get('dpi')
    use_unwarp = (params.get('doc_unwarp', 'on') == 'on')
    log('info', 'split', '载体：{} · 第 {} 页 · DPI {} · 文档矫正 {}'.format(
        ext.lstrip('.'), page, dpi or config.PDF_DPI,
        '开' if use_unwarp else '关（坐标直接叠原图）'))
    # 快照里不存内部解析字段（_column_lines），但保留它供 pdf.tables 使用
    rec['params_snapshot'] = {
        k: v for k, v in params.items() if not k.startswith('_')}
    rec['page'] = page
    img_path = None
    raw = []
    notes = []

    if ext in config.TEXT_EXTS:
        rec['kind'] = 'csv'
        text, enc = plain_mod.read_text(src_path)
        rec['plain_text'], rec['encoding'] = text, enc
        src_name = 'source' + ext
        shutil.copy2(src_path, os.path.join(case_abs, src_name))
        rec['source'] = src_name
        rec['table_route'] = 'text_layer'
        raw = plain_mod.tables(text, ext)
        rec['notes'].append('纯文本按 {} 解码，不跑 OCR'.format(enc))
        log('info', 'table', '纯文本按 {} 解码直读，不跑 OCR，解出 {} 张表'
            .format(enc, len(raw)))

    elif ext in config.PDF_EXTS:
        rec['kind'] = 'pdf'
        p1 = os.path.join(case_abs, 'pages', 'p1.png')
        # page 超出实际页数时夹到最后一页，避免空指针；快照仍保留用户填的原值
        _, npages, limited = pdf_mod.render_first_page(
            src_path, p1, page_no=page, dpi=dpi)
        rec['pages'], rec['cropbox_limited'] = npages, limited
        rec['page'] = min(max(int(page), 1), npages) if npages else page
        if rec['page'] != page:
            rec['notes'].append('页码 {} 超出实际 {} 页，已改用第 {} 页'
                                .format(page, npages, rec['page']))
        shutil.copy2(p1, os.path.join(case_abs, 'source.png'))
        rec['source'] = 'source.png'
        img_path = os.path.join(case_abs, 'source.png')
        rec['image_size'] = list(Image.open(img_path).size)
        tl = pdf_mod.text_layer(src_path, page_no=rec['page'])
        rec['text_layer'] = len(tl.strip()) > config.MIN_TEXT_LAYER_CHARS
        log('info', 'render', '已渲染第 {} 页（{}×{}，共 {} 页）→ PDF {}文本层'
            .format(rec['page'], *rec['image_size'], npages,
                    '有' if rec['text_layer'] else '无'))
        if rec['text_layer']:
            rec['plain_text'] = tl
            log('info', 'table', '走 pdfplumber 文本层直读（字符精确，不加载表格模型）')
            raw, notes = pdf_mod.tables(
                src_path, column_lines=params.get('_column_lines'),
                strategy=params.get('table_strategy') or 'auto', dpi=dpi,
                page_no=rec['page'])
            rec['table_route'] = 'text_layer'
            for n in notes:      # 文本层分支没有内部 emit，由 runner 统一发
                log('info', 'table', n)
        else:
            raw = _pp_route(rec, img_path, case_abs, params, use_unwarp,
                            log, emit)
        # 表格模型分支已在模块内即时 emit（时间戳准确），不再重复发
        rec['notes'].extend(notes)
        if limited:
            rec['notes'].append('PDF 有 CropBox 裁剪，预览图已按 MediaBox 整页渲染')

    else:
        rec['kind'] = 'image'
        src_name = 'source' + ext
        shutil.copy2(src_path, os.path.join(case_abs, src_name))
        rec['source'] = src_name
        img_path = os.path.join(case_abs, src_name)
        rec['image_size'] = list(Image.open(img_path).size)
        log('info', 'split', '图片 {}×{}，进入 PPStructureV3 单次推理'
            .format(*rec['image_size']))
        raw = _pp_route(rec, img_path, case_abs, params, use_unwarp, log, emit)

    # 整页 OCR 仅作「PDF 文本层」路线的文字源（该路线不跑 PPStructureV3）；
    # 图片/扫描路线的文字已由单次推理的 overall_ocr_res 投影提供，不再重复推理。
    if (rec['kind'] == 'pdf' and rec['text_layer']
            and img_path and os.path.isfile(img_path)):
        log('info', 'ocr', 'OCR 文字识别中（det={}, box={}, unclip={}, limit={}/{}）…'
            .format(params.get('det_thresh'), params.get('box_thresh'),
                    params.get('det_unclip'), params.get('det_limit_side_len'),
                    params.get('det_limit_type')))
        rec.update(ocr_mod.recognize(img_path, params=params))
        log('ok', 'ocr', '识别 {} 行，平均置信度 {}，低置信 {} 行，耗时 {}s'
            .format(rec['lines'], rec['avg_score'],
                    rec['low_score_lines'], rec['elapsed']))
    # 渲染期派生视图：ppstruct 路线从官方 parsing 现算投影/layout（不落盘）；
    # 文本层/CSV 无 parsing，投影已存储，hydrate 原样返回。
    viewmodel.hydrate(rec)
    if rec['table_route'] == 'ppstruct':
        log('ok', 'ocr', '单次推理投影 {} 行，平均置信度 {}，低置信 {} 行，耗时 {}s'
            .format(rec['lines'], rec['avg_score'],
                    rec['low_score_lines'], rec['elapsed']))
    if img_path and os.path.isfile(img_path) and rec['boxes']:
        ocr_mod.draw_boxes_png(
            img_path, rec, os.path.join(case_abs, config.BOXES_NAME))
        rec['boxes_png'] = config.BOXES_NAME

    rec['structured_tables'] = struct_mod.structure_all(raw)
    struct_mod.export_csvs(rec['structured_tables'], case_abs)
    for t in rec['structured_tables']:
        space = (t.get('coord') or {}).get('space')
        log('ok', 'table', '表 {}：{} 行 × {} 列 · 填充率 {} · 坐标空间 {}'
            .format(t.get('csv_file'), t['n_rows'], t['n_cols'],
                    t['fill_ratio'], space or 'none'))

    # 落盘 = 官方 parsing + structured_tables + 元信息（ppstruct 剥掉派生投影）；
    # 紧凑序列化（报告 JSON tab 渲染时再美化），避免 indent 把数值数组撑大。
    with open(os.path.join(case_abs, config.RESULT_JSON), 'w',
              encoding='utf-8') as f:
        json.dump(viewmodel.disk_view(rec), f, ensure_ascii=False,
                  separators=(',', ':'))
    return rec

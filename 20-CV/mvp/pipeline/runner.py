"""
pipeline/runner.py — 单文件提取的统一入口（编排各子模块）。

按后缀分流：
    图片        → OCR + 网格预筛 → 表格模型（矫正图 + 单元格框）
    PDF 有文本层 → 渲染首页 + OCR + pdfplumber 直读表格（带 bbox）
    PDF 无文本层 → 同图片路线
    CSV / TXT   → 直读文本，不跑 OCR
所有坐标统一以「报告左图」的像素为准，两套空间用 coord.space 区分。
"""
import os
import json
import shutil

from PIL import Image

from .. import config
from . import ocr as ocr_mod
from . import pdf as pdf_mod
from . import plain as plain_mod
from . import resplit as resplit_mod
from . import table_model as model_mod
from . import structure as struct_mod


def _blank_rec(name, case_rel):
    return {
        'file': name, 'case': case_rel, 'kind': '', 'source': None,
        'rectified': None, 'image_size': None, 'rectified_size': None,
        'boxes_png': None, 'pages': 1, 'text_layer': False,
        'cropbox_limited': False, 'encoding': '', 'plain_text': '',
        'texts': [], 'scores': [], 'boxes': [], 'lines': 0,
        'avg_score': 0.0, 'low_score_lines': 0, 'elapsed': 0.0,
        'tables': [], 'structured_tables': [],
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
    return resplit_mod.resplit(
        raw, lines, img_path,
        det_thresh=params.get('det_thresh'),
        box_thresh=params.get('box_thresh'), emit=log)


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
            raw, notes, rect = model_mod.tables(
                img_path, case_abs,
                min_h=params.get('grid_min_h'), min_v=params.get('grid_min_v'),
                use_unwarp=use_unwarp, emit=emit)
            raw = _maybe_resplit(raw, img_path, params, use_unwarp, log)
            rec['table_route'] = 'table_model' if raw else 'skipped'
            rec['rectified_size'] = rect
            # 只有「开了矫正」且真的落了矫正图，才需要原图/矫正图切换
            if rect and use_unwarp:
                rec['rectified'] = 'pages/' + config.RECTIFIED_NAME
        # 表格模型分支已在模块内即时 emit（时间戳准确），不再重复发
        if not emit:
            for n in notes:
                log('info', 'table', n)
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
        log('info', 'split', '图片 {}×{}，进入长直线预筛'.format(*rec['image_size']))
        raw, notes, rect = model_mod.tables(
            img_path, case_abs,
            min_h=params.get('grid_min_h'), min_v=params.get('grid_min_v'),
            use_unwarp=use_unwarp, emit=emit)
        raw = _maybe_resplit(raw, img_path, params, use_unwarp, log)
        rec['table_route'] = 'table_model' if raw else 'skipped'
        rec['rectified_size'] = rect
        if rect and use_unwarp:
            rec['rectified'] = 'pages/' + config.RECTIFIED_NAME
        if not emit:
            for n in notes:
                log('info', 'table', n)
        rec['notes'].extend(notes)

    # OCR：有图就跑（PDF 用首页渲染图，坐标正好对应预览图）
    if img_path and os.path.isfile(img_path):
        log('info', 'ocr', 'OCR 文字识别中（det={}, box={}）…'.format(
            params.get('det_thresh'), params.get('box_thresh')))
        rec.update(ocr_mod.recognize(
            img_path, det_thresh=params.get('det_thresh'),
            box_thresh=params.get('box_thresh')))
        ocr_mod.draw_boxes_png(
            img_path, rec, os.path.join(case_abs, config.BOXES_NAME))
        rec['boxes_png'] = config.BOXES_NAME
        log('ok', 'ocr', '识别 {} 行，平均置信度 {}，低置信 {} 行，耗时 {}s'
            .format(rec['lines'], rec['avg_score'],
                    rec['low_score_lines'], rec['elapsed']))

    rec['tables'] = raw
    rec['structured_tables'] = struct_mod.structure_all(raw)
    struct_mod.export_csvs(rec['structured_tables'], case_abs)
    for t in rec['structured_tables']:
        space = (t.get('coord') or {}).get('space')
        log('ok', 'table', '表 {}：{} 行 × {} 列 · 填充率 {} · 坐标空间 {}'
            .format(t.get('csv_file'), t['n_rows'], t['n_cols'],
                    t['fill_ratio'], space or 'none'))

    with open(os.path.join(case_abs, config.RESULT_JSON), 'w',
              encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return rec

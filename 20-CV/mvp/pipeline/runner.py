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


def extract_one(src_path, case_abs, case_rel, params=None):
    """
    处理一个文件，写产物到 case_abs，返回完整 rec dict。

    params 是本批调试参数（由 params.normalize 校验过的 dict）。整条 rec 都会
    带一份 params_snapshot —— 每个批次目录自解释「当时用了什么参数」，方便
    事后对比 badcase，不靠记忆。
    """
    os.makedirs(case_abs, exist_ok=True)
    name = os.path.basename(src_path)
    ext = os.path.splitext(name)[1].lower()
    rec = _blank_rec(name, case_rel)
    params = params or {}
    page = params.get('page') or 1
    dpi = params.get('dpi')
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
        if rec['text_layer']:
            rec['plain_text'] = tl
            raw, notes = pdf_mod.tables(
                src_path, column_lines=params.get('_column_lines'),
                strategy=params.get('table_strategy') or 'auto', dpi=dpi,
                page_no=rec['page'])
            rec['table_route'] = 'text_layer'
        else:
            raw, notes, rect = model_mod.tables(
                img_path, case_abs,
                min_h=params.get('grid_min_h'), min_v=params.get('grid_min_v'))
            rec['table_route'] = 'table_model' if raw else 'skipped'
            rec['rectified_size'] = rect
            if rect:
                rec['rectified'] = 'pages/' + config.RECTIFIED_NAME
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
        raw, notes, rect = model_mod.tables(
            img_path, case_abs,
            min_h=params.get('grid_min_h'), min_v=params.get('grid_min_v'))
        rec['table_route'] = 'table_model' if raw else 'skipped'
        rec['rectified_size'] = rect
        if rect:
            rec['rectified'] = 'pages/' + config.RECTIFIED_NAME
        rec['notes'].extend(notes)

    # OCR：有图就跑（PDF 用首页渲染图，坐标正好对应预览图）
    if img_path and os.path.isfile(img_path):
        rec.update(ocr_mod.recognize(
            img_path, det_thresh=params.get('det_thresh'),
            box_thresh=params.get('box_thresh')))
        ocr_mod.draw_boxes_png(
            img_path, rec, os.path.join(case_abs, config.BOXES_NAME))
        rec['boxes_png'] = config.BOXES_NAME

    rec['tables'] = raw
    rec['structured_tables'] = struct_mod.structure_all(raw)
    struct_mod.export_csvs(rec['structured_tables'], case_abs)

    with open(os.path.join(case_abs, config.RESULT_JSON), 'w',
              encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return rec

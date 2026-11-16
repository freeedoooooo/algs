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

import config
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
    }


def extract_one(src_path, case_abs, case_rel):
    """处理一个文件，写产物到 case_abs，返回完整 rec dict。"""
    os.makedirs(case_abs, exist_ok=True)
    name = os.path.basename(src_path)
    ext = os.path.splitext(name)[1].lower()
    rec = _blank_rec(name, case_rel)
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
        _, npages, limited = pdf_mod.render_first_page(src_path, p1)
        rec['pages'], rec['cropbox_limited'] = npages, limited
        shutil.copy2(p1, os.path.join(case_abs, 'source.png'))
        rec['source'] = 'source.png'
        img_path = os.path.join(case_abs, 'source.png')
        rec['image_size'] = list(Image.open(img_path).size)
        tl = pdf_mod.text_layer(src_path)
        rec['text_layer'] = len(tl.strip()) > config.MIN_TEXT_LAYER_CHARS
        if rec['text_layer']:
            rec['plain_text'] = tl
            raw, notes = pdf_mod.tables(src_path)
            rec['table_route'] = 'text_layer'
        else:
            raw, notes, rect = model_mod.tables(img_path, case_abs)
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
        raw, notes, rect = model_mod.tables(img_path, case_abs)
        rec['table_route'] = 'table_model' if raw else 'skipped'
        rec['rectified_size'] = rect
        if rect:
            rec['rectified'] = 'pages/' + config.RECTIFIED_NAME
        rec['notes'].extend(notes)

    # OCR：有图就跑（PDF 用首页渲染图，坐标正好对应预览图）
    if img_path and os.path.isfile(img_path):
        rec.update(ocr_mod.recognize(img_path))
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

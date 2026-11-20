"""
pipeline/runner.py — 单文件提取的统一入口（编排各子模块）。

按后缀分流，内部工作形态为「文件信封」rec：file/case/kind/encoding/
params_snapshot/page_count + pages:[pageRec…] + stitched_tables。
    图片        → PPStructureV3 单次推理（官方 parsing / 表格 / 矫正图），1 页
    PDF 有文本层 → 逐页渲染 + pdfplumber 直读表格（带 bbox）+ 整页 OCR 作文字源
    PDF 无文本层 → 同图片路线（逐页单次推理）
    CSV / TXT   → 直读文本，不跑 OCR，1 页
page 参数填 all 时 PDF 逐页全量提取，否则只处理指定页（默认单页）。
每页坐标以「该页报告左图」像素为准，两套空间用 coord.space / text_space 区分。

落盘边界（数据分层，算法零改动）：
  raw/*.json   引擎原样返回按路线分文件（paddle/pdfplumber/plain），永不服务前端；
  extract.json adapter 产出的 c1-extract 自有标准（派生视图提取期一次算好）。
内部 rec 的 parsing / 投影中间态不出 adapter；跨页续表由 structure.stitch_tables
合并成 stitched_tables（每格带 page/space，供报告页感知回溯）。
"""
import os
import json
import shutil

from PIL import Image

from .. import adapter
from .. import config
from . import ocr as ocr_mod
from . import pdf as pdf_mod
from . import plain as plain_mod
from . import ppstruct as pp_mod
from . import resplit as resplit_mod
from . import structure as struct_mod


def _blank_page(pno=1):
    return {
        'page': pno, 'source': None, 'rectified': None,
        'image_size': None, 'rectified_size': None, 'boxes_png': None,
        'text_layer': False, 'cropbox_limited': False, 'plain_text': '',
        'texts': [], 'scores': [], 'boxes': [], 'lines': 0,
        'avg_score': 0.0, 'low_score_lines': 0, 'elapsed': 0.0,
        'parsing': None, 'layout': [], 'text_space': 'source',
        'structured_tables': [], 'table_route': 'skipped', 'notes': [],
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


def _pp_route_page(page, img_path, case_abs, params, use_unwarp, log, emit,
                   rect_name):
    """图片/扫描路线：PPStructureV3 单次推理，官方 parsing 为源，返回 raw 表。

    投影 texts/scores/boxes 与 layout 由 adapter.hydrate 在提取期从 parsing
    派生（写进 extract.json，渲染期不再现算）；parsing 本体只落 raw/paddle.json。
    """
    res = pp_mod.extract(img_path, case_abs, use_unwarp=use_unwarp,
                         params=params, emit=emit, rect_name=rect_name)
    page['parsing'] = res['parsing']
    page['text_space'] = res['text_space']
    page['elapsed'] = res['elapsed']
    page['rectified_size'] = res['rect_size']
    if res['rect_size'] and use_unwarp:
        page['rectified'] = 'pages/' + rect_name
    raw = _maybe_resplit(res['raw'], img_path, params, use_unwarp, log)
    page['table_route'] = 'ppstruct' if raw else 'skipped'
    if not emit:
        for n in res['notes']:
            log('info', 'model', n)
    page['notes'].extend(res['notes'])
    return raw


def _extract_page_plain(src_path, case_abs, ext, log):
    page = _blank_page(1)
    text, enc = plain_mod.read_text(src_path)
    page['plain_text'] = text
    src_name = 'source' + ext
    shutil.copy2(src_path, os.path.join(case_abs, src_name))
    page['source'] = src_name
    page['table_route'] = 'text_layer'
    raw = plain_mod.tables(text, ext)
    page['_raw_text'] = text
    page['_raw_tables'] = raw
    page['notes'].append('纯文本按 {} 解码，不跑 OCR'.format(enc))
    log('info', 'table', '纯文本按 {} 解码直读，不跑 OCR，解出 {} 张表'
        .format(enc, len(raw)))
    page['structured_tables'] = struct_mod.structure_all(raw)
    return page, enc


def _extract_page_image(src_path, case_abs, ext, params, use_unwarp, log, emit):
    page = _blank_page(1)
    src_name = 'source' + ext
    shutil.copy2(src_path, os.path.join(case_abs, src_name))
    img_path = os.path.join(case_abs, src_name)
    page['source'] = src_name
    page['image_size'] = list(Image.open(img_path).size)
    log('info', 'split', '图片 {}×{}，进入 PPStructureV3 单次推理'
        .format(*page['image_size']))
    raw = _pp_route_page(page, img_path, case_abs, params, use_unwarp,
                         log, emit, config.RECTIFIED_NAME)
    page['structured_tables'] = struct_mod.structure_all(raw)
    return page


def _extract_page_pdf(src_path, case_abs, pno, npages, params, dpi,
                      use_unwarp, log, emit, multi):
    page = _blank_page(pno)
    if multi:
        img_rel = 'pages/p{}.png'.format(pno)
        rect_name = 'p{}_rectified.png'.format(pno)
    else:
        img_rel = 'source.png'
        rect_name = config.RECTIFIED_NAME
    img_path = os.path.join(case_abs, img_rel)
    os.makedirs(os.path.dirname(img_path), exist_ok=True)
    _, _np, limited = pdf_mod.render_first_page(
        src_path, img_path, page_no=pno, dpi=dpi)
    page['cropbox_limited'] = limited
    page['source'] = img_rel
    page['image_size'] = list(Image.open(img_path).size)
    tl = pdf_mod.text_layer(src_path, page_no=pno)
    page['text_layer'] = len(tl.strip()) > config.MIN_TEXT_LAYER_CHARS
    log('info', 'render', '第 {} 页已渲染（{}×{}，共 {} 页）→ PDF {}文本层'
        .format(pno, *page['image_size'], npages,
                '有' if page['text_layer'] else '无'))
    if page['text_layer']:
        page['plain_text'] = tl
        log('info', 'table', '第 {} 页走 pdfplumber 文本层直读'
            '（字符精确，不加载表格模型）'.format(pno))
        raw, notes = pdf_mod.tables(
            src_path, column_lines=params.get('_column_lines'),
            strategy=params.get('table_strategy') or 'auto', dpi=dpi,
            page_no=pno)
        page['table_route'] = 'text_layer'
        page['_raw_tables'] = raw
        page['_raw_text_layer'] = tl
        for n in notes:
            log('info', 'table', '第 {} 页 {}'.format(pno, n))
        page['notes'].extend(notes)
        log('info', 'ocr', '第 {} 页 OCR 文字识别中（det={}, box={}, unclip={}, '
            'limit={}/{}）…'.format(pno, params.get('det_thresh'),
                                    params.get('box_thresh'),
                                    params.get('det_unclip'),
                                    params.get('det_limit_side_len'),
                                    params.get('det_limit_type')))
        page.update(ocr_mod.recognize(img_path, params=params))
        log('ok', 'ocr', '第 {} 页识别 {} 行，平均置信度 {}，低置信 {} 行，耗时 {}s'
            .format(pno, page['lines'], page['avg_score'],
                    page['low_score_lines'], page['elapsed']))
    else:
        raw = _pp_route_page(page, img_path, case_abs, params, use_unwarp,
                             log, emit, rect_name)
    if limited:
        page['notes'].append('PDF 有 CropBox 裁剪，预览图已按 MediaBox 整页渲染')
    page['structured_tables'] = struct_mod.structure_all(raw)
    return page


def extract_one(src_path, case_abs, case_rel, params=None, emit=None):
    """
    处理一个文件，写产物到 case_abs（raw/ + extract.json + 页图 + CSV），
    返回 c1-extract 信封（含 pages / stitched_tables，自有标准，无引擎结构）。

    params 是本批调试参数；emit 是可选的日志回调 (level, stage, msg)，
    由 app 注入 —— 提取层只认回调，不 import Web 层。
    """
    os.makedirs(case_abs, exist_ok=True)
    name = os.path.basename(src_path)
    ext = os.path.splitext(name)[1].lower()
    params = params or {}

    def log(level, stage, msg):
        if emit:
            emit(level, stage, msg, case=name)

    page_param = params.get('page') or 'all'
    dpi = params.get('dpi')
    use_unwarp = (params.get('doc_unwarp', 'on') == 'on')
    file_rec = {
        'file': name, 'case': case_rel, 'kind': '', 'encoding': '',
        'params_snapshot': {k: v for k, v in params.items()
                            if not k.startswith('_')},
        'page_count': 1, 'pages': [], 'stitched_tables': [],
    }

    if ext in config.TEXT_EXTS:
        file_rec['kind'] = 'csv'
        log('info', 'split', '载体：{} · 纯文本直读（不跑 OCR）'.format(ext.lstrip('.')))
        page, enc = _extract_page_plain(src_path, case_abs, ext, log)
        file_rec['encoding'] = enc
        pages = [page]

    elif ext in config.PDF_EXTS:
        file_rec['kind'] = 'pdf'
        npages = pdf_mod.page_count(src_path)
        file_rec['page_count'] = npages or 1
        if page_param == 'all':
            page_list = list(range(1, (npages or 1) + 1))
            log('info', 'split', '载体：pdf · 全部 {} 页 · DPI {} · 文档矫正 {}'
                .format(npages, dpi or config.PDF_DPI,
                        '开' if use_unwarp else '关（坐标直接叠原图）'))
        else:
            p = int(page_param)
            clamped = min(max(p, 1), npages) if npages else p
            page_list = [clamped]
            log('info', 'split', '载体：pdf · 第 {} 页 · DPI {} · 文档矫正 {}'
                .format(clamped, dpi or config.PDF_DPI,
                        '开' if use_unwarp else '关（坐标直接叠原图）'))
        multi = len(page_list) > 1
        pages = []
        for pno in page_list:
            pg = _extract_page_pdf(src_path, case_abs, pno, npages, params,
                                   dpi, use_unwarp, log, emit, multi)
            if not multi and page_param != 'all' \
                    and page_list[0] != int(page_param):
                pg['notes'].append('页码 {} 超出实际 {} 页，已改用第 {} 页'
                                   .format(page_param, npages, pno))
            pages.append(pg)

    else:
        file_rec['kind'] = 'image'
        pages = [_extract_page_image(src_path, case_abs, ext, params,
                                     use_unwarp, log, emit)]

    file_rec['pages'] = pages
    # 多页时每页表 csv 名加页前缀，避免 table_1.csv 跨页互相覆盖
    if len(pages) > 1:
        for pg in pages:
            for t in pg['structured_tables']:
                t['csv_file'] = 'p{}_{}'.format(pg['page'], t['csv_file'])

    # 派生视图提取期一次算好（ppstruct 从官方 parsing；文本层/CSV 投影已存储）。
    # 带框图 / 跨页拼接都消费这份内部投影；落盘时 adapter 翻译成 c1-extract。
    adapter.hydrate(file_rec)

    # 每页带框 PNG（投影已在 hydrate 后就绪）
    multi_pdf = file_rec['kind'] == 'pdf' and len(pages) > 1
    for pg in pages:
        src = pg.get('source')
        if not src:
            continue
        img_path = os.path.join(case_abs, src)
        if not os.path.isfile(img_path) or not pg.get('boxes'):
            continue
        boxes_rel = ('pages/p{}_boxes.png'.format(pg['page'])
                     if multi_pdf else config.BOXES_NAME)
        ocr_mod.draw_boxes_png(img_path, pg, os.path.join(case_abs, boxes_rel))
        pg['boxes_png'] = boxes_rel
        if pg['table_route'] == 'ppstruct':
            log('ok', 'ocr', '第 {} 页单次推理投影 {} 行，平均置信度 {}，低置信 {} 行'
                .format(pg['page'], pg['lines'], pg['avg_score'],
                        pg['low_score_lines']))

    # 跨页续表合并（相邻页 + 同列 + 列对齐 + 重复表头）
    file_rec['stitched_tables'] = struct_mod.stitch_tables(pages)
    # 被并入合并表的逐页表 (page, 表下标) → 合并表下标（仅用于日志提示）。
    # 逐页表 CSV 全部落盘：表格 tab 下载/预览「仅本页这张表」；完整合并表另存
    # stitched_N.csv，在「跨页合并」tab 下载/预览（一个 PDF 可有多条跨页链）。
    merged = {(part['page'], part['tbl']): si
              for si, t in enumerate(file_rec['stitched_tables'])
              for part in t.get('parts') or []}
    for pg in pages:
        struct_mod.export_csvs(pg['structured_tables'], case_abs)
        for ti, t in enumerate(pg['structured_tables']):
            si = merged.get((pg['page'], ti))
            space = (t.get('coord') or {}).get('space')
            extra = ('；本页片段，完整见跨页合并表 {}'.format(si + 1)
                     if si is not None else '')
            log('ok', 'table', '第 {} 页表 {}：{} 行 × {} 列 · 填充率 {} · 坐标空间 {}{}'
                .format(pg['page'], t.get('csv_file'), t['n_rows'], t['n_cols'],
                        t['fill_ratio'], space or 'none', extra))
    if file_rec['stitched_tables']:
        struct_mod.export_csvs(file_rec['stitched_tables'], case_abs)
        for t in file_rec['stitched_tables']:
            log('ok', 'table', '跨页合并表 {}：{} 行 × {} 列 · 来源页 {}'
                .format(t['csv_file'], t['n_rows'], t['n_cols'],
                        t['source_pages']))

    # 落盘 = 数据分层：raw/ 引擎原样（按路线分文件）+ extract.json（c1-extract）。
    # 紧凑序列化（报告 JSON tab 渲染时再美化），避免 indent 把数值数组撑大。
    _write_raw(file_rec, case_abs)
    doc = adapter.adapt(file_rec)
    with open(os.path.join(case_abs, config.EXTRACT_JSON), 'w',
              encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    return doc


def _write_raw(file_rec, case_abs):
    """L0 原始层：引擎原样返回按路线分文件，供运维逐层比对（前端 403）。"""
    pages = file_rec.get('pages') or []
    raw_dir = os.path.join(case_abs, config.RAW_DIR)

    def dump(name, obj):
        os.makedirs(raw_dir, exist_ok=True)
        with open(os.path.join(raw_dir, name), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))

    paddle_pages = [{'page': pg['page'], 'parsing': pg['parsing']}
                    for pg in pages if pg.get('parsing')]
    if paddle_pages:
        dump('paddle.json', {'engine': 'PPStructureV3', 'pages': paddle_pages})
    if file_rec.get('kind') == 'csv':
        pg = pages[0] if pages else {}
        dump('plain.json', {'engine': 'plain',
                            'encoding': file_rec.get('encoding'),
                            'text': pg.get('_raw_text', ''),
                            'tables_raw': pg.get('_raw_tables') or []})
    else:
        tl_pages = [{'page': pg['page'],
                     'text_layer': pg.get('_raw_text_layer', ''),
                     'tables': pg.get('_raw_tables') or []}
                    for pg in pages if '_raw_tables' in pg]
        if tl_pages:
            dump('pdfplumber.json', {'engine': 'pdfplumber', 'pages': tl_pages})
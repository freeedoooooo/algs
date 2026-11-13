"""
第2周 · 表格检测与结构化提取（让「表格」成为一等公民）

【解决什么问题】
a_batch_ocr.py 原来只把表格当作「文字之外的补充」：
  - 103（有文本层 PDF）虽然抽到了一张表，但只是躺在 result.json 里的一块数据，
    而且被按文字行切碎（105 行伪表格）；
  - 107（扫描图）完全没有表格分支，只有 58 行零散的 OCR 文字。
可这两个文件里最关键的**恰恰是表格**：银行流水明细、事务所备案名单。

本模块补上一条「按载体分层」的表格路线，并把结果变成可复用的结构化数据：

    判载体
      ├─ 有文本层（PDF / CSV） ──→ 直读 pdfplumber，字符无损、不加载任何模型
      │                            表头 / 数据行分离 → 导出 CSV
      └─ 无文本层（图片 / 扫描 PDF）
            ├─ 先用长直线预筛：没有网格线就跳过（18 张合成样本全是纯文字）
            └─ 有网格线 → PPStructureV3 表格结构模型（自动校正整页方向）
                          表格 HTML → 解析成 rows → 导出 CSV

【谁在调用我】
a_batch_ocr.py 的 build_case_record() 末尾调用 enrich_case(rec, src_path, case_abs)，
把结构化结果写回 rec，再交给 vis_ocr_result.py 在报告里作为主区块展示。
自己带 main()，也能单独调试：python table_extract.py [文件...]（默认测 103 / 107）。
我 import 了 text_layer_extract（复用直读结果），不 import case_naming：
这里只处理文件内容，case 的分组 / 排序是 a_batch_ocr.py 的事。

【产物】（都在「调用方给的 case 目录」里，整目录可搬走）
    <case 目录>/tables.json      结构化表格 + 路由 + 诊断（给程序读）
    <case 目录>/table_1.csv      表头 + 数据行，UTF-8 BOM，Excel 双击不乱码
    <case 目录>/table_2.csv …    一页多表时按序号拆文件
单独调试时不碰正式产物，落在 output/table_extract/<输入名>/。

【为什么表格模型要「懒加载 + 单例」】
PPStructureV3 会加载十来个模型，首次约 23s。全量 25 个 case 如果每个都重建
一遍会慢到不能用，所以 _ENGINE 存在模块级变量里，一次加载整批复用；
而且只有「预筛命中网格」的 case 才会触发加载，纯文字图一分钱不花。

【坑位记录（11-13 实测）】
- 107 是旋转 90° 的扫描件。实测把原图直接喂给 PPStructureV3 就能自动转正
  并输出正确表格（内部的 PP-LCNet_x1_0_doc_ori 做整页方向分类），不必自己转图。
  这里只要 HTML / 结构，不需要识别框坐标，所以不受「预处理导致坐标错位」影响。
- res.html 是 dict（{'table_1': '<html>...'}），**空字典是正常情况**（这页没表格）。
  绝不能像 paddlex 的 save_to_html() 那样直接取第一个 key，会 IndexError。
- 表格 HTML 里常有 colspan（标题行）和单元格内换行，解析时要展开 / 压平。
"""

# =========================== 配置区：只改这里 ===========================
ENABLE_TABLE_MODEL = True        # 关掉就只走文本层直读，图片一律不加载表格模型
GRID_MIN_H_LINES = 5             # 长横线少于这个数 → 判定「没有表格网格」
GRID_MIN_V_LINES = 4             # 长竖线少于这个数 → 判定「没有表格网格」
GRID_RESIZE_MAX = 1000           # 预筛前把长边缩到这个尺寸，快且与分辨率无关
GRID_LINE_MIN_LEN = 80           # Hough 认定的「长直线」最小像素长度
MIN_TABLE_COLS = 3               # 少于 3 列不算表格
DEBUG_OUT = 'output/table_extract'   # 单独调试的产物根（按脚本名隔离）
# 不跟参数就测这两个：一个文本层 PDF、一个无文本层扫描图，正好覆盖两条路线。
DEBUG_CASES = (
    'input/103_real_bank_statement_textlayer.pdf',
    'input/107_real_scan_page2.jpg',
)
# ======================================================================

import os
import re
import csv
import sys
import json
from html.parser import HTMLParser

# ↓ 必须在任何 paddleocr / paddlex 被导入之前设置：模型走百度云源、跳过连通性检查。
# 本文件把真正的 paddle import 放进 build_engine()（懒加载），时序一定安全。
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

import text_layer_extract as textmod   # 复用文本层直读（不重复实现策略回退）


# --------------------------------------------------------------------------
# 一、把表格 HTML 解析成 rows（标准库，不引入 BeautifulSoup）
# --------------------------------------------------------------------------

class _TableParser(HTMLParser):
    """
    极简 <table> 解析器：只关心 tr / td / th / colspan / br。

    为什么自己写：PPStructureV3 给的是一段 HTML 字符串，直接正则去标签会
    丢失「哪几个字属于同一格」的信息；HTMLParser 是标准库，逐标签回调，
    能把每个 <td> 的文本收进独立的单元格。
    """

    def __init__(self):
        # convert_charrefs=True：&nbsp; / &amp; 之类自动转成正常字符
        super().__init__(convert_charrefs=True)
        self.tables = []       # 结果：[[[单元格, ...], ...], ...]
        self._table = None     # 当前正在解析的 <table>
        self._row = None       # 当前 <tr>
        self._buf = None       # 当前 <td> 里攒的文字片段
        self._colspan = 1

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self._table = []
        elif tag == 'tr' and self._table is not None:
            self._row = []
        elif tag in ('td', 'th') and self._row is not None:
            self._buf = []
            # colspan="5" 的标题行展开成 [标题, '', '', '', '']，
            # 后面 split_header() 才能认出「这行只有 1 个非空格，是标题不是表头」。
            attr = dict(attrs)
            try:
                self._colspan = max(1, int(attr.get('colspan', 1)))
            except (TypeError, ValueError):
                self._colspan = 1
        elif tag == 'br' and self._buf is not None:
            self._buf.append(' ')      # 单元格内换行先变空格

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._buf is not None:
            cell = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
            self._row.extend([cell] + [''] * (self._colspan - 1))
            self._buf = None
            self._colspan = 1
        elif tag == 'tr' and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == 'table' and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def parse_table_html(html_text):
    """把一段表格 HTML 解析成若干张表的 rows；输入为空返回 []。"""
    if not html_text or '<table' not in str(html_text).lower():
        return []
    parser = _TableParser()
    try:
        parser.feed(str(html_text))
        parser.close()
    except Exception:
        return []
    return parser.tables


# --------------------------------------------------------------------------
# 二、长直线预筛：只让「真有网格」的图去加载表格模型
# --------------------------------------------------------------------------

def grid_score(image_path):
    """
    数一数图里有多少条长横线 / 长竖线，返回 (横线数, 竖线数)。

    思路：先用形态学「开运算」只保留水平/垂直方向的长笔画，再用霍夫变换
    找线段。合成样本全是纯文字（竖线 0），103 之外的图不会误触发；
    106 / 107 这种带表格框线的扫描件会明显命中。
    cv2 / numpy 在这里才 import，纯文字 case 连这点开销都不用付。
    """
    if not image_path or not os.path.isfile(image_path):
        return 0, 0
    try:
        import cv2
        import numpy as np
    except ImportError:
        return 0, 0
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0, 0
        h, w = img.shape[:2]
        scale = GRID_RESIZE_MAX / max(h, w)
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale)
        bw = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 8)
        hkernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
        vkernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30))
        hmap = cv2.morphologyEx(bw, cv2.MORPH_OPEN, hkernel)
        vmap = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vkernel)
        args = dict(rho=1, theta=np.pi / 180, threshold=60,
                    minLineLength=GRID_LINE_MIN_LEN, maxLineGap=8)
        hl = cv2.HoughLinesP(hmap, **args)
        vl = cv2.HoughLinesP(vmap, **args)
        return (0 if hl is None else len(hl), 0 if vl is None else len(vl))
    except Exception:
        # 单张图处理异常不能连累整批：当作「无网格」跳过表格模型即可。
        return 0, 0


def looks_like_table(image_path):
    """返回 (是否有表格网格, 横线数, 竖线数)，阈值在配置区。"""
    nh, nv = grid_score(image_path)
    return (nh >= GRID_MIN_H_LINES and nv >= GRID_MIN_V_LINES), nh, nv


# --------------------------------------------------------------------------
# 三、表格结构模型（懒加载 + 单例）
# --------------------------------------------------------------------------

_ENGINE = None       # 模块级变量：整批 case 共用同一个模型实例


def build_engine():
    """第一次调用才 import 并加载模型；之后直接返回缓存的实例。"""
    global _ENGINE
    if _ENGINE is None:
        from paddleocr import PPStructureV3
        _ENGINE = PPStructureV3(
            use_formula_recognition=False,   # 只开表格识别，其它子模型都关掉
            use_chart_recognition=False,
            use_seal_recognition=False,
            use_region_detection=False,
            use_table_recognition=True,
            # CPU 上移动端 det/rec 比 server 快一个数量级，表格文字量不大够用
            text_detection_model_name='PP-OCRv4_mobile_det',
            text_recognition_model_name='PP-OCRv4_mobile_rec',
        )
    return _ENGINE


def _model_html_blocks(res):
    """
    从一个 PPStructureV3 结果里取出所有表格 HTML。

    优先用 res.html（{'table_1': '<html>...'}）；为空时从 parsing_res_list
    里 label 含 table 的内容块兜底（3.7.0 有些结果 html 为空但块里有表格）。
    判空很重要：这页没有表格时 res.html 是 {}，取 [0] 会 IndexError。
    """
    html_map = getattr(res, 'html', None) or {}
    blocks = [v for v in html_map.values() if v and '<table' in str(v).lower()]
    if blocks:
        return blocks
    data = res.json if hasattr(res, 'json') else res
    if isinstance(data, dict) and isinstance(data.get('res'), dict):
        data = data['res']
    found = []
    if isinstance(data, dict):
        for block in data.get('parsing_res_list', []) or []:
            if 'table' not in str(block.get('block_label', '')).lower():
                continue
            content = str(block.get('block_content', '') or '')
            if '<table' in content.lower():
                found.append(content)
    return found


def tables_from_model(image_path):
    """
    把一张图喂给表格模型，返回 (raw_tables, notes)。
    raw_tables 里一条 = 一张表，rows 是二维列表（还没做表头分离）。
    """
    raw, notes = [], []
    results = build_engine().predict(image_path)
    for page_no, res in enumerate(results, 1):          # 页码统一 1 起
        for html_text in _model_html_blocks(res):
            for rows in parse_table_html(html_text):
                if not rows:
                    continue
                raw.append({'page': page_no, 'rows': rows,
                            'source': 'PPStructureV3', 'strategy': 'table_model'})
                notes.append(f'第 {page_no} 页：表格模型还原出 {len(rows)} 行表格')
    if not raw:
        notes.append('表格模型未检测到表格（有网格线但不是表格，或识别失败）')
    return raw, notes


# --------------------------------------------------------------------------
# 四、结构化：表头 / 标题 / 数据行分离 + 落盘
# --------------------------------------------------------------------------

def normalize_cell(value):
    """把单元格里的换行 / 多余空白压成空格，CSV 里才不会出现断行。"""
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def split_header(rows):
    """
    猜哪一行是表头，返回 (标题行列表, 表头, 数据行列表)。

    规则很朴素但够用：前 6 行里，找「非空格子数 >= 3 且等于总列数」的第一行。
      - 103：第 1 行就是 8 个列名 → 表头 = 第 1 行，没有标题行
      - 107：第 1 行是 colspan=5 的大标题（只剩 1 个非空格），第 2 行才是
        「序号 / 会计师事务所名称 / …」→ 标题行单独留着，不混进数据
      - CSV：第 1 行是表头
    找不到就退而求其次把第 1 行当表头，并在报告里如实标注。
    """
    if not rows:
        return [], [], []
    width = max(len(r) for r in rows)
    rows = [list(r) + [''] * (width - len(r)) for r in rows]
    header_idx = 0
    for i, row in enumerate(rows[:6]):
        filled = sum(1 for c in row if str(c).strip())
        if filled >= MIN_TABLE_COLS and filled == width:
            header_idx = i
            break
    return rows[:header_idx], rows[header_idx], rows[header_idx + 1:]


def structure_table(raw, index):
    """把一张 raw 表整理成「有表头、有数据行」的结构化 dict。"""
    rows = [[normalize_cell(c) for c in r] for r in (raw.get('rows') or [])]
    title_rows, headers, data = split_header(rows)
    data = [r for r in data if any(r)]        # 丢掉全空行
    width = len(headers) if headers else max((len(r) for r in data), default=0)
    total = len(data) * width
    filled = sum(1 for r in data for c in r if c)
    ratio = round(filled / total, 3) if total else 0.0
    title = ' / '.join(c for r in title_rows for c in r if c)
    return {
        'page': raw.get('page', 1),
        'source': raw.get('source', '?'),
        'strategy': raw.get('strategy', '?'),
        'title': title,
        'headers': [normalize_cell(c) for c in headers],
        'rows': data,
        'n_rows': len(data),
        'n_cols': width,
        'fill_ratio': ratio,
        'low_confidence': ratio < 0.20,
        'csv_file': f'table_{index}.csv',
    }


def export_case_tables(case_abs, rec):
    """
    把结构化表格写到这个 case 自己的目录，返回写出的文件名列表。

    CSV 第一行固定是表头（方便 pandas / Excel 直接读），标题放在 tables.json
    和 HTML 报告里；编码用 utf-8-sig（带 BOM），Windows Excel 打开中文不乱码。
    """
    os.makedirs(case_abs, exist_ok=True)
    tables = rec.get('structured_tables') or []
    written = []
    for t in tables:
        path = os.path.join(case_abs, t['csv_file'])
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if t['headers']:
                writer.writerow(t['headers'])
            writer.writerows(t['rows'])
        written.append(t['csv_file'])
    payload = {
        'file': rec.get('file'),
        'route': rec.get('table_route'),
        'notes': rec.get('table_notes') or [],
        'n_tables': len(tables),
        'tables': tables,
    }
    with open(os.path.join(case_abs, 'tables.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    written.append('tables.json')
    return written


# --------------------------------------------------------------------------
# 五、统一入口：a_batch_ocr.py 调这个
# --------------------------------------------------------------------------

def enrich_case(rec, src_path, case_abs):
    """
    给一条 case 记录补上「结构化表格」，并把 CSV / JSON 落到它的目录。

    分层规则（这是本模块的核心）：
      · CSV / 有文本层 PDF → 直读，复用 text_layer_extract 已抽好的 tables
      · 图片 / 无文本层 PDF → 先长直线预筛，命中才加载表格结构模型
      · 没命中 / 关了开关 / 模型报错 → 不抛异常，只记诊断，OCR 结果照常保留

    rec 里新增三个字段（不动原来的 tables，避免破坏旧报告）：
        table_route          'text_layer' / 'table_model' / 'skipped' / 'failed'
        structured_tables    [{page, title, headers, rows, n_rows, n_cols, ...}]
        table_notes          人能读的诊断
    """
    kind = rec.get('kind', 'image')
    raw_tables, notes, route = [], [], ''

    if kind == 'csv' or (kind == 'pdf' and rec.get('text_layer')):
        route = 'text_layer'
        for raw in rec.get('tables') or []:
            raw_tables.append(dict(raw, source=raw.get('source') or 'text_layer'))
        notes.append('有文本层 / 纯文本：直接读字符，未加载任何表格模型')

    elif not ENABLE_TABLE_MODEL:
        route = 'skipped'
        notes.append('ENABLE_TABLE_MODEL=False，跳过图片表格模型')

    else:
        # 图片用原文件；扫描 PDF 用 extract_case() 渲染出来的首页图。
        image = src_path if kind == 'image' else (rec.get('preview_image') or '')
        hit, nh, nv = looks_like_table(image)
        if not hit:
            route = 'skipped'
            notes.append(f'长直线预筛未命中（长横线 {nh} / 长竖线 {nv}），'
                         f'判定无表格网格，跳过表格模型')
        else:
            try:
                route = 'table_model'
                notes.append(f'长直线预筛命中（长横线 {nh} / 长竖线 {nv}），'
                             f'启用 PPStructureV3（自动校正整页方向）')
                raw_tables, model_notes = tables_from_model(image)
                notes.extend(model_notes)
            except Exception as e:
                # 表格是增强功能，失败不能连累已经跑出来的 OCR 结果
                route = 'failed'
                raw_tables = []
                notes.append(f'表格模型失败（OCR 结果不受影响）：{e}')

    rec['table_route'] = route
    rec['structured_tables'] = [structure_table(t, i)
                                for i, t in enumerate(raw_tables, 1)]
    rec['table_notes'] = notes
    export_case_tables(case_abs, rec)
    return rec


# --------------------------------------------------------------------------
# 六、单独调试入口（不跑 a 的 OCR，不碰正式产物）
# --------------------------------------------------------------------------

def probe_record(path, case_abs):
    """单独调试时造一条最小 rec：PDF / CSV 走直读，图片只给基本信息。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.jpg', '.jpeg', '.png', '.bmp', '.webp'):
        return {'file': os.path.basename(path), 'kind': 'image',
                'preview_image': None, 'tables': [], 'text_layer': False}
    extra = textmod.extract_case(path, pages_dir=os.path.join(case_abs, 'pages'))
    return {'file': os.path.basename(path), 'kind': extra['kind'],
            'preview_image': extra['preview_image'], 'pages': extra['pages'],
            'text_layer': extra['text_layer'], 'tables': extra['tables']}


def print_summary(path, rec, case_abs):
    """把 enrich_case() 的结果打成人能读的摘要。"""
    print(f'>> {os.path.basename(path)}')
    print(f"   路线：{rec['table_route']}　结构化表格：{len(rec['structured_tables'])} 张")
    for note in rec['table_notes']:
        print(f'   · {note}')
    for t in rec['structured_tables']:
        print(f"   表：{t['n_rows']} 行 × {t['n_cols']} 列　填充率 {t['fill_ratio']}"
              f"　→ {t['csv_file']}")
        if t['title']:
            print(f"     标题：{t['title'][:60]}")
        print(f"     表头：{' | '.join(t['headers'])}")
        for row in t['rows'][:2]:
            print(f"     数据：{' | '.join(c[:18] for c in row)}")
    print(f"   产物目录：{os.path.join(case_abs).replace(os.sep, '/')}")


def main():
    """python table_extract.py [文件...]；不跟参数就测配置区的 DEBUG_CASES。"""
    paths = sys.argv[1:] or DEBUG_CASES
    for path in paths:
        if not os.path.isfile(path):
            print(f'!! 找不到文件：{path}')
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        case_abs = os.path.join(DEBUG_OUT, stem)
        os.makedirs(case_abs, exist_ok=True)
        rec = probe_record(path, case_abs)
        enrich_case(rec, path, case_abs)
        print_summary(path, rec, case_abs)
        print()


# 主程序守卫：被 a_batch_ocr.py import 时不会自动跑。
if __name__ == '__main__':
    main()

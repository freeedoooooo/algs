"""
第2周 · 表格专项 case 生成器（编号 20 起，只生成 input/ 里的样本文件）

【为什么单独一份脚本】
make_samples.py 负责 01~18 的「OCR 退化」样本和 101~ 的真实 case；
这一批 20~28 专门压测**表格提取**的边界：跨页、一页多表、合并单元格、
无线框、扫描件、旋转、空白页。两者互不干扰，重跑 make_samples.py 不会
删掉这些文件（它只覆盖自己命名的那批）。

【为什么用 pymupdf 手绘而不是真实文档】
1. 表格线是矢量 line，pdfplumber 的 find_tables() 能精确拿到每个单元格 bbox；
2. 中文用内置 CJK 字体 china-s 写入**真实文本层**，不经 OCR，字符无损；
3. 行数 / 列数 / 合并位置 / 页数全部可控，标准答案（manifest）能写死；
4. 无文本层的扫描件用 PIL 画完再贴进 PDF，走另一条（OCR / 表格模型）路线。

【用法】在 week-02 目录下：
    conda activate paddle
    python make_table_cases.py             # 已存在的文件默认跳过
    python make_table_cases.py --force     # 覆盖重生成
    python make_table_cases.py --no-manifest   # 只生成文件，不改说明书

【产物】input/20_*.pdf ~ 28_*，并向 samples_manifest.json upsert 登记条目
    （只增删 category 以「表格专项」开头的条目，不动其它 case）。
    ★ 若之后重跑过 make_samples.py（它会整体重写 manifest），
      再跑一次本脚本即可把 20~28 的登记补回来。

【设计原则】编号 <101 属合成样本（见 case_naming.py），新增 case 直接丢进
    input/ 就会被 a_batch_ocr.py 扫到，不用改任何清单白名单。
"""

# =========================== 配置区：调试只改这里 ===========================
OUT_DIR = 'input'                                  # 样本输出目录
MANIFEST = 'input/samples_manifest.json'           # 样本说明书
CJK_FONT = 'china-s'                               # pymupdf 内置简体中文字体（真实文本层）
PIL_FONT = 'C:/Windows/Fonts/msyh.ttc'             # 扫描件图片用的中文字体
PAGE_W, PAGE_H = 595, 842                          # A4 纵向，单位 pt（pdfplumber 同一坐标系）
LINE_W = 0.8                                       # 表格线宽（pt）
FONT_SIZE = 9                                      # 表格正文字号
HEADER_SIZE = 13                                   # 页眉标题字号
FORCE = False                                      # 命令行 --force 可覆盖
WRITE_MANIFEST = True                              # 命令行 --no-manifest 可关闭
# ==========================================================================

import os
import io
import sys
import json

import pymupdf
from PIL import Image, ImageDraw, ImageFont


# --------------------------------------------------------------------------
# 一、有文本层 PDF 的绘制工具
# --------------------------------------------------------------------------

def new_pdf():
    return pymupdf.open()


def new_page(doc):
    return doc.new_page(width=PAGE_W, height=PAGE_H)


def title(page, text, x=50, y=40, size=HEADER_SIZE):
    page.insert_text((x, y), text, fontname=CJK_FONT, fontsize=size)


def draw_table(page, col_lines, row_lines, cells, skip_v=(), skip_h=(),
               fs=FONT_SIZE):
    """
    画一张带矢量网格的表格。

    col_lines / row_lines 是格线坐标（长度分别为 列数+1 / 行数+1）。
    cells 是 {(行, 列): 文本}，空字符串表示该格无字（合并单元格的被吞格）。
    skip_v={(竖线序号, 行号)}：跳过该行里的这条内竖线 → 形成**横向合并**。
    skip_h={(横线序号, 列号)}：跳过该列段里的这条内横线 → 形成**纵向合并**。
    线段必须分段画，pdfplumber 才会把合并区域当成一个大单元格（实测返回 None
    表示被吞掉的格），整条画会把它切成正常格。
    """
    skip_v, skip_h = set(skip_v), set(skip_h)

    def ln(a, b):
        page.draw_line(a, b, color=(0, 0, 0), width=LINE_W)

    x0, x1 = col_lines[0], col_lines[-1]
    y0, y1 = row_lines[0], row_lines[-1]
    ln((x0, y0), (x1, y0))          # 上外框
    ln((x0, y1), (x1, y1))          # 下外框
    ln((x0, y0), (x0, y1))          # 左外框
    ln((x1, y0), (x1, y1))          # 右外框
    for k in range(1, len(col_lines) - 1):
        for r in range(len(row_lines) - 1):
            if (k, r) not in skip_v:
                ln((col_lines[k], row_lines[r]),
                   (col_lines[k], row_lines[r + 1]))
    for j in range(1, len(row_lines) - 1):
        for c in range(len(col_lines) - 1):
            if (j, c) not in skip_h:
                ln((col_lines[c], row_lines[j]),
                   (col_lines[c + 1], row_lines[j]))
    for (r, c), text in cells.items():
        if text:
            page.insert_text((col_lines[c] + 4, row_lines[r] + fs + 3),
                             str(text), fontname=CJK_FONT, fontsize=fs)


def grid(page, x, y, widths, row_h, rows, skip_v=(), skip_h=(), fs=FONT_SIZE):
    """按列宽 + 行高画一张规整表，rows 是二维列表；返回格线坐标备用。"""
    col_lines = [x]
    for w in widths:
        col_lines.append(col_lines[-1] + w)
    row_lines = [y + i * row_h for i in range(len(rows) + 1)]
    cells = {(r, c): v for r, row in enumerate(rows)
             for c, v in enumerate(row) if v}
    draw_table(page, col_lines, row_lines, cells, skip_v, skip_h, fs)
    return col_lines, row_lines


def save(doc, path):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    return path


# --------------------------------------------------------------------------
# 二、无文本层扫描件（PIL 画表格 → PNG → 贴进 PDF 或存成图片）
# --------------------------------------------------------------------------

def pil_font(size):
    try:
        return ImageFont.truetype(PIL_FONT, size)
    except OSError:
        return ImageFont.load_default()


def pil_table(rows, widths, row_h=46, head=''):
    """画一张白底黑线的表格图，模拟扫描件（不含任何文本层）。"""
    pad, gap = 24, (54 if head else 0)
    w = sum(widths) + pad * 2
    h = row_h * len(rows) + pad * 2 + gap
    img = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(img)
    f = pil_font(20)
    if head:
        d.text((pad, 14), head, fill='black', font=pil_font(26))
    xs = [pad]
    for cw in widths:
        xs.append(xs[-1] + cw)
    ys = [pad + gap + i * row_h for i in range(len(rows) + 1)]
    d.rectangle((xs[0], ys[0], xs[-1], ys[-1]), outline='black', width=2)
    for x in xs[1:-1]:
        d.line((x, ys[0], x, ys[-1]), fill='black', width=2)
    for y in ys[1:-1]:
        d.line((xs[0], y, xs[-1], y), fill='black', width=2)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            if val:
                d.text((xs[c] + 8, ys[r] + 11), str(val),
                       fill='black', font=f)
    return img


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def image_pdf(pages, path):
    """把若干张图贴成多页 PDF；页面里没有任何文字对象 → 无文本层。"""
    doc = new_pdf()
    for img in pages:
        page = doc.new_page(width=img.width, height=img.height)
        page.insert_image(page.rect, stream=png_bytes(img))
    return save(doc, path)


# --------------------------------------------------------------------------
# 三、每个 case 的具体内容
# --------------------------------------------------------------------------

FLOW_HEAD = ['交易日期', '订单编号', '客户名称', '摘要', '收入', '余额']
FLOW_ROWS = [
    ['2026-10-01', 'CK-2601', '宁波远景', '模块采购', '12,800.00', '128,000.00'],
    ['2026-10-02', 'CK-2602', '上海和裕', '年度服务费', '9,600.00', '137,600.00'],
    ['2026-10-03', 'CK-2603', '杭州启明', '设备租赁', '24,000.00', '161,600.00'],
    ['2026-10-04', 'CK-2604', '深圳恒达', '耗材补货', '3,450.00', '165,050.00'],
    ['2026-10-05', 'CK-2605', '苏州工业园区', '技术咨询', '18,200.00', '183,250.00'],
    ['2026-10-06', 'CK-2606', '广州白云', '培训服务', '7,800.00', '191,050.00'],
]
FLOW_W = [82, 78, 100, 92, 82, 86]


def flow_table(page, y, rows=FLOW_ROWS, head=FLOW_HEAD, widths=FLOW_W):
    return grid(page, 40, y, widths, 30, [head] + list(rows))


def case_20(path):
    """跨 3 页的同一张流水表：每页重复表头，数据连续。"""
    doc = new_pdf()
    for pno in (1, 2, 3):
        p = new_page(doc)
        title(p, f'2026 年第四季度交易明细（第 {pno} 页 / 共 3 页）')
        rows = [[r[0], f'CK-{2600 + pno * 6 + i}', r[2], r[3], r[4], r[5]]
                for i, r in enumerate(FLOW_ROWS, 1)]
        flow_table(p, 80, rows)
        p.insert_text((40, 340), '本页小计见第 3 页汇总；跨页表格应保持列结构一致。',
                      fontname=CJK_FONT, fontsize=FONT_SIZE)
    return save(doc, path)


def case_21(path):
    """一页两张表：上方 6 列明细，下方 4 列汇总（列数不同）。"""
    doc = new_pdf()
    p = new_page(doc)
    title(p, '月度结算单（一页两张独立表格）')
    flow_table(p, 80)
    grid(p, 40, 340, [120, 110, 110, 110], 30, [
        ['项目', '笔数', '金额', '状态'],
        ['收入合计', '6', '75,850.00', '已核对'],
        ['支出合计', '2', '11,200.00', '已核对'],
        ['净额', '4', '64,650.00', '待复核'],
    ])
    p.insert_text((40, 500), '两张表列数不同，用来验证多表切换与 tab 只叠当前表。',
                  fontname=CJK_FONT, fontsize=FONT_SIZE)
    return save(doc, path)


def case_22(path):
    """横向合并表头 + 纵向合并分组列，两种合并在同一张表里。"""
    doc = new_pdf()
    p = new_page(doc)
    title(p, '区域业绩表（含横向与纵向合并单元格）')
    rows = [
        ['区域 / 季度', '', '金额', '备注'],                    # 表头 col0+col1 横向合并
        ['华东区', '上海', '12,800', '已审'],
        ['', '杭州', '9,600', '已审'],                        # 左列纵向合并（第1~2行）
        ['华南区', '深圳', '24,000', '待审'],
        ['', '广州', '7,800', '待审'],                        # 左列纵向合并（第3~4行）
        ['合计', '', '54,200', '—'],                          # col1+col2 横向合并
    ]
    # skip_v：(竖线序号, 行号)；skip_h：(横线序号, 列号)
    skip_v = {(1, 0), (1, 5)}          # 表头 col0+col1、合计行 col0+col1
    skip_h = {(2, 0), (4, 0)}          # 左列 r1+r2、r3+r4 各纵向合并
    grid(p, 45, 90, [110, 100, 100, 100], 34, rows,
         skip_v=skip_v, skip_h=skip_h, fs=10)
    p.insert_text((45, 370), '合并格在 pdfplumber 里返回 None，报告里该格应无独立框。',
                  fontname=CJK_FONT, fontsize=FONT_SIZE)
    return save(doc, path)


def case_23(path):
    """3 页混合：第1页两表、第2页续表+小表、第3页一表。"""
    doc = new_pdf()
    p1 = new_page(doc)
    title(p1, '第 1 页：两张表（明细 + 汇总）')
    flow_table(p1, 80, FLOW_ROWS[:3])
    grid(p1, 40, 250, [120, 110, 110, 110], 30, [
        ['项目', '笔数', '金额', '状态'],
        ['本页收入', '3', '46,400.00', '已核对'],
    ])
    p2 = new_page(doc)
    title(p2, '第 2 页：续表 + 一张独立小表')
    flow_table(p2, 80, FLOW_ROWS[3:])
    grid(p2, 40, 300, [140, 140, 140], 30, [
        ['复核人', '日期', '结论'],
        ['张工', '2026-10-08', '通过'],
    ])
    p3 = new_page(doc)
    title(p3, '第 3 页：季度汇总（单表）')
    grid(p3, 40, 80, [130, 130, 130, 130], 32, [
        ['季度', '收入', '支出', '净额'],
        ['Q3', '180,000.00', '42,000.00', '138,000.00'],
        ['Q4', '75,850.00', '11,200.00', '64,650.00'],
    ])
    return save(doc, path)


def case_24(path):
    """无线框 stream 型：只有按列对齐的文字，测策略回退到 text。"""
    doc = new_pdf()
    p = new_page(doc)
    title(p, '无框线表格（靠文字对齐，测试策略回退）')
    rows = [
        ['品名', '规格', '数量', '单价', '金额'],
        ['图像采集模块', 'IVC-2400', '24', '1,280.00', '30,720.00'],
        ['工业相机', 'CAM-8G', '12', '2,400.00', '28,800.00'],
        ['支架', 'BR-01', '48', '85.00', '4,080.00'],
        ['合计', '', '84', '', '63,600.00'],
    ]
    xs = [45, 175, 285, 355, 445]
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            if val:
                p.insert_text((xs[c], 100 + r * 34), val,
                              fontname=CJK_FONT, fontsize=10)
    p.insert_text((45, 330), '页面里没有任何矢量线，lines 策略会失败，应回退到 text。',
                  fontname=CJK_FONT, fontsize=FONT_SIZE)
    return save(doc, path)


def case_25(path):
    """无文本层扫描件 PDF：2 页各一张表，必须走 OCR / 表格模型路线。"""
    imgs = [
        pil_table([['序号', '名称', '数量', '金额'],
                   ['1', '采集模块', '24', '30,720.00'],
                   ['2', '工业相机', '12', '28,800.00'],
                   ['3', '支架', '48', '4,080.00']],
                  [110, 240, 130, 180], head='扫描件第 1 页 · 出库明细'),
        pil_table([['月份', '收入', '支出', '净额'],
                   ['9 月', '180,000', '42,000', '138,000'],
                   ['10 月', '75,850', '11,200', '64,650']],
                  [150, 180, 180, 180], head='扫描件第 2 页 · 月度汇总'),
    ]
    return image_pdf(imgs, path)


def case_26(path):
    """一页三张小表 + 页眉页脚噪声文字，测多表与噪声区分。"""
    doc = new_pdf()
    p = new_page(doc)
    title(p, '多表混排页（三张表 + 说明文字噪声）')
    grid(p, 40, 80, [110, 110, 110], 28, [
        ['部门', '人数', '状态'], ['研发', '18', '在岗'], ['测试', '6', '在岗'],
    ])
    p.insert_text((40, 190), '以下为第二张表：项目进度（这段说明不应被并入表格）。',
                  fontname=CJK_FONT, fontsize=FONT_SIZE)
    grid(p, 40, 215, [130, 110, 110], 28, [
        ['项目', '进度', '负责人'], ['A-01', '80%', '李工'], ['B-07', '45%', '王工'],
    ])
    p.insert_text((40, 325), '以下为第三张表：费用（列数与上面两张都不同）。',
                  fontname=CJK_FONT, fontsize=FONT_SIZE)
    grid(p, 40, 350, [100, 100, 100, 100], 28, [
        ['费用项', '预算', '实际', '差额'],
        ['差旅', '20,000', '18,400', '1,600'],
        ['耗材', '8,000', '8,650', '-650'],
    ])
    p.insert_text((40, 480), '制表：财务部　审核：—　日期：2026-10-08',
                  fontname=CJK_FONT, fontsize=FONT_SIZE)
    return save(doc, path)


def case_27(path):
    """旋转 90° 的一页双表扫描图（PNG），测表格模型自动转正 + 多表。"""
    img = pil_table([
        ['编号', '客户', '金额'], ['A-01', '宁波远景', '12,800'],
        ['A-02', '上海和裕', '9,600'], ['A-03', '杭州启明', '24,000'],
    ], [130, 240, 180], head='旋转扫描页 · 表一')
    img2 = pil_table([
        ['月份', '收入'], ['9 月', '180,000'], ['10 月', '75,850'],
    ], [200, 200], head='旋转扫描页 · 表二')
    canvas = Image.new('RGB', (max(img.width, img2.width),
                              img.height + img2.height + 30), 'white')
    canvas.paste(img, (0, 0))
    canvas.paste(img2, (0, img.height + 30))
    canvas.rotate(90, expand=True).save(path, 'PNG')
    return path


def case_28(path):
    """4 页混合边界：纯文字页 / 表格页 / 空白页 / 表格页。"""
    doc = new_pdf()
    p1 = new_page(doc)
    title(p1, '第 1 页：只有说明文字，没有表格')
    for i, line in enumerate([
        '本文件用于验证跨页提取时，空页与无表格页不会干扰其它页。',
        '第 2 页开始才出现表格；第 3 页是故意留白的页面。',
        '若抽取结果里出现 3 张以上表格，说明空页被误判了。',
    ]):
        p1.insert_text((45, 90 + i * 30), line,
                       fontname=CJK_FONT, fontsize=11)
    p2 = new_page(doc)
    title(p2, '第 2 页：唯一的表格之一')
    flow_table(p2, 80, FLOW_ROWS[:3])
    new_page(doc)                       # 第 3 页：完全空白
    p4 = new_page(doc)
    title(p4, '第 4 页：唯一的表格之二')
    flow_table(p4, 80, FLOW_ROWS[3:])
    return save(doc, path)


# (编号, 文件名, 生成函数, 类别, 说明, 预期页数, 预期表数, 标准答案行)
CASES = [
    (20, '20_multipage_3pages.pdf', case_20, '跨页表格',
     '3 页连续流水表，每页重复表头，数据延续', 3, 3,
     ['2026 年第四季度交易明细（第 1 页 / 共 3 页）']),
    (21, '21_two_tables_1page.pdf', case_21, '一页多表',
     '1 页两张列数不同的表（6 列明细 + 4 列汇总）', 1, 2,
     ['月度结算单（一页两张独立表格）']),
    (22, '22_merged_cells.pdf', case_22, '合并单元格',
     '横向合并表头 + 纵向合并分组列，合并处 cells 为 None', 1, 1,
     ['区域业绩表（含横向与纵向合并单元格）']),
    (23, '23_multipage_multitable.pdf', case_23, '跨页+多表',
     '3 页：p1 两表 / p2 续表+小表 / p3 单表', 3, 5,
     ['第 1 页：两张表（明细 + 汇总）']),
    (24, '24_stream_no_grid.pdf', case_24, '无线框表格',
     '无任何矢量线，靠文字对齐，测策略回退 text', 1, 1,
     ['无框线表格（靠文字对齐，测试策略回退）']),
    (25, '25_scan_multipage.pdf', case_25, '扫描件跨页',
     '无文本层，2 页各一张表，走 OCR / 表格模型', 2, 2, []),
    (26, '26_three_tables_noise.pdf', case_26, '一页多表+噪声',
     '1 页三张小表，夹杂页眉说明与页脚', 1, 3,
     ['多表混排页（三张表 + 说明文字噪声）']),
    (27, '27_rotated_two_tables.png', case_27, '旋转多表',
     '顺时针旋转 90° 的一页双表扫描图，测模型自动转正', 1, 2, []),
    (28, '28_multipage_blank_mixed.pdf', case_28, '跨页边界',
     '4 页：纯文字 / 表格 / 空白 / 表格', 4, 2,
     ['第 1 页：只有说明文字，没有表格']),
]


# --------------------------------------------------------------------------
# 四、manifest 登记（只 upsert 自己这批，不动其它 case）
# --------------------------------------------------------------------------

def upsert_manifest(entries):
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        data = json.load(f)
    samples = [s for s in data.get('samples', [])
               if not str(s.get('category', '')).startswith('表格专项')]
    samples.extend(entries)
    data['samples'] = samples
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(samples)


def main():
    global FORCE, WRITE_MANIFEST
    FORCE = '--force' in sys.argv
    WRITE_MANIFEST = '--no-manifest' not in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    entries, made, skipped = [], 0, 0
    print('>> 表格专项 case 生成器：编号 20 起，输出到 %s/' % OUT_DIR)
    for no, fname, builder, category, desc, pages, tables, expect in CASES:
        path = os.path.join(OUT_DIR, fname)
        if os.path.isfile(path) and not FORCE:
            print('  跳过 %s（已存在，--force 可覆盖）' % fname)
            skipped += 1
        else:
            builder(path)
            print('  生成 %-36s %s' % (fname, desc))
            made += 1
        entries.append({
            'file': fname,
            'category': '表格专项_' + category,
            'distortion': '无退化；' + desc,
            'source': 'synthetic',
            'expect_lines': expect,
            'group': 'synthetic',
            'table_expect': {'pages': pages, 'tables': tables,
                             'note': '设计意图（人工标注）；当前流水线实测基线见 notes.md'},
        })
    if WRITE_MANIFEST:
        n = upsert_manifest(entries)
        print('>> manifest 已 upsert：本次 %d 条，总 %d 条' % (len(entries), n))
    print('>> 完成：新增 %d 个，跳过 %d 个。重跑 a_batch_ocr.py 即生效。'
          % (made, skipped))


if __name__ == '__main__':
    main()

"""
第2周 · bad case 样本生成器（一次运行，把素材铺满 input/）

【这份脚本在做什么】
用程序"画"出一批中文文档图片，再对同一份干净底稿分别施加一种图像退化
（模糊、倾斜、反光、阴影……），生成第2周压测要用的 bad case 素材。

【为什么不直接从网上下载真实图片】
1. 版权与隐私不可控，工作场景还有涉密风险；
2. 网络图片往往是「好几种毛病混在一起」，无法判断到底是哪个因素导致识别变差；
3. 合成图自带「标准答案」（samples_manifest.json 里的 expect_lines），
   能精确看出 OCR 漏了哪一行、认错了哪个字 —— 这是真实照片做不到的。

因此这里采用「同一份干净底稿 + 每次只变一个因素」的对照实验设计。
在此基础上，脚本还会把第1周的真实图与原始文件复制进来当真实世界对照组。
11-13 定稿：**合成样本 01~18；真实 case 从 101 起编号，格式 101_real_xxx**。
数字前缀方便排序查找，real_ 一眼看出是自己的素材；分组与排序规则统一放在
case_naming.py（唯一真相源）。新增 case 只要丢进 input/ 再跑 a_batch_ocr.py
就会被自动扫到，不用改这份清单，也不用改任何脚本。
重复素材已去掉（原先 test1/test2 各存了两份字节相同的副本）。

【用法】在 week-02 目录下：
    conda activate paddle
    python make_samples.py

【产物】
    input/01_xxx.png ~ 18_xxx.png        18 张合成退化样本（编号连续）
    input/101_real_xxx.* ~ 107_real_*    7 个用户真实 case（101 起编号，恒排最后，已去重）
    input/108_real_xxx.* ...             你自己新增的 case：接着编号，重跑即生效
    input/samples_manifest.json          每个 case 的类别 / 退化说明 / 分组 / 标准答案

其中 15~18 是「重度退化」：首轮实测轻度退化几乎打不垮 PP-OCRv4，
这 4 张专门把图像劣化到能观察到明显失败，给 bad case 库提供真素材。

脚本只覆盖自己命名的这些文件，不会删除你放进 input/ 的其他图片，可以反复运行。
"""

# =========================== 配置区：调试只改这里 ===========================
OUT_DIR = 'input'                                  # 样本输出目录
MANIFEST = 'input/samples_manifest.json'           # 样本说明书（标准答案在这里）
WEEK01_INPUT = '../week-01/input'                  # 真实样本来源目录
WEEK01_PAGES = '../week-01/output/c_pdf_text_layer/test3_image/pages'  # 真实扫描页来源
# 与 a_batch_ocr.py 保持一致：这些后缀才算 case。补登记用户新增 case 时要用到。
SUPPORTED_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.pdf', '.csv', '.txt', '.md')
SEED = 20261112                                    # 随机种子：固定后每次生成的噪声完全一样
PAGE_W, PAGE_H = 1100, 760                         # 干净底稿的尺寸（像素）
FONT_REGULAR = 'C:/Windows/Fonts/msyh.ttc'         # 微软雅黑：正文
FONT_BOLD = 'C:/Windows/Fonts/msyhbd.ttc'          # 微软雅黑粗体：标题
FONT_MONO = 'C:/Windows/Fonts/consola.ttf'         # 等宽字体：模拟终端截图
FONT_HAND = 'C:/Windows/Fonts/STXINGKA.TTF'        # 华文行楷：模拟手写
# ==========================================================================

import os
import json
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import cv2  # 只用来做透视变换，其余图像操作都用 PIL

# 命名 / 分组 / 排序规则的唯一真相源（本文件不自己猜「谁是真实 case」）。
import case_naming as naming


# --------------------------------------------------------------------------
# 一、干净底稿
# --------------------------------------------------------------------------

# 底稿上要画的每一行：(文字, x, y, 字号, 是否粗体)。
# 这些文字是虚构的示例单据，不含任何真实信息。
DOC_LINES = [
    ('华远科技有限公司  出库单', 70, 58, 34, True),
    ('单据编号：CK-2026-1112-0087', 70, 150, 24, False),
    ('客户名称：宁波海曙区远景贸易行', 70, 200, 24, False),
    ('商品名称：工业级图像采集模块', 70, 250, 24, False),
    ('规格型号：IVC-2400 / 8GB', 70, 300, 24, False),
    ('数量：24 台        单价：¥ 1,280.00', 70, 350, 24, False),
    ('金额合计：¥ 30,720.00', 70, 400, 24, False),
    ('备注：请在收货后 7 个工作日内完成验收', 70, 470, 21, False),
    ('联系电话：0574-8731 6620', 70, 520, 21, False),
    ('制单日期：2026 年 11 月 12 日', 70, 570, 21, False),
    ('SAMPLE DOCUMENT - NOT FOR OFFICIAL USE', 70, 670, 17, False),
]

BG = (250, 249, 245)   # 米白纸色
INK = (28, 32, 38)     # 深灰墨色（比纯黑更接近真实打印）


def load_font(size, kind='regular'):
    """按字号取字体；字体文件找不到时退化成 PIL 自带字体（会显示不了中文）。"""
    path = {'regular': FONT_REGULAR, 'bold': FONT_BOLD,
            'mono': FONT_MONO, 'hand': FONT_HAND}[kind]
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        print(f'!! 字体缺失：{path}，中文可能画成方块')
        return ImageFont.load_default()


def make_base_page():
    """画一张干净的「出库单」。返回 (图片, 标准答案文字列表)。"""
    img = Image.new('RGB', (PAGE_W, PAGE_H), BG)
    draw = ImageDraw.Draw(img)

    # 顶部一条装饰横线，让版面更像真实单据（OCR 不会把它当文字）
    draw.line([(70, 122), (PAGE_W - 70, 122)], fill=(190, 190, 185), width=2)

    lines = []
    for text, x, y, size, bold in DOC_LINES:
        font = load_font(size, 'bold' if bold else 'regular')
        draw.text((x, y), text, font=font, fill=INK)
        lines.append(text)          # 同时记下标准答案，供日后判断漏检 / 错字
    return img, lines


def make_dense_page():
    """密集小字 + 双栏：字号小、行距紧，是检测模型最容易漏的一类。"""
    img = Image.new('RGB', (PAGE_W, PAGE_H), BG)
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), '设备巡检记录表（局部）', font=load_font(26, 'bold'), fill=INK)

    left = [
        '01  机房温度  23.5 ℃   正常', '02  机房湿度  48 %    正常',
        '03  UPS 负载  32 %    正常', '04  电池电压  54.2 V  正常',
        '05  空调 A 组  运行中  正常', '06  空调 B 组  待机    正常',
        '07  消防主机  自检通过  正常', '08  门禁记录  无异常  正常',
        '09  摄像头 01  在线    正常', '10  摄像头 02  在线    正常',
        '11  摄像头 03  离线    异常', '12  交换机 A  丢包 0.1%',
        '13  交换机 B  丢包 0.0%', '14  存储阵列  容量 71%',
    ]
    right = [
        '15  服务器 A  CPU 18%  正常', '16  服务器 B  CPU 42%  正常',
        '17  服务器 C  CPU 67%  关注', '18  内存占用  61.3%  正常',
        '19  磁盘 IO  12 MB/s  正常', '20  网络延迟  3.2 ms  正常',
        '21  备份任务  已完成  正常', '22  日志容量  8.4 GB  正常',
        '23  告警条数  1 条    关注', '24  巡检人员  张工（代）',
        '25  复核人员  李工     ', '26  巡检时间  09:15     ',
        '27  备注：摄像头 03 待报修', '28  下次巡检  11 月 19 日',
    ]
    small = load_font(16)
    lines = []
    for col, items in enumerate((left, right)):
        x = 60 + col * 520
        draw.line([(x, 92), (x + 470, 92)], fill=(200, 200, 195), width=1)
        for i, text in enumerate(items):
            y = 105 + i * 42
            draw.text((x, y), text, font=small, fill=INK)
            lines.append(text)
    return img, lines


def make_terminal_page():
    """亮字暗底：复刻第1周 test1.jpg 的失败场景（终端截图）。"""
    img = Image.new('RGB', (PAGE_W, PAGE_H), (16, 22, 34))
    draw = ImageDraw.Draw(img)
    rows = [
        'PS D:\\work> python -m pip show paddleocr',
        'Name: paddleocr          Version: 3.7.0',
        'Location: D:\\miniforge3\\envs\\paddle\\Lib\\site-packages',
        '',
        'PS D:\\work> python b_ocr_image.py',
        'Loading PP-OCRv4_mobile_det ... done in 2.41s',
        'Detected 20 text lines, avg score 0.99',
        'Result saved to output/b_ocr_result.txt',
    ]
    mono = load_font(22, 'mono')
    lines = []
    for i, text in enumerate(rows):
        draw.text((60, 70 + i * 62), text, font=mono, fill=(214, 226, 240))
        if text.strip():
            lines.append(text)
    return img, [t for t in lines if t.strip()]


def make_handwriting_page():
    """手写风格：用行楷字体模拟，只用于观察效果，不要求救回来。"""
    img = Image.new('RGB', (PAGE_W, PAGE_H), (252, 250, 240))
    draw = ImageDraw.Draw(img)
    for y in range(150, PAGE_H - 40, 86):     # 笔记本横线
        draw.line([(60, y), (PAGE_W - 60, y)], fill=(205, 215, 225), width=1)
    rows = [
        '今日巡检记录',
        '三楼机房温度正常，空调运行平稳。',
        '摄像头 03 离线，已报修，等待更换。',
        '下次复查时间：十一月十九日。',
    ]
    hand = load_font(40, 'hand')
    for i, text in enumerate(rows):
        draw.text((80, 92 + i * 86), text, font=hand, fill=(38, 52, 92))
    return img, rows


# --------------------------------------------------------------------------
# 二、各种「退化」函数：输入一张干净图，输出一张有毛病的图
# --------------------------------------------------------------------------

def to_array(img):
    """PIL 图片 → numpy 数组，方便做逐像素的数值运算（如加减亮度）。"""
    return np.asarray(img).astype(np.float32)


def to_image(arr):
    """numpy 数组 → PIL 图片。clip 把超出 0~255 的值压回合法范围，防止溢出变花屏。"""
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def degrade_blur(img, radius=2.4):
    """高斯模糊：模拟对焦不准 / 手抖。radius 越大越糊（重度样本用 7.0）。"""
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def degrade_lowres(img):
    """低分辨率：先缩小到 1/5 再放大回来，细节永久丢失（不是简单模糊）。"""
    small = img.resize((PAGE_W // 5, PAGE_H // 5), Image.Resampling.BILINEAR)
    return small.resize((PAGE_W, PAGE_H), Image.Resampling.BILINEAR)


def degrade_skew(img, angle=8):
    """整体倾斜：模拟拍照时手机没端平。重度样本用 35°。"""
    return img.rotate(angle, resample=Image.Resampling.BICUBIC,
                      expand=False, fillcolor=BG)


def degrade_perspective(img):
    """透视变形：用 OpenCV 把矩形拉成梯形，模拟斜着拍一张纸。"""
    src = np.float32([[0, 0], [PAGE_W - 1, 0],
                      [PAGE_W - 1, PAGE_H - 1], [0, PAGE_H - 1]])
    dst = np.float32([[90, 55], [PAGE_W - 130, 10],
                      [PAGE_W - 40, PAGE_H - 70], [15, PAGE_H - 25]])
    matrix = cv2.getPerspectiveTransform(src, dst)
    arr = cv2.warpPerspective(np.asarray(img), matrix, (PAGE_W, PAGE_H),
                              borderValue=BG)
    return Image.fromarray(arr)


def degrade_glare(img, strength=185, sx=250, sy=150):
    """
    反光：在左中部叠一个椭圆形高光。
    强度 ≥ 400 时中心像素会被 clip 到纯白，那一块文字被彻底"洗掉"（重度样本）。
    """
    arr = to_array(img)
    # np.mgrid 生成每个像素的 (y, x) 坐标网格，后面是二维高斯公式
    yy, xx = np.mgrid[0:PAGE_H, 0:PAGE_W]
    glow = np.exp(-(((xx - 430) / sx) ** 2 + ((yy - 330) / sy) ** 2) / 2)
    arr = arr + glow[:, :, None] * strength     # [:, :, None] 把单通道扩成 3 通道
    return to_image(arr)


def degrade_shadow(img, keep=0.45):
    """光照不均：右侧逐渐变暗。keep 是最右侧保留的亮度比例，越小越黑。"""
    arr = to_array(img)
    xx = np.linspace(0, 1, PAGE_W)               # 0→1 的横向渐变
    shade = 1.0 - (1.0 - keep) * xx ** 2
    return to_image(arr * shade[None, :, None])


def degrade_low_contrast(img, factor=0.42):
    """低对比度：把整张图往白色拉。factor 越小，墨字越接近纸色。"""
    return to_image(255 - (255 - to_array(img)) * factor)


def degrade_noise(img):
    """传感器噪声：叠加固定种子的高斯噪声，模拟暗光拍摄或老旧扫描仪。"""
    rng = np.random.default_rng(SEED)
    arr = to_array(img) + rng.normal(0, 22, (PAGE_H, PAGE_W, 1))
    return to_image(arr)


def degrade_rot180(img):
    """整页倒置 180°：用来观察 use_textline_orientation 是否起作用。"""
    return img.rotate(180)


def degrade_mixed(img):
    """混合退化：模糊 + 倾斜 + 阴影，接近真实拍坏的文档。"""
    return degrade_shadow(degrade_skew(degrade_blur(img)))


# --------------------------------------------------------------------------
# 三、样本清单与生成主流程
# --------------------------------------------------------------------------

# 每项：(文件名, 分类, 退化说明, 底稿函数, 退化函数或 None)
# 分类名刻意与 README 模块 B 的 6 类目录保持一致，方便 Day 2 归档。
SYNTHETIC = [
    ('01_clear.png',            '对照组',       '无退化，清晰印刷体',       make_base_page,        None),
    ('02_blur.png',             '01_模糊低质',  '高斯模糊 radius=2.4',      make_base_page,        degrade_blur),
    ('03_lowres.jpg',           '01_模糊低质',  '缩小至 1/5 再放大',        make_base_page,        degrade_lowres),
    ('04_skew.png',             '02_倾斜透视',  '整体顺时针倾斜 8°',        make_base_page,        degrade_skew),
    ('05_perspective.png',      '02_倾斜透视',  '四点透视拉成梯形',         make_base_page,        degrade_perspective),
    ('06_glare.png',            '03_反光光照',  '左中部椭圆高光过曝',       make_base_page,        degrade_glare),
    ('07_shadow.png',           '03_反光光照',  '右侧渐暗至 45% 亮度',      make_base_page,        degrade_shadow),
    ('08_low_contrast.png',     '03_反光光照',  '整体对比度压到 42%',       make_base_page,        degrade_low_contrast),
    ('09_dense_small.png',      '04_密集小字',  '双栏 16px 小字，28 行',    make_dense_page,       None),
    ('10_inverted.png',         '06_漏检',      '亮字暗底（终端截图风格）', make_terminal_page,    None),
    ('11_low_contrast_noise.png', '01_模糊低质', '低对比 + 高斯噪声 σ=22',   make_base_page,
     lambda im: degrade_noise(degrade_low_contrast(im))),
    ('12_handwriting.png',      '05_识别错误',  '行楷手写体（只观察）',     make_handwriting_page, None),
    ('13_rotated_180.png',      '02_倾斜透视',  '整页倒置 180°',            make_base_page,        degrade_rot180),
    ('14_mixed.png',            '06_漏检',      '模糊 + 倾斜 + 阴影',       make_base_page,        degrade_mixed),
    # ---- 以下 4 张是「重度退化」：首轮实测轻度退化几乎打不垮 PP-OCRv4，
    #      这几张专门用来制造可见的失败，给 bad case 库提供真正的素材 ----
    ('15_heavy_blur.png',       '01_模糊低质',  '重度高斯模糊 radius=7.0',  make_base_page,
     lambda im: degrade_blur(im, radius=7.0)),
    ('16_glare_wipe.png',       '03_反光光照',  '强反光过曝，中部整片洗白', make_base_page,
     lambda im: degrade_glare(im, strength=520, sx=330, sy=95)),
    ('17_dark_shadow.png',      '03_反光光照',  '右侧亮度降到 10%',         make_base_page,
     lambda im: degrade_shadow(im, keep=0.10)),
    ('18_faint.png',            '06_漏检',      '对比度压到 13%',           make_base_page,
     lambda im: degrade_low_contrast(im, factor=0.13)),
]

# 真实 case：**编号从 101 起，格式 101_real_xxx**（用户 11-13 定稿）。
# 数字前缀方便查找排序，real_ 一眼看出是自己的素材；分组 / 排序 / 编号规则
# 统一由 case_naming.py 决定，这里只负责「铺哪些文件」。
# 去重说明：旧版 19_real_terminal / 20_real_doc 与 week-01 的 test1/test2 是
#   字节级完全相同的副本，已删掉，只留下面这份正本。
#   real_scan_page1/2 是 PDF 渲染页缩放出来的 JPEG，和 PDF 原件内容不同，
#   作为独立的「真实扫描页」bad case 保留。
# 每项：(目标名, 分类, 说明, 来源类型, 源文件名, source 说明)
#   kind='copy' → 从 WEEK01_INPUT 直接复制；kind='scan' → 从 WEEK01_PAGES 渲染页图缩放
REAL_CASES = [
    ('101_real_terminal_screenshot.jpg',       '06_漏检',
     '真实终端截图（亮字暗底、命令行小字）',      'copy', 'test1.jpg',
     'week-01/input/test1.jpg'),
    ('102_real_clear_doc.jpg',                 '对照组',
     '真实清晰文档（20 行、平均置信度 0.99）',    'copy', 'test2.jpg',
     'week-01/input/test2.jpg'),
    ('103_real_bank_statement_textlayer.pdf',  '文本层表格',
     '有文本层的银行流水 PDF（含 8 列表格）',      'copy', 'test3.pdf',
     'week-01/input/test3.pdf'),
    ('104_real_certificates_scan.pdf',         '扫描件',
     '5 页证书 / 备案表扫描件 PDF',                'copy', 'test3_image.pdf',
     'week-01/input/test3_image.pdf'),
    ('105_real_transactions_gbk.csv',          '纯文本表格',
     'GBK 编码的 CSV 交易流水',                    'copy', 'test4.csv',
     'week-01/input/test4.csv'),
    ('106_real_scan_page1.jpg',                '01_模糊低质',
     '真实扫描件第 1 页（渲染图缩放，带噪点与印章）', 'scan', 'c_page_1.png',
     'week-01/output/c_pdf_text_layer/test3_image/pages/c_page_1.png'),
    ('107_real_scan_page2.jpg',                '04_密集小字',
     '真实扫描件第 2 页（备案名单表格）',          'scan', 'c_page_2.png',
     'week-01/output/c_pdf_text_layer/test3_image/pages/c_page_2.png'),
]
# 第1周 11-13 把页图改成 1 起编号并挪进两层隔离目录，旧的 c_page_0.png 已不存在。


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = {
        'generated_by': 'make_samples.py',
        'design': ('01~18 为合成退化样本；101~ 起编号的 1xx_real_* 为用户真实 case'
                   '（规则见 case_naming.py，新增 case 重跑 a_batch_ocr.py 即生效）。'
                   'expect_lines 是标准答案'),
        'groups': {'synthetic': '01~18 合成样本（编号 < 101）',
                   'real': '101~ 起的真实 case（101_real_*，恒排最后）'},
        'real_start_no': naming.REAL_START_NO,
        'seed': SEED,
        'samples': [],
    }

    for filename, category, distortion, base_fn, degrade_fn in SYNTHETIC:
        base, ground_truth = base_fn()
        img = degrade_fn(base) if degrade_fn else base
        path = os.path.join(OUT_DIR, filename)

        # 低分辨率样本存成 JPEG 并压质量，才真的会丢细节
        if filename.lower().endswith('.jpg'):
            img.save(path, quality=35)
        else:
            img.save(path)

        manifest['samples'].append({
            'file': filename,
            'category': category,
            'distortion': distortion,
            'source': 'synthetic',
            'group': 'synthetic',
            'expect_lines': ground_truth,
        })
        print(f'>> 已生成 {filename:28s} {category} / {distortion}')

    for dst_name, category, note, kind, src_name, source in REAL_CASES:
        src_dir = WEEK01_INPUT if kind == 'copy' else WEEK01_PAGES
        src = os.path.join(src_dir, src_name)
        dst = os.path.join(OUT_DIR, dst_name)
        if not os.path.isfile(src):
            print(f'!! 跳过真实 case（源文件不存在）：{src}')
            continue
        if kind == 'copy':
            shutil.copy2(src, dst)            # copy2 连修改时间一起复制
        else:
            # 扫描页来自 200 DPI 渲染图，等比缩小减少体积与推理耗时
            page = Image.open(src).convert('RGB')
            if page.width > 1200:
                new_h = int(page.height * 1200 / page.width)
                page = page.resize((1200, new_h), Image.Resampling.LANCZOS)
            page.save(dst, quality=88)
        manifest['samples'].append({
            'file': dst_name,
            'category': category,
            'distortion': note,
            'source': source,
            'group': 'real',
            'expect_lines': None,             # 真实素材没有逐行标准答案
        })
        print(f'>> 已{"复制" if kind == "copy" else "生成"} {dst_name:34s} {category} / 真实 case')

    # ---- 用户自己新增的 case：不在上面两张清单里，也补一条说明书记录 ----
    # 这样以后重跑 make_samples.py，不会把新增 case 的分类 / 说明抹掉。
    # a_batch_ocr.py 本来就不依赖 manifest（分组统一由 case_naming.py 推断），
    # 这里补登记只是让对比报告里的「分类 / 退化说明」更完整。
    known = {item['file'] for item in manifest['samples']}
    extra_count = 0
    for name in sorted(os.listdir(OUT_DIR), key=naming.case_sort_key):
        if (name in known or name == os.path.basename(MANIFEST)
                or name.startswith('.')
                or not name.lower().endswith(SUPPORTED_EXTS)):
            continue
        manifest['samples'].append({
            'file': name,
            'category': '自定义',
            'distortion': '用户新增 case（未登记退化说明，可手工补写）',
            'source': 'user',
            'group': naming.case_group(name),
            'expect_lines': None,
        })
        extra_count += 1
    if extra_count:
        print(f'>> 另有 {extra_count} 个用户新增 case 已补登记进说明书')
        print(f'>> 下一个建议编号：{naming.next_real_no(os.listdir(OUT_DIR))}')

    manifest['sample_count'] = len(manifest['samples'])
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f'\n>> 共 {manifest["sample_count"]} 个 case 已放入 {os.path.abspath(OUT_DIR)}')
    print(f'>> 样本说明书：{os.path.abspath(MANIFEST)}')
    print('>> 下一步：python a_batch_ocr.py   （跑完会自动生成可视化对照报告）')


# 主程序守卫：直接运行才执行；被别的文件 import 时不会自动跑。
if __name__ == '__main__':
    main()

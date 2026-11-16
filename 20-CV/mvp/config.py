"""
mvp/config.py — 唯一配置源。

所有模块都从这里取常量，不在别处写死模型名 / 路径 / 阈值。
环境变量必须在任何 paddleocr / paddlex 被 import 之前设置，
所以本模块由 app.py 顶层第一个导入。
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(ROOT, 'input')
OUTPUT_DIR = os.path.join(ROOT, 'output')
ASSETS_DIR = os.path.join(ROOT, 'report', 'assets')

os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

# ---- 服务 ----
HOST, PORT = '127.0.0.1', 8765
MAX_FILE_MB = 20

# ---- 模型与识别 ----
DET_MODEL = 'PP-OCRv4_mobile_det'
REC_MODEL = 'PP-OCRv4_mobile_rec'
PDF_DPI = 110
LOW_SCORE = 0.8
MIN_TEXT_LAYER_CHARS = 50

# ---- 输入类型 ----
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff')
PDF_EXTS = ('.pdf',)
TEXT_EXTS = ('.csv', '.txt', '.md')
ALLOWED_EXTS = IMAGE_EXTS + PDF_EXTS + TEXT_EXTS
TEXT_ENCODINGS = ('utf-8-sig', 'gbk', 'latin-1')

# ---- 表格网格预筛 ----
GRID_MIN_H = 5
GRID_MIN_V = 4
GRID_RESIZE_MAX = 1000
GRID_LINE_MIN_LEN = 80

# ---- 人工列边界模板（固定版式专用）----
# 键是「去掉数字编号后的语义文件名」，所以 103 → 108 换编号仍命中。
# 只有「有横线但没竖线」的流水表才需要；自动 words 聚类会把页眉混进表头。
# 没有登记的文件一律走 auto_column_lines() 自动推断，不写死任何 case 名。
TABLE_COLUMN_LINES = {
    'real_bank_statement_textlayer.pdf':
        [17, 112, 175, 265, 326, 393, 463, 532, 578],
}

# ---- 产物文件名 ----
RECTIFIED_NAME = 'rectified.png'
BOXES_NAME = 'boxes.png'
RESULT_JSON = 'result.json'
REPORT_NAME = 'index.html'

for _d in (INPUT_DIR, OUTPUT_DIR):
    os.makedirs(_d, exist_ok=True)

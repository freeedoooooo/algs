"""
mvp/config.py — 唯一配置源。

所有模块都从这里取常量，不在别处写死模型名 / 路径 / 阈值。
环境变量必须在任何 paddleocr / paddlex 被 import 之前设置，
所以本模块由 app.py 顶层第一个导入。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# 兜底：即使有旧脚本用顶层 `import config` 也能找到（新代码统一走包相对导入）
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
INPUT_DIR = os.path.join(ROOT, 'input')
OUTPUT_DIR = os.path.join(ROOT, 'output')
ASSETS_DIR = os.path.join(ROOT, 'report', 'assets')

# 官方模型首次推理时下载到 ${PADDLE_PDX_CACHE_HOME:-~/.paddlex}/official_models。
# 离线部署：先在联网机器跑一次把模型下全，再把该目录随代码一起拷到目标机，
# 并设 PADDLE_PDX_CACHE_HOME 指向它 —— 这里用 setdefault，不覆盖外部已有设置。
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

# ---- 服务（全部可用环境变量覆盖，方便容器 / 服务器部署）----
#   CV_MVP_HOST=0.0.0.0 CV_MVP_PORT=9000 CV_MVP_WARMUP=1 python app.py
HOST = os.getenv('CV_MVP_HOST', '127.0.0.1')
PORT = int(os.getenv('CV_MVP_PORT', '8765'))
MAX_FILE_MB = int(os.getenv('CV_MVP_MAX_FILE_MB', '20'))
WARMUP_ON_START = os.getenv('CV_MVP_WARMUP', '0') == '1'

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

# ---- 人工列边界兜底模板（固定版式专用；页面参数 column_lines 优先）----
# 键 = 「剥掉上传批次时间戳后的原文件名」，源文件自带的数字编号保留。
# 也兼容去掉编号后的语义名（week-02 的旧写法，换成 108 仍命中）。
# 只有「有横线但没竖线」的流水表才需要；自动 words 聚类会把页眉混进表头。
# ★ 现在这个固定值已作为调试参数放上页面：用户填 column_lines 会覆盖这里，
#   本字典只在页面留空时兜底。没有登记的文件走 auto_column_lines() 自动推断。
_BANK_LINES = [17, 112, 175, 265, 326, 393, 463, 532, 578]
TABLE_COLUMN_LINES = {
    '103_real_bank_statement_textlayer.pdf': _BANK_LINES,
    # 兼容 week-02 的「去掉编号后语义名」写法：换成 108 也照样命中
    'real_bank_statement_textlayer.pdf': _BANK_LINES,
}

# ---- 命名：一次上传 = 一个批次戳，input/ 与 output/ 共用同一前缀 ----
# 例：20261116160231_103_real_bank_statement_textlayer.pdf
#                          ↓ 去后缀（源文件自带的 103_ 编号完整保留）
#     output/20261116160231_103_real_bank_statement_textlayer/
# 精确到秒；同一秒内重复上传再加 -2 / -3 区分。
BATCH_TS_FMT = '%Y%m%d%H%M%S'
CASE_NAME_MAX = 80

# ---- 产物文件名 ----
RECTIFIED_NAME = 'rectified.png'
BOXES_NAME = 'boxes.png'
RESULT_JSON = 'result.json'
REPORT_NAME = 'index.html'

for _d in (INPUT_DIR, OUTPUT_DIR):
    os.makedirs(_d, exist_ok=True)

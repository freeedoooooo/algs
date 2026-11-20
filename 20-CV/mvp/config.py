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
LOG_DIR = os.path.join(ROOT, 'logs')
ASSETS_DIR = os.path.join(ROOT, 'extract_report', 'assets')
TEMPLATES_DIR = os.path.join(ROOT, 'extract_report', 'templates')

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

# 列边界不再写死任何 case：自动从 PDF 横线端点推断（pipeline/pdf.py::_lines_from_edges），
# 实测与原先 103 的人工模板逐字一致。特殊版式在上传页用 column_lines 参数临时覆盖即可。

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
# 对照报告：每批次一份独立自包含 HTML，直接放在该批次的 output/<批次戳_文件名>/
# 目录里，与 result.json / 图片 / CSV 同级；模板（assets）只有一份，生成时内联。
EXTRACT_REPORT_NAME = '对照报告.html'

for _d in (INPUT_DIR, OUTPUT_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)

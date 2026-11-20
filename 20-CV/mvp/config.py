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
# 数据根：默认 = mvp/ 根；服务器部署整体拷贝后设 CV_MVP_DATA_ROOT 即可，代码零改动。
# DB 与 JSON 只存相对路径（正斜杠），to_abs/to_rel 是唯一换算点。
DATA_ROOT = os.path.abspath(os.getenv('CV_MVP_DATA_ROOT', ROOT))
INPUT_DIR = os.path.join(DATA_ROOT, 'input')
OUTPUT_DIR = os.path.join(DATA_ROOT, 'output')
LOG_DIR = os.path.join(DATA_ROOT, 'logs')
SOURCES_DIR = os.path.join(DATA_ROOT, 'sources')
DATA_DIR = os.path.join(DATA_ROOT, 'data')
ASSETS_DIR = os.path.join(ROOT, 'extract_report', 'assets')
TEMPLATES_DIR = os.path.join(ROOT, 'extract_report', 'templates')


def to_abs(rel):
    """相对路径（正斜杠）→ 本机绝对路径。"""
    return os.path.normpath(os.path.join(DATA_ROOT, rel.replace('/', os.sep)))


def to_rel(path):
    """本机绝对路径 → 相对 DATA_ROOT 的正斜杠路径（落盘 / 入库统一形态）。"""
    return os.path.relpath(path, DATA_ROOT).replace(os.sep, '/')

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

# ---- 产物文件名（数据分层：raw/ 引擎原样 → extract.json 自有标准 → records.json 记录事实源）----
RECTIFIED_NAME = 'rectified.png'
BOXES_NAME = 'boxes.png'
RAW_DIR = 'raw'
EXTRACT_JSON = 'extract.json'
RECORDS_JSON = 'records.json'
RUN_JSON = 'run.json'
# 对照报告：每批次一份独立自包含 HTML，直接放在该批次的 output/<批次戳_文件名>/
# 目录里，与 extract.json / 图片 / CSV 同级；模板（assets）只有一份，生成时内联。
EXTRACT_REPORT_NAME = '对照报告.html'

# ---- 平台目录库凭据引用名（解析顺序 env → data/secrets.json，见 store/db.py）----
PLATFORM_DB_REF = 'CV_PLATFORM_DB'

# 存储契约（design-artifacts-db.md）：DB 是唯一事实源——目录/记录/血缘在关系表，
# 产物字节在 extract_artifact BLOB；磁盘仅运行期 scratch（跑完即清）。
# file 模式已删除（初期调试过渡态，2026-11-20 用户裁决）；审计/file:// 用
# export_artifacts.py 按需导出。DB 不可用＝服务显式失败（503），不降级。

for _d in (INPUT_DIR, OUTPUT_DIR, LOG_DIR, SOURCES_DIR, DATA_DIR):
    os.makedirs(_d, exist_ok=True)

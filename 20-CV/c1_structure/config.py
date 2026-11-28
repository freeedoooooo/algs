"""
c1_structure/config.py — 唯一配置源。

所有模块都从这里取常量，不在别处写死模型名 / 路径 / 阈值。
环境变量必须在任何 paddleocr / paddlex 被 import 之前设置，
所以本模块由 app.py 顶层第一个导入。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# 本地 secrets.json 兜底（已被 .gitignore 覆盖）：仅当环境变量未设置时注入，
# 便于开发期免去每次导出模型凭据；生产/容器仍以真实环境变量为准。
# 路径取 <DATA_ROOT>/data/secrets.json，环境变量 C1_STRUCTURE_DATA_ROOT 可改根。
# 纯标准库解析，零新依赖；密钥不进代码库、不进日志。
import json as _json
_DATA_ROOT_EARLY = os.path.abspath(
    os.getenv('C1_STRUCTURE_DATA_ROOT', ROOT))
_SECRET_FILE = os.path.join(_DATA_ROOT_EARLY, 'data', 'secrets.json')
if os.path.isfile(_SECRET_FILE):
    try:
        with open(_SECRET_FILE, encoding='utf-8') as _f:
            _secrets = _json.load(_f)
        if isinstance(_secrets, dict):
            for _k, _v in _secrets.items():
                if isinstance(_v, (str, int, float)) and str(_k) not in os.environ:
                    os.environ[str(_k)] = str(_v)
    except (ValueError, OSError):
        pass  # 配置损坏不阻断启动；缺凭据时各调用点显式报错
# 兜底：即使有旧脚本用顶层 `import config` 也能找到（新代码统一走包相对导入）
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# 数据根：默认 = 包根；服务器部署整体拷贝后设 C1_STRUCTURE_DATA_ROOT 即可。
# 只承载运维态目录（logs/ 运行日志、data/ 备份）与 tmp/ 运行期 scratch；
# 业务数据全在 DB，无持久 input/output/sources。
DATA_ROOT = os.path.abspath(os.getenv('C1_STRUCTURE_DATA_ROOT', ROOT))
LOG_DIR = os.path.join(DATA_ROOT, 'logs')
DATA_DIR = os.path.join(DATA_ROOT, 'data')
# scratch 收敛在包内 tmp/（跑完即清）：input=上传副本，work=提取工作区
TMP_DIR = os.path.join(DATA_ROOT, 'tmp')
TMP_INPUT = os.path.join(TMP_DIR, 'input')
TMP_WORK = os.path.join(TMP_DIR, 'work')
WEB_DIR = os.path.join(ROOT, 'web')
TEMPLATES_DIR = os.path.join(ROOT, 'parse_report', 'templates')

# 官方模型首次推理时下载到 ${PADDLE_PDX_CACHE_HOME:-~/.paddlex}/official_models。
# 离线部署：先在联网机器跑一次把模型下全，再把该目录随代码一起拷到目标机，
# 并设 PADDLE_PDX_CACHE_HOME 指向它 —— 这里用 setdefault，不覆盖外部已有设置。
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

# ---- 服务（全部可用环境变量覆盖，方便容器 / 服务器部署）----
#   C1_STRUCTURE_HOST=0.0.0.0 C1_STRUCTURE_PORT=9000 C1_STRUCTURE_WARMUP=1 python app.py
HOST = os.getenv('C1_STRUCTURE_HOST', '0.0.0.0')
PORT = int(os.getenv('C1_STRUCTURE_PORT', '8765'))
MAX_FILE_MB = int(os.getenv('C1_STRUCTURE_MAX_FILE_MB', '20'))
WARMUP_ON_START = os.getenv('C1_STRUCTURE_WARMUP', '0') == '1'

# ---- 模型与识别 ----
DET_MODEL = 'PP-OCRv4_mobile_det'
REC_MODEL = 'PP-OCRv4_mobile_rec'
PDF_DPI = 110
LOW_SCORE = 0.8
MIN_TEXT_LAYER_CHARS = 50

# ---- 智能抽取与规则生成回退（OpenAI 兼容端点；凭据只从环境变量读取，不进代码/DB/日志）----
# 例：C1_LLM_BASE_URL=https://api.example.com/v1 C1_LLM_API_KEY=... C1_LLM_MODEL=gpt-4o-mini
LLM_BASE_URL = os.getenv('C1_LLM_BASE_URL', '').rstrip('/')
LLM_API_KEY = os.getenv('C1_LLM_API_KEY', '')
LLM_MODEL = os.getenv('C1_LLM_MODEL', '')
LLM_TIMEOUT = float(os.getenv('C1_LLM_TIMEOUT', '60'))
LLM_TEMPERATURE = float(os.getenv('C1_LLM_TEMPERATURE', '0'))

# ---- AI 规则生成（QoderCN SDK 优先，OpenAI 兼容端点回退）----
# PAT 只从官方环境变量读取；data/secrets.json 存在时会先注入进程环境。
# 未配置 PAT 时，规则生成复用完整的 C1_LLM_BASE_URL / C1_LLM_API_KEY / C1_LLM_MODEL。
QODERCN_PERSONAL_ACCESS_TOKEN = os.getenv('QODERCN_PERSONAL_ACCESS_TOKEN', '')
QODER_PERSONAL_ACCESS_TOKEN = (
    QODERCN_PERSONAL_ACCESS_TOKEN
    or os.getenv('QODER_PERSONAL_ACCESS_TOKEN', ''))
QODER_REGION = os.getenv(
    'C1_QODER_REGION', 'cn' if QODERCN_PERSONAL_ACCESS_TOKEN else 'global'
).strip().lower()
if QODER_REGION not in ('cn', 'global'):
    raise ValueError('C1_QODER_REGION 非法值「{}」：只接受 cn / global'.format(
        QODER_REGION))
# 留空使用 Qoder 账户默认模型；如需固定模型，填对应区域的 Qoder 模型 ID。
QODER_MODEL = os.getenv('C1_QODER_MODEL', '').strip()
QODER_CLI_PATH = os.getenv('C1_QODER_CLI_PATH', '').strip()
QODER_TIMEOUT = float(os.getenv('C1_QODER_TIMEOUT', '120'))
# Windows 下 qodercli 会在系统 Temp 解压原生模块并读取 SDK 认证文件；
# 部分长路径/受限目录会报 EPERM 或“认证文件不存在”，可指定短路径规避。
QODER_TMP_DIR = os.getenv('C1_QODER_TMP_DIR', '').strip()
if QODER_TMP_DIR:
    QODER_TMP_DIR = os.path.abspath(os.path.expanduser(QODER_TMP_DIR))
    os.makedirs(QODER_TMP_DIR, exist_ok=True)
    os.environ['TEMP'] = QODER_TMP_DIR
    os.environ['TMP'] = QODER_TMP_DIR
    import tempfile as _tempfile
    _tempfile.tempdir = QODER_TMP_DIR
# 智能抽取/规则生成模式开关（语义值）：
#   stub = 联调占位，不访问模型、不烧 token（默认）
#   live = 真实模型调用（规则生成优先 QoderCN SDK、缺 PAT 时复用 C1_LLM_*；smart_extract 走 C1_LLM_*）
# 兼容旧值：1/true/on → stub，0/false/off → live；其它值显式报错，不静默走错模式。
_MODE_RAW = os.getenv('C1_SMART_STUB', 'stub').strip().lower()
if _MODE_RAW in ('stub', '1', 'true', 'on'):
    SMART_STUB = True
elif _MODE_RAW in ('live', '0', 'false', 'off'):
    SMART_STUB = False
else:
    raise ValueError(
        'C1_SMART_STUB 非法值「{}」：只接受 stub / live（兼容 1/0）。'.format(
            _MODE_RAW))

# ---- 输入类型 ----
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff')
PDF_EXTS = ('.pdf',)
TEXT_EXTS = ('.csv', '.txt', '.md')
ALLOWED_EXTS = IMAGE_EXTS + PDF_EXTS + TEXT_EXTS
TEXT_ENCODINGS = ('utf-8-sig', 'gbk', 'latin-1')

# 列边界不再写死任何 case：自动从 PDF 横线端点推断（pipeline/pdf.py::_lines_from_edges），
# 实测与原先 103 的人工抽取规则逐字一致。特殊版式在上传页用 column_lines 参数临时覆盖即可。

# ---- 产物文件名（数据分层：raw/ 引擎原样 → parse.json 自有标准 → records DB 三表）----
RECTIFIED_NAME = 'rectified.png'
BOXES_NAME = 'boxes.png'
RAW_DIR = 'raw'
PARSE_JSON = 'parse.json'
RECORDS_JSON = 'records.json'
# 对照报告：每 task_file 一份独立自包含 HTML，与 parse.json / 图片 / CSV 同入
# c1_parse_artifact BLOB；页面与报告共用资产在 web/，生成时内联。
PARSE_REPORT_NAME = '对照报告.html'

# ---- 平台库 DSN（配置直接入库管理；环境变量 C1_STRUCTURE_DB 优先，方便部署覆盖）----
PLATFORM_DB = os.getenv('C1_STRUCTURE_DB', 'mysql://root:Dib12345*@10.0.6.161:3306/c1_structure_dev')

# 存储契约：DB 是唯一事实源——目录/记录/血缘在关系表，
# 原件字节在 c1_doc_file.content，产物字节在 c1_parse_artifact BLOB（task_file 粒度）；
# 磁盘仅 tmp/ 运行期 scratch。审计/file:// 用 export_artifacts.py 按需导出。
# DB 不可用＝服务显式失败（503），不降级。

for _d in (LOG_DIR, DATA_DIR, TMP_INPUT, TMP_WORK):
    os.makedirs(_d, exist_ok=True)
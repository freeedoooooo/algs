"""
mvp/app.py — Web 工具入口（FastAPI + uvicorn）。只负责路由与任务编排。

启动：
    D:\\miniforge3\\envs\\paddle\\python.exe mvp/app.py
    浏览器打开 http://127.0.0.1:8765

路由：
    GET  /              上传页（assets/upload.html + /static 资源）
    GET  /healthz       健康检查
    POST /api/upload    上传（base64 JSON，不依赖 python-multipart）
    GET  /api/status    处理进度
    GET  /extract-report   对照报告（重定向到最新 case 的报告真实地址）
    /files/<path>       各 case 的产物
    /static/<path>      上传页的 css / js

提取逻辑在 pipeline/，对照报告生成在 extract_report/，配置在 config.py。
"""
import os
import re
import sys
import time
import base64
import importlib
import threading
import traceback
from contextlib import asynccontextmanager

# ★ 零 IDE 配置的关键：mvp 内部模块一律以「包」方式加载。
# 静态分析器能直接解析包内相对导入（from .. import config），不需要标记
# Sources Root / extraPaths；同时下面四种启动方式都成立：
#   python app.py · python mvp/app.py · uvicorn app:app · uvicorn mvp.app:app
# 包名从目录名动态取，整个目录拷走改名也照样能跑。
ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name):
    """以 <包名>.<name> 加载 mvp 内部模块，保证包内相对导入始终有效。"""
    return importlib.import_module(PKG + '.' + name)


config = _load('config')           # 必须在 paddle 相关导入之前：设置模型源环境变量
params_mod = _load('params')       # 调试参数 schema / 校验（纯 Python，不碰模型）
from fastapi import FastAPI, Request
from fastapi.responses import (HTMLResponse, JSONResponse, FileResponse,
                               RedirectResponse)
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(_app):
    """
    默认什么都不做 —— 模型保持懒加载，服务启动约 0.5s。
    部署时若想「启动即加载」，设 CV_MVP_WARMUP=1，避免第一个请求等 20~40s；
    代价是启动变慢、内存常驻。两种启动方式（app.py / uvicorn app:app）都生效。
    """
    if config.WARMUP_ON_START:
        engines = _load('pipeline.engines')
        engines.ocr()
        engines.structure()
        print('>> 模型预热完成（PaddleOCR + PPStructureV3）')
    yield


app = FastAPI(title='CV 提取 MVP', version='0.1', lifespan=lifespan)
app.mount('/files', StaticFiles(directory=config.OUTPUT_DIR), name='files')
app.mount('/static', StaticFiles(directory=config.ASSETS_DIR), name='static')


@app.middleware('http')
async def no_cache(request, call_next):
    """本地调试工具：禁止浏览器启发式缓存。StaticFiles/FileResponse 带 ETag/
    Last-Modified，no-cache 让每次使用前先校验（未变 304、变了 200），
    避免「改了 css/js 或重启服务后页面仍是旧样式」——缓存发生在浏览器侧，重启服务无效。"""
    resp = await call_next(request)
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

# 单任务串行：模型单例不是线程安全的，也没必要并发加载第二份大模型
STATE = {
    'running': False, 'ready': False, 'error': None,
    'steps': [], 'cases': [], 'batch': None,
    'started': None, 'elapsed': 0,
    'params': {}, 'warnings': [],
    'logs': [], 'progress': 0, 'stage': '',
    'log_file': None,
}
LOCK = threading.Lock()


def step(msg, level='info', stage='batch'):
    """兼容旧调用：纯文本 steps 仍保留，同时生成一条结构化日志。"""
    with LOCK:
        STATE['steps'].append(msg)
        STATE['logs'].append({
            't': round(time.time() - (STATE['started'] or time.time()), 2),
            'ms': 0, 'level': level, 'stage': stage, 'msg': msg,
        })


def _on_log(row):
    """RunLog 每条日志同步进 STATE，页面轮询 /api/status 即可看到。"""
    with LOCK:
        STATE['logs'].append(row)
        STATE['stage'] = row['stage']


def safe_name(name):
    """只替换 Windows 文件名非法字符，保留中文与空格。"""
    name = os.path.basename(name or 'upload.bin')
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip()
    return name[:120] or 'upload.bin'


def batch_tag():
    """
    本次上传的批次前缀：YYYYMMDDHHmmss（例 20261116160231）。

    input/ 与 output/ 共用它，所以重复传同一个文件也不会覆盖上一次的产物，
    目录按字典序排就是按时间排。同一秒内再传一次加 -2 / -3 区分。
    注意：只加前缀，原文件名（含 103_ 这类数字编号）一字不改。
    """
    existing = (set(os.listdir(config.INPUT_DIR))
                | set(os.listdir(config.OUTPUT_DIR)))
    tag = time.strftime(config.BATCH_TS_FMT, time.localtime())
    if not any(n.startswith(tag) for n in existing):
        return tag
    i = 2
    while any(n.startswith('{}-{}'.format(tag, i)) for n in existing):
        i += 1
    return '{}-{}'.format(tag, i)


def case_dir_name(name):
    """输出目录名 = 带时间戳的输入文件名去掉后缀，与 input/ 一一对应。"""
    stem = os.path.splitext(name)[0]
    stem = re.sub(r'[^\w\u4e00-\u9fff.-]', '_', stem)
    return stem[:config.CASE_NAME_MAX] or 'case'


def asset(name):
    with open(os.path.join(config.ASSETS_DIR, name), 'r',
              encoding='utf-8') as f:
        return f.read()


@app.get('/', response_class=HTMLResponse)
def index():
    return HTMLResponse(asset('upload.html'))


@app.get('/healthz')
def health():
    return {'ok': True, 'service': 'cv-mvp', 'running': STATE['running']}


@app.get('/api/params')
def api_params():
    """返回参数 schema（顺序=优先级）与当前默认值，上传页据此渲染面板。"""
    return {'schema': params_mod.public_schema(),
            'defaults': params_mod.defaults()}


@app.post('/api/upload')
async def upload(request: Request):
    if STATE['running']:
        return JSONResponse(
            {'ok': False, 'error': '已有任务正在处理，请等它完成'},
            status_code=409)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({'ok': False, 'error': '请求体不是合法 JSON'},
                            status_code=400)
    files = body.get('files') or []
    if not files:
        return JSONResponse({'ok': False, 'error': '没有收到文件'},
                            status_code=400)
    # 调试参数：校验一次，非法值回退默认并把警告带回页面（不让整批失败）
    params, warns = params_mod.normalize(body.get('params'))

    tag = batch_tag()
    paths, used = [], set()
    for item in files:
        name = safe_name(item.get('name', ''))
        ext = os.path.splitext(name)[1].lower()
        if ext not in config.ALLOWED_EXTS:
            return JSONResponse(
                {'ok': False, 'error': '不支持的格式：{}'.format(ext)},
                status_code=400)
        # 同一批里出现重名文件时加 -2 区分，避免后一个把前一个覆盖掉
        if name in used:
            stem, e = os.path.splitext(name)
            k = 2
            while '{}-{}{}'.format(stem, k, e) in used:
                k += 1
            name = '{}-{}{}'.format(stem, k, e)
        used.add(name)
        try:
            data = base64.b64decode(str(item.get('data', '')).split(',')[-1])
        except Exception:
            return JSONResponse(
                {'ok': False, 'error': '{} 的 base64 数据无效'.format(name)},
                status_code=400)
        if len(data) > config.MAX_FILE_MB * 1024 * 1024:
            return JSONResponse(
                {'ok': False,
                 'error': '{} 超过 {}MB'.format(name, config.MAX_FILE_MB)},
                status_code=400)
        path = os.path.join(config.INPUT_DIR, '{}_{}'.format(tag, name))
        with open(path, 'wb') as f:
            f.write(data)
        paths.append(path)

    return _launch(tag, paths, params, warns)


def _launch(tag, paths, params, warns):
    """建日志 → 重置 STATE → 起后台线程。"""
    runlog = _load('runlog')
    log = runlog.RunLog(tag, log_path=os.path.join(config.LOG_DIR,
                                                   tag + '.log'),
                        on_emit=_on_log)
    with LOCK:
        STATE.update(running=True, ready=False, error=None, steps=[],
                     cases=[], batch=tag, started=time.time(), elapsed=0,
                     params={k: v for k, v in params.items()
                             if not k.startswith('_')}, warnings=warns,
                     logs=[], progress=0, stage='batch',
                     log_file='{}.log'.format(tag))
    log.stage('batch', '批次 {} · 收到 {} 个文件'.format(tag, len(paths)))
    log.info('params', '生效参数：{}'.format(
        ', '.join('{}={}'.format(k, v) for k, v in params.items()
                  if not k.startswith('_'))))
    for w in warns:
        log.warn('params', w)
    threading.Thread(target=run_batch, args=(paths, params, log),
                     daemon=True).start()
    return {'ok': True, 'count': len(paths), 'batch': tag,
            'warnings': warns}


@app.get('/api/status')
def status():
    with LOCK:
        return dict(STATE)


@app.get('/api/logs')
def api_logs():
    """下载当前批次的纯文本运行日志（结构化日志在 /api/status 的 logs 里）。"""
    rel = STATE.get('log_file')
    path = os.path.join(config.LOG_DIR, rel) if rel else None
    if not path or not os.path.isfile(path):
        return JSONResponse({'ok': False, 'error': '暂无日志'}, status_code=404)
    return FileResponse(path, media_type='text/plain; charset=utf-8',
                        filename='{}.log'.format(STATE.get('batch') or 'run'))


@app.get('/extract-report')
def extract_report():
    """对照报告：重定向到最新 case 的 对照报告.html 真实地址（/files/<case>/…）。
    报告内资源全是相对路径，必须落在 case 目录的 URL 下才能解析；
    历史批次直接打开各自 output 目录里的报告文件（file:// 同样可用）。"""
    from urllib.parse import quote
    for name in sorted(os.listdir(config.OUTPUT_DIR), reverse=True):
        path = os.path.join(config.OUTPUT_DIR, name,
                            config.EXTRACT_REPORT_NAME)
        if os.path.isfile(path):
            return RedirectResponse('/files/{}/{}'.format(
                quote(name, safe=''),
                quote(config.EXTRACT_REPORT_NAME, safe='')))
    return HTMLResponse(
        '<h3>还没有对照报告</h3><p><a href="/">返回上传页</a>先上传一个文件。</p>')


# 阶段 → 单文件内的进度占比（只增不减）。长耗时的模型加载/推理与 OCR
# 各占一段可见区间，进度条不再整个文件期间停在 0%。
_STAGE_FRAC = {
    ('split', 'info'): 0.05,
    ('render', 'info'): 0.15,
    ('model', 'info'): 0.30,
    ('model', 'ok'): 0.60,
    ('model', 'warn'): 0.60,
    ('table', 'info'): 0.45,
    ('ocr', 'info'): 0.70,
    ('ocr', 'ok'): 0.90,
    ('table', 'ok'): 0.95,
}


def run_batch(paths, params=None, log=None):
    """后台线程：逐个提取 → 落 result.json → 在各自 output 目录生成对照报告。"""
    try:
        def progress(v):
            with LOCK:
                STATE['progress'] = v

        log.stage('load', '加载提取流水线（首次会导入 cv2 / pdfplumber）…')
        progress(1)
        pipeline = _load('pipeline')
        report_mod = _load('extract_report.builder')
        records = []
        total = len(paths)
        for i, path in enumerate(paths, 1):
            name = os.path.basename(path)
            log.stage('case', '[{}/{}] 开始处理 {}'.format(i, total, name))
            progress(int((i - 1) / total * 100))
            case_rel = case_dir_name(name)
            case_abs = os.path.join(config.OUTPUT_DIR, case_rel)
            os.makedirs(case_abs, exist_ok=True)
            frac = [0.0]

            def emit(level, stage, msg, _i=i, _frac=frac, **kw):
                f = _STAGE_FRAC.get((stage, level))
                if f is not None and f > _frac[0]:
                    _frac[0] = f
                    with LOCK:
                        STATE['progress'] = int((_i - 1 + f) / total * 100)
                log.emit(level, stage, msg, **kw)

            rec = pipeline.extract_one(path, case_abs, case_rel, params,
                                       emit=emit)
            records.append(rec)
            pages = rec.get('pages') or []
            tot_lines = sum(p.get('lines', 0) for p in pages)
            tot_tables = sum(len(p.get('structured_tables') or []) for p in pages)
            routes = '/'.join(sorted({p.get('table_route', '-') for p in pages}))
            log.ok('case', '识别 {} 行文字 · 表格 {} 张 · 路线 {} · {} 页{}'.format(
                tot_lines, tot_tables, routes, len(pages),
                ' · 跨页合并 {} 张'.format(len(rec.get('stitched_tables') or []))
                if rec.get('stitched_tables') else ''), case=name)
            # 报告与 result.json 同级，落在该 case 自己的 output 目录里
            report_mod.build([rec],
                             os.path.join(case_abs, config.EXTRACT_REPORT_NAME),
                             params=params)
            progress(int(i / total * 100))
        with LOCK:
            STATE.update(running=False, ready=True,
                         cases=[{'file': r['file'], 'case': r['case']}
                                for r in records],
                         elapsed=round(time.time()
                                       - (STATE['started'] or time.time()), 1),
                         progress=100, stage='done')
        log.ok('done', '完成，共 {} 个文件，耗时 {}s'.format(
            len(records), STATE['elapsed']))
    except Exception as e:
        if log:
            log.error('error', '出错：' + str(e))
            log.error('error', traceback.format_exc(limit=3).strip())
        with LOCK:
            STATE.update(running=False, ready=False, error=str(e),
                         stage='error')
        print(traceback.format_exc(limit=3))


if __name__ == '__main__':
    import uvicorn
    print('>> CV MVP 启动： http://{}:{}'.format(config.HOST, config.PORT))
    print('>> 输入目录：{}'.format(config.INPUT_DIR))
    print('>> 产物目录：{}'.format(config.OUTPUT_DIR))
    uvicorn.run(app, host=config.HOST, port=config.PORT,
                log_level='warning')

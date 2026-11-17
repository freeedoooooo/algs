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
    GET  /report        生成的报告
    /files/<path>       各 case 的产物
    /static/<path>      上传页的 css / js

提取逻辑在 pipeline/，报告生成在 report/，配置在 config.py。
"""
import os
import re
import sys
import time
import base64
import shutil
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
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
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
app.mount('/inputs', StaticFiles(directory=config.INPUT_DIR), name='inputs')
app.mount('/static', StaticFiles(directory=config.ASSETS_DIR), name='static')

# 单任务串行：模型单例不是线程安全的，也没必要并发加载第二份大模型
STATE = {
    'running': False, 'ready': False, 'error': None,
    'steps': [], 'cases': [], 'batch': None,
    'started': None, 'elapsed': 0,
    'params': {}, 'warnings': [],
    'logs': [], 'progress': 0, 'stage': '',
    'log_file': None,
    'last_paths': [], 'last_names': [],
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
    paths, names, used = [], [], set()
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
        names.append(name)
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

    return _launch(tag, paths, names, params, warns)


def _launch(tag, paths, names, params, warns):
    """建日志 → 重置 STATE → 起后台线程。upload 与 rerun 共用，保证行为一致。"""
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
                     log_file='{}.log'.format(tag),
                     last_paths=list(paths), last_names=list(names))
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


def _last_inputs():
    """上一批的 (输入文件绝对路径, 原始文件名) 列表。

    优先用 STATE 里记的本次进程上传记录；进程重启后 STATE 清空，则回退扫描
    input/ 取最新批次（文件名形如 <批次戳>_<原名>，按第一个下划线切分）。
    """
    pairs = [(p, n) for p, n in zip(STATE.get('last_paths') or [],
                                    STATE.get('last_names') or [])
             if os.path.isfile(p)]
    if pairs:
        return pairs
    by_tag = {}
    for f in os.listdir(config.INPUT_DIR):
        tag, sep, nm = f.partition('_')
        if sep:
            by_tag.setdefault(tag, []).append((f, nm))
    if not by_tag:
        return []
    newest = max(by_tag)
    return [(os.path.join(config.INPUT_DIR, f), nm)
            for f, nm in sorted(by_tag[newest])]


@app.get('/api/last')
def api_last():
    """上传页据此列出「上次文件」并预览，调参后可一键重跑，无需重新上传。"""
    files = []
    for p, nm in _last_inputs():
        ext = os.path.splitext(nm)[1].lower()
        kind = ('image' if ext in config.IMAGE_EXTS else
                'pdf' if ext in config.PDF_EXTS else 'text')
        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0
        files.append({'name': nm, 'size': size, 'kind': kind,
                      'url': '/inputs/' + os.path.basename(p)})
    return {'files': files}


@app.post('/api/rerun')
async def rerun(request: Request):
    """复用上次输入文件、只换参数重跑。复制到新批次戳下，产物不覆盖旧结果。"""
    if STATE['running']:
        return JSONResponse(
            {'ok': False, 'error': '已有任务正在处理，请等它完成'},
            status_code=409)
    try:
        body = await request.json()
    except Exception:
        body = {}
    last = _last_inputs()
    if not last:
        return JSONResponse(
            {'ok': False, 'error': '没有可复用的上次文件，请先上传'},
            status_code=400)
    params, warns = params_mod.normalize(body.get('params'))
    tag = batch_tag()
    paths, names, used = [], [], set()
    for oldpath, origname in last:
        name = safe_name(origname)
        if name in used:
            stem, e = os.path.splitext(name)
            k = 2
            while '{}-{}{}'.format(stem, k, e) in used:
                k += 1
            name = '{}-{}{}'.format(stem, k, e)
        used.add(name)
        names.append(name)
        newpath = os.path.join(config.INPUT_DIR, '{}_{}'.format(tag, name))
        shutil.copyfile(oldpath, newpath)
        paths.append(newpath)
    return _launch(tag, paths, names, params, warns)


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


@app.get('/report')
def report():
    path = os.path.join(config.OUTPUT_DIR, config.REPORT_NAME)
    if not os.path.isfile(path):
        return HTMLResponse(
            '<h3>还没有报告</h3><p><a href="/">返回上传页</a>先上传一个文件。</p>')
    return FileResponse(path, media_type='text/html; charset=utf-8')


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
    """后台线程：逐个提取 → 落 result.json → 生成汇总报告。"""
    try:
        def progress(v):
            with LOCK:
                STATE['progress'] = v

        log.stage('load', '加载提取流水线（首次会导入 cv2 / pdfplumber）…')
        progress(1)
        pipeline = _load('pipeline')
        report_mod = _load('report')
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
            log.ok('case', '识别 {} 行文字 · 表格 {} 张 · 路线 {} · 第 {} 页'
                   .format(rec['lines'], len(rec['structured_tables']),
                           rec['table_route'], rec.get('page', 1)),
                   case=name)
            progress(int(i / total * 100))
        log.stage('report', '正在生成汇总报告 …')
        progress(99)
        report_mod.build(
            records, os.path.join(config.OUTPUT_DIR, config.REPORT_NAME),
            params=params)
        with LOCK:
            STATE.update(running=False, ready=True,
                         cases=[r['file'] for r in records],
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

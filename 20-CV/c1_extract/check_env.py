"""
c1_extract/check_env.py — 独立部署自检（只读，不加载任何模型权重，秒级完成）。

用法：
    cd c1_extract && python check_env.py

检查四件事：
    1) requirements.txt 里的包能否 import、装的是哪个版本
    2) logs/ data/ tmp/ 是否存在且可写（业务数据全在 DB，无持久 input/output）
    3) PaddleX 官方模型缓存是否就绪（没有→首次处理会联网下载）
    4) 平台库（MySQL）连通性 —— 必选项（DB 唯一事实源），连不上即 FAIL

有任何缺包 / 目录缺失 / 平台库不通时退出码为 1，方便在 CI / Docker build 里当门禁用。
"""
import os
import sys
import importlib
from importlib.metadata import version, PackageNotFoundError

ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# 与 app.py 一致：以包方式加载，静态分析器无需任何 IDE 配置
config = importlib.import_module(PKG + '.config')

# (pip 发行包名, import 名, 用途)
PACKAGES = [
    ('fastapi', 'fastapi', 'Web 框架'),
    ('uvicorn', 'uvicorn', 'ASGI 服务器'),
    ('jinja2', 'jinja2', '对照报告模板渲染'),
    # paddleocr/paddlex 必须先于 paddlepaddle：paddleocr 会引入 torch，而 torch 的
    # shm.dll 须在 paddle 之前加载，否则 paddle↔torch 同名 DLL 冲突（WinError 127）。
    # app 运行时同样先 import paddleocr（pipeline/engines.py），此处保持一致。
    ('paddleocr', 'paddleocr', 'OCR / 表格模型'),
    ('paddlex', 'paddlex', '模型管线'),
    ('paddlepaddle', 'paddle', 'Paddle 运行时'),
    ('opencv-contrib-python', 'cv2', '网格预筛（cv2）'),
    ('numpy', 'numpy', '数值计算'),
    ('Pillow', 'PIL', '图像处理'),
    ('pdfplumber', 'pdfplumber', '文本层表格 + bbox'),
    ('PyMuPDF', 'pymupdf', 'PDF 首页渲染'),
    ('PyMySQL', 'pymysql', '平台库驱动（DB 唯一事实源）'),
]


def check_packages():
    missing = []
    for dist, mod, use in PACKAGES:
        try:
            importlib.import_module(mod)
            try:
                v = version(dist)
            except PackageNotFoundError:
                v = '? (换个发行包装的)'
            print('  OK      {:<24} {:<14} {}'.format(dist, v, use))
        except Exception as e:
            missing.append(dist)
            print('  MISSING {:<24} {:<14} {} · {}'.format(
                dist, '-', use, type(e).__name__))
    return missing


def check_dirs():
    bad = []
    for label, path in (('logs', config.LOG_DIR),
                        ('data', config.DATA_DIR),
                        ('tmp/input', config.TMP_INPUT),
                        ('tmp/work', config.TMP_WORK),
                        ('web', config.WEB_DIR),
                        ('templates', config.TEMPLATES_DIR)):
        ok = os.path.isdir(path) and (label in ('web', 'templates')
                                      or os.access(path, os.W_OK))
        print('  {:<7} {:<8} {}'.format('OK' if ok else 'FAIL',
                                        label, path))
        if not ok:
            bad.append(path)
    return bad


def check_models():
    cache = (os.environ.get('PADDLE_PDX_CACHE_HOME')
             or os.path.join(os.path.expanduser('~'), '.paddlex'))
    models = os.path.join(cache, 'official_models')
    if os.path.isdir(models):
        n = len([d for d in os.listdir(models)
                 if os.path.isdir(os.path.join(models, d))])
        print('  OK      模型缓存 {}（{} 个模型）'.format(models, n))
        if n < 5:
            print('           模型偏少，首次处理仍可能联网补齐')
    else:
        print('  WARN    未找到模型缓存 {}'.format(models))
        print('           首次处理会联网下载（数百 MB）；离线部署请先预置该目录')
        print('           并设置环境变量 PADDLE_PDX_CACHE_HOME 指向其上级目录')


def check_platform_db():
    """平台库（MySQL）连通性：必选项（DB 唯一事实源，不通＝服务不可用）。

    只读探针（SELECT VERSION()，不写库）；只回显脱敏 host/库名，
    凭据永不打印。未配引用 / 连不上 → FAIL。
    """
    ref = config.PLATFORM_DB_REF
    db = importlib.import_module(PKG + '.store.db')
    try:
        p = db._parts(db.resolve_conn(ref))
    except Exception as e:
        print('  FAIL    凭据引用 {} 未配置：{}'.format(ref, e))
        print('           设环境变量 {} 或 data/secrets.json'.format(ref))
        return False
    detail = '{}:{}/{}'.format(p['host'], p['port'], p['database'])
    try:
        import pymysql
        conn = pymysql.connect(
            host=p['host'], port=p['port'], user=p['user'],
            password=p['password'], database=p['database'],
            charset='utf8mb4', connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT VERSION()')
                ver = cur.fetchone()[0]
        finally:
            conn.close()
        print('  OK      MySQL {} · {}'.format(ver, detail))
        return True
    except Exception as e:
        print('  FAIL    平台库连接失败（{}）：{}'.format(detail, type(e).__name__))
        print('           DB 是唯一事实源：上传/运行/读端点都将显式失败')
        return False


def main():
    print('Python {} · c1_extract = {}'.format(sys.version.split()[0], ROOT))
    print('\n[1/4] 依赖包')
    missing = check_packages()
    print('\n[2/4] 目录')
    bad_dirs = check_dirs()
    print('\n[3/4] 模型缓存')
    check_models()
    print('\n[4/4] 平台库（必选 · DB 唯一事实源）')
    db_ok = check_platform_db()
    ok = not (missing or bad_dirs) and db_ok
    print('\n结论：', '依赖齐全、平台库可达，可启动' if ok
          else '缺 {} 个包 / {} 个目录 / 平台库{}'.format(
              len(missing), len(bad_dirs), '可达' if db_ok else '不可达'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

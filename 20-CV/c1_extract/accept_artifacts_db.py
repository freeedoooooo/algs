"""
c1_extract/accept_artifacts_db.py — 产物全量入库六项验收（C1 契约，
design-c1-storage.md：DB 唯一事实源，附件键＝run_file_id，无 file 模式）。

前置：C1_EXTRACT_DB 已配置（env 或 data/secrets.json，用户配置的库）。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u c1_extract/accept_artifacts_db.py

1 迁移门禁幂等+读回 sha 自洽 · 2 真链路无持久磁盘+BLOB · 3 /files 路由/ETag/raw403 ·
4 runs/报告/暂存全查库 · 5 导出字节一致 · 6 断库显式 503。
上传字节取自 source_file.content；断库用不可达 DSN 的临时服务模拟，
不触碰真实库可用性。破坏性操作只落临时 run 与临时导出目录，验完按 id 清理
（附件随 run_file FK 级联）；真实 run / source 只读。用户的 8765 全程不动。
临时服务 8799(真库)/8797(不可达 DSN)。两套验收脚本严禁并行。
"""
import os
import sys
import json
import time
import base64
import shutil
import socket
import hashlib
import tempfile
import subprocess
import importlib
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault('PYTHONUTF8', '1')
config = importlib.import_module(PKG + '.config')
db = importlib.import_module(PKG + '.store.db')
catalog = importlib.import_module(PKG + '.store.catalog')
content_db = importlib.import_module(PKG + '.store.content_db')
artifact_db = importlib.import_module(PKG + '.store.artifact_db')

BAD_DSN = 'mysql://nobody:unused@127.0.0.1:3399/co_dev'
FAILS = []


def check(name, ok, detail=''):
    print('  {}  {}{}'.format('PASS' if ok else 'FAIL', name,
                              (' · ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


def http(port, path, body=None, headers=None):
    # Starlette 回小写 header 名：统一 lower()，避免大小写查空
    req = urllib.request.Request(
        'http://127.0.0.1:{}{}'.format(port, path),
        data=json.dumps(body).encode() if body is not None else None,
        headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, \
                r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def http_json(port, path, body=None):
    st, _h, b = http(port, path, body)
    try:
        return st, json.loads(b.decode())
    except Exception:
        return st, {}


def wait_http(port, secs=30):
    for _ in range(secs * 2):
        try:
            http(port, '/healthz')
            return True
        except Exception:
            time.sleep(0.5)
    return False


def wait_db(secs=60):
    p = db._parts(db.resolve_conn(config.PLATFORM_DB_REF))
    for _ in range(secs):
        try:
            s = socket.create_connection((p['host'], p['port']), timeout=2)
            s.close()
            time.sleep(2)
            return True
        except Exception:
            time.sleep(1)
    return False


def art_counts():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*), COALESCE(SUM(size_bytes),0)'
                        ' FROM extract_artifact')
            return tuple(cur.fetchone())
    finally:
        conn.close()


def start_service(port, dsn=None):
    # 端口必须空闲：否则 wait_http 会误连到别的服务（两套脚本严禁并行跑）
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port))
    except OSError:
        raise RuntimeError('端口 {} 已被占用，先停掉占用者再跑'.format(port))
    finally:
        s.close()
    env = dict(os.environ, C1_EXTRACT_PORT=str(port), C1_EXTRACT_WARMUP='0')
    if dsn:
        env['C1_EXTRACT_DB'] = dsn
    else:
        env.pop('C1_EXTRACT_DB', None)
    p = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', PKG + '.app:app',
         '--host', '127.0.0.1', '--port', str(port)],
        cwd=PARENT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_http(port) or p.poll() is not None:
        p.kill()
        raise RuntimeError('服务 {} 启动失败'.format(port))
    return p


def upload(port, src_bytes, name):
    st, j = http_json(port, '/api/upload',
                      {'files': [{'name': name,
                                  'data': base64.b64encode(src_bytes).decode()}],
                       'mode': 'preview'})
    if st != 200 or not j.get('ok'):
        raise RuntimeError('upload 失败：{} {}'.format(st, j))
    run_id = j['run_id']
    for _ in range(300):
        _, s = http_json(port, '/api/status')
        if not s.get('running'):
            return run_id, s
        time.sleep(0.5)
    raise RuntimeError('upload 超时')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def find_pdf_source():
    """size>1KB 过滤：排除验收合成的假 PDF 行。"""
    page = 1
    while True:
        b = catalog.list_sources(page=page, per_page=100)
        for row in b['items']:
            if row['kind'] == 'pdf' and row['size_bytes'] > 1024:
                s = catalog.get_source_content(row['id'])
                s['id'] = row['id']
                return s
        if page * 100 >= b['total']:
            return None
        page += 1


def scratch_clean():
    tmp = tempfile.gettempdir()
    return not any(n.startswith(('c1_in_', 'c1_case_'))
                   for n in os.listdir(tmp))


def cleanup_run(run_id):
    """先子后父：staging_record 无级联须显式删；artifact 随 run_file FK 级联。
    上传命中真实 source 的 sha 去重，source 行不动。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE sr FROM extract_staging_record sr'
                ' JOIN extract_run_file rf ON rf.id=sr.run_file_id'
                ' WHERE rf.run_id=%s', (run_id,))
            cur.execute('DELETE FROM extract_quarantine WHERE run_id=%s',
                        (run_id,))
            cur.execute('DELETE FROM extract_load_log WHERE run_id=%s',
                        (run_id,))
            cur.execute('DELETE FROM extract_run_file WHERE run_id=%s',
                        (run_id,))
            cur.execute('DELETE FROM extract_run WHERE id=%s', (run_id,))
        conn.commit()
    finally:
        conn.close()


def main():
    print('== 产物入库验收（C1）· {} =='.format(
        db.safe_detail(config.PLATFORM_DB_REF)))
    try:
        if not wait_db():
            print('配置库不可达，检查 C1_EXTRACT_DB（env / data/secrets.json）')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    db.connect().close()  # 触发 001-006 迁移门禁
    up = []
    try:
        rc = _main(up)
    finally:
        print('清理临时产物')
        for rid in up:
            cleanup_run(rid)
    print('\n结论：{}'.format('六项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return rc


def _main(up):
    print('[1/6] 迁移门禁幂等 + 读回 sha 自洽')
    c0 = art_counts()
    db._READY.clear()       # 强制重跑门禁：schema_version 已全，应零变更
    db.connect().close()
    check('门禁重跑行数/字节不变', art_counts() == c0,
          '{} vs {}'.format(c0, art_counts()))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT DISTINCT run_file_id FROM extract_artifact')
            rfs = [r[0] for r in cur.fetchall()]
            cur.execute('SELECT id, sha256, size_bytes, content'
                        ' FROM extract_source_file')
            sources = cur.fetchall()
    finally:
        conn.close()
    bad, n = [], 0
    for rf in rfs:
        for m in artifact_db.list(rf):
            n += 1
            a = artifact_db.get(rf, m['name'])
            if a is None or a['sha'] != m['sha'] \
                    or sha(a['data']) != m['sha'] \
                    or len(a['data']) != m['size']:
                bad.append('{}/{}'.format(rf, m['name']))
    check('附件全量读回 sha/size 自洽', not bad,
          '{} 个文件'.format(n) if not bad else '不一致：{}'.format(bad[:5]))
    bad_src = [r[0] for r in sources
               if sha(r[3]) != r[1] or len(r[3]) != r[2]]
    check('source_file.content sha/size 自洽', not bad_src,
          '{} 个原件'.format(len(sources)) if not bad_src
          else '不一致 id：{}'.format(bad_src))

    print('[2/6] 真链路：无持久磁盘 + BLOB（临时服务 8799）')
    src = find_pdf_source()
    if src is None:
        print('  FAIL  source_file 无 PDF 原件，无法真链路验收')
        return 1
    svc = start_service(8799)
    try:
        run_id, st = upload(8799, src['data'], src['name'])
        up.append(run_id)
        time.sleep(1)  # finally 清理 scratch 在 running=False 之后
        rrun = catalog.get_run(run_id)
        rf_id = rrun['files'][0]['run_file_id']
        check('真链路 previewed', st.get('error') is None
              and rrun['state'] == 'previewed'
              and rrun['files'][0]['state'] == 'previewed',
              'err={}'.format(st.get('error')))
        check('无持久 scratch 副本', scratch_clean())
        names = {m['name'] for m in artifact_db.list(rf_id)}
        check('产物入 BLOB', {config.EXTRACT_JSON,
                             config.EXTRACT_REPORT_NAME} <= names,
              '{} 个文件'.format(len(names)))

        print('[3/6] /files 路由：mime / ETag 304 / raw 403 / records 404')
        q = urllib.request.quote
        st1, h1, b1 = http(8799, '/files/{}/{}'.format(rf_id,
                           q(config.EXTRACT_JSON)))
        check('/files extract 200+mime', st1 == 200
              and h1.get('content-type', '').startswith('application/json')
              and json.loads(b1.decode()).get('schema'))
        st2, h2, _b2 = http(8799, '/files/{}/{}'.format(rf_id,
                            q(config.EXTRACT_REPORT_NAME)))
        check('/files 报告 200+html', st2 == 200
              and h2.get('content-type', '').startswith('text/html'))
        etag = h1.get('etag')
        st3, _h3, _b3 = http(8799, '/files/{}/{}'.format(rf_id,
                             q(config.EXTRACT_JSON)),
                             headers={'If-None-Match': etag} if etag else None)
        check('ETag 304', bool(etag) and st3 == 304, 'etag={}'.format(etag))
        st4, _h4, _b4 = http(8799, '/files/{}/raw/pdfplumber.json'.format(rf_id))
        check('raw 403', st4 == 403)
        st5, _h5, _b5 = http(8799, '/files/{}/records.json'.format(rf_id))
        check('records.json 404（DB 三表为事实源）', st5 == 404)
        st6, _h6, b6 = http(8799, '/srcfiles/{}'.format(src['id']))
        check('/srcfiles 200 + sha 一致', st6 == 200 and sha(b6) == src['sha'])

        print('[4/6] runs / 报告重定向 / 暂存全查库（无磁盘依赖）')
        st, j = http_json(8799, '/api/runs')
        check('runs 列表含新 run', st == 200
              and any(r.get('run_id') == run_id for r in j['items']))
        st, j = http_json(8799, '/api/runs/{}'.format(run_id))
        check('run 详情 previewed', st == 200
              and j['run']['files'][0]['state'] == 'previewed')
        req = urllib.request.Request('http://127.0.0.1:8799/extract-report')
        with urllib.request.urlopen(req, timeout=30) as r:
            check('报告重定向落 /files/', r.status == 200
                  and '/files/' in r.url and r.url.endswith(
                      q(config.EXTRACT_REPORT_NAME)))
        st, j = http_json(8799, '/api/runs/{}/staging'.format(run_id))
        n_rec = rrun['files'][0]['records_n']
        check('暂存 API 记录数一致', st == 200 and n_rec > 0
              and len(j['files'][0]['records']) == n_rec,
              '{} 条'.format(n_rec))
        kw = next((str(v)[:4] for f in j['files'] for rec in f['records']
                   for v in rec['values'].values() if v not in (None, '')),
                  '流水')
        st, j = http_json(8799, '/api/staging/query?q=' + q(kw))
        check('跨 run 查询 200', st == 200 and j.get('ok')
              and len(j.get('items', [])) > 0)
    finally:
        svc.kill()

    print('[5/6] 导出字节一致 + records 重建')
    out_dir = tempfile.mkdtemp(prefix='c1_export_')
    try:
        p = subprocess.run(
            [sys.executable, os.path.join(PKG, 'export_artifacts.py'),
             '--run', str(up[0]), '--out', out_dir],
            cwd=PARENT, env=dict(os.environ, PYTHONUTF8='1'),
            capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            print(p.stdout[-2000:], p.stderr[-2000:])
        check('导出脚本退出 0', p.returncode == 0)
        run = catalog.get_run(up[0])
        base = os.path.join(out_dir, 'output', 'run_{}'.format(up[0]))
        bad = []
        for f in run['files']:
            for m in artifact_db.list(f['run_file_id']):
                fp = os.path.join(base, f['name'],
                                  m['name'].replace('/', os.sep))
                if not os.path.isfile(fp):
                    bad.append('缺 ' + f['name'] + '/' + m['name'])
                    continue
                with open(fp, 'rb') as fh:
                    if sha(fh.read()) != m['sha']:
                        bad.append('sha ' + f['name'] + '/' + m['name'])
        rp = os.path.join(base, config.RECORDS_JSON)
        want = content_db.get_records(up[0])
        if want is not None:
            if not os.path.isfile(rp):
                bad.append('缺 records.json')
            else:
                with open(rp, encoding='utf-8') as fh:
                    if json.load(fh) != want:
                        bad.append('records 语义')
        check('导出逐文件字节一致 + records 语义一致', not bad,
              '{} 个 run_file'.format(len(run['files'])) if not bad
              else '问题：{}'.format(bad[:5]))
        # sources：全量导出，重名加 _<id>（与 export 同算法核对）
        used, page = set(), 1
        while True:
            batch = catalog.list_sources(page=page, per_page=100)
            for row in batch['items']:
                s = catalog.get_source_content(row['id'])
                name = row['name']
                if name in used:
                    stem, e = os.path.splitext(name)
                    name = '{}_{}{}'.format(stem, row['id'], e)
                used.add(name)
                fp = os.path.join(out_dir, 'sources', name)
                if not os.path.isfile(fp):
                    bad.append('缺 sources/' + name)
                    continue
                with open(fp, 'rb') as fh:
                    if sha(fh.read()) != s['sha']:
                        bad.append('sha sources/' + name)
            if page * 100 >= batch['total']:
                break
            page += 1
        check('sources 导出字节一致', not bad,
              '{} 个原件'.format(len(used)) if not bad
              else '问题：{}'.format(bad[:5]))
        rep = os.path.join(base, run['files'][0]['name'],
                           config.EXTRACT_REPORT_NAME)
        check('导出报告可 file:// 直开（文件在树内）', os.path.isfile(rep))
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    print('[6/6] 断库显式 503（临时服务 8797，不可达 DSN）')
    svc = start_service(8797, dsn=BAD_DSN)
    try:
        st, j = http_json(8797, '/api/upload',
                          {'files': [{'name': src['name'],
                                      'data': base64.b64encode(
                                          src['data']).decode()}],
                           'mode': 'preview'})
        check('断库上传 503', st == 503, 'st={} err={}'.format(
            st, j.get('error')))
        st, _j = http_json(8797, '/api/runs')
        check('断库 runs 503', st == 503)
        st, _h, _b = http(8797, '/files/{}/{}'.format(
            rf_id, urllib.request.quote(config.EXTRACT_JSON)))
        check('断库 /files 503', st == 503)
        st, _h, _b = http(8797, '/extract-report')
        check('断库报告入口 503', st == 503)
        st, _j = http_json(8797, '/api/runs/{}/staging'.format(up[0]))
        check('断库暂存 503', st == 503)
    finally:
        svc.kill()
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
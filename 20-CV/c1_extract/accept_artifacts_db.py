"""
mvp/accept_artifacts_db.py — 产物全量入库六项验收（DB-only 契约，
design-artifacts-db.md §7：DB 唯一事实源，无 file 模式）。

前置：CV_PLATFORM_DB 已配置（env 或 data/secrets.json，用户配置的库）。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u mvp/accept_artifacts_db.py

1 回填幂等+读回 sha 自洽 · 2 真链路无持久磁盘+BLOB · 3 /files 路由/ETag/raw403 ·
4 runs/报告/暂存全查库 · 5 导出字节一致 · 6 断库显式 503。
磁盘已清空：上传字节取自 sources BLOB；断库用不可达 DSN 的临时服务模拟，
不触碰真实库可用性。破坏性操作只落临时批次与临时导出目录，验完清理；
用户的 8765 全程不动。临时服务 8799(真库)/8797(不可达 DSN)。
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
content = importlib.import_module(PKG + '.store.content')
content_db = importlib.import_module(PKG + '.store.content_db')
artifact_db = importlib.import_module(PKG + '.store.artifact_db')
mig_art = importlib.import_module(PKG + '.migrate_artifacts_to_db')

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
    env = dict(os.environ, CV_MVP_PORT=str(port), CV_MVP_WARMUP='0')
    if dsn:
        env['CV_PLATFORM_DB'] = dsn
    else:
        env.pop('CV_PLATFORM_DB', None)
    p = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'mvp.app:app',
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
    batch = j['batch']
    for _ in range(300):
        _, s = http_json(port, '/api/status')
        if not s.get('running'):
            return batch, s
        time.sleep(0.5)
    raise RuntimeError('upload 超时')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _delete_batch_rows(cur, batch):
    cur.execute(
        'DELETE sr FROM extract_staging_record sr'
        ' JOIN extract_run_file rf ON rf.id=sr.run_file_id'
        ' JOIN extract_run r ON r.id=rf.run_id WHERE r.batch_tag=%s', (batch,))
    cur.execute(
        'DELETE q FROM extract_quarantine q'
        ' JOIN extract_run r ON r.id=q.run_id WHERE r.batch_tag=%s', (batch,))
    cur.execute(
        'DELETE rf FROM extract_run_file rf'
        ' JOIN extract_run r ON r.id=rf.run_id WHERE r.batch_tag=%s', (batch,))
    cur.execute('DELETE FROM extract_run WHERE batch_tag=%s', (batch,))


def cleanup_batch(batch):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT rf.output_rel_dir FROM extract_run_file rf'
                ' JOIN extract_run r ON r.id=rf.run_id'
                ' WHERE r.batch_tag=%s', (batch,))
            cases = [r[0].rsplit('/', 1)[-1] for r in cur.fetchall()]
            _delete_batch_rows(cur, batch)
        conn.commit()
    finally:
        conn.close()
    for c in cases:
        artifact_db.delete_case(c)
        shutil.rmtree(os.path.join(config.OUTPUT_DIR, c), ignore_errors=True)


def main():
    print('== 产物入库验收 · {} =='.format(
        db.safe_detail(config.PLATFORM_DB_REF)))
    try:
        if not wait_db():
            print('配置库不可达，检查 CV_PLATFORM_DB（env / data/secrets.json）')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    db.connect().close()  # 触发 001-004 迁移

    print('[1/6] 回填幂等 + 读回 sha 自洽')
    mig_art.main()
    c1 = art_counts()
    mig_art.main()
    c2 = art_counts()
    check('两遍行数/字节不变', c1 == c2, '{} vs {}'.format(c1, c2))
    bad, n = [], 0
    for case in artifact_db.cases() + ['sources']:
        for m in artifact_db.list(case):
            n += 1
            a = artifact_db.get(case, m['name'])
            if a is None or a['sha'] != m['sha'] \
                    or sha(a['data']) != m['sha'] \
                    or len(a['data']) != m['size']:
                bad.append('{}/{}'.format(case, m['name']))
    check('全量读回 sha/size 自洽', not bad,
          '{} 个文件'.format(n) if not bad else '不一致：{}'.format(bad[:5]))

    print('[2/6] 真链路：无持久磁盘 + BLOB（临时服务 8799）')
    src = artifact_db.get('sources', '83ef00a8_招行流水（已脱敏）.pdf')
    if src is None:
        print('  FAIL  sources BLOB 缺招行流水 PDF，无法真链路验收')
        return 1
    svc = start_service(8799)
    up_batch = None
    try:
        batch, st = upload(8799, src['data'], '招行流水（已脱敏）.pdf')
        up_batch = batch
        case = batch + '_招行流水_已脱敏_'
        time.sleep(1)  # finally 清理 scratch 在 running=False 之后
        rrun = content.get_run(case)
        check('真链路 previewed', st.get('error') is None
              and rrun and rrun['files'][0]['state'] == 'previewed',
              'err={}'.format(st.get('error')))
        check('无持久 output/input 副本',
              not os.path.exists(os.path.join(config.OUTPUT_DIR, case))
              and not any(nm.startswith(batch + '_')
                          for nm in os.listdir(config.INPUT_DIR)))
        names = {m['name'] for m in artifact_db.list(case)}
        check('产物入 BLOB', {config.EXTRACT_JSON, config.RUN_JSON,
                             config.EXTRACT_REPORT_NAME} <= names,
              '{} 个文件'.format(len(names)))

        print('[3/6] /files 路由：mime / ETag 304 / raw 403 / records 404')
        q = urllib.request.quote
        st1, h1, b1 = http(8799, '/files/{}/{}'.format(q(case),
                           q(config.EXTRACT_JSON)))
        check('/files extract 200+mime', st1 == 200
              and h1.get('content-type', '').startswith('application/json')
              and json.loads(b1.decode()).get('schema'))
        st2, h2, _b2 = http(8799, '/files/{}/{}'.format(q(case),
                            q(config.EXTRACT_REPORT_NAME)))
        check('/files 报告 200+html', st2 == 200
              and h2.get('content-type', '').startswith('text/html'))
        etag = h1.get('etag')
        st3, _h3, _b3 = http(8799, '/files/{}/{}'.format(q(case),
                             q(config.EXTRACT_JSON)),
                             headers={'If-None-Match': etag} if etag else None)
        check('ETag 304', bool(etag) and st3 == 304, 'etag={}'.format(etag))
        st4, _h4, _b4 = http(8799, '/files/{}/raw/pdfplumber.json'.format(
            q(case)))
        check('raw 403', st4 == 403)
        st5, _h5, _b5 = http(8799, '/files/{}/records.json'.format(q(case)))
        check('records.json 404（DB 三表为事实源）', st5 == 404)
        srcs = artifact_db.list('sources')
        st6, _h6, b6 = http(8799, '/srcfiles/{}'.format(q(srcs[0]['name'])))
        check('/srcfiles 200', st6 == 200 and len(b6) > 0)

        print('[4/6] runs / 报告重定向 / 暂存全查库（无磁盘依赖）')
        st, j = http_json(8799, '/api/runs')
        check('runs 列表含新批次', st == 200
              and any(r.get('batch_tag') == up_batch for r in j['items']))
        st, j = http_json(8799, '/api/runs/{}'.format(up_batch))
        check('run 详情 previewed', st == 200
              and j['run']['files'][0]['state'] == 'previewed')
        req = urllib.request.Request('http://127.0.0.1:8799/extract-report')
        with urllib.request.urlopen(req, timeout=30) as r:
            check('报告重定向落 /files/', r.status == 200
                  and '/files/' in r.url and r.url.endswith(
                      q(config.EXTRACT_REPORT_NAME)))
        st, j = http_json(8799, '/api/runs/{}/staging'.format(up_batch))
        check('暂存 API 24 条', st == 200
              and len(j['files'][0]['records']) == 24)
        st, j = http_json(8799, '/api/staging/query?q=' + q('报销'))
        check('跨批查询 200', st == 200 and j.get('ok')
              and len(j.get('items', [])) > 0)
    finally:
        svc.kill()

    print('[5/6] 导出字节一致 + records 重建')
    out_dir = tempfile.mkdtemp(prefix='cv_export_')
    try:
        p = subprocess.run(
            [sys.executable, 'mvp/export_artifacts.py', '--out', out_dir],
            cwd=PARENT, env=dict(os.environ, PYTHONUTF8='1'),
            capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            print(p.stdout[-2000:], p.stderr[-2000:])
        check('导出脚本退出 0', p.returncode == 0)
        bad = []
        cases = [c for c in artifact_db.cases() if c != 'sources']
        for d in cases:
            for m in artifact_db.list(d):
                fp = os.path.join(out_dir, 'output', d,
                                  m['name'].replace('/', os.sep))
                if not os.path.isfile(fp):
                    bad.append('缺 ' + d + '/' + m['name'])
                    continue
                with open(fp, 'rb') as f:
                    if sha(f.read()) != m['sha']:
                        bad.append('sha ' + d + '/' + m['name'])
            rp = os.path.join(out_dir, 'output', d, config.RECORDS_JSON)
            want = content_db.get_records(d)
            if want is not None:
                if not os.path.isfile(rp):
                    bad.append('缺 records ' + d)
                else:
                    with open(rp, encoding='utf-8') as f:
                        if json.load(f) != want:
                            bad.append('records 语义 ' + d)
        for m in artifact_db.list('sources'):
            fp = os.path.join(out_dir, 'sources', m['name'])
            if not os.path.isfile(fp):
                bad.append('缺 sources/' + m['name'])
                continue
            with open(fp, 'rb') as f:
                if sha(f.read()) != m['sha']:
                    bad.append('sha sources/' + m['name'])
        check('导出逐文件字节一致 + records 语义一致', not bad,
              '{} case'.format(len(cases)) if not bad
              else '问题：{}'.format(bad[:5]))
        rep = os.path.join(out_dir, 'output',
                           up_batch + '_招行流水_已脱敏_',
                           config.EXTRACT_REPORT_NAME)
        check('导出报告可 file:// 直开（文件在树内）', os.path.isfile(rep))
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    print('[6/6] 断库显式 503（临时服务 8797，不可达 DSN）')
    svc = start_service(8797, dsn=BAD_DSN)
    try:
        st, j = http_json(8797, '/api/upload',
                          {'files': [{'name': '招行流水（已脱敏）.pdf',
                                      'data': base64.b64encode(
                                          src['data']).decode()}],
                           'mode': 'preview'})
        check('断库上传 503', st == 503, 'st={} err={}'.format(
            st, j.get('error')))
        st, _j = http_json(8797, '/api/runs')
        check('断库 runs 503', st == 503)
        st, _h, _b = http(8797, '/files/{}/{}'.format(
            urllib.request.quote(up_batch + '_招行流水_已脱敏_'),
            urllib.request.quote(config.EXTRACT_JSON)))
        check('断库 /files 503', st == 503)
        st, _h, _b = http(8797, '/extract-report')
        check('断库报告入口 503', st == 503)
        st, _j = http_json(8797, '/api/runs/{}/staging'.format(up_batch))
        check('断库暂存 503', st == 503)
    finally:
        svc.kill()

    print('清理临时产物')
    if up_batch:
        cleanup_batch(up_batch)

    print('\n结论：{}'.format('六项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
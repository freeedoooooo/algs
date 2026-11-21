"""
c1_extract/accept_artifacts_db.py — 产物全量入库六项验收（任务化契约，
design-task-schema.md：DB 唯一事实源，附件键＝task_file_id，无外键）。

前置：C1_EXTRACT_DB 已配置（env 或 data/secrets.json，用户配置的库）。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u c1_extract/accept_artifacts_db.py

1 连接零副作用+读回 sha 自洽 · 2 真链路无持久磁盘+BLOB · 3 /files 路由/ETag/raw403 ·
4 tasks/报告/暂存全查库 · 5 导出字节一致 · 6 断库显式 503。
上传字节取自 extract_file.content；断库用不可达 DSN 的临时服务模拟，
不触碰真实库可用性。破坏性操作只落临时 task 与临时导出目录，验完按 id 清理
（无外键：artifact/record 等子表须显式先删）；真实 task / file 只读。
用户的 8765 全程不动。临时服务 8799(真库)/8797(不可达 DSN)。
两套验收脚本严禁并行。
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


def http(port, path, body=None, headers=None, timeout=60):
    # Starlette 回小写 header 名：统一 lower()，避免大小写查空
    req = urllib.request.Request(
        'http://127.0.0.1:{}{}'.format(port, path),
        data=json.dumps(body).encode() if body is not None else None,
        headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, \
                r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def http_json(port, path, body=None, timeout=60):
    st, _h, b = http(port, path, body, timeout=timeout)
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
    # WARMUP=0 时后台线程即刻建 paddle 模型（oneDNN 初始化持 GIL），
    # 事件循环回包被饿死，首个 POST 可能数十秒——放宽到 120s
    st, j = http_json(port, '/api/upload',
                      {'files': [{'name': name,
                                  'data': base64.b64encode(src_bytes).decode()}]},
                      timeout=120)
    if st != 200 or not j.get('ok'):
        raise RuntimeError('upload 失败：{} {}'.format(st, j))
    task_id = j['task_id']
    for _ in range(300):
        _, s = http_json(port, '/api/status')
        if not s.get('running'):
            return task_id, s
        time.sleep(0.5)
    raise RuntimeError('upload 超时')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def find_pdf_file():
    """size>1KB 过滤：排除验收合成的假 PDF 行。"""
    page = 1
    while True:
        b = catalog.list_files(page=page, per_page=100)
        for row in b['items']:
            if row['kind'] == 'pdf' and row['size_bytes'] > 1024:
                s = catalog.get_file_content(row['id'])
                s['id'] = row['id']
                return s
        if page * 100 >= b['total']:
            return None
        page += 1


def scratch_clean(wait=5):
    # 清理在 running=False 发布后的 finally 里收尾，给几秒宽限轮询
    for _ in range(wait * 2):
        if not any(n.startswith(('in_', 'case_'))
                   for d in (config.TMP_INPUT, config.TMP_WORK)
                   for n in os.listdir(d)):
            return True
        time.sleep(0.5)
    return False


def sweep_stale_scratch(max_age=3600):
    """清上一轮中断（kill/断电）留下的孤儿 scratch：只动 mtime 超 1 小时的
    in_*/case_* 目录——任何在跑任务的 scratch 都远比这新，不会误伤。"""
    now = time.time()
    for d in (config.TMP_INPUT, config.TMP_WORK):
        for n in os.listdir(d):
            if not n.startswith(('in_', 'case_')):
                continue
            p = os.path.join(d, n)
            if os.path.isdir(p) and now - os.path.getmtime(p) > max_age:
                shutil.rmtree(p, ignore_errors=True)
                print('  清扫孤儿 scratch：{}'.format(p))


def cleanup_task(task_id):
    """先子后父（无外键，全部显式删）：field/lineage→record→artifact→
    quarantine→load_log→task_file→task。上传命中真实 file 的 sha 去重，
    file 行不动。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_task_file WHERE task_id=%s',
                        (task_id,))
            tfs = [r[0] for r in cur.fetchall()]
            for tf in tfs:
                cur.execute(
                    'DELETE FROM extract_staging_field WHERE record_id IN'
                    ' (SELECT id FROM extract_staging_record'
                    '  WHERE task_file_id=%s)', (tf,))
                cur.execute(
                    'DELETE FROM extract_staging_lineage WHERE record_id IN'
                    ' (SELECT id FROM extract_staging_record'
                    '  WHERE task_file_id=%s)', (tf,))
                cur.execute(
                    'DELETE FROM extract_staging_record WHERE task_file_id=%s',
                    (tf,))
                cur.execute(
                    'DELETE FROM extract_artifact WHERE task_file_id=%s',
                    (tf,))
            cur.execute('DELETE FROM extract_quarantine WHERE task_id=%s',
                        (task_id,))
            cur.execute('DELETE FROM extract_load_log WHERE task_id=%s',
                        (task_id,))
            cur.execute('DELETE FROM extract_task_file WHERE task_id=%s',
                        (task_id,))
            cur.execute('DELETE FROM extract_task WHERE id=%s', (task_id,))
        conn.commit()
    finally:
        conn.close()


def main():
    print('== 产物入库验收（任务化）· {} =='.format(
        db.safe_detail(config.PLATFORM_DB_REF)))
    try:
        if not wait_db():
            print('配置库不可达，检查 C1_EXTRACT_DB（env / data/secrets.json）')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    db.connect().close()  # 连通探针（纯连接，不建表不迁移）
    sweep_stale_scratch()
    up = []
    try:
        rc = _main(up)
    finally:
        print('清理临时产物')
        for tid in up:
            cleanup_task(tid)
    print('\n结论：{}'.format('六项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return rc


def _main(up):
    print('[1/6] 连接零副作用 + 读回 sha 自洽')
    c0 = art_counts()
    db.connect().close()    # 纯连接：不得建表/写行（自动迁移门禁已删）
    db.connect().close()
    check('连接重开行数/字节不变', art_counts() == c0,
          '{} vs {}'.format(c0, art_counts()))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT DISTINCT task_file_id FROM extract_artifact')
            tfs = [r[0] for r in cur.fetchall()]
            cur.execute('SELECT id, sha256, size_bytes, content'
                        ' FROM extract_file')
            files = cur.fetchall()
            cur.execute(
                'SELECT COUNT(*) FROM extract_artifact a'
                ' LEFT JOIN extract_task_file tf ON tf.id=a.task_file_id'
                ' WHERE tf.id IS NULL')
            orphan_art = cur.fetchone()[0]
    finally:
        conn.close()
    check('无孤儿 artifact（反查=0）', orphan_art == 0,
          '悬空={}'.format(orphan_art))
    bad, n = [], 0
    for tf in tfs:
        for m in artifact_db.list(tf):
            n += 1
            a = artifact_db.get(tf, m['name'])
            if a is None or a['sha'] != m['sha'] \
                    or sha(a['data']) != m['sha'] \
                    or len(a['data']) != m['size']:
                bad.append('{}/{}'.format(tf, m['name']))
    check('附件全量读回 sha/size 自洽', not bad,
          '{} 个文件'.format(n) if not bad else '不一致：{}'.format(bad[:5]))
    bad_src = [r[0] for r in files
               if sha(r[3]) != r[1] or len(r[3]) != r[2]]
    check('extract_file.content sha/size 自洽', not bad_src,
          '{} 个原件'.format(len(files)) if not bad_src
          else '不一致 id：{}'.format(bad_src))

    print('[2/6] 真链路：无持久磁盘 + BLOB（临时服务 8799）')
    src = find_pdf_file()
    if src is None:
        print('  FAIL  extract_file 无 PDF 原件，无法真链路验收')
        return 1
    svc = start_service(8799)
    try:
        task_id, st = upload(8799, src['data'], src['name'])
        up.append(task_id)
        time.sleep(1)  # finally 清理 scratch 在 running=False 之后
        rtask = catalog.get_task(task_id)
        tf_id = rtask['files'][0]['task_file_id']
        check('真链路 previewed', st.get('error') is None
              and rtask['state'] == 'previewed'
              and rtask['files'][0]['state'] == 'previewed',
              'err={}'.format(st.get('error')))
        check('tmp/input+tmp/work 无 scratch 残留', scratch_clean())
        names = {m['name'] for m in artifact_db.list(tf_id)}
        check('产物入 BLOB', {config.EXTRACT_JSON,
                             config.EXTRACT_REPORT_NAME} <= names,
              '{} 个文件'.format(len(names)))

        print('[3/6] /files 路由：mime / ETag 304 / raw 403 / records 404')
        q = urllib.request.quote
        st1, h1, b1 = http(8799, '/files/{}/{}'.format(tf_id,
                           q(config.EXTRACT_JSON)))
        check('/files extract 200+mime', st1 == 200
              and h1.get('content-type', '').startswith('application/json')
              and json.loads(b1.decode()).get('schema'))
        st2, h2, _b2 = http(8799, '/files/{}/{}'.format(tf_id,
                            q(config.EXTRACT_REPORT_NAME)))
        check('/files 报告 200+html', st2 == 200
              and h2.get('content-type', '').startswith('text/html'))
        etag = h1.get('etag')
        st3, _h3, _b3 = http(8799, '/files/{}/{}'.format(tf_id,
                             q(config.EXTRACT_JSON)),
                             headers={'If-None-Match': etag} if etag else None)
        check('ETag 304', bool(etag) and st3 == 304, 'etag={}'.format(etag))
        st4, _h4, _b4 = http(8799, '/files/{}/raw/pdfplumber.json'.format(tf_id))
        check('raw 403', st4 == 403)
        st5, _h5, _b5 = http(8799, '/files/{}/records.json'.format(tf_id))
        check('records.json 404（DB 三表为事实源）', st5 == 404)
        st6, _h6, b6 = http(8799, '/srcfiles/{}'.format(src['id']))
        check('/srcfiles 200 + sha 一致', st6 == 200 and sha(b6) == src['sha'])

        print('[4/6] tasks / 报告重定向 / 暂存全查库（无磁盘依赖）')
        st, j = http_json(8799, '/api/tasks')
        check('tasks 列表含新 task', st == 200
              and any(r.get('task_id') == task_id for r in j['items']))
        st, j = http_json(8799, '/api/tasks/{}'.format(task_id))
        check('task 详情 previewed', st == 200
              and j['task']['files'][0]['state'] == 'previewed')
        req = urllib.request.Request('http://127.0.0.1:8799/extract-report')
        with urllib.request.urlopen(req, timeout=30) as r:
            check('报告重定向落 /files/', r.status == 200
                  and '/files/' in r.url and r.url.endswith(
                      q(config.EXTRACT_REPORT_NAME)))
        st, j = http_json(8799, '/api/tasks/{}/staging'.format(task_id))
        n_rec = rtask['files'][0]['records_n']
        check('暂存 API 记录数一致', st == 200 and n_rec > 0
              and len(j['files'][0]['records']) == n_rec,
              '{} 条'.format(n_rec))
        kw = next((str(v)[:4] for f in j['files'] for rec in f['records']
                   for v in rec['values'].values() if v not in (None, '')),
                  '流水')
        st, j = http_json(8799, '/api/staging/query?q=' + q(kw))
        check('跨 task 查询 200', st == 200 and j.get('ok')
              and len(j.get('items', [])) > 0)
    finally:
        svc.kill()

    print('[5/6] 导出字节一致 + records 重建')
    out_dir = tempfile.mkdtemp(prefix='c1_export_')
    try:
        p = subprocess.run(
            [sys.executable, os.path.join(PKG, 'export_artifacts.py'),
             '--task', str(up[0]), '--out', out_dir],
            cwd=PARENT, env=dict(os.environ, PYTHONUTF8='1'),
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=600)
        if p.returncode != 0:
            print(p.stdout[-2000:], p.stderr[-2000:])
        check('导出脚本退出 0', p.returncode == 0)
        task = catalog.get_task(up[0])
        base = os.path.join(out_dir, 'output', 'task_{}'.format(up[0]))
        bad = []
        for f in task['files']:
            for m in artifact_db.list(f['task_file_id']):
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
              '{} 个 task_file'.format(len(task['files'])) if not bad
              else '问题：{}'.format(bad[:5]))
        # sources：全量导出，重名加 _<id>（与 export 同算法核对）
        used, page = set(), 1
        while True:
            batch = catalog.list_files(page=page, per_page=100)
            for row in batch['items']:
                s = catalog.get_file_content(row['id'])
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
        rep = os.path.join(base, task['files'][0]['name'],
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
                                          src['data']).decode()}]})
        check('断库上传 503', st == 503, 'st={} err={}'.format(
            st, j.get('error')))
        st, _j = http_json(8797, '/api/tasks')
        check('断库 tasks 503', st == 503)
        st, _h, _b = http(8797, '/files/{}/{}'.format(
            tf_id, urllib.request.quote(config.EXTRACT_JSON)))
        check('断库 /files 503', st == 503)
        st, _h, _b = http(8797, '/extract-report')
        check('断库报告入口 503', st == 503)
        st, _j = http_json(8797, '/api/tasks/{}/staging'.format(up[0]))
        check('断库暂存 503', st == 503)
    finally:
        svc.kill()
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
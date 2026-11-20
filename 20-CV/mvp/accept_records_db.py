"""
mvp/accept_records_db.py — records 入库六项验收（DB-only 契约，
design-records-db.md + design-artifacts-db.md：DB 唯一事实源，无 file 模式）。

前置：CV_PLATFORM_DB 已配置（env 或 data/secrets.json，用户配置的库）。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u mvp/accept_records_db.py

1 回填幂等+真实 case 投影往返一致 · 2 重跑级联替换 · 3 patch_record ·
4 跨批查询 · 5 真链路（临时服务 8799）· 6 断库显式 503（临时服务 8797）。
磁盘已清空：上传字节取自 sources BLOB；断库用不可达 DSN 的临时服务模拟，
全程不触碰真实库的可用性。破坏性操作只落合成 case（_accept_tmp）与临时批次，
验完清理；真实 case 只读。用户的 8765 全程不动。
"""
import os
import sys
import json
import time
import base64
import shutil
import socket
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
mig = importlib.import_module(PKG + '.migrate_records_to_db')

# 本地无人监听的端口：模拟库不可达，凭据为假值，永不落日志
BAD_DSN = 'mysql://nobody:unused@127.0.0.1:3399/co_dev'
SYN_TAG = '99990101000000'
SYN_CASE = '_accept_tmp'
FAILS = []


def check(name, ok, detail=''):
    print('  {}  {}{}'.format('PASS' if ok else 'FAIL', name,
                              (' · ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


def http(port, path, body=None):
    req = urllib.request.Request(
        'http://127.0.0.1:{}{}'.format(port, path),
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


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


def counts():
    # 每次新开连接：避免 REPEATABLE READ 旧快照读到不变行数
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            out = []
            for t in ('extract_staging_record', 'extract_staging_field',
                      'extract_staging_lineage'):
                cur.execute('SELECT COUNT(*) FROM ' + t)
                out.append(cur.fetchone()[0])
            return tuple(out)
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


def upload(port, src_path, name):
    with open(src_path, 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    st, j = http(port, '/api/upload',
                 {'files': [{'name': name, 'data': data}], 'mode': 'preview'})
    if st != 200 or not j.get('ok'):
        raise RuntimeError('upload 失败：{}'.format(j))
    batch = j['batch']
    for _ in range(240):
        _, s = http(port, '/api/status')
        if not s.get('running'):
            return batch, s
        time.sleep(0.5)
    raise RuntimeError('upload 超时')


def _delete_batch_rows(cur, batch):
    # run_file→run 无级联：先子后父（field/lineage 随 record 级联）
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
    print('== records 入库验收 · {} =='.format(
        db.safe_detail(config.PLATFORM_DB_REF)))
    try:
        if not wait_db():
            print('配置库不可达，检查 CV_PLATFORM_DB（env / data/secrets.json）')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    conn = db.connect()  # 触发 001-004 迁移

    print('[1/6] 回填幂等 + 真实 case 投影往返一致')
    c0 = counts()
    mig.main()
    mig.main()
    c1 = counts()
    check('回填两遍行数不变', c0 == c1, '{} vs {}'.format(c0, c1))
    real = []
    for case, _tag in catalog.list_run_cases():
        if case not in [r[0] for r in real]:
            doc = content_db.get_records(case)
            if doc is not None:
                real.append((case, doc))
    tv = mig.ensure_template_version(conn, '原始透传', 1)
    run_id = mig.ensure_run(conn, SYN_TAG, 'preview', tv, {})
    syn_shas, src_real = [], None
    for case, doc in real:
        conn.commit()  # 结束旧快照：catalog 用独立连接提交，须读得到
        remap = json.loads(json.dumps(doc))
        for i, f in enumerate(remap['files']):
            fake = '{:064x}'.format(i + 1)
            syn_shas.append(fake)
            sid, _ = catalog.register_source(
                f['name'], 'pdf', 1, fake, 'sources/accept.pdf')
            f['source_file_id'] = sid
            f['run_file_id'] = mig.ensure_run_file(conn, run_id, sid, SYN_CASE)
        remap['run_id'] = run_id
        content_db.save_records(SYN_CASE, remap)
        got = content_db.get_records(SYN_CASE)
        ok = got is not None and len(got['files']) == len(doc['files'])
        if ok:
            for gf, wf in zip(got['files'], doc['files']):
                ok = ok and gf['records'] == wf['records']
        check('投影往返一致 ' + case, ok,
              '{} 条记录'.format(sum(len(f['records']) for f in doc['files'])))
        if src_real is None:
            for f in doc['files']:
                if f['records']:
                    src_real = f['records'][:2]
                    break
    if src_real is None:
        print('  FAIL  无可用真实记录，后续项无法执行')
        return 1

    print('[2/6] 重跑级联替换（合成 case）')
    syn_doc = {'schema': 'c1-extract-records/1', 'run_id': run_id,
               'template': {'name': '原始透传', 'version': 1},
               'files': [{'run_file_id': None, 'source_file_id': None,
                          'name': SYN_TAG + '_accept.pdf',
                          'records': json.loads(json.dumps(src_real))}]}
    sid, _ = catalog.register_source('accept.pdf', 'pdf', 22,
                                     '0' * 64, 'sources/00000000_accept.pdf')
    syn_shas.append('0' * 64)
    conn.commit()  # 同上：刷新快照再查 run_file
    rf = mig.ensure_run_file(conn, run_id, sid, SYN_CASE)
    syn_doc['files'][0]['run_file_id'] = rf
    syn_doc['files'][0]['source_file_id'] = sid
    content_db.save_records(SYN_CASE, syn_doc)
    n2 = counts()
    one = json.loads(json.dumps(syn_doc))
    one['files'][0]['records'] = one['files'][0]['records'][:1]
    content_db.save_records(SYN_CASE, one)
    n1 = counts()
    content_db.save_records(SYN_CASE, syn_doc)
    n2b = counts()
    check('2→1→2 级联', n1[0] == n2[0] - 1 and n2b == n2,
          '{}→{}→{}'.format(n2, n1, n2b))

    print('[3/6] patch_record 语义')
    ok, rec = content.patch_record(SYN_CASE, 0, 0, {'摘要': 'ACCEPT_EDIT'})
    back = content_db.get_records(SYN_CASE)['files'][0]['records'][0]
    check('edited+original 不变+DB 读回一致',
          ok and rec['review']['state'] == 'edited'
          and rec['original'] == src_real[0]['original']
          and rec['values']['摘要'] == 'ACCEPT_EDIT'
          and back['values']['摘要'] == 'ACCEPT_EDIT'
          and back['review']['state'] == 'edited')

    print('[4/6] 跨批查询')
    hit = content_db.query_fields(field='摘要', q='ACCEPT_EDIT')
    hit2 = content_db.query_fields(q='报销')
    check('field 投影命中', any(h['case'] == SYN_CASE for h in hit)
          and len(hit2) > 0, 'syn={} real={}'.format(len(hit), len(hit2)))

    print('[5/6] 真链路（临时服务 8799，上传字节取自 sources BLOB）')
    src = artifact_db.get('sources', '83ef00a8_招行流水（已脱敏）.pdf')
    if src is None:
        print('  FAIL  sources BLOB 缺招行流水 PDF，无法真链路验收')
        return 1
    fd, pdf = tempfile.mkstemp(suffix='.pdf', prefix='cv_accept_')
    with os.fdopen(fd, 'wb') as f:
        f.write(src['data'])
    svc = start_service(8799)
    up_batch = None
    try:
        batch, st = upload(8799, pdf, '招行流水（已脱敏）.pdf')
        up_batch = batch
        case = batch + '_招行流水_已脱敏_'
        time.sleep(1)  # finally 清理 scratch 在 running=False 之后
        rj = content_db.get_records(case)
        rrun = content.get_run(case)
        check('真链路 previewed',
              st.get('error') is None
              and rrun and rrun['files'][0]['state'] == 'previewed'
              and rj['files'][0]['run_file_id'] is not None,
              'state={} rf_id={} err={}'.format(
                  rrun['files'][0]['state'], rj['files'][0]['run_file_id'],
                  st.get('error')))
        check('无持久 output/input 副本',
              not os.path.exists(os.path.join(config.OUTPUT_DIR, case))
              and not any(n.startswith(batch + '_')
                          for n in os.listdir(config.INPUT_DIR)))
        stq, jq = http(8799, '/api/runs/{}/staging'.format(batch))
        check('暂存 API 24 条', stq == 200
              and len(jq['files'][0]['records']) == 24)
        stq, jq = http(8799, '/api/staging/query?q=' +
                       urllib.request.quote('报销'))
        check('查询 API 200', stq == 200 and jq.get('ok')
              and len(jq.get('items', [])) > 0)
    finally:
        svc.kill()
        os.remove(pdf)

    print('[6/6] 断库显式 503（临时服务 8797，不可达 DSN）')
    svc_down = start_service(8797, BAD_DSN)
    try:
        data = base64.b64encode(src['data']).decode()
        st, j = http(8797, '/api/upload',
                     {'files': [{'name': '招行流水（已脱敏）.pdf',
                                 'data': data}], 'mode': 'preview'})
        check('断库上传 503（不建 run）', st == 503, 'st={}'.format(st))
        st, _j = http(8797, '/api/runs')
        check('断库 runs 503', st == 503)
        st, _j = http(8797, '/api/runs/{}/staging'.format(up_batch))
        check('断库暂存读 503（无快照回落）', st == 503)
        st, _j = http(8797, '/api/templates')
        check('断库模板 503（不降级）', st == 503)
    finally:
        svc_down.kill()

    print('清理临时产物')
    if up_batch:
        cleanup_batch(up_batch)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _delete_batch_rows(cur, SYN_TAG)
            if syn_shas:
                ph = ','.join(['%s'] * len(syn_shas))
                cur.execute(
                    'DELETE FROM extract_source_file WHERE sha256 IN ({})'
                    .format(ph), syn_shas)
        conn.commit()
    finally:
        conn.close()

    print('\n结论：{}'.format('六项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
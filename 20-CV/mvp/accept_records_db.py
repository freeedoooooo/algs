"""
mvp/accept_records_db.py — 选项 B 六项验收（design-records-db.md §6，
契约已按 design-artifacts-db.md 更新：自动快照退役、DB 必选不降级）。

前置：CV_PLATFORM_DB 已配置（env 或 data/secrets.json，用户配置的库）。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u mvp/accept_records_db.py

本脚本验 RECORDS_STORE=db + ARTIFACT_STORE=file（产物仍磁盘）。
库故障用「不可达 DSN 的临时服务」模拟，全程不触碰真实库的可用性。
破坏性操作只落在合成 case（_accept_tmp）与临时批次，验完清理；
真实 case 仅做迁移回填（id 补齐 + schema 刷新，设计内行为）。
临时服务 8799(db)/8797(db 不可达)/8798(file)，用户的 8765 全程不动。
"""
import os
import sys
import json
import time
import base64
import shutil
import socket
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
os.environ['CV_MVP_RECORDS_STORE'] = 'db'
os.environ.setdefault('PYTHONUTF8', '1')
config = importlib.import_module(PKG + '.config')
db = importlib.import_module(PKG + '.store.db')
catalog = importlib.import_module(PKG + '.store.catalog')
content = importlib.import_module(PKG + '.store.content')
content_db = importlib.import_module(PKG + '.store.content_db')
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


def start_service(port, store, dsn=None):
    env = dict(os.environ, CV_MVP_RECORDS_STORE=store, CV_MVP_PORT=str(port),
               CV_MVP_WARMUP='0')
    if dsn:
        env['CV_PLATFORM_DB'] = dsn
    else:
        env.pop('CV_PLATFORM_DB', None)
    p = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'mvp.app:app',
         '--host', '127.0.0.1', '--port', str(port)],
        cwd=PARENT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_http(port):
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


def case_doc(case):
    with open(os.path.join(config.OUTPUT_DIR, case, config.RECORDS_JSON),
              encoding='utf-8') as f:
        return json.load(f)


def run_doc(case):
    with open(os.path.join(config.OUTPUT_DIR, case, config.RUN_JSON),
              encoding='utf-8') as f:
        return json.load(f)


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
    for d in os.listdir(config.OUTPUT_DIR):
        if d.startswith(batch + '_'):
            shutil.rmtree(os.path.join(config.OUTPUT_DIR, d), ignore_errors=True)
    for d in os.listdir(config.INPUT_DIR):
        if d.startswith(batch + '_'):
            os.remove(os.path.join(config.INPUT_DIR, d))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _delete_batch_rows(cur, batch)
        conn.commit()
    finally:
        conn.close()


def main():
    print('== 选项 B 验收 · {} =='.format(db.safe_detail(config.PLATFORM_DB_REF)))
    try:
        if not wait_db():
            print('配置库不可达，检查 CV_PLATFORM_DB（env / data/secrets.json）')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    conn = db.connect()  # 触发 001-003 迁移

    print('[1/6] 迁移幂等 + 逐字段一致')
    real = [d for d in sorted(os.listdir(config.OUTPUT_DIR))
            if os.path.isfile(os.path.join(config.OUTPUT_DIR, d,
                                           config.RECORDS_JSON))
            and d[:14].isdigit()]
    pre = {d: case_doc(d) for d in real}
    mig.main()
    c1 = counts()
    mig.main()
    c2 = counts()
    check('两遍行数不变', c1 == c2, '{} vs {}'.format(c1, c2))
    for d in real:
        got = content_db.get_records(d)
        want = pre[d]
        ok = got is not None and len(got['files']) == len(want['files'])
        if ok:
            for gf, wf in zip(got['files'], want['files']):
                ok = ok and gf['name'] == wf['name'] \
                    and gf['records'] == wf['records']
        check('逐字段一致 ' + d, ok)

    print('[2/6] 重跑级联替换（合成 case）')
    src_real = pre[real[0]]['files'][0]['records'][:2]
    syn_doc = {'schema': 'c1-extract-records/1', 'run_id': None,
               'template': {'name': '原始透传', 'version': 1},
               'files': [{'run_file_id': None, 'source_file_id': None,
                          'name': SYN_TAG + '_accept.pdf',
                          'records': json.loads(json.dumps(src_real))}]}
    dummy = os.path.join(config.INPUT_DIR, SYN_TAG + '_accept.pdf')
    with open(dummy, 'wb') as f:
        f.write(b'%PDF-1.4 accept dummy')
    tv = mig.ensure_template_version(conn, '原始透传', 1)
    run_id = mig.ensure_run(conn, SYN_TAG, 'preview', tv, {})
    sid, _ = catalog.register_source('accept.pdf', 'pdf', 22,
                                     '0' * 64, 'sources/00000000_accept.pdf')
    rf = mig.ensure_run_file(conn, run_id, sid, SYN_CASE)
    syn_doc['run_id'] = run_id
    syn_doc['files'][0]['run_file_id'] = rf
    syn_doc['files'][0]['source_file_id'] = sid
    os.makedirs(os.path.join(config.OUTPUT_DIR, SYN_CASE), exist_ok=True)
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

    print('[5/6] 真链路 + 断库显式失败（临时服务 8799 / 8797）')
    pdf = os.path.join(config.INPUT_DIR,
                       '20261120211314_招行流水（已脱敏）.pdf')
    svc = start_service(8799, 'db')
    svc_down = None
    try:
        batch, st = upload(8799, pdf, '招行流水（已脱敏）.pdf')
        case = batch + '_招行流水_已脱敏_'
        rj = content_db.get_records(case)
        rrun = run_doc(case)
        check('db 模式真链路 previewed',
              st.get('error') is None
              and rrun['files'][0]['state'] == 'previewed'
              and rj['files'][0]['run_file_id'] is not None,
              'state={} rf_id={} err={}'.format(
                  rrun['files'][0]['state'], rj['files'][0]['run_file_id'],
                  st.get('error')))
        stq, jq = http(8799, '/api/staging/query?q=' +
                       urllib.request.quote('报销'))
        check('查询 API 200', stq == 200 and jq.get('ok')
              and len(jq.get('items', [])) > 0)
        up_batch = batch
        # 断库：不可达 DSN 的独立服务（真实库不受影响）。
        # 新契约：无快照回落 —— 运行显式 failed，旧数据读 503。
        svc_down = start_service(8797, 'db', BAD_DSN)
        batch2, st2 = upload(8797, pdf, '招行流水（已脱敏）.pdf')
        case2 = batch2 + '_招行流水_已脱敏_'
        rep2 = os.path.isfile(os.path.join(config.OUTPUT_DIR, case2,
                                           config.EXTRACT_REPORT_NAME))
        ext2 = os.path.isfile(os.path.join(config.OUTPUT_DIR, case2,
                                           config.EXTRACT_JSON))
        check('断库：引擎照常+运行显式 failed',
              run_doc(case2)['state'] == 'failed'
              and rep2 and ext2,
              'state={}'.format(run_doc(case2)['state']))
        sto, jo = http(8797, '/api/runs/{}/staging'.format(up_batch))
        check('断库：暂存读 503（无快照回落）', sto == 503)
        down_batch = batch2
    finally:
        svc.kill()
        if svc_down:
            svc_down.kill()

    print('[6/6] 回滚 file 模式（临时服务 8798，DB 不可达）')
    svc2 = start_service(8798, 'file', BAD_DSN)
    try:
        batch3, st3 = upload(8798, pdf, '招行流水（已脱敏）.pdf')
        case3 = batch3 + '_招行流水_已脱敏_'
        check('file 模式无 DB 照常', st3.get('error') is None
              and run_doc(case3)['files'][0]['state'] == 'previewed'
              and os.path.isfile(os.path.join(config.OUTPUT_DIR, case3,
                                              config.RECORDS_JSON)))
        rollback_batch = batch3
    finally:
        svc2.kill()

    print('清理临时产物')
    for b in (up_batch, down_batch, rollback_batch):
        cleanup_batch(b)
    shutil.rmtree(os.path.join(config.OUTPUT_DIR, SYN_CASE), ignore_errors=True)
    if os.path.isfile(dummy):
        os.remove(dummy)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _delete_batch_rows(cur, SYN_TAG)
            cur.execute('DELETE FROM extract_source_file WHERE sha256=%s',
                        ('0' * 64,))
        conn.commit()
    finally:
        conn.close()

    print('\n结论：{}'.format('六项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
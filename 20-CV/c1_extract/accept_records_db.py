"""
c1_extract/accept_records_db.py — records 入库六项验收（C1 契约，
design-c1-storage.md：DB 唯一事实源，run_id / run_file_id 粒度，无 file 模式）。

前置：C1_EXTRACT_DB 已配置（env 或 data/secrets.json，用户配置的库）。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u c1_extract/accept_records_db.py

1 迁移门禁幂等+真实 run 投影往返一致 · 2 重跑级联替换 · 3 patch_record ·
4 跨 run 查询 · 5 真链路（临时服务 8799）· 6 断库显式 503（临时服务 8797）。
上传字节取自 source_file.content；断库用不可达 DSN 的临时服务模拟，
全程不触碰真实库的可用性。破坏性操作只落合成 run（验完按 id 清理，
附件随 run_file FK 级联）；真实 run / source 只读。用户的 8765 全程不动。
两套验收脚本严禁并行（共用 8799/8797 端口）。
"""
import os
import sys
import json
import time
import base64
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

# 本地无人监听的端口：模拟库不可达，凭据为假值，永不落日志
BAD_DSN = 'mysql://nobody:unused@127.0.0.1:3399/co_dev'
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
    st, j = http(port, '/api/upload',
                 {'files': [{'name': name,
                             'data': base64.b64encode(src_bytes).decode()}],
                  'mode': 'preview'})
    if st != 200 or not j.get('ok'):
        raise RuntimeError('upload 失败：{} {}'.format(st, j))
    run_id = j['run_id']
    for _ in range(300):
        _, s = http(port, '/api/status')
        if not s.get('running'):
            return run_id, s
        time.sleep(0.5)
    raise RuntimeError('upload 超时')


def find_pdf_source():
    """真实原件（source_file.content）里第一个 PDF，真链路上传字节来源。
    size>1KB 过滤：排除验收合成的假 PDF 行。"""
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


def cleanup_runs(run_ids, source_ids):
    """按 run id 先子后父：staging_record 无级联须显式删（field/lineage 随
    record 级联）；artifact 随 run_file FK 级联；合成 source 只删本次新建的。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for rid in run_ids:
                cur.execute(
                    'DELETE sr FROM extract_staging_record sr'
                    ' JOIN extract_run_file rf ON rf.id=sr.run_file_id'
                    ' WHERE rf.run_id=%s', (rid,))
                cur.execute('DELETE FROM extract_quarantine WHERE run_id=%s',
                            (rid,))
                cur.execute('DELETE FROM extract_load_log WHERE run_id=%s',
                            (rid,))
                cur.execute('DELETE FROM extract_run_file WHERE run_id=%s',
                            (rid,))
                cur.execute('DELETE FROM extract_run WHERE id=%s', (rid,))
            if source_ids:
                ph = ','.join(['%s'] * len(source_ids))
                cur.execute(
                    'DELETE FROM extract_source_file WHERE id IN ({})'
                    .format(ph), source_ids)
            # 真链路若误传合成字节会按真实 sha 新建 source 行（去重不命中
            # 假 sha）：按合成内容 sha 兜底清理，只删未被引用的
            syn_shas = [hashlib.sha256(b'%PDF-1.4 accept').hexdigest(),
                        hashlib.sha256(b'%PDF-1.4 accept-two').hexdigest()]
            cur.execute(
                'DELETE FROM extract_source_file WHERE sha256 IN (%s,%s)'
                ' AND id NOT IN (SELECT source_file_id FROM extract_run_file)',
                syn_shas)
        conn.commit()
    finally:
        conn.close()


def main():
    print('== records 入库验收（C1）· {} =='.format(
        db.safe_detail(config.PLATFORM_DB_REF)))
    try:
        if not wait_db():
            print('配置库不可达，检查 C1_EXTRACT_DB（env / data/secrets.json）')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    db.connect().close()  # 触发 001-006 迁移门禁
    syn_runs, syn_sids, up = [], [], []
    try:
        rc = _main(syn_runs, syn_sids, up)
    finally:
        print('清理临时产物')
        cleanup_runs(syn_runs + up, syn_sids)
    print('\n结论：{}'.format('六项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return rc


def _main(syn_runs, syn_sids, up):
    print('[1/6] 迁移门禁幂等 + 真实 run 投影往返一致')
    c0 = counts()
    db._READY.clear()       # 强制重跑门禁：schema_version 已全，应零变更
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT version FROM schema_version ORDER BY version')
            vers = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    check('门禁重跑零变更 + schema 1-6', counts() == c0 and vers == [1, 2, 3, 4, 5, 6],
          '{} vs {} · {}'.format(c0, counts(), vers))
    tv = catalog.get_template_version(name='原始透传')
    real = []
    for run in catalog.list_runs():
        doc = content_db.get_records(run['run_id'])
        if doc and any(f['records'] for f in doc['files']):
            real.append(doc)
    if not real:
        print('  FAIL  无可用真实记录，后续项无法执行')
        return 1
    src_real, field, real_kw = None, None, None
    for doc in real:
        run_id = catalog.create_run('preview', tv['id'], {})
        syn_runs.append(run_id)
        remap = json.loads(json.dumps(doc))
        remap['run_id'] = run_id
        for i, f in enumerate(remap['files']):
            fake = '{:064x}'.format(i + 1)
            sid, dup = catalog.register_source(
                f['name'], 'pdf', 1, fake, b'%PDF-1.4 accept')
            if not dup:
                syn_sids.append(sid)
            f['source_file_id'] = sid
            f['run_file_id'] = catalog.add_run_file(run_id, sid)
        content_db.save_records(remap)
        got = content_db.get_records(run_id)
        ok = got is not None and len(got['files']) == len(doc['files'])
        if ok:
            for gf, wf in zip(got['files'], doc['files']):
                ok = ok and gf['records'] == wf['records'] \
                    and gf['name'] == wf['name']
        check('投影往返一致 run {}'.format(doc['run_id']), ok,
              '{} 条记录'.format(sum(len(f['records']) for f in doc['files'])))
        if src_real is None:
            for f in doc['files']:
                if f['records']:
                    src_real = f['records'][:2]
                    vals = src_real[0]['values']
                    field = next(iter(vals))
                    real_kw = next((str(v)[:4] for v in vals.values()
                                    if v not in (None, '')), '流水')
                    break

    print('[2/6] 重跑级联替换（合成 run）')
    run2 = catalog.create_run('preview', tv['id'], {})
    syn_runs.append(run2)
    sid, dup = catalog.register_source('accept.pdf', 'pdf', 22, '0' * 64,
                                       b'%PDF-1.4 accept-two')
    if not dup:
        syn_sids.append(sid)
    rf = catalog.add_run_file(run2, sid)
    syn_doc = {'schema': 'c1-extract-records/1', 'run_id': run2,
               'template': {'name': tv['name'], 'version': tv['version']},
               'files': [{'run_file_id': rf, 'source_file_id': sid,
                          'name': 'accept.pdf',
                          'records': json.loads(json.dumps(src_real))}]}
    content_db.save_records(syn_doc)
    n2 = counts()
    one = json.loads(json.dumps(syn_doc))
    one['files'][0]['records'] = one['files'][0]['records'][:1]
    content_db.save_records(one)
    n1 = counts()
    content_db.save_records(syn_doc)
    n2b = counts()
    check('2→1→2 级联', n1[0] == n2[0] - 1 and n2b == n2,
          '{}→{}→{}'.format(n2, n1, n2b))

    print('[3/6] patch_record 语义')
    ok, rec = content.patch_record(run2, 0, 0, {field: 'ACCEPT_EDIT'})
    back = content_db.get_records(run2)['files'][0]['records'][0]
    check('edited+original 不变+DB 读回一致',
          ok and rec['review']['state'] == 'edited'
          and rec['original'] == src_real[0]['original']
          and rec['values'][field] == 'ACCEPT_EDIT'
          and back['values'][field] == 'ACCEPT_EDIT'
          and back['review']['state'] == 'edited')

    print('[4/6] 跨 run 查询')
    hit = content_db.query_fields(field=field, q='ACCEPT_EDIT')
    hit2 = content_db.query_fields(q=real_kw)
    check('field 投影命中', any(h['run_id'] == run2 for h in hit)
          and len(hit2) > 0, 'syn={} real={}'.format(len(hit), len(hit2)))

    print('[5/6] 真链路（临时服务 8799，上传字节取自 source_file.content）')
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
        check('真链路 previewed',
              st.get('error') is None and rrun['state'] == 'previewed'
              and rrun['files'][0]['state'] == 'previewed',
              'state={} rf_id={} err={}'.format(
                  rrun['state'], rf_id, st.get('error')))
        check('无持久 scratch 副本', scratch_clean())
        stq, jq = http(8799, '/api/runs/{}/staging'.format(run_id))
        n_rec = rrun['files'][0]['records_n']
        check('暂存 API 记录数一致', stq == 200 and n_rec > 0
              and len(jq['files'][0]['records']) == n_rec,
              '{} 条'.format(n_rec))
        stq, jq = http(8799, '/api/staging/query?q=' +
                       urllib.request.quote(real_kw))
        check('查询 API 200', stq == 200 and jq.get('ok')
              and len(jq.get('items', [])) > 0)
    finally:
        svc.kill()

    print('[6/6] 断库显式 503（临时服务 8797，不可达 DSN）')
    svc_down = start_service(8797, BAD_DSN)
    try:
        st, j = http(8797, '/api/upload',
                     {'files': [{'name': src['name'],
                                 'data': base64.b64encode(
                                     src['data']).decode()}],
                      'mode': 'preview'})
        check('断库上传 503（不建 run）', st == 503, 'st={}'.format(st))
        st, _j = http(8797, '/api/runs')
        check('断库 runs 503', st == 503)
        st, _j = http(8797, '/api/runs/{}/staging'.format(up[0]))
        check('断库暂存读 503（无快照回落）', st == 503)
        st, _j = http(8797, '/api/templates')
        check('断库模板 503（不降级）', st == 503)
    finally:
        svc_down.kill()
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
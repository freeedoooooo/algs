"""
c1_extract/accept_records_db.py — records 入库六项验收（任务化契约，
design-task-schema.md：DB 唯一事实源，task_id / task_file_id 粒度，无外键）。

前置：C1_EXTRACT_DB 已配置（env 或 data/secrets.json，用户配置的库）。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u c1_extract/accept_records_db.py

1 迁移门禁幂等+真实 task 投影往返一致 · 2 重跑级联替换（应用层）· 3 patch_record ·
4 跨 task 查询 · 5 真链路（临时服务 8799）· 6 断库显式 503（临时服务 8797）。
上传字节取自 extract_file.content；断库用不可达 DSN 的临时服务模拟，
全程不触碰真实库的可用性。破坏性操作只落合成 task（验完按 id 清理，
无外键：field/lineage/artifact 等子表须显式先删）；真实 task / file 只读。
用户的 8765 全程不动。两套验收脚本严禁并行（共用 8799/8797 端口）。
"""
import os
import sys
import json
import time
import base64
import socket
import hashlib
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


def orphan_counts():
    """无外键后引用完整性归应用层：反查三张子表不得有悬空引用。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            out = []
            for sql in (
                    'SELECT COUNT(*) FROM extract_staging_field f'
                    ' LEFT JOIN extract_staging_record r ON r.id=f.record_id'
                    ' WHERE r.id IS NULL',
                    'SELECT COUNT(*) FROM extract_staging_lineage l'
                    ' LEFT JOIN extract_staging_record r ON r.id=l.record_id'
                    ' WHERE r.id IS NULL',
                    'SELECT COUNT(*) FROM extract_staging_record sr'
                    ' LEFT JOIN extract_task_file tf ON tf.id=sr.task_file_id'
                    ' WHERE tf.id IS NULL'):
                cur.execute(sql)
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
    task_id = j['task_id']
    for _ in range(300):
        _, s = http(port, '/api/status')
        if not s.get('running'):
            return task_id, s
        time.sleep(0.5)
    raise RuntimeError('upload 超时')


def find_pdf_file():
    """真实原件（extract_file.content）里第一个 PDF，真链路上传字节来源。
    size>1KB 过滤：排除验收合成的假 PDF 行。"""
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


def scratch_clean():
    return not any(
        n.startswith(('in_', 'case_'))
        for d in (config.TMP_INPUT, config.TMP_WORK)
        for n in os.listdir(d))


def cleanup_tasks(task_ids, file_ids):
    """按 task id 先子后父（无外键，全部显式删）：field/lineage→record→
    artifact→quarantine→load_log→task_file→task；合成 file 只删本次新建的。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for tid in task_ids:
                cur.execute(
                    'SELECT id FROM extract_task_file WHERE task_id=%s',
                    (tid,))
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
                        'DELETE FROM extract_staging_record'
                        ' WHERE task_file_id=%s', (tf,))
                    cur.execute(
                        'DELETE FROM extract_artifact WHERE task_file_id=%s',
                        (tf,))
                cur.execute('DELETE FROM extract_quarantine WHERE task_id=%s',
                            (tid,))
                cur.execute('DELETE FROM extract_load_log WHERE task_id=%s',
                            (tid,))
                cur.execute('DELETE FROM extract_task_file WHERE task_id=%s',
                            (tid,))
                cur.execute('DELETE FROM extract_task WHERE id=%s', (tid,))
            if file_ids:
                ph = ','.join(['%s'] * len(file_ids))
                cur.execute(
                    'DELETE FROM extract_file WHERE id IN ({})'
                    .format(ph), file_ids)
            # 真链路若误传合成字节会按真实 sha 新建 file 行（去重不命中
            # 假 sha）：按合成内容 sha 兜底清理，只删未被引用的
            syn_shas = [hashlib.sha256(b'%PDF-1.4 accept').hexdigest(),
                        hashlib.sha256(b'%PDF-1.4 accept-two').hexdigest()]
            cur.execute(
                'DELETE FROM extract_file WHERE sha256 IN (%s,%s)'
                ' AND id NOT IN (SELECT file_id FROM extract_task_file)',
                syn_shas)
        conn.commit()
    finally:
        conn.close()


def main():
    print('== records 入库验收（任务化）· {} =='.format(
        db.safe_detail(config.PLATFORM_DB_REF)))
    try:
        if not wait_db():
            print('配置库不可达，检查 C1_EXTRACT_DB（env / data/secrets.json）')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    db.connect().close()  # 触发 001 baseline 迁移门禁
    syn_tasks, syn_fids, up = [], [], []
    try:
        rc = _main(syn_tasks, syn_fids, up)
    finally:
        print('清理临时产物')
        cleanup_tasks(syn_tasks + up, syn_fids)
    print('\n结论：{}'.format('六项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return rc


def _main(syn_tasks, syn_fids, up):
    print('[1/6] 迁移门禁幂等 + 真实 task 投影往返一致')
    c0 = counts()
    db._READY.clear()       # 强制重跑门禁：baseline 已应用，应零变更
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT version FROM schema_version ORDER BY version')
            vers = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    check('门禁重跑零变更 + schema baseline [1]',
          counts() == c0 and vers == [1],
          '{} vs {} · {}'.format(c0, counts(), vers))
    tv = catalog.get_template_version()
    real = []
    for task in catalog.list_tasks():
        doc = content_db.get_records(task['task_id'])
        if doc and any(f['records'] for f in doc['files']):
            real.append(doc)
    if not real:
        print('  FAIL  无可用真实记录，后续项无法执行')
        return 1
    src_real, field, real_kw = None, None, None
    for doc in real:
        task_id = catalog.create_task('preview', tv['id'], {})
        syn_tasks.append(task_id)
        remap = json.loads(json.dumps(doc))
        remap['task_id'] = task_id
        for i, f in enumerate(remap['files']):
            fake = '{:064x}'.format(i + 1)
            fid, dup = catalog.register_file(
                f['name'], 'pdf', 1, fake, b'%PDF-1.4 accept')
            if not dup:
                syn_fids.append(fid)
            f['file_id'] = fid
            f['task_file_id'] = catalog.add_task_file(task_id, fid)
        content_db.save_records(remap)
        got = content_db.get_records(task_id)
        ok = got is not None and len(got['files']) == len(doc['files'])
        if ok:
            for gf, wf in zip(got['files'], doc['files']):
                ok = ok and gf['records'] == wf['records'] \
                    and gf['name'] == wf['name']
        check('投影往返一致 task {}'.format(doc['task_id']), ok,
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

    print('[2/6] 重跑级联替换（合成 task，应用层先删子表）')
    task2 = catalog.create_task('preview', tv['id'], {})
    syn_tasks.append(task2)
    fid, dup = catalog.register_file('accept.pdf', 'pdf', 22, '0' * 64,
                                     b'%PDF-1.4 accept-two')
    if not dup:
        syn_fids.append(fid)
    tf = catalog.add_task_file(task2, fid)
    syn_doc = {'schema': 'c1-extract-records/1', 'task_id': task2,
               'template': {'name': tv['name'], 'version': tv['version']},
               'files': [{'task_file_id': tf, 'file_id': fid,
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
    orph = orphan_counts()
    check('无孤儿 field/lineage/record（反查=0）', orph == (0, 0, 0),
          'field/lineage/record 悬空={}'.format(orph))

    print('[3/6] patch_record 语义')
    ok, rec = content.patch_record(task2, 0, 0, {field: 'ACCEPT_EDIT'})
    back = content_db.get_records(task2)['files'][0]['records'][0]
    check('edited+original 不变+DB 读回一致',
          ok and rec['review']['state'] == 'edited'
          and rec['original'] == src_real[0]['original']
          and rec['values'][field] == 'ACCEPT_EDIT'
          and back['values'][field] == 'ACCEPT_EDIT'
          and back['review']['state'] == 'edited')

    print('[4/6] 跨 task 查询')
    hit = content_db.query_fields(field=field, q='ACCEPT_EDIT')
    hit2 = content_db.query_fields(q=real_kw)
    check('field 投影命中', any(h['task_id'] == task2 for h in hit)
          and len(hit2) > 0, 'syn={} real={}'.format(len(hit), len(hit2)))

    print('[5/6] 真链路（临时服务 8799，上传字节取自 extract_file.content）')
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
        check('真链路 previewed',
              st.get('error') is None and rtask['state'] == 'previewed'
              and rtask['files'][0]['state'] == 'previewed',
              'state={} tf_id={} err={}'.format(
                  rtask['state'], tf_id, st.get('error')))
        check('tmp/input+tmp/work 无 scratch 残留', scratch_clean())
        stq, jq = http(8799, '/api/tasks/{}/staging'.format(task_id))
        n_rec = rtask['files'][0]['records_n']
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
        check('断库上传 503（不建 task）', st == 503, 'st={}'.format(st))
        st, _j = http(8797, '/api/tasks')
        check('断库 tasks 503', st == 503)
        st, _j = http(8797, '/api/tasks/{}/staging'.format(up[0]))
        check('断库暂存读 503（无快照回落）', st == 503)
        st, _j = http(8797, '/api/templates')
        check('断库模板 503（不降级）', st == 503)
    finally:
        svc_down.kill()
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
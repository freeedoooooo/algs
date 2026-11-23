"""
c1_structure/accept_records_db.py — records 入库七项验收（任务化契约，
DB 唯一事实源，task_id / task_file_id 粒度，无外键）。

前置：C1_STRUCTURE_DB 已配置（环境变量或 config.PLATFORM_DB 默认值，用户配置的库）。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u c1_structure/accept_records_db.py

1 连接零副作用+真实 task 投影往返一致 · 2 重跑级联替换（应用层）· 3 patch/set_review ·
4 跨 task 查询 · 5 真链路（临时服务 8799，含 P1 校验路由冒烟）· 6 断库显式 503（临时服务 8797）·
7 P2c 入库（合成目标表 _accept_p2_load＋合成抽取规则/数据源/映射：上传不带模式、
入库时绑定目标（预检/门禁失败不留绑定可换目标）、已绑定锁死 409、
门禁 409、全部确认→loaded、回执幂等、transform/数据级隔离→to_load、重试、upsert update、
数据源目标锁定/映射只读审计）。
上传字节取自 c1_doc_file.content；断库用不可达 DSN 的临时服务模拟，
全程不触碰真实库的可用性。破坏性操作只落合成 task/抽取规则/数据源/目标表（验完按 id 清理＋DROP，
无外键：field/lineage/artifact 等子表须显式先删）；真实 task / file / 抽取规则只读。
用户的 8765 全程不动。两套验收脚本严禁并行（共用 8799/8797 端口）。
"""
import os
import sys
import json
import time
import base64
import socket
import shutil
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
errors = importlib.import_module(PKG + '.store.errors')

# 本地无人监听的端口：模拟库不可达，凭据为假值，永不落日志
BAD_DSN = 'mysql://nobody:unused@127.0.0.1:3399/c1_structure_dev'
P2_TABLE = '_accept_p2_load'
FAILS = []


def check(name, ok, detail=''):
    print('  {}  {}{}'.format('PASS' if ok else 'FAIL', name,
                              (' · ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


def http(port, path, body=None, timeout=30, method=None):
    req = urllib.request.Request(
        'http://127.0.0.1:{}{}'.format(port, path),
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
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
    p = db._parts(db.resolve_conn(config.PLATFORM_DB))
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
            for t in ('c1_staging_record', 'c1_staging_field',
                      'c1_staging_lineage'):
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
                    'SELECT COUNT(*) FROM c1_staging_field f'
                    ' LEFT JOIN c1_staging_record r ON r.id=f.record_id'
                    ' WHERE r.id IS NULL',
                    'SELECT COUNT(*) FROM c1_staging_lineage l'
                    ' LEFT JOIN c1_staging_record r ON r.id=l.record_id'
                    ' WHERE r.id IS NULL',
                    'SELECT COUNT(*) FROM c1_staging_record sr'
                    ' LEFT JOIN c1_task_file tf ON tf.id=sr.task_file_id'
                    ' WHERE tf.id IS NULL'):
                cur.execute(sql)
                out.append(cur.fetchone()[0])
            return tuple(out)
    finally:
        conn.close()


def baseline():
    """全量基线快照：验收清理后必须逐项守恒（真实数据不可动的量化守卫）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*), COALESCE(SUM(size_bytes),0)'
                        ' FROM c1_parse_artifact')
            art = tuple(cur.fetchone())
            out = [counts(), art]
            for sql in ('SELECT COUNT(*) FROM c1_doc_file',
                        'SELECT id FROM c1_task ORDER BY id',
                        'SELECT COUNT(*) FROM c1_extract_rule',
                        'SELECT COUNT(*) FROM c1_extract_rule_version',
                        'SELECT COUNT(*) FROM c1_load_datasource',
                        'SELECT COUNT(*) FROM c1_load_table',
                        'SELECT COUNT(*) FROM c1_load_table_field',
                        'SELECT COUNT(*) FROM c1_load_log',
                        'SELECT COUNT(*) FROM c1_load_quarantine'):
                cur.execute(sql)
                rows = cur.fetchall()
                out.append(tuple(r[0] for r in rows))
            return tuple(out)
    finally:
        conn.close()


def p2_cleanup(p2):
    """P2c 合成对象清理（在 cleanup_tasks 之后跑，引用已空）：
    字段行/映射/数据源/抽取规则＋DROP 表。"""
    if not p2:
        return
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for lid in p2.get('lts', []):
                cur.execute('DELETE FROM c1_load_table_field'
                            ' WHERE load_table_id=%s', (lid,))
                cur.execute('DELETE FROM c1_load_table WHERE id=%s',
                            (lid,))
            for did in p2.get('dss', []):
                cur.execute('DELETE FROM c1_load_datasource'
                            ' WHERE id=%s', (did,))
            for tid in p2.get('tpls', []):
                cur.execute('DELETE FROM c1_extract_rule_version'
                            ' WHERE rule_id=%s', (tid,))
                cur.execute('DELETE FROM c1_extract_rule WHERE id=%s', (tid,))
            for tname in p2.get('tables', []):
                cur.execute('DROP TABLE IF EXISTS ' + tname)
        conn.commit()
    finally:
        conn.close()


def wait_load(port, task_id, secs=120):
    for _ in range(secs * 2):
        _, s = http(port, '/api/status')
        if not s.get('running'):
            return catalog.get_task(task_id)
        time.sleep(0.5)
    raise RuntimeError('load 超时 task {}'.format(task_id))


def start_service(port, dsn=None):
    # 端口必须空闲：否则 wait_http 会误连到别的服务（两套脚本严禁并行跑）
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port))
    except OSError:
        raise RuntimeError('端口 {} 已被占用，先停掉占用者再跑'.format(port))
    finally:
        s.close()
    env = dict(os.environ, C1_STRUCTURE_PORT=str(port), C1_STRUCTURE_WARMUP='0')
    if dsn:
        env['C1_STRUCTURE_DB'] = dsn
    else:
        env.pop('C1_STRUCTURE_DB', None)
    p = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', PKG + '.app:app',
         '--host', '127.0.0.1', '--port', str(port)],
        cwd=PARENT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_http(port) or p.poll() is not None:
        p.kill()
        raise RuntimeError('服务 {} 启动失败'.format(port))
    return p


def upload(port, src_bytes, name, extra=None):
    # WARMUP=0 时后台线程即刻建 paddle 模型（oneDNN 初始化持 GIL），
    # 事件循环回包被饿死，首个 POST 可能数十秒——放宽到 120s
    body = {'files': [{'name': name,
                       'data': base64.b64encode(src_bytes).decode()}]}
    if extra:
        body.update(extra)
    st, j = http(port, '/api/upload', body, timeout=120)
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
    """真实原件（c1_doc_file.content）里第一个 PDF，真链路上传字节来源。
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


def cleanup_tasks(task_ids, file_ids):
    """按 task id 先子后父（无外键，全部显式删）：field/lineage→record→
    artifact→quarantine→load_log→task_file→task；合成 file 只删本次新建的。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for tid in task_ids:
                cur.execute(
                    'SELECT id FROM c1_task_file WHERE task_id=%s',
                    (tid,))
                tfs = [r[0] for r in cur.fetchall()]
                for tf in tfs:
                    cur.execute(
                        'DELETE FROM c1_staging_field WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record'
                        '  WHERE task_file_id=%s)', (tf,))
                    cur.execute(
                        'DELETE FROM c1_staging_lineage WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record'
                        '  WHERE task_file_id=%s)', (tf,))
                    cur.execute(
                        'DELETE FROM c1_staging_record'
                        ' WHERE task_file_id=%s', (tf,))
                    cur.execute(
                        'DELETE FROM c1_parse_artifact WHERE task_file_id=%s',
                        (tf,))
                cur.execute('DELETE FROM c1_load_quarantine WHERE task_id=%s',
                            (tid,))
                cur.execute('DELETE FROM c1_load_log WHERE task_id=%s',
                            (tid,))
                cur.execute('DELETE FROM c1_task_file WHERE task_id=%s',
                            (tid,))
                cur.execute('DELETE FROM c1_task WHERE id=%s', (tid,))
            if file_ids:
                ph = ','.join(['%s'] * len(file_ids))
                cur.execute(
                    'DELETE FROM c1_doc_file WHERE id IN ({})'
                    .format(ph), file_ids)
            # 真链路若误传合成字节会按真实 sha 新建 file 行（去重不命中
            # 假 sha）：按合成内容 sha 兜底清理，只删未被引用的
            syn_shas = [hashlib.sha256(b'%PDF-1.4 accept').hexdigest(),
                        hashlib.sha256(b'%PDF-1.4 accept-two').hexdigest()]
            cur.execute(
                'DELETE FROM c1_doc_file WHERE sha256 IN (%s,%s)'
                ' AND id NOT IN (SELECT file_id FROM c1_task_file)',
                syn_shas)
        conn.commit()
    finally:
        conn.close()


def main():
    print('== records 入库验收（任务化）· {} =='.format(
        db.safe_detail(config.PLATFORM_DB)))
    try:
        if not wait_db():
            print('配置库不可达，检查 C1_STRUCTURE_DB（环境变量 / config.PLATFORM_DB）')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    db.connect().close()  # 连通探针（纯连接，不建表不迁移）
    base0 = baseline()
    sweep_stale_scratch()
    syn_tasks, syn_fids, up = [], [], []
    p2 = {'lts': [], 'dss': [], 'tpls': [], 'tables': []}
    try:
        rc = _main(syn_tasks, syn_fids, up, p2)
    finally:
        print('清理临时产物')
        cleanup_tasks(syn_tasks + up, syn_fids)
        p2_cleanup(p2)
        base1 = baseline()
        check('清理后全量基线守恒（真实数据不动）', base1 == base0,
              '' if base1 == base0 else '{} vs {}'.format(base0, base1))
    print('\n结论：{}'.format('七项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return rc


def _main(syn_tasks, syn_fids, up, p2):
    print('[1/7] 连接零副作用 + 真实 task 投影往返一致')
    c0 = counts()
    db.connect().close()    # 纯连接：不得建表/写行（自动迁移门禁已删）
    db.connect().close()
    check('连接重开零变更', counts() == c0,
          '{} vs {}'.format(c0, counts()))
    tv = catalog.get_rule_version()
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
        task_id = catalog.create_task(tv['id'], {})
        syn_tasks.append(task_id)
        remap = json.loads(json.dumps(doc))
        remap['task_id'] = task_id
        for i, f in enumerate(remap['files']):
            # 假 sha 按 task+file 唯一：跨 task 撞 sha 会去重命中别 task 的文件行
            fake = hashlib.sha256(
                'accept-{}-{}'.format(task_id, i).encode()).hexdigest()
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
                # 级联验收需 ≥2 条：单记录 task（如截图）会让 2→1→2 退化
                if len(f['records']) >= 2:
                    src_real = f['records'][:2]
                    vals = src_real[0]['values']
                    field = next(iter(vals))
                    real_kw = next((str(v)[:4] for v in vals.values()
                                    if v not in (None, '')), '流水')
                    break

    print('[2/7] 重跑级联替换（合成 task，应用层先删子表）')
    task2 = catalog.create_task(tv['id'], {})
    syn_tasks.append(task2)
    fid, dup = catalog.register_file('accept.pdf', 'pdf', 22, '0' * 64,
                                     b'%PDF-1.4 accept-two')
    if not dup:
        syn_fids.append(fid)
    tf = catalog.add_task_file(task2, fid)
    syn_doc = {'schema': 'c1-structure-records/1', 'task_id': task2,
               'rule': {'name': tv['name'], 'version': tv['version']},
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

    print('[3/7] patch_record / set_review 语义（类型化错误）')
    rec = content.patch_record(task2, 0, 0, {field: 'ACCEPT_EDIT'})
    back = content_db.get_records(task2)['files'][0]['records'][0]
    check('edited+original 不变+DB 读回一致',
          rec['review']['state'] == 'edited'
          and rec['original'] == src_real[0]['original']
          and rec['values'][field] == 'ACCEPT_EDIT'
          and back['values'][field] == 'ACCEPT_EDIT'
          and back['review']['state'] == 'edited')
    n2r = content.set_review(task2, 0, [0], 'confirmed')
    back = content_db.get_records(task2)['files'][0]['records'][0]
    check('set_review confirmed', n2r == 1
          and back['review']['state'] == 'confirmed')
    n3r = content.set_review(task2, 0, [0], 'rejected')
    back = content_db.get_records(task2)['files'][0]['records'][0]
    hitr = content_db.query_fields(task=task2, state='rejected')
    check('set_review rejected + 状态查询命中', n3r == 1
          and back['review']['state'] == 'rejected' and len(hitr) > 0)
    try:
        content.patch_record(task2, 0, 0, {'不存在的字段': 'x'})
        raised = None
    except errors.BadRequest as e:
        raised = str(e)
    check('patch 未知键抛 BadRequest', raised is not None
          and '未知字段' in raised, str(raised))
    try:
        content.patch_record(task2, 0, 99999, {field: 'x'})
        raised_nf = None
    except errors.NotFound as e:
        raised_nf = str(e)
    check('patch 越界抛 NotFound', raised_nf is not None, str(raised_nf))

    print('[4/7] 跨 task 查询')
    hit = content_db.query_fields(field=field, q='ACCEPT_EDIT')
    hit2 = content_db.query_fields(q=real_kw)
    check('field 投影命中', any(h['task_id'] == task2 for h in hit)
          and len(hit2) > 0, 'syn={} real={}'.format(len(hit), len(hit2)))

    print('[5/7] 真链路（临时服务 8799，上传字节取自 c1_doc_file.content）')
    src = find_pdf_file()
    if src is None:
        print('  FAIL  c1_doc_file 无 PDF 原件，无法真链路验收')
        return 1
    svc = start_service(8799)
    try:
        task_id, st = upload(8799, src['data'], src['name'])
        up.append(task_id)
        time.sleep(1)  # finally 清理 scratch 在 running=False 之后
        rtask = catalog.get_task(task_id)
        tf_id = rtask['files'][0]['task_file_id']
        check('真链路仅解析=待抽取 · 未绑规则',
              st.get('error') is None and rtask['state'] == 'to_extract'
              and rtask['files'][0]['state'] == 'to_extract'
              and rtask['rule'] is None,
              'state={} tf_id={} rule={}'.format(
                  rtask['state'], tf_id, rtask.get('rule')))
        ste0, je0 = http(8799, '/api/tasks/{}/extract'.format(task_id), {},
                         method='POST', timeout=120)
        rtask = catalog.get_task(task_id)
        check('执行抽取→待校验 · 缺省绑原始透传',
              ste0 == 200 and je0.get('ok')
              and rtask['state'] == 'to_review'
              and (rtask['rule'] or {}).get('name') == '原始透传',
              'st={} state={} rule={}'.format(
                  ste0, rtask['state'], rtask.get('rule')))
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
        # P1 校验台路由冒烟：PATCH 改值 → 未知键 400 → POST 确认 → loaded 409
        stq, jq = http(8799, '/api/tasks/{}/staging'.format(task_id))
        r0 = jq['files'][0]['records'][0]
        k0 = next(iter(r0['values']))
        stp, jp = http(8799, '/api/tasks/{}/staging/{}/{}'.format(
            task_id, tf_id, r0['index']),
            {'values': {k0: 'ACCEPT_P1'}}, method='PATCH')
        check('PATCH 改值→edited', stp == 200 and jp.get('ok')
              and jp['record']['values'][k0] == 'ACCEPT_P1'
              and jp['record']['review']['state'] == 'edited')
        stb, _jb = http(8799, '/api/tasks/{}/staging/{}/{}'.format(
            task_id, tf_id, r0['index']),
            {'values': {'不存在的字段': 'x'}}, method='PATCH')
        check('PATCH 未知键 400', stb == 400)
        stn, _jn = http(8799, '/api/tasks/{}/staging/{}/{}'.format(
            task_id, tf_id, 99999),
            {'values': {k0: 'x'}}, method='PATCH')
        check('PATCH 越界 404（类型化错误）', stn == 404)
        stv, jv = http(8799, '/api/tasks/{}/staging/{}/review'.format(
            task_id, tf_id),
            {'indexes': [r0['index']], 'state': 'confirmed'})
        check('POST review confirmed', stv == 200 and jv.get('updated') == 1
              and jv.get('task_state') == 'to_review')
        catalog.set_task_state(task_id, 'loaded')
        stl, _jl = http(8799, '/api/tasks/{}/staging/{}/review'.format(
            task_id, tf_id),
            {'indexes': [r0['index']], 'state': 'rejected'})
        check('loaded 写操作 409', stl == 409)
        catalog.set_task_state(task_id, 'to_load')
    finally:
        svc.kill()

    print('[6/7] 断库显式 503（临时服务 8797，不可达 DSN）')
    svc_down = start_service(8797, BAD_DSN)
    try:
        st, j = http(8797, '/api/upload',
                     {'files': [{'name': src['name'],
                                 'data': base64.b64encode(
                                     src['data']).decode()}]})
        check('断库上传 503（不建 task）', st == 503, 'st={}'.format(st))
        st, _j = http(8797, '/api/tasks')
        check('断库 tasks 503', st == 503)
        st, _j = http(8797, '/api/tasks/{}/staging'.format(up[0]))
        check('断库暂存读 503（无快照回落）', st == 503)
        st, _j = http(8797, '/api/extract-rules')
        check('断库抽取规则 503（不降级）', st == 503)
    finally:
        svc_down.kill()

    print('[7/7] P2c 入库（合成目标表＋抽取规则/数据源/映射，入库时绑定目标）')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS ' + P2_TABLE)
            cur.execute('CREATE TABLE {} (id INT AUTO_INCREMENT PRIMARY KEY,'
                        ' c_name VARCHAR(255), c_amt VARCHAR(255),'
                        ' c_note VARCHAR(255))'.format(P2_TABLE))
        conn.commit()
    finally:
        conn.close()
    p2['tables'].append(P2_TABLE)
    fields3 = [{'name': '名称'}, {'name': '金额'}, {'name': '备注'}]
    FROWS = [{'rule_field': '名称', 'target_column': 'c_name',
              'is_business_key': 1},
             {'rule_field': '金额', 'target_column': 'c_amt',
              'is_business_key': 0},
             {'rule_field': '备注', 'target_column': 'c_note',
              'is_business_key': 0}]
    vid1 = catalog.create_rule(
        '_accept_p2_tpl', schema={'fields': fields3},
        mapping={'table': {'index': 0},
                 'fields': [{'target': '名称', 'column': {'index': 0}},
                            {'target': '金额', 'column': {'index': 1}},
                            {'target': '备注', 'column': {'index': 2}}]},
        transform={'fields': [{'target': '名称', 'apply': ['trim']}]})
    tpl1 = catalog.get_rule_version(vid1)
    p2['tpls'].append(tpl1['rule_id'])
    vid2 = catalog.create_rule(
        '_accept_p2_num', schema={'fields': fields3},
        transform={'fields': [{'target': '名称', 'apply': ['trim']},
                              {'target': '金额',
                               'apply': ['trim', 'number']}]})
    tpl2 = catalog.get_rule_version(vid2)
    p2['tpls'].append(tpl2['rule_id'])

    svc = start_service(8799)
    try:
        p = db._parts(db.resolve_conn(config.PLATFORM_DB))
        stds, jds = http(8799, '/api/load/datasources')
        seed = [d for d in jds.get('items', []) if d['name'] == '产品库']
        check('默认数据源「产品库」种子存在（明文落行）',
              stds == 200 and len(seed) == 1
              and seed[0]['host'] == p['host']
              and seed[0]['db_name'] == p['database'],
              db.safe_detail(config.PLATFORM_DB))
        st, j = http(8799, '/api/load/datasources',
                     {'name': '_accept_p2_ds', 'host': p['host'],
                      'port': p['port'], 'user': p['user'],
                      'password': p['password'], 'db_name': p['database']})
        ds_id = j.get('id')
        p2['dss'].append(ds_id)
        stt, jt = http(8799, '/api/load/datasources/{}/test'.format(ds_id), {})
        check('数据源 CRUD＋测试连接（仅 host:port/库名）',
              st == 200 and stt == 200 and jt.get('ok')
              and jt.get('detail') == db.safe_detail(config.PLATFORM_DB),
              str(jt.get('detail')))
        stb, jb = http(8799, '/api/load/datasources/{}/tables'.format(ds_id))
        stc, jc = http(8799, '/api/load/datasources/{}/columns?table={}'.format(
            ds_id, P2_TABLE))
        check('目标库 introspection（表/列）',
              stb == 200 and P2_TABLE in jb['items'] and stc == 200
              and {c['name'] for c in jc['items']}
              >= {'c_name', 'c_amt', 'c_note'})
        st, j = http(8799, '/api/load/tables',
                     {'datasource_id': ds_id,
                      'rule_id': tpl1['rule_id'],
                      'target_table': P2_TABLE, 'write_mode': 'upsert',
                      'fields': FROWS})
        lt1 = j.get('id')
        p2['lts'].append(lt1)
        st2, j2 = http(8799, '/api/load/tables',
                       {'datasource_id': ds_id,
                        'rule_id': tpl2['rule_id'],
                        'target_table': P2_TABLE, 'write_mode': 'upsert',
                        'fields': FROWS})
        lt2 = j2.get('id')
        p2['lts'].append(lt2)
        check('POST 映射 ×2（同表不同抽取规则）', st == 200 and st2 == 200,
              '{} {}'.format(lt1, lt2))
        stgd, jgd = http(8799, '/api/load/tables/{}'.format(lt1))
        check('映射详情：字段行＋业务键',
              stgd == 200 and len(jgd.get('fields', [])) == 3
              and [f['target_column'] for f in jgd['fields']
                   if f['is_business_key']] == ['c_name'])
        stn, _ = http(8799, '/api/load/tables',
                      {'datasource_id': ds_id,
                       'rule_id': tpl1['rule_id'],
                       'target_table': P2_TABLE, 'write_mode': 'upsert',
                       'fields': FROWS[:1]})
        nobk = [dict(f, is_business_key=0) for f in FROWS]
        stn2, _ = http(8799, '/api/load/tables',
                       {'datasource_id': ds_id,
                        'rule_id': tpl1['rule_id'],
                        'target_table': '_accept_p2_other',
                        'write_mode': 'upsert', 'fields': nobk})
        check('映射契约 400（覆盖不全 / upsert 无业务键）',
              stn == 400 and stn2 == 400)
        stdup, _ = http(8799, '/api/load/tables',
                        {'datasource_id': ds_id,
                         'rule_id': tpl1['rule_id'],
                         'target_table': P2_TABLE, 'write_mode': 'upsert',
                         'fields': FROWS})
        check('同数据源＋抽取规则＋表重复映射 409', stdup == 409)
        stlk, _ = http(8799, '/api/load/datasources/{}'.format(ds_id),
                       {'host': '127.0.0.1'}, method='PATCH')
        stpw, _ = http(8799, '/api/load/datasources/{}'.format(ds_id),
                       {'password': p['password']}, method='PATCH')
        check('被引用数据源：目标锁定 409 · 密码可改 200',
              stlk == 409 and stpw == 200)
        stb, jb = http(8799, '/api/load/tables',
                       {'datasource_id': ds_id,
                        'rule_id': tpl1['rule_id'],
                        'target_table': '_accept_p2_nosuch',
                        'write_mode': 'upsert', 'fields': FROWS})
        lt_bad = jb.get('id')
        small = base64.b64encode(b'%PDF-1.4 accept').decode()
        strk, _ = http(8799, '/api/upload',
                       {'files': [{'name': 'p2.pdf', 'data': small}],
                        'mode': 'load'})
        check('退役契约键上传 400（不再收 mode/入库目标）', strk == 400)
        srv, _rv = http(8799, '/api/upload',
                        {'files': [{'name': 'p2.pdf', 'data': small}],
                         'rule_version_id': vid1})
        check('上传选抽取规则已退役 400', srv == 400)

        # ---- Leg A：解析→抽取→校验→入库（新状态机全程）；失败不留痕 ----
        task_a, sta = upload(8799, src['data'], src['name'])
        up.append(task_a)
        time.sleep(1)
        ra = catalog.get_task(task_a)
        tfa = ra['files'][0]['task_file_id']
        check('普通上传仅解析=待抽取 · 无入库目标 · 未绑规则',
              sta.get('error') is None and ra['state'] == 'to_extract'
              and ra['files'][0]['state'] == 'to_extract'
              and ra.get('load') is None and ra['rule'] is None,
              'state={} load={} rule={}'.format(
                  ra['state'], ra.get('load'), ra.get('rule')))
        ste0, je0 = http(8799, '/api/tasks/{}/extract'.format(task_a),
                         {'rule_version_id': vid1},
                         method='POST', timeout=120)
        ra = catalog.get_task(task_a)
        n_rec = ra['files'][0]['records_n']
        check('执行抽取(选规则)→待校验 · 改绑 vid1',
              ste0 == 200 and je0.get('ok')
              and ra['state'] == 'to_review'
              and ra['files'][0]['state'] == 'to_review' and n_rec > 0
              and (ra['rule'] or {}).get('version_id') == vid1,
              'state={} recs={} rule={}'.format(
                  ra['state'], n_rec, ra.get('rule')))
        stg, jg = http(8799, '/api/tasks/{}/staging'.format(task_a))
        names = [r['values'].get('名称', '')
                 for r in jg['files'][0]['records']]
        tgt = {'load_datasource_id': ds_id, 'load_table_id': lt1}
        stg1, jg1 = http(8799, '/api/tasks/{}/load'.format(task_a), tgt)
        ra = catalog.get_task(task_a)
        check('门禁：全校验中 409 不留绑定', stg1 == 409
              and '待入库' in jg1.get('error', '')
              and ra.get('load') is None,
              str(jg1.get('error')))
        stc, jcs = http(8799, '/api/tasks/{}/staging/{}/review'.format(
            task_a, tfa), {'indexes': list(range(n_rec)),
                           'state': 'confirmed'})
        ra = catalog.get_task(task_a)
        check('全部确认派生→待入库', stc == 200
              and jcs.get('task_state') == 'to_load'
              and ra['state'] == 'to_load'
              and ra['files'][0]['state'] == 'to_load',
              'state={} ts={}'.format(ra['state'], jcs.get('task_state')))
        stx, _ = http(8799, '/api/tasks/{}/load'.format(task_a), {})
        sty, _ = http(8799, '/api/tasks/{}/load'.format(task_a),
                      {'load_datasource_id': ds_id, 'load_table_id': lt2})
        stz, _ = http(8799, '/api/tasks/{}/load'.format(task_a),
                      {'load_datasource_id': ds_id, 'load_table_id': lt_bad})
        ra = catalog.get_task(task_a)
        check('入库时校验 400（缺目标 · 抽取规则不匹配 · 目标表不存在）不留绑定',
              stx == 400 and sty == 400 and stz == 400
              and ra.get('load') is None,
              '{} {} {}'.format(stx, sty, stz))
        std, _ = http(8799, '/api/load/tables/{}'.format(lt_bad),
                      method='DELETE')
        check('无引用映射可删', std == 200)
        ste, _ = http(8799, '/api/load/tables/{}'.format(lt2),
                      {'write_mode': 'upsert', 'fields': FROWS},
                      method='PATCH')
        check('无任务引用映射可编辑 200', ste == 200)
        stp, _ = http(8799, '/api/tasks/{}/load'.format(up[0]), {})
        check('未绑定任务未选目标入库 400', stp == 400)
        http(8799, '/api/tasks/{}/staging/{}/review'.format(task_a, tfa),
             {'indexes': [0], 'state': 'rejected'})
        stg2, jg2 = http(8799, '/api/tasks/{}/load'.format(task_a), tgt)
        ra = catalog.get_task(task_a)
        check('门禁：rejected 回退待校验 409', stg2 == 409
              and ra['state'] == 'to_review', str(jg2.get('error')))
        http(8799, '/api/tasks/{}/staging/{}/review'.format(task_a, tfa),
             {'indexes': [0], 'state': 'confirmed'})
        stl, jl = http(8799, '/api/tasks/{}/load'.format(task_a), tgt)
        ra = wait_load(8799, task_a)
        check('全确认→loaded · 启动成功才绑定目标', stl == 200 and jl.get('ok')
              and ra['state'] == 'loaded'
              and (ra.get('load') or {}).get('load_table_id') == lt1,
              'state={} err={} load={}'.format(
                  ra['state'], ra.get('error'), ra.get('load')))
        want = len({str(v).strip() for v in names})
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM ' + P2_TABLE)
                n_rows = cur.fetchone()[0]
        finally:
            conn.close()
        stlog, jlog = http(8799, '/api/tasks/{}/load-log'.format(task_a))
        check('目标行数＝业务键去重＋回执逐条',
              n_rows == want and stlog == 200
              and len(jlog['items']) == n_rec,
              'rows={} want={} receipts={}'.format(
                  n_rows, want, len(jlog['items'])))
        strer, _ = http(8799, '/api/tasks/{}/load'.format(task_a), {})
        stpat, _ = http(8799, '/api/tasks/{}/staging/{}/{}'.format(
            task_a, tfa, 0), {'values': {'名称': 'x'}}, method='PATCH')
        check('loaded 重入库 409＋记录只读 409',
              strer == 409 and stpat == 409)
        stdd, _ = http(8799, '/api/load/datasources/{}'.format(ds_id),
                       method='DELETE')
        stmd, _ = http(8799, '/api/load/tables/{}'.format(lt1),
                       method='DELETE')
        stmp, _ = http(8799, '/api/load/tables/{}'.format(lt1),
                       {'write_mode': 'insert'}, method='PATCH')
        check('被任务引用的数据源/映射禁删禁改 409',
              stdd == 409 and stmd == 409 and stmp == 409)

        # ---- 重放解析（任务台账·原地重跑）：loaded 拒绝；完成文件清空重跑 ----
        strr, jtr = http(8799, '/api/tasks/{}/reparse'.format(task_a),
                         {}, timeout=30, method='POST')
        check('loaded 任务重放解析拒绝 409', strr == 409,
              str(jtr.get('error')))
        stp2, jp2 = http(8799, '/api/upload', {
            'files': [{'name': 'replay.pdf',
                      'data': base64.b64encode(src['data']).decode()}]},
            timeout=120)
        task_r = jp2['task_id']
        up.append(task_r)
        tfr = catalog.get_task(task_r)['files'][0]['task_file_id']
        http(8799, '/api/tasks/{}/extract'.format(task_r), {},
             timeout=120, method='POST')
        recs0 = catalog.get_task(task_r)['files'][0]['records_n']
        strp, jtp = http(8799, '/api/tasks/{}/reparse'.format(task_r),
                         {}, timeout=30, method='POST')
        check('重放解析受理 200', strp == 200 and jtp.get('ok'),
              str(jtp.get('error')))
        for _k in range(300):
            _, s2 = http(8799, '/api/status')
            if not s2.get('running'):
                break
            time.sleep(0.5)
        rr = catalog.get_task(task_r)
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM c1_parse_artifact'
                            ' WHERE task_file_id=%s', (tfr,))
                n_art = cur.fetchone()[0]
        finally:
            conn.close()
        check('原地重放：记录清空回落待抽取 · 产物已重灌',
              rr['state'] == 'to_extract' and rr['error'] is None
              and rr['files'][0]['records_n'] == 0 and recs0 > 0
              and n_art > 0,
              'state={} recs0={} artifacts={}'.format(
                  rr['state'], recs0, n_art))

        # ---- Leg B：合成 task（number transform＋超长值）→ 隔离（待入库）→ 重试 ----
        def syn_load_task(vid, lt, recs, tag, bind=True):
            tid = catalog.create_task(vid, {})
            syn_tasks.append(tid)
            fake = hashlib.sha256(
                'accept-{}-{}'.format(tag, tid).encode()).hexdigest()
            fid, dup = catalog.register_file(
                'accept-{}.pdf'.format(tag), 'pdf', 11, fake,
                b'%PDF-1.4 accept')
            if not dup:
                syn_fids.append(fid)
            tf = catalog.add_task_file(tid, fid)
            if bind:
                catalog.set_task_load(tid, ds_id, lt)
            content_db.save_records(
                {'schema': 'c1-structure-records/1', 'task_id': tid,
                 'rule': {'name': '_accept_p2', 'version': 1},
                 'files': [{'task_file_id': tf, 'file_id': fid,
                            'name': 'accept-{}.pdf'.format(tag),
                            'records': recs}]})
            catalog.set_task_state(tid, 'to_load')
            catalog.set_task_file_state(tf, 'to_load')
            return tid, tf

        def rec(i, vals):
            return {'index': i, 'values': vals, 'original': dict(vals),
                    'lineage': {k: [] for k in vals},
                    'review': {'state': 'confirmed', 'at': None}}

        tid_b, tfb = syn_load_task(vid2, lt2, [
            rec(0, {'名称': ' 合成甲 ', '金额': ' 1,234.5 ', '备注': 'n0'}),
            rec(1, {'名称': '合成乙', '金额': '88', '备注': 'x' * 300}),
            rec(2, {'名称': '合成丙', '金额': 'bad', '备注': 'n2'})], 'p2b')
        http(8799, '/api/tasks/{}/load'.format(tid_b), {})
        rb = wait_load(8799, tid_b)
        stq, jq = http(8799, '/api/tasks/{}/quarantine'.format(tid_b))
        stlog, jlog = http(8799, '/api/tasks/{}/load-log'.format(tid_b))
        qidx = {r['record_index'] for r in jq['items']
                if r['stage'] == 'load'}
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT c_name, c_amt FROM {}'
                            ' WHERE c_name=%s'.format(P2_TABLE), ('合成甲',))
                row_a = cur.fetchone()
        finally:
            conn.close()
        check('transform 消费＋数据级隔离→待入库（可重试）',
              rb['state'] == 'to_load' and '隔离' in (rb.get('error') or '')
              and len(jlog['items']) == 1
              and qidx == {1, 2} and row_a == ('合成甲', '1234.5'),
              'state={} err={} receipts={} q={} row={}'.format(
                  rb['state'], rb.get('error'), len(jlog['items']),
                  sorted(qidx), row_a))
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('ALTER TABLE {} MODIFY c_note VARCHAR(512)'
                            .format(P2_TABLE))
            conn.commit()
        finally:
            conn.close()
        http(8799, '/api/tasks/{}/load'.format(tid_b), {})
        rb = wait_load(8799, tid_b)
        stlog, jlog = http(8799, '/api/tasks/{}/load-log'.format(tid_b))
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT c_name FROM {} ORDER BY c_name'
                            .format(P2_TABLE))
                got_names = [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
        check('隔离重试：回执跳过＋隔离重试（幂等不重写）',
              rb['state'] == 'to_load' and len(jlog['items']) == 2
              and got_names.count('合成甲') == 1
              and '合成乙' in got_names and '合成丙' not in got_names,
              'receipts={} names={}'.format(len(jlog['items']), got_names))
        stbt, jbt = http(8799, '/api/tasks/{}/load'.format(tid_b),
                         {'load_datasource_id': ds_id, 'load_table_id': lt1})
        check('已绑定任务带新目标 409（重试沿用原目标）',
              stbt == 409 and '已绑定' in jbt.get('error', ''),
              str(jbt.get('error')))
        stpb, _ = http(8799, '/api/tasks/{}/staging/{}/{}'.format(
            tid_b, tfb, 2), {'values': {'金额': '9'}}, method='PATCH')
        check('隔离后记录仍可修改（待入库非只读）', stpb == 200)

        # ---- Leg C：同映射跨 task upsert 命中已有行 → update ----
        name0 = str(names[0]).strip()
        tid_c, _tfc = syn_load_task(vid1, lt1, [
            rec(0, {'名称': name0, '金额': 'C1', '备注': 'UPDATED-C'})], 'p2c')
        http(8799, '/api/tasks/{}/load'.format(tid_c), {})
        rc = wait_load(8799, tid_c)
        stlog, jlog = http(8799, '/api/tasks/{}/load-log'.format(tid_c))
        it = jlog['items'][0] if jlog['items'] else {}
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT c_note FROM {} WHERE c_name=%s'
                            .format(P2_TABLE), (name0,))
                rows_c = cur.fetchall()
                cur.execute('SELECT COUNT(*) FROM ' + P2_TABLE)
                total_c = cur.fetchone()[0]
        finally:
            conn.close()
        check('upsert 命中→update＋行数不增',
              rc['state'] == 'loaded' and it.get('action') == 'update'
              and it.get('target_pk') == json.dumps([name0],
                                                    ensure_ascii=False)
              and len(rows_c) == 1 and rows_c[0][0] == 'UPDATED-C'
              and total_c == want + 2,  # Leg B 已写入合成甲/乙两行
              'action={} rows={} total={}'.format(
                  it.get('action'), rows_c, total_c))

        # ---- Leg D：门禁失败不留绑定 → 确认后换另一映射入库成功（P2c 自由度）----
        ALT_TABLE = '_accept_p2_alt'
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('DROP TABLE IF EXISTS ' + ALT_TABLE)
                cur.execute('CREATE TABLE {} (id INT AUTO_INCREMENT PRIMARY KEY,'
                            ' c_name VARCHAR(255), c_amt VARCHAR(255),'
                            ' c_note VARCHAR(255))'.format(ALT_TABLE))
            conn.commit()
        finally:
            conn.close()
        p2['tables'].append(ALT_TABLE)
        st3, j3 = http(8799, '/api/load/tables',
                       {'datasource_id': ds_id,
                        'rule_id': tpl1['rule_id'],
                        'target_table': ALT_TABLE, 'write_mode': 'upsert',
                        'fields': FROWS})
        lt3 = j3.get('id')
        p2['lts'].append(lt3)
        recd = rec(0, {'名称': '换目标丁', '金额': '7', '备注': 'd0'})
        recd['review'] = {'state': 'pending', 'at': None}
        tid_d, tfd = syn_load_task(vid1, lt1, [recd], 'p2d', bind=False)
        stdg, _ = http(8799, '/api/tasks/{}/load'.format(tid_d),
                       {'load_datasource_id': ds_id, 'load_table_id': lt1})
        rd = catalog.get_task(tid_d)
        check('合成任务门禁 409 不留绑定',
              stdg == 409 and rd.get('load') is None)
        http(8799, '/api/tasks/{}/staging/{}/review'.format(tid_d, tfd),
             {'indexes': [0], 'state': 'confirmed'})
        stdl, _ = http(8799, '/api/tasks/{}/load'.format(tid_d),
                       {'load_datasource_id': ds_id, 'load_table_id': lt3})
        rd = wait_load(8799, tid_d)
        check('门禁失败后换另一映射入库成功（绑定落在 lt3）',
              st3 == 200 and stdl == 200 and rd['state'] == 'loaded'
              and (rd.get('load') or {}).get('load_table_id') == lt3,
              'state={} load={}'.format(rd['state'], rd.get('load')))
    finally:
        svc.kill()
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
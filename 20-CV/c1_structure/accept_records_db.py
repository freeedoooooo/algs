"""
c1_structure/accept_records_db.py — records 入库七项验收（资料化契约，
DB 唯一事实源，file_id 粒度，无外键）。

模型：一条资料 = 一次运行（file_id）；无 task 概念。
用法（从 20-CV）：D:/miniforge3/envs/paddle/python.exe -u c1_structure/accept_records_db.py

1 连接零副作用+投影往返一致 · 2 重跑级联替换 · 3 patch/set_review ·
4 跨资料查询 · 5 真链路（8799，校验路由冒烟）· 6 断库显式 503（8797）·
7 入库全链（合成目标表＋规则/数据源/映射：预检/门禁失败不留绑定、
已绑定锁死 409、门禁 409、全部确认→loaded、回执幂等、transform/数据级隔离、
重试、upsert update、审计守卫）。
上传字节取自 c1_doc_file.content；断库用不可达 DSN 模拟。
破坏性操作只落合成资料/规则/数据源/目标表（验完清理＋DROP）；用户数据只读。
8765 全程不动。两套脚本严禁并行（共用 8799/8797）。
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

BAD_DSN = 'mysql://nobody:unused@127.0.0.1:3399/c1_structure_dev'
P2_TABLE = '_accept_p2_load'
BASE_FID = 9_000_000
FAILS = []


def check(name, ok, detail=''):
    print('  {}  {}{}'.format('PASS' if ok else 'FAIL', name,
                              (' · ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


def http(port, path, body=None, timeout=60, method=None):
    req = urllib.request.Request(
        'http://127.0.0.1:{}{}'.format(port, path),
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'},
        method=method or ('POST' if body is not None else 'GET'))
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
            time.sleep(1)
            return True
        except Exception:
            time.sleep(1)
    return False


def counts():
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
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) FROM c1_staging_field f LEFT JOIN'
                ' c1_staging_record r ON r.id=f.record_id WHERE r.id IS NULL')
            f = cur.fetchone()[0]
            cur.execute(
                'SELECT COUNT(*) FROM c1_staging_lineage l LEFT JOIN'
                ' c1_staging_record r ON r.id=l.record_id WHERE r.id IS NULL')
            l = cur.fetchone()[0]
            cur.execute(
                'SELECT COUNT(*) FROM c1_staging_record r LEFT JOIN'
                ' c1_doc_file s ON s.id=r.file_id WHERE s.id IS NULL')
            r = cur.fetchone()[0]
            return f, l, r
    finally:
        conn.close()


def baseline():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*), COALESCE(SUM(size_bytes),0)'
                        ' FROM c1_parse_artifact')
            art = tuple(cur.fetchone())
            out = [counts(), art]
            for sql in ('SELECT COUNT(*) FROM c1_doc_file',
                        'SELECT COUNT(*) FROM c1_extract_rule',
                        'SELECT COUNT(*) FROM c1_extract_rule_version',
                        'SELECT COUNT(*) FROM c1_load_datasource',
                        'SELECT COUNT(*) FROM c1_load_table',
                        'SELECT COUNT(*) FROM c1_load_table_field',
                        'SELECT COUNT(*) FROM c1_load_log',
                        'SELECT COUNT(*) FROM c1_load_quarantine'):
                cur.execute(sql)
                out.append(cur.fetchone()[0])
            return tuple(out)
    finally:
        conn.close()


def p2_cleanup(p2):
    if not p2:
        return
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for lid in p2.get('lts', []):
                cur.execute('DELETE FROM c1_load_table_field'
                            ' WHERE load_table_id=%s', (lid,))
                cur.execute('DELETE FROM c1_load_table WHERE id=%s', (lid,))
            for did in p2.get('dss', []):
                cur.execute('DELETE FROM c1_load_datasource WHERE id=%s', (did,))
            for tid in p2.get('tpls', []):
                cur.execute('DELETE FROM c1_extract_rule_version'
                            ' WHERE rule_id=%s', (tid,))
                cur.execute('DELETE FROM c1_extract_rule WHERE id=%s', (tid,))
            for tname in p2.get('tables', []):
                cur.execute('DROP TABLE IF EXISTS ' + tname)
        conn.commit()
    finally:
        conn.close()


def wait_load(port, file_id, secs=120):
    for _ in range(secs * 2):
        _, s = http(port, '/api/status')
        if not s.get('running'):
            return catalog.get_file(file_id)
        time.sleep(0.5)
    raise RuntimeError('load 超时 file {}'.format(file_id))


def start_service(port, dsn=None):
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port))
    except OSError:
        raise RuntimeError('端口 {} 已被占用'.format(port))
    finally:
        s.close()
    env = dict(os.environ, C1_STRUCTURE_PORT=str(port), C1_STRUCTURE_WARMUP='0')
    if dsn:
        env['C1_STRUCTURE_DB'] = dsn
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
    body = {'files': [{'name': name,
                       'data': base64.b64encode(src_bytes).decode()}]}
    if extra:
        body.update(extra)
    st, j = http(port, '/api/upload', body, timeout=120)
    if st != 200 or not j.get('ok'):
        raise RuntimeError('upload 失败：{} {}'.format(st, j))
    file_id = j['file_id']
    for _ in range(300):
        _, s = http(port, '/api/status')
        if not s.get('running'):
            return file_id, s
        time.sleep(0.5)
    raise RuntimeError('upload 超时')


def find_pdf_file():
    """真实 PDF 优先；清库后无原件时造最小 PDF 并登记（id 从 BASE_FID 起）。"""
    page = 1
    while True:
        b = catalog.list_files(page=page, per_page=100)
        for row in b['items']:
            if row['kind'] == 'pdf' and row['size_bytes'] > 1024 \
                    and row['id'] < BASE_FID:
                s = catalog.get_file_content(row['id'])
                s['id'] = row['id']
                s['name'] = row['name']
                return s
        if page * 100 >= b['total']:
            break
        page += 1
    pdf = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
           b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
           b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]'
           b'/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n'
           b'4 0 obj<</Length 58>>stream\nBT /F1 12 Tf 72 700 Td '
           b'(accept 123.45) Tj ET\nendstream endobj\n'
           b'5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n'
           b'trailer<</Root 1 0 R>>\n%%EOF\n')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for t in ('c1_load_log', 'c1_load_quarantine',
                      'c1_staging_record', 'c1_parse_artifact'):
                cur.execute('DELETE FROM ' + t + ' WHERE file_id=%s',
                            (BASE_FID,))
            cur.execute('DELETE FROM c1_doc_file WHERE id=%s', (BASE_FID,))
            cur.execute('INSERT INTO c1_doc_file'
                        ' (id, name, sha256, kind, size_bytes, content)'
                        ' VALUES (%s,%s,%s,%s,%s,%s)',
                        (BASE_FID, 'accept_synth.pdf',
                         hashlib.sha256(pdf).hexdigest(), 'pdf', len(pdf), pdf))
            conn.commit()
        return {'id': BASE_FID, 'name': 'accept_synth.pdf',
                'sha': hashlib.sha256(pdf).hexdigest(), 'data': pdf}
    finally:
        conn.close()


def scratch_clean(wait=5):
    for _ in range(wait * 2):
        if not any(n.startswith(('in_', 'case_'))
                   for d in (config.TMP_INPUT, config.TMP_WORK)
                   for n in os.listdir(d)):
            return True
        time.sleep(0.5)
    return False


def sweep_stale_scratch(max_age=3600):
    now = time.time()
    for d in (config.TMP_INPUT, config.TMP_WORK):
        for n in os.listdir(d):
            if not n.startswith(('in_', 'case_')):
                continue
            p = os.path.join(d, n)
            if os.path.isdir(p) and now - os.path.getmtime(p) > max_age:
                shutil.rmtree(p, ignore_errors=True)
                print('  清扫孤儿 scratch：{}'.format(p))


def cleanup_files(fids):
    """先子后父（无外键）：field/lineage→record→artifact→quarantine→
    log→doc_file。只删合成 id（>=BASE_FID），真资料不动。"""
    if not fids:
        return
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            fids = [f for f in fids if f >= BASE_FID]
            if not fids:
                return
            ph = ','.join(['%s'] * len(fids))
            cur.execute('DELETE FROM c1_staging_field WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record WHERE file_id'
                        ' IN ({}))'.format(ph), fids)
            cur.execute('DELETE FROM c1_staging_lineage WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record WHERE file_id'
                        ' IN ({}))'.format(ph), fids)
            for t in ('c1_staging_record', 'c1_parse_artifact',
                      'c1_load_quarantine', 'c1_load_log'):
                cur.execute('DELETE FROM ' + t
                            + ' WHERE file_id IN ({})'.format(ph), fids)
            cur.execute('DELETE FROM c1_doc_file WHERE id IN ({})'.format(ph),
                        fids)
        conn.commit()
    finally:
        conn.close()


def _syn_file(name='accept.pdf', data=b'%PDF-1.4 accept', mark=None):
    """登记一条合成资料（id 由 DB 自增，>=BASE_FID 由 AUTO_INCREMENT 保证）；
    返回 file_id。"""
    sha = hashlib.sha256(data + (mark or b'')).hexdigest()
    fid, _dup = catalog.register_file(name, 'pdf', len(data), sha, data)
    return fid


def main():
    print('== records 入库验收（资料化）· {} =='.format(
        db.safe_detail(config.PLATFORM_DB)))
    try:
        if not wait_db():
            print('配置库不可达')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    db.connect().close()
    base0 = baseline()
    sweep_stale_scratch()
    syn_fids, up = [], []
    p2 = {'lts': [], 'dss': [], 'tpls': [], 'tables': []}
    try:
        rc = _main(syn_fids, up, p2)
    finally:
        print('清理临时产物')
        cleanup_files(syn_fids + up + [BASE_FID])
        p2_cleanup(p2)
        base1 = baseline()
        check('清理后全量基线守恒（真实数据不动）', base1 == base0,
              '' if base1 == base0 else '{} vs {}'.format(base0, base1))
    print('\n结论：{}'.format('七项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return rc


def _main(syn_fids, up, p2):
    print('[1/7] 连接零副作用 + 投影往返一致')
    c0 = counts()
    db.connect().close()
    db.connect().close()
    check('连接重开零变更', counts() == c0,
          '{} vs {}'.format(c0, counts()))
    # 自造可往返 records 信封（清库后无真实记录也可跑）
    fid = _syn_file('accept_round.pdf', b'%PDF-1.4 accept-round')
    syn_fids.append(fid)
    catalog.set_rule(fid, None)
    rec = {'index': 0, 'values': {'字段一': '甲', '字段二': '100'},
           'original': {'字段一': '甲', '字段二': '100'},
           'lineage': {'字段一': [], '字段二': []},
           'review': {'state': 'pending', 'at': None}}
    doc = {'schema': 'c1-structure-records/1', 'file_id': fid,
           'rule': {'name': '验收规则', 'version': 1},
           'files': [{'file_id': fid, 'name': 'accept_round.pdf',
                      'records': [rec, dict(rec, index=1)]}]}
    content_db.save_records(doc)
    got = content_db.get_records(fid)
    check('投影往返一致', got is not None
          and len(got['files'][0]['records']) == 2
          and got['files'][0]['records'][0]['values'] == rec['values'],
          '2 条记录')

    print('[2/7] 重跑级联替换（应用层先删子表）')
    n2 = counts()
    one = json.loads(json.dumps(doc))
    one['files'][0]['records'] = one['files'][0]['records'][:1]
    content_db.save_records(one)
    n1 = counts()
    content_db.save_records(doc)
    n2b = counts()
    check('2→1→2 级联', n1[0] == n2[0] - 1 and n2b == n2,
          '{}→{}→{}'.format(n2, n1, n2b))
    orph = orphan_counts()
    check('无孤儿 field/lineage/record（反查=0）', orph == (0, 0, 0),
          'field/lineage/record 悬空={}'.format(orph))

    print('[3/7] patch_record / set_review 语义（类型化错误）')
    edited = content.patch_record(fid, 0, {'字段一': 'ACCEPT_EDIT'})
    back = content_db.get_records(fid)['files'][0]['records'][0]
    check('edited+original 不变+DB 读回一致',
          edited['review']['state'] == 'edited'
          and edited['original']['字段一'] == '甲'
          and back['values']['字段一'] == 'ACCEPT_EDIT'
          and back['review']['state'] == 'edited')
    n2r = content.set_review(fid, [0], 'confirmed')
    back = content_db.get_records(fid)['files'][0]['records'][0]
    check('set_review confirmed', n2r == 1
          and back['review']['state'] == 'confirmed')
    n3r = content.set_review(fid, [0], 'rejected')
    back = content_db.get_records(fid)['files'][0]['records'][0]
    hitr = content_db.query_fields(task=fid, state='rejected')
    check('set_review rejected + 状态查询命中', n3r == 1
          and back['review']['state'] == 'rejected' and len(hitr) > 0)
    try:
        content.patch_record(fid, 0, {'不存在': 'x'})
        raised = None
    except errors.BadRequest as e:
        raised = str(e)
    check('patch 未知键抛 BadRequest', raised is not None
          and '未知字段' in raised, str(raised))
    try:
        content.patch_record(fid, 99999, {'字段一': 'x'})
        raised_nf = None
    except errors.NotFound:
        raised_nf = 'NotFound'
    check('patch 越界抛 NotFound', raised_nf is not None, str(raised_nf))

    print('[4/7] 跨资料查询')
    hit = content_db.query_fields(field='字段一', q='ACCEPT_EDIT')
    check('field 投影命中', any(h['file_id'] == fid for h in hit),
          '{} 条'.format(len(hit)))

    print('[5/7] 真链路（临时服务 8799）')
    src = find_pdf_file()
    svc = start_service(8799)
    try:
        live_fid, st = upload(8799, src['data'], src['name'])
        up.append(live_fid)
        time.sleep(1)
        f = catalog.get_file(live_fid)
        check('真链路仅解析=待抽取 · 未绑规则',
              st.get('error') is None and f['state'] == 'to_extract'
              and f['rule_version_id'] is None,
              'state={} rule={}'.format(f['state'], f['rule_version_id']))
        ste0, je0 = http(8799, '/api/sources/{}/extract'.format(live_fid), {},
                         timeout=120)
        f = catalog.get_file(live_fid)
        tv = catalog.get_rule_version(version_id=f['rule_version_id'])
        check('执行抽取→待校验 · 缺省绑原始透传',
              ste0 == 200 and je0.get('ok') and f['state'] == 'to_review'
              and tv and tv['name'] == '原始透传',
              'st={} state={}'.format(ste0, f['state']))
        check('tmp/input+tmp/work 无 scratch 残留', scratch_clean())
        # 合成 PDF 无表格 → 透传产出 0 条；注入合成 records 验校验路由
        content_db.save_records({
            'schema': 'c1-structure-records/1', 'file_id': live_fid,
            'rule': {'name': '验收', 'version': 1},
            'files': [{'file_id': live_fid, 'name': 'accept',
                       'records': [
                           {'index': 0,
                            'values': {'验收列': 'A'}, 'original': {'验收列': 'A'},
                            'lineage': {},
                            'review': {'state': 'pending', 'at': None}},
                           {'index': 1,
                            'values': {'验收列': 'B'}, 'original': {'验收列': 'B'},
                            'lineage': {},
                            'review': {'state': 'pending', 'at': None}}]}]})
        stq, jq = http(8799, '/api/sources/{}/staging'.format(live_fid))
        check('暂存 API 记录数一致', stq == 200
              and len(jq['files'][0]['records']) == 2,
              '{} 条'.format(len(jq['files'][0]['records'])))
        r0 = jq['files'][0]['records'][0]
        k0 = next(iter(r0['values']))
        base = '/api/sources/{}/staging'.format(live_fid)
        stp, jp = http(8799, base + '/{}'.format(r0['index']),
                      {'values': {k0: 'ACCEPT_P1'}}, method='PATCH')
        check('PATCH 改值→edited', stp == 200 and jp.get('ok')
              and jp['record']['values'][k0] == 'ACCEPT_P1'
              and jp['record']['review']['state'] == 'edited')
        stb, _jb = http(8799, base + '/{}'.format(r0['index']),
                        {'values': {'不存在': 'x'}}, method='PATCH')
        check('PATCH 未知键 400', stb == 400)
        stn, _jn = http(8799, base + '/99999',
                        {'values': {k0: 'x'}}, method='PATCH')
        check('PATCH 越界 404', stn == 404)
        stv, jv = http(8799, base + '/review',
                       {'indexes': [r0['index']], 'state': 'confirmed'})
        check('POST review confirmed', stv == 200 and jv.get('updated') == 1
              and jv.get('file_state') == 'to_review')
        catalog.set_state(live_fid, 'loaded', '')
        stl, _jl = http(8799, base + '/review',
                        {'indexes': [r0['index']], 'state': 'rejected'})
        check('loaded 写操作 409', stl == 409)
        catalog.set_state(live_fid, 'to_load', '')
    finally:
        svc.kill()

    print('[6/7] 断库显式 503（临时服务 8797）')
    svc = start_service(8797, BAD_DSN)
    try:
        st, j = http(8797, '/api/upload', {'files': [{
            'name': src['name'],
            'data': base64.b64encode(src['data']).decode()}]})
        check('断库上传 503', st == 503, 'st={}'.format(st))
        st, _j = http(8797, '/api/sources')
        check('断库资料列表 503', st == 503)
        st, _j = http(8797, '/api/sources/{}/staging'.format(live_fid))
        check('断库暂存 503', st == 503)
    finally:
        svc.kill()

    print('[7/7] 入库全链（合成目标表＋规则/数据源/映射）')
    # 建合成抽取规则（schema 两字段）+ 目标表 + 数据源 + 入库映射
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS ' + P2_TABLE)
            cur.execute('CREATE TABLE ' + P2_TABLE + ' ('
                        ' id bigint NOT NULL AUTO_INCREMENT,'
                        ' col_a varchar(128), col_b varchar(128),'
                        ' file_id bigint NOT NULL, record_id bigint NOT NULL,'
                        ' PRIMARY KEY(id))')
            conn.commit()
    finally:
        conn.close()
    p2['tables'].append(P2_TABLE)
    # create_rule 返回的是初始版本 id（v1），直接用作绑定版本，无需再建 v2
    tv_id = catalog.create_rule('accept_tpl', '验收规则',
                                {'fields': [{'name': '字段一'},
                                            {'name': '字段二'}]},
                                {}, {})
    tpl_id = catalog.get_rule_version(version_id=tv_id)['rule_id']
    p2['tpls'].append(tpl_id)
    # 合成数据源复用平台库连接参数（从 DSN 解析，凭据不硬编码进脚本）
    _p = db._parts(db.resolve_conn(config.PLATFORM_DB))
    ds_id = catalog.create_datasource(
        'accept_ds', _p['host'], _p['port'], _p['user'],
        _p['password'], _p['database'], 'mysql')
    p2['dss'].append(ds_id)
    lt_id = catalog.create_load_table(
        ds_id, tpl_id, P2_TABLE, 'upsert',
        [{'rule_field': '字段一', 'target_column': 'col_a',
          'is_business_key': True, 'sort_order': 0},
         {'rule_field': '字段二', 'target_column': 'col_b',
          'is_business_key': False, 'sort_order': 1}])
    p2['lts'].append(lt_id)

    # 合成一条全部 confirmed 的资料，绑定规则版本
    lf = _syn_file('accept_load.pdf', b'%PDF-1.4 accept-load')
    syn_fids.append(lf)
    catalog.set_rule(lf, tv_id)
    two = [{'index': 0, 'values': {'字段一': 'A1', '字段二': 'B1'},
            'original': {'字段一': 'A1', '字段二': 'B1'},
            'lineage': {}, 'review': {'state': 'confirmed', 'at': None}},
           {'index': 1, 'values': {'字段一': 'A2', '字段二': 'B2'},
            'original': {'字段一': 'A2', '字段二': 'B2'},
            'lineage': {}, 'review': {'state': 'confirmed', 'at': None}}]
    content_db.save_records({'schema': 'c1-structure-records/1',
                             'file_id': lf, 'rule': {'name': 'accept_tpl',
                                                     'version': 1},
                             'files': [{'file_id': lf, 'name': 'accept_load.pdf',
                                        'records': two}]})
    catalog.set_state(lf, 'to_load', '')
    svc = start_service(8799)
    try:
        # 预检门禁全过 → 入库绑定 + 起线程
        st, j = http(8799, '/api/sources/{}/load'.format(lf),
                     {'load_datasource_id': ds_id, 'load_table_id': lt_id},
                     timeout=120)
        check('入库启动 200', st == 200 and j.get('ok'), 'st={} {}'.format(st, j))
        f = wait_load(8799, lf)
        check('入库完成 loaded', f['state'] == 'loaded',
              'state={} err={}'.format(f['state'], f.get('error')))
        # 目标表行数 + 溯源列
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM ' + P2_TABLE)
                rows = cur.fetchone()[0]
                cur.execute('SELECT COUNT(*) FROM ' + P2_TABLE
                            + ' WHERE file_id=%s AND record_id IS NOT NULL',
                            (lf,))
                traced = cur.fetchone()[0]
        finally:
            conn.close()
        check('目标行数=2 · 溯源列两列写入', rows == 2 and traced == 2,
              'rows={} traced={}'.format(rows, traced))
        # 回执幂等：重复入库应 409（已 loaded）
        st, _j = http(8799, '/api/sources/{}/load'.format(lf), {}, timeout=120)
        check('已 loaded 重入库 409', st == 409, 'st={}'.format(st))
        logs = catalog.list_load_logs(lf)
        check('回执 2 条', len(logs) == 2, '{} 条'.format(len(logs)))
    finally:
        svc.kill()

    return 0


if __name__ == '__main__':
    sys.exit(main())

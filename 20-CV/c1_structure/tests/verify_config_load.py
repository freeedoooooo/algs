"""验证「配置绑定入库规则 → 执行入库空体」路径（8799 验证库）。"""
import base64
import importlib
import json
import os
import sys
import time
import urllib.request
import urllib.error

os.environ['C1_STRUCTURE_DB'] = 'mysql://root:Dib12345*@10.0.6.161:3306/c1_structure_v2'
BASE = 'http://127.0.0.1:8799'
TABLE = '_accept_cfg_load'


def call(method, path, body='__none__'):
    data = json.dumps(body).encode() if body != '__none__' else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def ok(c, n, d=''):
    print(('  PASS ' if c else '  FAIL ') + n + (' · '+str(d) if d else ''))
    if not c:
        raise AssertionError(n)


def main():
    print('== 配置绑定 → 执行入库（空体）==')
    ROOT = os.getcwd()
    PARENT = os.path.dirname(ROOT)
    for p in (PARENT, ROOT):
        if p not in sys.path:
            sys.path.insert(0, p)
    catalog = importlib.import_module('c1_structure.store.catalog')
    content = importlib.import_module('c1_structure.store.content')
    artifact = importlib.import_module('c1_structure.store.artifact')
    db = importlib.import_module('c1_structure.store.db')

    # 建合成规则 + 目标表 + 映射
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS ' + TABLE)
        cur.execute('CREATE TABLE ' + TABLE +
                    ' (id bigint auto_increment primary key,'
                    ' col varchar(128), file_id bigint, record_id bigint)')
        conn.commit()
    conn.close()
    vid = catalog.create_rule('cfg_load_tpl', '配置入库测试',
                              {'fields': [{'name': '列'}]}, {}, {})
    rid = catalog.get_rule_version(version_id=vid)['rule_id']
    dss = catalog.list_datasources()
    ds = dss[0]
    lt = catalog.create_load_table(
        ds['id'], rid, TABLE, 'upsert',
        [{'rule_field': '列', 'target_column': 'col',
          'is_business_key': True, 'sort_order': 0}])

    st, j = call('POST', '/api/sources', {
        'name': 'cfg_load.pdf',
        'data': base64.b64encode(b'%PDF-1.4 cfg-load').decode()})
    ok(st == 200 and j.get('ok'), '登记资料')
    fid = j['id']

    try:
        # 写 parse.json + records（全部 confirmed）+ 绑定规则
        doc = {'schema': 'c1-structure-parse/1', 'file_id': fid,
               'pages': [{'index': 1}], 'tables': []}
        artifact.save(fid, 'parse.json', json.dumps(doc).encode(),
                      'application/json', 'json')
        rec = {'index': 0, 'values': {'列': 'V1'}, 'original': {'列': 'V1'},
               'lineage': {}, 'review': {'state': 'confirmed', 'at': None}}
        content.save_records({'schema': 'c1-structure-records/1', 'file_id': fid,
                              'rule': {'name': 'cfg_load_tpl', 'version': 1},
                              'files': [{'file_id': fid, 'name': 'x',
                                         'records': [rec]}]})
        catalog.set_rule(fid, vid)
        catalog.set_state(fid, 'to_load', None)

        # ① 通过配置 API 绑定入库规则
        st, j = call('POST', '/api/sources/%d/config' % fid,
                     {'load': {'datasource_id': ds['id'], 'load_table_id': lt}})
        ok(st == 200 and 'load' in j['changed'], '配置绑定入库规则', j)

        # ② 执行入库：空体（沿用绑定）
        st, j = call('POST', '/api/sources/%d/load' % fid, {})
        ok(st == 200 and j.get('ok'), '执行入库（空体）', j)

        # 等入库线程完成
        for _ in range(120):
            _, s = call('GET', '/api/status')
            if not s.get('running'):
                break
            time.sleep(0.5)
        st, f = call('GET', '/api/sources/%d' % fid)
        ok(f['file']['state'] == 'loaded', '状态 loaded', f['file']['state'])

        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute('SELECT col, file_id FROM ' + TABLE)
            rows = cur.fetchall()
        conn.close()
        ok(len(rows) == 1 and rows[0][0] == 'V1', '目标表写入 1 行', rows)
        print('\n全部通过')
    finally:
        time.sleep(0.5)
        call('DELETE', '/api/sources/%d' % fid)
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS ' + TABLE)
            cur.execute('DELETE FROM c1_load_table_field WHERE load_table_id=%s', (lt,))
            cur.execute('DELETE FROM c1_load_table WHERE id=%s', (lt,))
            cur.execute('DELETE FROM c1_extract_rule_version WHERE rule_id=%s', (rid,))
            cur.execute('DELETE FROM c1_extract_rule WHERE id=%s', (rid,))
        conn.commit()
        conn.close()
        print('  cleanup done')


if __name__ == '__main__':
    main()

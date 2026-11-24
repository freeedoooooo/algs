"""端到端：配置 API + 四节点执行按钮链路（连 8799 验证库）。"""
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

# 直连 DB 的部分（注入 records）必须与服务同一库
os.environ['C1_STRUCTURE_DB'] = 'mysql://root:Dib12345*@10.0.6.161:3306/c1_structure_v2'

BASE = 'http://127.0.0.1:8799'


def call(method, path, body='__none__'):
    data = json.dumps(body).encode() if body != '__none__' else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def ok(cond, name, detail=''):
    print(('  PASS ' if cond else '  FAIL ') + name + (' · ' + str(detail) if detail else ''))
    if not cond:
        raise AssertionError(name)


def wait_idle():
    for _ in range(120):
        _, s = call('GET', '/api/status')
        if not s.get('running'):
            return s
        time.sleep(0.5)
    raise RuntimeError('timeout')


def main():
    print('== 四节点执行 + 配置 端到端 ==')
    # 用一条合成资料（直接登记，不跑 OCR）
    pdf = b'%PDF-1.4 node-actions'
    st, j = call('POST', '/api/sources', {'name': 'node_actions.pdf',
                 'data': base64.b64encode(pdf).decode()})
    ok(st == 200 and j.get('ok'), '登记资料', j)
    fid = j['id']

    try:
        # --- 配置 API 读 ---
        st, cfg = call('GET', '/api/sources/%d/config' % fid)
        ok(st == 200 and cfg['ok'], 'GET config', st)
        ok(cfg['file_id'] == fid and 'schema' in cfg and 'rules' in cfg
           and 'datasources' in cfg and 'load_tables' in cfg,
           'config 四节点数据齐全')
        ok(len(cfg['schema']) > 0, '解析参数 schema 非空', len(cfg['schema']))

        # --- 配置写入：解析参数 ---
        first = cfg['schema'][0]['key']
        st, j = call('POST', '/api/sources/%d/config' % fid,
                     {'params': {first: cfg['schema'][0]['default']}})
        ok(st == 200 and j.get('ok') and 'params' in j['changed'], '写解析参数', j)

        # --- 配置写入：抽取规则（绑定第一个规则版本，若有） ---
        if cfg['rules']:
            vid = cfg['rules'][0]['version_id']
            st, j = call('POST', '/api/sources/%d/config' % fid,
                         {'rule_version_id': vid})
            ok(st == 200 and 'rule_version_id' in j['changed'], '绑定抽取规则', j)
            st, cfg2 = call('GET', '/api/sources/%d/config' % fid)
            ok(cfg2['rule_version_id'] == vid, '抽取规则读回一致')

        # --- 手动注入 parse.json + records，模拟已解析待校验 ---
        import importlib, os
        ROOT = os.getcwd()
        PARENT = os.path.dirname(ROOT)
        for p in (PARENT, ROOT):
            if p not in sys.path:
                sys.path.insert(0, p)
        content = importlib.import_module('c1_structure.store.content')
        catalog = importlib.import_module('c1_structure.store.catalog')
        cdb = importlib.import_module('c1_structure.store.content_db')
        doc = {'schema': 'c1-structure-parse/1', 'file_id': fid,
               'pages': [{'index': 1, 'texts': ['x']}], 'tables': []}
        # 走 artifact 直接写 parse.json
        artifact = importlib.import_module('c1_structure.store.artifact')
        artifact.save(fid, 'parse.json', json.dumps(doc).encode(),
                      'application/json', 'json')
        recs = [{'index': 0, 'values': {'列': '甲'}, 'original': {'列': '甲'},
                 'lineage': {}, 'review': {'state': 'pending', 'at': None}},
                {'index': 1, 'values': {'列': '乙'}, 'original': {'列': '乙'},
                 'lineage': {}, 'review': {'state': 'edited', 'at': None}}]
        content.save_records({'schema': 'c1-structure-records/1', 'file_id': fid,
                              'rule': {'name': 'r', 'version': 1},
                              'files': [{'file_id': fid, 'name': 'x', 'records': recs}]})
        catalog.set_state(fid, 'to_review', None)

        # --- gate 计数 ---
        st, g = call('GET', '/api/sources/%d/gate' % fid)
        ok(st == 200 and g['pending'] == 1 and g['edited'] == 1,
           'gate 待审计数', g)

        # --- 执行校验（全部通过）---
        st, j = call('POST', '/api/sources/%d/approve-all' % fid, {})
        ok(st == 200 and j.get('ok') and j['updated'] == 2,
           '执行校验：全部通过 2 条', j)
        st, cfg2 = call('GET', '/api/sources/%d/config' % fid)
        st, f = call('GET', '/api/sources/%d' % fid)
        ok(f['file']['state'] == 'to_load', '校验后推进 to_load', f['file']['state'])

        # --- pipeline 的 load 字段（前端判断用）---
        st, pl = call('GET', '/api/sources/%d/pipeline' % fid)
        ok(st == 200 and 'load' in pl['pipeline'], 'pipeline 含 load 字段')

        # --- 配置写入：入库规则（若有数据源/映射）---
        if cfg['datasources'] and cfg['load_tables']:
            ds = cfg['datasources'][0]
            lt = [t for t in cfg['load_tables'] if t['datasource_id'] == ds['id']]
            if lt:
                st, j = call('POST', '/api/sources/%d/config' % fid,
                             {'load': {'datasource_id': ds['id'],
                                       'load_table_id': lt[0]['id']}})
                ok(st == 200 and 'load' in j['changed'], '绑定入库规则', j)
                st, pl = call('GET', '/api/sources/%d/pipeline' % fid)
                ok(pl['pipeline']['load'] and pl['pipeline']['load'].get('load_table_id'),
                   'pipeline load_table_id 可读')

        # --- 页面与静态资源 ---
        for path in ('/', '/sources', '/static/sources.js', '/static/sources.css'):
            st, _ = call('GET', path) if path.startswith('/api') else (
                urllib.request.urlopen(BASE + path).status, None)
            ok(st == 200, '资源 ' + path)

        print('\n全部通过')
    finally:
        # 清理（delete_file 已做应用层级联）
        time.sleep(0.5)
        st, _ = call('DELETE', '/api/sources/%d' % fid)
        print('  cleanup:', st)


if __name__ == '__main__':
    main()

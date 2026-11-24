"""P1 store 层自测（不进 unittest discover；直连指定库，默认 c1_structure_v2）。

用法：python tests/verify_p1_store.py [dsn]
只读验证库，跑完清理自己造的行（file_id 从 9_000_000 起避免撞真实数据）。
"""
import os
import sys
import hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import config
from c1_structure.store import db, catalog, artifact, content_db, loader

DSN = sys.argv[1] if len(sys.argv) > 1 else config.PLATFORM_DB.replace(
    'c1_structure_dev', 'c1_structure_v2')


def main():
    from urllib.parse import urlparse
    u = urlparse(DSN)
    print('verify against:', u.path.lstrip('/'))
    assert 'c1_structure_v2' in DSN, '自测只允许打验证库，拒绝其他库'
    # DSN 必须在 import config 前由环境变量 C1_STRUCTURE_DB 指定；
    # 这里复写 config.PLATFORM_DB（db.connect 默认参数运行时读它，安全）。
    config.PLATFORM_DB = DSN

    fid = 9000000
    raw = b'%PDF-1.4 P1 verify ' + os.urandom(8)
    sha = hashlib.sha256(raw).hexdigest()

    # 1. 登记两次同字节 → 两个不同 id，dedup 恒 False（去哈希去重）
    f1, d1 = catalog.register_file('p1.pdf', 'pdf', len(raw), sha, raw)
    f2, d2 = catalog.register_file('p1.pdf', 'pdf', len(raw), sha, raw)
    print('register:', f1, f2, 'dedup', d1, d2)
    assert d1 is False and d2 is False and f1 != f2, '去哈希去重失败'

    # 2. 状态/规则/入库绑定
    catalog.set_state(f1, 'parsing')
    catalog.set_state(f1, 'to_extract')
    catalog.set_params(f1, {'dpi': 110})
    f = catalog.get_file(f1)
    print('state/params:', f['state'], f['params_json'])
    assert f['state'] == 'to_extract' and f['params_json'] == {'dpi': 110}
    assert 'content' not in f, '列表列不应含 BLOB'

    # 3. 产物按 file_id 存取（两次覆盖 same name）
    artifact.save(f1, 'parse.json', b'{"a":1}', 'application/json', 'json')
    a = artifact.get(f1, 'parse.json')
    print('artifact:', a['data'])
    assert a['data'] == b'{"a":1}'
    assert artifact.latest_file_with('parse.json') == f1

    # 4. 暂存记录 + 血缘 + field
    doc = {'file_id': f1, 'files': [{
        'file_id': f1, 'name': 'p1.pdf',
        'records': [{
            'index': 0, 'values': {'金额': '123'},
            'original': {'金额': '123'},
            'lineage': {'金额': [{'page': 1, 'table_index': 0,
                              'table_scope': 'page', 'cell_bbox': [1, 2, 3, 4],
                              'space': 'source', 'raw_text': '123'}]},
            'review': {'state': 'pending', 'at': None},
        }]}]}
    content_db.save_records(doc)
    recs = content_db.get_records(f1)
    print('records:', recs['file_id'], len(recs['files'][0]['records']))
    assert recs['file_id'] == f1
    assert recs['files'][0]['records'][0]['lineage']['金额'][0]['raw_text'] == '123'

    # 5. 门禁 / 改值 / 确认
    g = content_db.gate_counts(f1)
    assert g['records_n'] == 1 and g['pending'] == 1, g
    content_db.patch_record(f1, 0, {'金额': '456'})
    content_db.set_review(f1, [0], 'confirmed')
    g = content_db.gate_counts(f1)
    print('gate after review:', g)
    assert g['confirmed'] == 1 and g['pending'] == 0

    # 6. record_id_map / locate
    rid_map = content_db.record_id_map(f1)
    rid = rid_map[(f1, 0)]
    loc = content_db.locate_record(rid)
    print('locate:', loc)
    assert loc['file_id'] == f1 and loc['record_index'] == 0

    # 7. 回执（幂等）
    first = catalog.add_load_log(f1, 0, 1, 't', 'pk1', 'insert')
    second = catalog.add_load_log(f1, 0, 1, 't', 'pk1', 'insert')
    logs = catalog.list_load_logs(f1)
    print('load log:', first, second, len(logs))
    assert first is True and second is False and len(logs) == 1

    # 8. ledger 扁平行
    led = content_db.ledger()
    hit = [x for x in led if x['file_id'] == f1]
    print('ledger:', hit)
    assert hit and hit[0]['confirmed_n'] == 1

    # 9. TRACE_COLS
    print('TRACE_COLS:', loader.TRACE_COLS)
    assert loader.TRACE_COLS == ('file_id', 'record_id')

    # 清理
    conn = db.connect()
    with conn.cursor() as cur:
        for t in ('c1_staging_field', 'c1_staging_lineage'):
            cur.execute('DELETE FROM {} WHERE record_id IN (SELECT id FROM'
                        ' c1_staging_record WHERE file_id=%s)'.format(t), (f1,))
        for t in ('c1_staging_record', 'c1_parse_artifact', 'c1_load_log',
                  'c1_load_quarantine'):
            cur.execute('DELETE FROM {} WHERE file_id=%s'.format(t), (f1,))
        cur.execute('DELETE FROM c1_doc_file WHERE id IN (%s,%s)', (f1, f2))
        conn.commit()
    conn.close()
    print('P1 STORE VERIFY PASS')


if __name__ == '__main__':
    main()

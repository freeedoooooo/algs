"""P2 service 编排自测：登记→绑规则→抽取（引擎 mock）→ 门禁派生。

在验证库 c1_structure_v2 上跑；mock pipeline 避免真 OCR；跑完清理。
用法：python tests/verify_p2_service.py
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
config.PLATFORM_DB = config.PLATFORM_DB.replace(
    'c1_structure_dev', 'c1_structure_v2')
assert 'c1_structure_v2' in config.PLATFORM_DB

from c1_structure import service, collect
from c1_structure.store import db, catalog, content

PARSE_DOC = {
    'schema_version': 'c1-structure/1',
    'file': {'name': 'p2.pdf'},
    'pages': [{'index': 1, 'space': 'source',
               'texts': [{'text': '金额 100', 'box': [[1, 1], [50, 1],
                                                   [50, 9], [1, 9]]}],
               'tables': [{'headers': ['金额'], 'rows': [['100']],
                           'cells': [[[1, 1], [50, 1], [50, 9], [1, 9]]]}]}],
    'stitched_tables': [],
}


def main():
    raw = b'%PDF-1.4 P2 service ' + os.urandom(6)
    sha = hashlib.sha256(raw).hexdigest()
    fid, dup = catalog.register_file('p2.pdf', 'pdf', len(raw), sha, raw)
    print('registered:', fid, 'dedup', dup)
    assert dup is False

    # 走真 catalog 绑规则+状态；mock 掉 get_extract 提供 parse.json
    catalog.set_state(fid, 'to_extract', '')
    rule = service.resolve_rule()   # 默认「原始透传」v1
    catalog.set_rule(fid, rule['version_id'])
    print('rule:', rule['name'], 'v', rule['version'])

    real_get_extract = content.get_extract
    try:
        content.get_extract = lambda file_id: PARSE_DOC
        result = service.run_extract(fid)
        print('extract:', result['ok'], result['files'][0]['records_n'])
        assert result['ok'] and result['files'][0]['records_n'] >= 1

        f = catalog.get_file(fid)
        print('state after extract:', f['state'])
        assert f['state'] == 'to_review'

        # 全部确认 → 派生 to_load
        from c1_structure.store import content_db
        recs = content_db.get_records(fid)['files'][0]['records']
        content_db.set_review(fid, [r['index'] for r in recs], 'confirmed')
        new_state = service.derive_review_state(fid)
        print('state after confirm-all:', new_state)
        assert new_state == 'to_load'
    finally:
        content.get_extract = real_get_extract

    # 清理
    conn = db.connect()
    with conn.cursor() as cur:
        for t in ('c1_staging_field', 'c1_staging_lineage'):
            cur.execute('DELETE FROM ' + t + ' WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record WHERE file_id=%s)',
                        (fid,))
        for t in ('c1_staging_record', 'c1_parse_artifact', 'c1_load_log',
                  'c1_load_quarantine'):
            cur.execute('DELETE FROM ' + t + ' WHERE file_id=%s', (fid,))
        cur.execute('DELETE FROM c1_doc_file WHERE id=%s', (fid,))
        conn.commit()
    conn.close()
    print('P2 SERVICE VERIFY PASS')


if __name__ == '__main__':
    main()

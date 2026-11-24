"""C5 只读验证：真实 parse.json（8765 GET）→ collect.build → records。

用法：
    D:/miniforge3/envs/paddle/python.exe tests/verify_real_extract.py [task_id]

只读约束：仅 GET 已运行服务，不启停服务、不写 DB、不新建任务、不落盘产物。
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import collect

BASE = 'http://127.0.0.1:8765'
DEFAULT_TASK = 446


def fetch_doc(task_id):
    url = '{}/api/tasks/{}/parse'.format(BASE, task_id)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def make_spec():
    return {
        'spec_version': 2,
        'tables': [{'ref': 'main', 'header_contains': '期末余额'}],
        'records': {'strategy': 'row'},
        'fields': [
            {'target': '项目', 'pipeline': [
                {'op': 'cell', 'source': 'main', 'column': {'index': 0}}]},
            {'target': '附注', 'pipeline': [
                {'op': 'cell', 'source': 'main',
                 'column': {'header_contains': '附注六'}}]},
            {'target': '期末余额', 'pipeline': [
                {'op': 'cell', 'source': 'main',
                 'column': {'header_contains': '期末余额'}},
                {'op': 'regex', 'pattern': r'-?[\d,]+\.\d{2}'},
                {'op': 'number', 'strip': ','}]},
        ],
    }


def main():
    task_id = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TASK
    doc = fetch_doc(task_id)
    print('输入 schema={} pages={}'.format(
        doc.get('schema'), len(doc.get('pages') or [])))

    records = collect.build(doc, {'mapping_json': make_spec()})
    assert records, '抽取结果为空'
    keys = {'index', 'values', 'original', 'lineage', 'review'}
    for rec in records:
        assert set(rec) == keys, 'records 信封键变化'
        assert rec['review'] == {'state': 'pending', 'at': None}
    assert [r['index'] for r in records] == list(range(len(records)))

    sample = records[0]
    print('输出 records={} 首条 values={}'.format(
        len(records), json.dumps(sample['values'], ensure_ascii=False)))
    print('首条 original={}'.format(
        json.dumps(sample['original'], ensure_ascii=False)))
    for target in sample['lineage']:
        anchors = sample['lineage'][target]
        if anchors:
            a = anchors[0]
            print('血缘 {} page={} bbox={} raw={}'.format(
                target, a['page'], a['cell_bbox'], a['raw_text']))
    print('C5 本层验证通过：真实 parse.json → records，未写 DB')


if __name__ == '__main__':
    main()

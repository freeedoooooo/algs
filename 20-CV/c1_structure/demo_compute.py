"""可重复执行的计算示例配置；不改表结构、不覆盖已有定义。"""
import argparse
import json

from .compute import execute_frame, execute_index, execute_rule
from .store import catalog, db, index_repo, loader, rule_repo, frame_repo
from .store.catalog import load as load_repo

PREFIX = '演示·'
INDEX_NAMES = [
    '业务记录总数', '最小业务主键', '最大业务主键',
    '唯一溯源记录数', '借方发生额种类', '账户余额种类',
    '头部业务样本数', '尾部业务样本数',
]
RULE_NAMES = [
    '数据量达到基准', '主键区间有效', '溯源记录完整',
    '金额字段覆盖充分', '头尾样本均存在',
]
FRAME_NAMES = [
    '流水数据质量评估', '记录覆盖完整性', '流水综合评估',
]
LEGACY_INDEX_NAMES = [
    PREFIX + '业务行数', PREFIX + '最小记录ID', PREFIX + '最大记录ID',
    PREFIX + '唯一记录数', PREFIX + '借方金额种类', PREFIX + '贷方金额种类',
    PREFIX + '头部十条记录数', PREFIX + '尾部十条记录数',
]
LEGACY_RULE_NAMES = [
    PREFIX + '数据量充足', PREFIX + '记录ID有跨度', PREFIX + '记录唯一完整',
    PREFIX + '金额字段丰富', PREFIX + '尾部样本存在',
]
LEGACY_FRAME_NAMES = [
    PREFIX + '数据质量评估', PREFIX + '记录覆盖检查', PREFIX + '综合演示',
]
DEMO_NAMES = set(INDEX_NAMES + RULE_NAMES + FRAME_NAMES +
                 LEGACY_INDEX_NAMES + LEGACY_RULE_NAMES + LEGACY_FRAME_NAMES)


def rename_legacy_defs():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for table, names in (
                    ('c1_index_info', zip(LEGACY_INDEX_NAMES, INDEX_NAMES)),
                    ('c1_rule_info', zip(LEGACY_RULE_NAMES, RULE_NAMES)),
                    ('c1_frame_info', zip(LEGACY_FRAME_NAMES, FRAME_NAMES))):
                for old, new in names:
                    cur.execute('UPDATE {} SET name=%s WHERE name=%s'
                                .format(table), (new, old))
        conn.commit()
    finally:
        conn.close()


def find_demo_source():
    datasource_id = load_repo.ensure_default_datasource()
    if not datasource_id:
        raise RuntimeError('没有可用的产品库数据源')
    datasource = load_repo.get_datasource(datasource_id)
    required = {'id', 'file_id', 'record_id', 'account_1', 'account_2'}
    tables = loader.list_tables(datasource)
    if 'biz_test_1' in tables:
        tables = ['biz_test_1'] + [t for t in tables if t != 'biz_test_1']
    for table in tables:
        if table.startswith('c1_'):
            continue
        columns = {c['name'] for c in loader.list_columns(datasource, table)}
        if required <= columns:
            return datasource, table
    raise RuntimeError('没有找到含 id/file_id/record_id/account_1/account_2 的业务表')


def ensure_trace_sample(datasource, table):
    file = catalog.get_file(2)
    if not file:
        return {'file_id': None, 'seeded': False}
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id,record_index,values_json'
                        ' FROM c1_staging_record WHERE file_id=2'
                        ' ORDER BY record_index LIMIT 1')
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return {'file_id': 2, 'seeded': False, 'reason': '没有抽取记录'}
    record_id, record_index, raw = row
    values = json.loads(raw)
    normalized = {''.join(str(k).split()): k for k in values}
    debit_key = next((normalized[k] for k in
                      ('借方发生额', '借方金额') if k in normalized), None)
    balance_key = normalized.get('余额')
    if not debit_key or not balance_key:
        return {'file_id': 2, 'seeded': False, 'reason': '金额字段不匹配'}
    fields = [
        {'rule_field': debit_key, 'target_column': 'account_1',
         'is_business_key': False},
        {'rule_field': balance_key, 'target_column': 'account_2',
         'is_business_key': False},
    ]
    snapshot = {'schema_version': 1, 'fields': [
        {'name': f['rule_field'], 'type': 'text'} for f in fields]}
    load_table_id = file.get('load_table_id')
    if not load_table_id:
        load_table_id = catalog.create_load_table(
            datasource['id'], None, table, 'insert', fields,
            snapshot=snapshot)
    if (file.get('load_datasource_id') != datasource['id'] or
            file.get('load_table_id') != load_table_id):
        catalog.set_load(2, datasource['id'], load_table_id)
    conn = loader.connect_datasource(datasource)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM {} WHERE file_id=%s AND record_id=%s'
                        .format(loader._ident(table)), (2, record_id))
            hit = cur.fetchone()
            if hit:
                target_pk = str(hit[0])
                action = 'exists'
            else:
                column_map = {f['rule_field']: f['target_column']
                              for f in fields}
                action, target_pk = loader.write_record(
                    cur, table, column_map,
                    {debit_key: values[debit_key],
                     balance_key: values[balance_key]},
                    'insert', [], {'file_id': 2, 'record_id': record_id})
        conn.commit()
    finally:
        conn.close()
    catalog.add_load_log(2, record_index, datasource['id'], table,
                           target_pk, 'insert')
    return {'file_id': 2, 'seeded': action == 'insert',
            'record_id': record_id, 'target_pk': target_pk,
            'load_table_id': load_table_id}


def read_stats(datasource, table):
    conn = loader.connect_datasource(datasource)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*),MIN(id),MAX(id),COUNT(DISTINCT record_id),'
                'COUNT(DISTINCT account_1),COUNT(DISTINCT account_2) '
                'FROM {}'.format(loader._ident(table)))
            row = cur.fetchone()
            cur.execute(
                'SELECT COUNT(*) FROM {} WHERE id>%s'.format(loader._ident(table)),
                (row[2],))
            tail = cur.fetchone()[0]
    finally:
        conn.close()
    total, min_id, max_id, unique_records, debit_kinds, balance_kinds = row
    return {
        'total': int(total or 0), 'min_id': int(min_id or 0),
        'max_id': int(max_id or 0), 'unique_records': int(unique_records or 0),
        'debit_kinds': int(debit_kinds or 0),
        'balance_kinds': int(balance_kinds or 0),
        'tail': int(tail or 0),
    }


def index_specs(table, stats):
    return [
        (INDEX_NAMES[0], None, 'count', []),
        (INDEX_NAMES[1], 'id', 'min', []),
        (INDEX_NAMES[2], 'id', 'max', []),
        (INDEX_NAMES[3], 'record_id', 'count_distinct', []),
        (INDEX_NAMES[4], 'account_1', 'count_distinct', []),
        (INDEX_NAMES[5], 'account_2', 'count_distinct', []),
        (INDEX_NAMES[6], None, 'count', [{'column': 'id', 'op': 'lte', 'value': stats['min_id'] + 9}]),
        (INDEX_NAMES[7], None, 'count', [{'column': 'id', 'op': 'gt', 'value': stats['max_id'] - 10}]),
    ]


def ensure_index(datasource_id, table, spec):
    name, column, aggregate, filters = spec
    existing = index_repo.get_def(name=name)
    if existing:
        return existing['id'], False
    return index_repo.save_def(name, datasource_id, table, column, aggregate, filters), True


def ensure_rule(name, refs, conditions, combine='all'):
    existing = rule_repo.get_def(name=name)
    if existing:
        return existing['id'], False
    return rule_repo.save_def(name, refs, conditions, combine), True


def ensure_frame(name, refs, combine='weighted', threshold='0.65'):
    existing = frame_repo.get_def(name=name)
    if existing:
        return existing['id'], False
    return frame_repo.save_def(name, refs, combine, threshold), True


def seed_demo(run=True):
    rename_legacy_defs()
    datasource, table = find_demo_source()
    trace = ensure_trace_sample(datasource, table)
    stats = read_stats(datasource, table)
    specs = index_specs(table, stats)
    index_ids, created = {}, 0
    for spec in specs:
        index_id, is_new = ensure_index(datasource['id'], table, spec)
        index_ids[spec[0]] = index_id
        created += int(is_new)

    def refs(*names):
        return [{'index_id': index_ids[name], 'alias': 'm' + str(i + 1)}
                for i, name in enumerate(names)]

    def rule(name, index_names, conditions, combine='all'):
        nonlocal created
        rule_id, is_new = ensure_rule(name, refs(*index_names), conditions, combine)
        created += int(is_new)
        return rule_id

    def cond(alias, op, threshold):
        return {'alias': alias, 'op': op, 'threshold': threshold}

    volume = max(1, stats['total'] // 2)
    rule_ids = {
        RULE_NAMES[0]: rule(
            RULE_NAMES[0], [INDEX_NAMES[0]],
            [cond('m1', 'gte', volume)]),
        RULE_NAMES[1]: rule(
            RULE_NAMES[1], [INDEX_NAMES[1], INDEX_NAMES[2]],
            [cond('m1', 'eq', stats['min_id']),
             cond('m2', 'gt', stats['min_id'])]),
        RULE_NAMES[2]: rule(
            RULE_NAMES[2], [INDEX_NAMES[3], INDEX_NAMES[0]],
            [cond('m1', 'gte', stats['total']), cond('m2', 'gt', 0)]),
        RULE_NAMES[3]: rule(
            RULE_NAMES[3], [INDEX_NAMES[4], INDEX_NAMES[5]],
            [cond('m1', 'gt', 1), cond('m2', 'gt', 1)]),
        RULE_NAMES[4]: rule(
            RULE_NAMES[4], [INDEX_NAMES[6], INDEX_NAMES[7]],
            [cond('m1', 'gt', 0), cond('m2', 'gt', 0)], 'any'),
    }

    def frame_refs(items):
        return [{'rule_id': rule_ids[name], 'weight': str(weight), 'veto': bool(veto)}
                for name, weight, veto in items]

    frames = [
        (FRAME_NAMES[0], frame_refs([(RULE_NAMES[2], .5, False),
                                     (RULE_NAMES[3], .3, False),
                                     (RULE_NAMES[4], .2, False)]), 'weighted', '0.7'),
        (FRAME_NAMES[1], frame_refs([(RULE_NAMES[1], 1, False),
                                     (RULE_NAMES[2], 1, False)]), 'all_pass', None),
        (FRAME_NAMES[2], frame_refs([(RULE_NAMES[0], .25, False),
                                     (RULE_NAMES[1], .2, False),
                                     (RULE_NAMES[2], .25, False),
                                     (RULE_NAMES[3], .15, False),
                                     (RULE_NAMES[4], .15, False)]), 'weighted', '0.65'),
    ]
    frame_ids = {}
    for name, rule_refs, combine, threshold in frames:
        frame_id, is_new = ensure_frame(name, rule_refs, combine, threshold)
        frame_ids[name] = frame_id
        created += int(is_new)

    results = {}
    if run:
        for name, index_id in index_ids.items():
            results[name] = execute_index(index_id)['value']
        for name, rule_id in rule_ids.items():
            results[name] = execute_rule(rule_id)['value']
        for name, frame_id in frame_ids.items():
            results[name] = execute_frame(frame_id)['value']
    return {'table': table, 'stats': stats, 'created': created, 'trace': trace,
            'index_ids': index_ids, 'rule_ids': rule_ids,
            'frame_ids': frame_ids, 'results': results}


def cleanup_demo():
    removed = {'index': 0, 'rule': 0, 'frame': 0}
    for name in FRAME_NAMES + LEGACY_FRAME_NAMES:
        found = frame_repo.get_def(name=name)
        if found:
            frame_repo.delete_def(found['id'])
            removed['frame'] += 1
    for name in RULE_NAMES + LEGACY_RULE_NAMES:
        found = rule_repo.get_def(name=name)
        if found:
            rule_repo.delete_def(found['id'])
            removed['rule'] += 1
    for name in INDEX_NAMES + LEGACY_INDEX_NAMES:
        found = index_repo.get_def(name=name)
        if found:
            index_repo.delete_def(found['id'])
            removed['index'] += 1
    return removed


def main():
    parser = argparse.ArgumentParser(description='幂等补充计算示例配置')
    parser.add_argument('--cleanup', action='store_true', help='只删除本脚本的示例定义及结果')
    parser.add_argument('--no-run', action='store_true', help='只写定义，不执行计算')
    args = parser.parse_args()
    if args.cleanup:
        print(cleanup_demo())
        return
    result = seed_demo(run=not args.no_run)
    print('业务表: {table}; 新建定义: {created}; 统计: {stats}'.format(**result))
    print('多资料追溯: {}'.format(result['trace']))
    if result['results']:
        for name, value in result['results'].items():
            print('{} = {}'.format(name, value))


if __name__ == '__main__':
    main()

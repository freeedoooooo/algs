"""可重复执行的计算示例配置；rich-demo 显式创建独立演示业务表。"""
import argparse
import hashlib
import json

from .compute import execute_frame, execute_index, execute_rule
from .store import artifact, catalog, db, index_repo, loader, rule_repo, frame_repo
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

RICH_TABLES = ['biz_demo_2', 'biz_demo_3']
RICH_INDEX_NAMES = [
    '四月流水笔数', '四月借方金额合计', '五月流水笔数', '五月借方金额合计',
]
RICH_RULE_NAMES = ['四月流水量达标', '五月借方金额充足']
RICH_FRAME_NAMES = ['多月流水综合评估']
RICH_DOCUMENTS = [
    {'name': '演示·流水账单（四月上旬）.pdf', 'table': RICH_TABLES[0],
     'title': '四月流水账单（上旬）',
     'rows': [('1200.00', '98200.00'), ('0.00', '99400.00'),
              ('860.50', '100260.50'), ('3200.00', '97060.50'),
              ('0.00', '100260.50'), ('4999.90', '95260.60')]},
    {'name': '演示·流水账单（四月下旬）.pdf', 'table': RICH_TABLES[0],
     'title': '四月流水账单（下旬）',
     'rows': [('0.00', '96260.60'), ('15000.00', '81260.60'),
              ('680.00', '81940.60'), ('2300.00', '79640.60'),
              ('0.00', '84640.60')]},
    {'name': '演示·流水账单（五月上旬）.pdf', 'table': RICH_TABLES[1],
     'title': '五月流水账单（上旬）',
     'rows': [('3600.00', '120600.00'), ('0.00', '124600.00'),
              ('820.00', '125420.00'), ('4800.00', '120620.00'),
              ('260.00', '120880.00'), ('0.00', '126880.00'),
              ('1950.00', '124930.00')]},
    {'name': '演示·流水账单（五月下旬）.pdf', 'table': RICH_TABLES[1],
     'title': '五月流水账单（下旬）',
     'rows': [('0.00', '129930.00'), ('7600.00', '122330.00'),
              ('430.00', '122760.00'), ('9800.00', '112960.00')]},
]
DEMO_NAMES.update(RICH_INDEX_NAMES + RICH_RULE_NAMES + RICH_FRAME_NAMES)


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


def _demo_pdf(title, rows):
    import pymupdf
    scale = 1.5
    pdf = pymupdf.open()
    page = pdf.new_page(width=842, height=595)
    page.draw_rect(pymupdf.Rect(0, 0, 842, 92), color=None,
                   fill=(0.12, 0.25, 0.45))
    page.insert_text((48, 40), '结构化工具 · 计算演示',
                     fontname='china-s', fontsize=15, color=(1, 1, 1))
    page.insert_text((48, 68), title, fontname='china-s', fontsize=12,
                     color=(0.82, 0.9, 1))
    page.insert_text((48, 124), '演示数据，仅用于流程展示',
                     fontname='china-s', fontsize=11, color=(0.35, 0.4, 0.48))
    headers = [('序号', 58), ('借方发生额', 250), ('余额', 570)]
    for text, x in headers:
        page.insert_text((x, 176), text, fontname='china-s', fontsize=12)
    page.draw_line(pymupdf.Point(48, 190), pymupdf.Point(794, 190),
                   color=(0.75, 0.8, 0.86), width=1)
    cells = []
    for i, (debit, balance) in enumerate(rows, 1):
        y = 226 + (i - 1) * 42
        if i % 2 == 0:
            page.draw_rect(pymupdf.Rect(48, y - 22, 794, y + 12),
                           color=None, fill=(0.95, 0.97, 0.99))
        page.insert_text((58, y), str(i), fontname='china-s', fontsize=11)
        page.insert_text((250, y), debit, fontname='china-s', fontsize=11)
        page.insert_text((570, y), balance, fontname='china-s', fontsize=11)
        cells.append({
            '借方发生额': [250 * scale, (y - 13) * scale,
                         (250 + pymupdf.get_text_length(
                             debit, fontname='china-s', fontsize=11) + 4) * scale,
                         (y + 3) * scale],
            '余额': [570 * scale, (y - 13) * scale,
                    (570 + pymupdf.get_text_length(
                        balance, fontname='china-s', fontsize=11) + 4) * scale,
                    (y + 3) * scale],
        })
    page.insert_text((48, 552), 'C1 Structure / Compute Demo',
                     fontname='china-s', fontsize=9, color=(0.55, 0.6, 0.67))
    data = pdf.tobytes()
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    preview = pixmap.tobytes('png')
    size = [pixmap.width, pixmap.height]
    pdf.close()
    return data, preview, size, cells


def ensure_rich_tables(datasource):
    conn = loader.connect_datasource(datasource)
    try:
        with conn.cursor() as cur:
            for i, table in enumerate(RICH_TABLES, 2):
                cur.execute(
                    'CREATE TABLE IF NOT EXISTS `{}` ('
                    '`id` bigint NOT NULL AUTO_INCREMENT,'
                    '`file_id` bigint DEFAULT NULL,'
                    '`record_id` bigint DEFAULT NULL,'
                    '`account_1` varchar(200) DEFAULT NULL,'
                    '`account_2` varchar(200) DEFAULT NULL,'
                    '`created_at` datetime DEFAULT CURRENT_TIMESTAMP,'
                    '`updated_at` datetime DEFAULT CURRENT_TIMESTAMP'
                    ' ON UPDATE CURRENT_TIMESTAMP,'
                    'PRIMARY KEY (`id`))'
                    ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'
                    " COLLATE=utf8mb4_0900_ai_ci COMMENT='计算演示业务表_{}'"
                    .format(table, i))
        conn.commit()
    finally:
        conn.close()


def ensure_rich_mapping(datasource, table):
    for mapping in catalog.list_load_tables(datasource['id']):
        if mapping['target_table'] == table:
            return mapping['id'], False
    fields = [
        {'rule_field': '借方发生额', 'target_column': 'account_1',
         'is_business_key': False},
        {'rule_field': '余额', 'target_column': 'account_2',
         'is_business_key': False},
    ]
    snapshot = {'schema_version': 1, 'fields': [
        {'name': field['rule_field'], 'type': 'text'} for field in fields]}
    return catalog.create_load_table(
        datasource['id'], None, table, 'insert', fields, snapshot=snapshot), True


def _save_rich_preview(file_id, spec, preview, size, cells, record_ids):
    artifact.save(file_id, 'source.png', preview, 'image/png', 'image')
    artifact.save(file_id, 'boxes.png', preview, 'image/png', 'image')
    lines = [spec['title'], '演示数据，仅用于流程展示',
             '序号\t借方发生额\t余额']
    lines.extend('{}\t{}\t{}'.format(i, debit, balance)
                 for i, (debit, balance) in enumerate(spec['rows'], 1))
    artifact.save_json(file_id, 'parse.json', {
        'schema': 'c1-structure/1',
        'file': {'name': spec['name'], 'kind': 'pdf', 'encoding': '',
                 'page_count': 1},
        'params': {'model': '内置演示', 'page': 'all', 'dpi': 108},
        'pages': [{
            'index': 1, 'size': size, 'rectified_size': None,
            'image': 'source.png', 'rectified_image': None,
            'boxes_image': 'boxes.png', 'space': 'source',
            'route': 'demo', 'text_layer': False, 'cropbox_limited': False,
            'plain_text': '\n'.join(lines), 'elapsed': 0,
            'notes': ['计算演示 PDF：字段框与暂存记录一一对应'],
            'stats': {'lines': len(lines), 'avg_score': 1,
                      'low_score_lines': 0},
            'texts': [], 'blocks': [], 'tables': [],
        }],
        'stitched_tables': [],
    })
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM c1_staging_lineage WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record WHERE file_id=%s)',
                        (file_id,))
            for seq, (record_id, row_cells) in enumerate(zip(record_ids, cells)):
                for field_name, bbox in row_cells.items():
                    cur.execute(
                        'INSERT INTO c1_staging_lineage'
                        ' (record_id,field_name,region_seq,page,table_index,'
                        ' table_scope,space,cell_bbox,raw_text)'
                        ' VALUES (%s,%s,%s,1,1,%s,%s,%s,%s)',
                        (record_id, field_name, seq, 'source', 'source',
                         json.dumps(bbox), spec['rows'][seq][
                             0 if field_name == '借方发生额' else 1]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_rich_document(datasource, spec, load_table_id):
    content, preview, page_size, cells = _demo_pdf(spec['title'], spec['rows'])
    file_id = None
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_doc_file'
                        " WHERE name=%s AND tags='计算演示'", (spec['name'],))
            row = cur.fetchone()
            if row:
                file_id = row[0]
        conn.commit()
    finally:
        conn.close()
    created = file_id is None
    if created:
        file_id, _ = catalog.register_file(
            spec['name'], 'pdf', len(content),
            hashlib.sha256(content).hexdigest(), content)
        catalog.update_file_meta(file_id, tags='计算演示',
                                 note='计算流程图演示数据')
    catalog.set_load(file_id, datasource['id'], load_table_id)
    catalog.set_state(file_id, 'loaded')

    record_ids = []
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for record_index, (debit, balance) in enumerate(spec['rows']):
                values = {'借方发生额': debit, '余额': balance}
                raw = json.dumps(values, ensure_ascii=False)
                cur.execute('SELECT id FROM c1_staging_record'
                            ' WHERE file_id=%s AND record_index=%s',
                            (file_id, record_index))
                row = cur.fetchone()
                if row:
                    record_id = row[0]
                else:
                    cur.execute(
                        'INSERT INTO c1_staging_record'
                        ' (file_id,record_index,review_state,values_json,original_json)'
                        " VALUES (%s,%s,'confirmed',%s,%s)",
                        (file_id, record_index, raw, raw))
                    record_id = cur.lastrowid
                    for name, value in values.items():
                        cur.execute(
                            'INSERT INTO c1_staging_field'
                            ' (record_id,field_name,value_text,original_text)'
                            ' VALUES (%s,%s,%s,%s)',
                            (record_id, name, value, value))
                record_ids.append(record_id)
        conn.commit()
    finally:
        conn.close()

    _save_rich_preview(file_id, spec, preview, page_size, cells, record_ids)

    conn = loader.connect_datasource(datasource)
    inserted = 0
    try:
        with conn.cursor() as cur:
            for record_index, record_id in enumerate(record_ids):
                debit, balance = spec['rows'][record_index]
                cur.execute('SELECT id FROM {} WHERE file_id=%s AND record_id=%s'
                            .format(loader._ident(spec['table'])),
                            (file_id, record_id))
                hit = cur.fetchone()
                if hit:
                    target_pk = str(hit[0])
                else:
                    values = {'借方发生额': debit, '余额': balance}
                    _, target_pk = loader.write_record(
                        cur, spec['table'],
                        {'借方发生额': 'account_1', '余额': 'account_2'},
                        values, 'insert', [],
                        {'file_id': file_id, 'record_id': record_id})
                    inserted += 1
                catalog.add_load_log(file_id, record_index, datasource['id'],
                                     spec['table'], target_pk, 'insert')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {'file_id': file_id, 'name': spec['name'], 'table': spec['table'],
            'rows': len(spec['rows']), 'created': created, 'inserted': inserted}


def seed_rich_demo(run=True):
    datasource_id = load_repo.ensure_default_datasource()
    if not datasource_id:
        raise RuntimeError('没有可用的产品库数据源')
    datasource = load_repo.get_datasource(datasource_id)
    ensure_rich_tables(datasource)
    mappings = {table: ensure_rich_mapping(datasource, table)
                for table in RICH_TABLES}
    documents = [ensure_rich_document(
        datasource, spec, mappings[spec['table']][0]) for spec in RICH_DOCUMENTS]

    specs = [
        (RICH_INDEX_NAMES[0], RICH_TABLES[0], None, 'count', []),
        (RICH_INDEX_NAMES[1], RICH_TABLES[0], 'account_1', 'sum', []),
        (RICH_INDEX_NAMES[2], RICH_TABLES[1], None, 'count', []),
        (RICH_INDEX_NAMES[3], RICH_TABLES[1], 'account_1', 'sum', []),
    ]
    index_ids = {}
    created = sum(int(item[1]) for item in mappings.values())
    created += sum(int(doc['created']) for doc in documents)
    for spec in specs:
        index_spec = (spec[0], spec[2], spec[3], spec[4])
        index_id, is_new = ensure_index(datasource_id, spec[1], index_spec)
        index_ids[spec[0]] = index_id
        created += int(is_new)

    def refs(*names):
        return [{'index_id': index_ids[name], 'alias': 'm' + str(i + 1)}
                for i, name in enumerate(names)]

    def cond(alias, op, threshold):
        return {'alias': alias, 'op': op, 'threshold': threshold}

    april_id, is_new = ensure_rule(
        RICH_RULE_NAMES[0], refs(RICH_INDEX_NAMES[0], RICH_INDEX_NAMES[1]),
        [cond('m1', 'gte', 10), cond('m2', 'gt', 10000)])
    created += int(is_new)
    may_id, is_new = ensure_rule(
        RICH_RULE_NAMES[1], refs(RICH_INDEX_NAMES[3]),
        [cond('m1', 'gt', 50000)])
    created += int(is_new)
    base_rule = rule_repo.get_def(name=RULE_NAMES[0])
    if not base_rule:
        raise RuntimeError('缺少基础演示规则，请先运行 demo_compute.py')
    frame_id, is_new = ensure_frame(
        RICH_FRAME_NAMES[0],
        [{'rule_id': base_rule['id'], 'weight': '0.5', 'veto': False},
         {'rule_id': april_id, 'weight': '0.25', 'veto': False},
         {'rule_id': may_id, 'weight': '0.25', 'veto': False}],
        'weighted', '0.7')
    created += int(is_new)
    rule_ids = {RICH_RULE_NAMES[0]: april_id, RICH_RULE_NAMES[1]: may_id}
    frame_ids = {RICH_FRAME_NAMES[0]: frame_id}

    results = {}
    if run:
        for name, index_id in index_ids.items():
            results[name] = execute_index(index_id)['value']
        for name, rule_id in rule_ids.items():
            results[name] = execute_rule(rule_id)['value']
        for name, frame_id in frame_ids.items():
            results[name] = execute_frame(frame_id)['value']
    return {'created': created, 'documents': documents, 'mappings': mappings,
            'index_ids': index_ids, 'rule_ids': rule_ids,
            'frame_ids': frame_ids, 'results': results}


def cleanup_demo():
    removed = {'index': 0, 'rule': 0, 'frame': 0}
    for name in FRAME_NAMES + LEGACY_FRAME_NAMES + RICH_FRAME_NAMES:
        found = frame_repo.get_def(name=name)
        if found:
            frame_repo.delete_def(found['id'])
            removed['frame'] += 1
    for name in RULE_NAMES + LEGACY_RULE_NAMES + RICH_RULE_NAMES:
        found = rule_repo.get_def(name=name)
        if found:
            rule_repo.delete_def(found['id'])
            removed['rule'] += 1
    for name in INDEX_NAMES + LEGACY_INDEX_NAMES + RICH_INDEX_NAMES:
        found = index_repo.get_def(name=name)
        if found:
            index_repo.delete_def(found['id'])
            removed['index'] += 1
    return removed


def main():
    parser = argparse.ArgumentParser(description='幂等补充计算示例配置')
    parser.add_argument('--cleanup', action='store_true', help='只删除本脚本的示例定义及结果')
    parser.add_argument('--no-run', action='store_true', help='只写定义，不执行计算')
    parser.add_argument('--rich-demo', action='store_true', help='额外生成多文档、多数据节点演示')
    args = parser.parse_args()
    if args.cleanup:
        print(cleanup_demo())
        return
    result = seed_demo(run=not args.no_run)
    print('业务表: {table}; 新建定义: {created}; 统计: {stats}'.format(**result))
    print('多资料追溯: {}'.format(result['trace']))
    if args.rich_demo:
        rich = seed_rich_demo(run=not args.no_run)
        print('多节点演示: 新建对象 {}; 文档 {}; 映射 {}'.format(
            rich['created'], rich['documents'], rich['mappings']))
        result['results'].update(rich['results'])
    if result['results']:
        for name, value in result['results'].items():
            print('{} = {}'.format(name, value))


if __name__ == '__main__':
    main()

"""旧 file-centric 库迁移到抽取/入库解耦模型。

契约：docs/design-decoupled-extraction-loading.md。
用法（从 20-CV 目录）：
    python -m c1_structure.store.migrations.007_decouple_extraction_loading
    python -m c1_structure.store.migrations.007_decouple_extraction_loading --confirm

默认只读预演。--confirm 先在 <DATA_ROOT>/data/backup/ 做全库逻辑备份，
再按阶段迁移。MySQL DDL 会隐式提交，不能用 rollback 撤销 DDL；失败时停止，
保留备份并输出已完成阶段，修正问题后需人工评估恢复或续跑。

兼容既有 001 基线：保留 c1_doc_file.sha256（改名后仍为 c1_doc.sha256），
删除 c1_parse_artifact.sha256。未绑定规则版本但有暂存记录/回执的旧文档，
使用“原始透传”兜底结果，避免非空 extract_result_id 回填失败。
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import datetime

from ... import config
from .. import db
from .apply_to_dev import _dump_sql, _q
from .init_db import statements


NEW_TABLES = (
    'c1_doc', 'c1_extract_rule', 'c1_parse_artifact', 'c1_extract_result',
    'c1_extract_record', 'c1_extract_record_field',
    'c1_extract_record_lineage', 'c1_load_datasource', 'c1_load_table',
    'c1_load_mapping_field', 'c1_load_binding', 'c1_load_receipt',
    'c1_quarantine_record',
)
OLD_TABLES = (
    'c1_doc_file', 'c1_extract_rule_version', 'c1_staging_record',
    'c1_staging_field', 'c1_staging_lineage', 'c1_load_table_field',
    'c1_load_log', 'c1_load_quarantine',
)
RULE_JSON_COLUMNS = (
    'output_schema_json', 'extraction_spec_json',
    'reference_doc_ids_json', 'validation_report_json',
)


def _tables(cur):
    cur.execute('SHOW TABLES')
    return {r[0] for r in cur.fetchall()}


def _table_exists(cur, table):
    cur.execute(
        'SELECT COUNT(*) FROM information_schema.tables'
        ' WHERE table_schema=DATABASE() AND table_name=%s', (table,))
    return cur.fetchone()[0] > 0


def _columns(cur, table):
    if not _table_exists(cur, table):
        return set()
    cur.execute(
        'SELECT column_name FROM information_schema.columns'
        ' WHERE table_schema=DATABASE() AND table_name=%s', (table,))
    return {r[0] for r in cur.fetchall()}


def _column_exists(cur, table, name):
    return name in _columns(cur, table)


def _indexes(cur, table):
    """返回 {索引名: [(列名, seq_in_index), ...]}。"""
    if not _table_exists(cur, table):
        return {}
    cur.execute(
        'SELECT index_name, column_name, seq_in_index'
        ' FROM information_schema.statistics'
        ' WHERE table_schema=DATABASE() AND table_name=%s'
        ' ORDER BY index_name, seq_in_index', (table,))
    out = {}
    for name, column, seq in cur.fetchall():
        out.setdefault(name, []).append((column, seq))
    return out


def _index_exists(cur, table, name):
    return name in _indexes(cur, table)


def _rows(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _json(value, default):
    if value is None or value == '':
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError('旧库 JSON 无法解析，拒绝静默丢失: {}'.format(value)) from exc


def _dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _execute(cur, sql):
    cur.execute(sql)
    print('  DDL: ' + sql.split(' COMMENT')[0])


def _add_column(cur, table, name, definition):
    if not _column_exists(cur, table, name):
        _execute(cur, 'ALTER TABLE {} ADD COLUMN {} {}'.format(
            _q(table), _q(name), definition))


def _drop_column(cur, table, name):
    if _column_exists(cur, table, name):
        _execute(cur, 'ALTER TABLE {} DROP COLUMN {}'.format(_q(table), _q(name)))


def _rename_column(cur, table, old, new, definition):
    cols = _columns(cur, table)
    if old in cols:
        if new in cols:
            raise RuntimeError('{} 同时存在 {} 和 {}，需人工处理'.format(
                table, old, new))
        _execute(cur, 'ALTER TABLE {} RENAME COLUMN {} TO {}'.format(
            _q(table), _q(old), _q(new)))
    elif new not in cols:
        raise RuntimeError('{} 缺少字段 {}'.format(table, new))


def _drop_indexes_for_columns(cur, table, columns):
    for name, parts in _indexes(cur, table).items():
        if name != 'PRIMARY' and any(c in columns for c, _ in parts):
            _execute(cur, 'ALTER TABLE {} DROP INDEX {}'.format(
                _q(table), _q(name)))


def _rename_table(cur, old, new):
    if _table_exists(cur, old):
        if _table_exists(cur, new):
            raise RuntimeError('旧表 {} 与新表 {} 同时存在，拒绝判断归属'.format(
                old, new))
        _execute(cur, 'ALTER TABLE {} RENAME TO {}'.format(_q(old), _q(new)))


def _alias(cur, old, new, required=True):
    has_old, has_new = _table_exists(cur, old), _table_exists(cur, new)
    if has_old and has_new:
        raise RuntimeError('旧表 {} 与新表 {} 同时存在，拒绝迁移'.format(old, new))
    if has_new:
        return new
    if has_old:
        return old
    if required:
        raise RuntimeError('缺少必需表 {}（或 {}）'.format(old, new))
    return None


def _doc_id_column(cur, table):
    return 'doc_id' if _column_exists(cur, table, 'doc_id') else 'file_id'


def _create_target_tables(cur, existing):
    """只执行新基线的 CREATE TABLE，不执行种子 INSERT。"""
    baseline = os.path.join(os.path.dirname(__file__), '001_file_baseline.sql')
    with io.open(baseline, encoding='utf-8') as f:
        for stmt in statements(f.read()):
            match = re.match(
                r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`([^`]+)`', stmt, re.I)
            if not match:
                continue
            table = match.group(1)
            # 旧表尚在时先保留旧表，回填后再改名，不能提前建空新表。
            renamed_pairs = {
                'c1_doc': 'c1_doc_file',
                'c1_extract_record': 'c1_staging_record',
                'c1_extract_record_field': 'c1_staging_field',
                'c1_extract_record_lineage': 'c1_staging_lineage',
                'c1_load_mapping_field': 'c1_load_table_field',
                'c1_load_receipt': 'c1_load_log',
                'c1_quarantine_record': 'c1_load_quarantine',
            }
            if renamed_pairs.get(table) in existing:
                continue
            if table not in existing:
                _execute(cur, stmt)
                existing.add(table)


def _preflight(cur, tables):
    for old, new in (
            ('c1_doc_file', 'c1_doc'),
            ('c1_staging_record', 'c1_extract_record'),
            ('c1_staging_field', 'c1_extract_record_field'),
            ('c1_staging_lineage', 'c1_extract_record_lineage'),
            ('c1_load_table_field', 'c1_load_mapping_field'),
            ('c1_load_log', 'c1_load_receipt'),
            ('c1_load_quarantine', 'c1_quarantine_record')):
        if old in tables and new in tables:
            raise RuntimeError('{} 与 {} 同时存在，无法安全判断旧表归属'.format(
                old, new))
    doc = 'c1_doc' if 'c1_doc' in tables else 'c1_doc_file'
    record = ('c1_extract_record' if 'c1_extract_record' in tables
              else 'c1_staging_record')
    receipt = 'c1_load_receipt' if 'c1_load_receipt' in tables else 'c1_load_log'
    for table in (doc, record, receipt, 'c1_extract_rule', 'c1_load_table',
                  'c1_load_datasource'):
        if table not in tables:
            raise RuntimeError('缺少旧库必需表 {}'.format(table))
    if not _column_exists(cur, doc, 'sha256'):
        raise RuntimeError('{} 缺少 sha256；本迁移不会删除文档原件哈希'.format(doc))
    doc_key = _doc_id_column(cur, record)
    cur.execute('SELECT COUNT(*) FROM {} r LEFT JOIN {} d ON d.id=r.{}'
                ' WHERE d.id IS NULL'.format(_q(record), _q(doc), _q(doc_key)))
    if cur.fetchone()[0]:
        raise RuntimeError('存在无所属文档的暂存记录，需先修复再迁移')
    receipt_key = _doc_id_column(cur, receipt)
    cur.execute('SELECT COUNT(*) FROM {} r LEFT JOIN {} d ON d.id=r.{}'
                ' WHERE d.id IS NULL'.format(_q(receipt), _q(doc), _q(receipt_key)))
    if cur.fetchone()[0]:
        raise RuntimeError('存在无所属文档的旧回执，需先修复再迁移')


def _merge_rules(cur, has_versions, has_current_version):
    for name in RULE_JSON_COLUMNS:
        _add_column(cur, 'c1_extract_rule', name, 'JSON NULL')
    cur.execute('SELECT id FROM c1_extract_rule ORDER BY id')
    for (rule_id,) in cur.fetchall():
        cur.execute(
            'SELECT output_schema_json, extraction_spec_json'
            ' FROM c1_extract_rule WHERE id=%s', (rule_id,))
        current = cur.fetchone()
        version = None
        if has_versions:
            if has_current_version:
                cur.execute(
                    'SELECT id, schema_json, mapping_json'
                    ' FROM c1_extract_rule_version'
                    ' WHERE rule_id=%s AND version=(SELECT current_version'
                    ' FROM c1_extract_rule WHERE id=%s)', (rule_id, rule_id))
            else:
                cur.execute(
                    'SELECT id, schema_json, mapping_json'
                    ' FROM c1_extract_rule_version WHERE rule_id=%s'
                    ' ORDER BY version DESC LIMIT 1', (rule_id,))
            version = cur.fetchone()
        if version:
            schema = _json(version[1], {'fields': []})
            spec = _json(version[2], {})
            cur.execute(
                'UPDATE c1_extract_rule SET'
                ' output_schema_json=COALESCE(output_schema_json,%s),'
                ' extraction_spec_json=COALESCE(extraction_spec_json,%s)'
                ' WHERE id=%s', (_dumps(schema), _dumps(spec), rule_id))
        elif not current[0] or not current[1]:
            empty_schema = current[0] or _dumps({'fields': []})
            empty_spec = current[1] or _dumps({})
            cur.execute(
                'UPDATE c1_extract_rule SET output_schema_json=%s,'
                ' extraction_spec_json=%s WHERE id=%s',
                (empty_schema, empty_spec, rule_id))
    print('  规则当前版本已合并；历史版本尚未删除')


def _fallback_rule(cur):
    cur.execute("SELECT id FROM c1_extract_rule WHERE name='原始透传'")
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        'INSERT INTO c1_extract_rule'
        " (name,description,output_schema_json,extraction_spec_json,"
        ' reference_doc_ids_json,validation_report_json)'
        " SELECT %s,%s,%s,%s,%s,%s WHERE NOT EXISTS"
        " (SELECT 1 FROM c1_extract_rule WHERE name='原始透传')",
        ('原始透传', '迁移兜底：旧文档未绑定规则版本。',
         _dumps({'fields': []}), _dumps({}), _dumps([]), _dumps({})))
    cur.execute("SELECT id FROM c1_extract_rule WHERE name='原始透传'")
    return cur.fetchone()[0]


def _snapshot(cur, rule_id, version_id=None):
    if version_id and _table_exists(cur, 'c1_extract_rule_version'):
        cur.execute(
            'SELECT schema_json,mapping_json FROM c1_extract_rule_version'
            ' WHERE id=%s AND rule_id=%s', (version_id, rule_id))
        row = cur.fetchone()
        if row:
            return {
                'output_schema': _json(row[0], {'fields': []}),
                'extraction_spec': _json(row[1], {}),
            }
    cur.execute(
        'SELECT output_schema_json,extraction_spec_json'
        ' FROM c1_extract_rule WHERE id=%s', (rule_id,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError('规则 {} 不存在，且历史版本不可用'.format(rule_id))
    return {
        'output_schema': _json(row[0], {'fields': []}),
        'extraction_spec': _json(row[1], {}),
    }


def _doc_select(cur, doc_table, record_table, receipt_table):
    doc_cols = _columns(cur, doc_table)
    record_key = _doc_id_column(cur, record_table)
    receipt_key = _doc_id_column(cur, receipt_table)
    fields = ['d.id', 'd.state', 'd.error', 'd.created_at', 'd.updated_at']
    for name in ('rule_version_id', 'load_datasource_id', 'load_table_id'):
        fields.append('d.{} AS {}'.format(
            _q(name), name) if name in doc_cols else 'NULL AS {}'.format(name))
    fields.extend([
        '(SELECT COUNT(*) FROM {} r WHERE r.{}=d.id) AS record_count'.format(
            _q(record_table), _q(record_key)),
        'EXISTS(SELECT 1 FROM {} r WHERE r.{}=d.id) AS has_receipt'.format(
            _q(receipt_table), _q(receipt_key)),
    ])
    cur.execute('SELECT {} FROM {} d ORDER BY d.id'.format(
        ','.join(fields), _q(doc_table)))
    return _rows(cur)


def _doc_by_id(cur, doc_table, record_table, receipt_table, doc_id):
    for doc in _doc_select(cur, doc_table, record_table, receipt_table):
        if doc['id'] == doc_id:
            return doc
    raise RuntimeError('文档 {} 不存在'.format(doc_id))


def _result_status(state, count):
    if state == 'failed':
        return 'failed'
    if count or state in ('to_review', 'to_load', 'loading', 'loaded'):
        return 'ready'
    return 'pending'


def _load_rule_id(cur, doc):
    if doc.get('rule_version_id') and _table_exists(cur, 'c1_extract_rule_version'):
        cur.execute('SELECT rule_id FROM c1_extract_rule_version WHERE id=%s',
                    (doc['rule_version_id'],))
        row = cur.fetchone()
        if row:
            return row[0], doc['rule_version_id']
    if doc.get('load_table_id') and _column_exists(cur, 'c1_load_table', 'rule_id'):
        cur.execute('SELECT rule_id FROM c1_load_table WHERE id=%s',
                    (doc['load_table_id'],))
        row = cur.fetchone()
        if row and row[0]:
            return row[0], None
    return None, None


def _refresh_result_counts(cur, record_table):
    cur.execute(
        'UPDATE c1_extract_result e LEFT JOIN'
        ' (SELECT extract_result_id,COUNT(*) n FROM {}'
        ' GROUP BY extract_result_id) r ON r.extract_result_id=e.id'
        ' SET e.record_count=COALESCE(r.n,0)'.format(_q(record_table)))


def _ensure_result(cur, doc):
    # 断点续跑时旧标量可能已删除；已有结果必须原样保留，不能再建兜底结果。
    cur.execute('SELECT id FROM c1_extract_result WHERE doc_id=%s'
                ' ORDER BY id LIMIT 1', (doc['id'],))
    existing = cur.fetchone()
    if existing:
        return existing[0]
    rule_id, version_id = _load_rule_id(cur, doc)
    if not rule_id:
        rule_id = _fallback_rule(cur)
    snapshot = _snapshot(cur, rule_id, version_id)
    status = _result_status(doc['state'], doc['record_count'])
    error = doc['error'] if status == 'failed' else None
    cur.execute(
        'INSERT INTO c1_extract_result'
        ' (doc_id,rule_id,rule_snapshot_json,status,record_count,error,'
        ' created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)'
        ' ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)',
        (doc['id'], rule_id, _dumps(snapshot), status, doc['record_count'],
         error, doc['created_at'], doc['updated_at']))
    result_id = cur.lastrowid
    cur.execute('SELECT id FROM c1_extract_result WHERE doc_id=%s AND rule_id=%s',
                (doc['id'], rule_id))
    return cur.fetchone()[0]


def _ensure_results(cur, doc_table, record_table, receipt_table):
    docs = _doc_select(cur, doc_table, record_table, receipt_table)
    candidates = [d for d in docs if d['rule_version_id'] or d['load_table_id']
                  or d['load_datasource_id'] or d['record_count'] or d['has_receipt']]
    for doc in candidates:
        _ensure_result(cur, doc)
    # 兼容回执引用文档但文档标量已被清理的部分迁移状态。
    receipt_key = _doc_id_column(cur, receipt_table)
    cur.execute('SELECT DISTINCT r.{} FROM {} r LEFT JOIN c1_extract_result e'
                ' ON e.doc_id=r.{} WHERE e.id IS NULL'.format(
                    _q(receipt_key), _q(receipt_table), _q(receipt_key)))
    for (doc_id,) in cur.fetchall():
        _ensure_result(cur, _doc_by_id(
            cur, doc_table, record_table, receipt_table, doc_id))
    # 仅有抽取阶段隔离记录的旧文档也应有可追溯结果。
    quarantine_table = None
    if _table_exists(cur, 'c1_quarantine_record'):
        quarantine_table = 'c1_quarantine_record'
    elif _table_exists(cur, 'c1_load_quarantine'):
        quarantine_table = 'c1_load_quarantine'
    if quarantine_table:
        quarantine_key = _doc_id_column(cur, quarantine_table)
        cur.execute(
            'SELECT DISTINCT q.{0} FROM {1} q LEFT JOIN c1_extract_result e'
            ' ON e.doc_id=q.{0} WHERE e.id IS NULL AND q.stage<>%s'.format(
                _q(quarantine_key), _q(quarantine_table)), ('load',))
        for (doc_id,) in cur.fetchall():
            _ensure_result(cur, _doc_by_id(
                cur, doc_table, record_table, receipt_table, doc_id))
    print('  文档结果已回填: {} 个候选文档'.format(len(candidates)))


def _link_records(cur, doc_table, record_table):
    key = _doc_id_column(cur, record_table)
    _add_column(cur, record_table, 'extract_result_id', 'BIGINT NULL')
    cur.execute(
        'UPDATE {} r JOIN c1_extract_result e ON e.doc_id=r.{}'
        ' AND e.id=(SELECT MIN(e2.id) FROM c1_extract_result e2'
        ' WHERE e2.doc_id=r.{})'
        ' SET r.extract_result_id=e.id WHERE r.extract_result_id IS NULL'.format(
            _q(record_table), _q(key), _q(key)))
    cur.execute('SELECT COUNT(*) FROM {} WHERE extract_result_id IS NULL'.format(
        _q(record_table)))
    if cur.fetchone()[0]:
        raise RuntimeError('仍有暂存记录未关联抽取结果')
    _execute(cur, 'ALTER TABLE {} MODIFY COLUMN extract_result_id BIGINT NOT NULL'.format(
        _q(record_table)))
    _rename_column(cur, record_table, key, 'doc_id', 'BIGINT NOT NULL')
    if _index_exists(cur, record_table, 'uk_file_idx'):
        _execute(cur, 'ALTER TABLE {} DROP INDEX uk_file_idx'.format(_q(record_table)))
    if not _index_exists(cur, record_table, 'uk_extract_result_record'):
        _execute(cur, 'ALTER TABLE {} ADD UNIQUE KEY uk_extract_result_record'
                 ' (extract_result_id,record_index)'.format(_q(record_table)))
    if not _index_exists(cur, record_table, 'idx_record_doc_result'):
        _execute(cur, 'ALTER TABLE {} ADD KEY idx_record_doc_result'
                 ' (doc_id,extract_result_id)'.format(_q(record_table)))
    _refresh_result_counts(cur, record_table)
    print('  暂存记录已关联结果并改键')


def _mapping_rows(cur, mapping_table, load_table_id):
    cols = _columns(cur, mapping_table)
    target = 'field_name' if 'field_name' in cols else 'target_column'
    source = 'rule_field' if 'rule_field' in cols else None
    business = 'is_business_key' if 'is_business_key' in cols else None
    selected = ['id', target]
    if source:
        selected.append(source)
    if business:
        selected.append(business)
    cur.execute('SELECT {} FROM {} WHERE load_table_id=%s ORDER BY id'.format(
        ','.join(_q(c) for c in selected), _q(mapping_table)), (load_table_id,))
    rows = _rows(cur)
    field_map, keys = {}, []
    for row in rows:
        name = row[target]
        if source and row.get(source):
            field_map[row[source]] = name
        if business and row.get(business) and name not in keys:
            keys.append(name)
    return field_map, keys


def _binding_status(state):
    if state == 'loaded':
        return 'ready'
    if state == 'loading':
        return 'running'
    if state == 'failed':
        return 'failed'
    return 'pending'


def _insert_binding(cur, doc_id, result_id, table_id, field_map, keys,
                    write_mode, status, error=None):
    cur.execute(
        'INSERT INTO c1_load_binding'
        ' (doc_id,extract_result_id,load_table_id,field_map_json,write_mode,'
        ' business_keys_json,status,error) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)'
        ' ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)',
        (doc_id, result_id, table_id, _dumps(field_map), write_mode,
         _dumps(keys) if keys else None, status, error))
    cur.execute('SELECT id FROM c1_load_binding WHERE extract_result_id=%s',
                (result_id,))
    return cur.fetchone()[0]


def _ensure_bindings(cur, doc_table, record_table, receipt_table,
                     receipt_key, mapping_table):
    table_cols = _columns(cur, 'c1_load_table')
    for doc in _doc_select(cur, doc_table, record_table, receipt_table):
        if not doc['load_table_id']:
            continue
        cur.execute('SELECT * FROM c1_load_table WHERE id=%s',
                    (doc['load_table_id'],))
        row = cur.fetchone()
        if not row:
            raise RuntimeError('文档 {} 引用的入库表 {} 不存在'.format(
                doc['id'], doc['load_table_id']))
        names = [d[0] for d in cur.description]
        table = dict(zip(names, row))
        datasource_id = doc['load_datasource_id'] or table['datasource_id']
        cur.execute('SELECT id FROM c1_extract_result WHERE doc_id=%s ORDER BY id',
                    (doc['id'],))
        results = cur.fetchall()
        if len(results) != 1:
            raise RuntimeError('文档 {} 应有唯一旧规则结果，实际 {} 条'.format(
                doc['id'], len(results)))
        field_map, keys = _mapping_rows(
            cur, mapping_table, doc['load_table_id'])
        mode = table.get('write_mode') or 'upsert'
        if mode not in ('insert', 'upsert', 'update'):
            mode = 'upsert'
        status = _binding_status(doc['state'])
        error = doc['error'] if status == 'failed' else None
        _insert_binding(cur, doc['id'], results[0][0], doc['load_table_id'],
                        field_map, keys, mode, status, error)

    # 旧回执可能没有文档标量配置；用回执自带的数据源/表名补绑定，绝不丢回执。
    cur.execute(
        'SELECT r.{},r.datasource_id,r.target_table FROM {} r'
        ' LEFT JOIN c1_load_binding b ON b.doc_id=r.{}'
        ' WHERE b.id IS NULL GROUP BY r.{},r.datasource_id,r.target_table'.format(
            _q(receipt_key), _q(receipt_table), _q(receipt_key), _q(receipt_key)))
    missing = cur.fetchall()
    for doc_id, datasource_id, target_table in missing:
        cur.execute(
            'SELECT id FROM c1_load_table WHERE datasource_id=%s'
            ' AND target_table=%s ORDER BY id LIMIT 1',
            (datasource_id, target_table))
        row = cur.fetchone()
        if row:
            table_id = row[0]
        else:
            cur.execute(
                'INSERT INTO c1_load_table (datasource_id,target_table)'
                ' VALUES (%s,%s)', (datasource_id, target_table))
            table_id = cur.lastrowid
        cur.execute('SELECT id FROM c1_extract_result WHERE doc_id=%s ORDER BY id',
                    (doc_id,))
        results = cur.fetchall()
        if len(results) != 1:
            raise RuntimeError('回执补绑定：文档 {} 结果数 {}'.format(doc_id, len(results)))
        field_map, keys = _mapping_rows(cur, mapping_table, table_id)
        _insert_binding(
            cur, doc_id, results[0][0], table_id, field_map, keys, 'upsert',
            'failed', '迁移补全：旧回执缺少文档入库配置，请核对后重新确认。')
    print('  入库绑定已回填；另补全无配置回执 {} 组'.format(len(missing)))


def _link_receipts(cur, receipt_table):
    key = _doc_id_column(cur, receipt_table)
    _add_column(cur, receipt_table, 'load_binding_id', 'BIGINT NULL')
    cur.execute(
        'UPDATE {} r JOIN c1_load_binding b ON b.doc_id=r.{}'
        ' AND b.id=(SELECT MIN(b2.id) FROM c1_load_binding b2'
        ' WHERE b2.doc_id=r.{})'
        ' SET r.load_binding_id=b.id WHERE r.load_binding_id IS NULL'.format(
            _q(receipt_table), _q(key), _q(key)))
    cur.execute('SELECT COUNT(*) FROM {} WHERE load_binding_id IS NULL'.format(
        _q(receipt_table)))
    if cur.fetchone()[0]:
        raise RuntimeError('仍有旧回执未关联入库绑定')
    _execute(cur, 'ALTER TABLE {} MODIFY COLUMN load_binding_id BIGINT NOT NULL'.format(
        _q(receipt_table)))
    _rename_column(cur, receipt_table, key, 'doc_id', 'BIGINT NOT NULL')
    if _index_exists(cur, receipt_table, 'uk_load_receipt'):
        _execute(cur, 'ALTER TABLE {} DROP INDEX uk_load_receipt'.format(
            _q(receipt_table)))
    if not _index_exists(cur, receipt_table, 'uk_load_binding_record'):
        _execute(cur, 'ALTER TABLE {} ADD UNIQUE KEY uk_load_binding_record'
                 ' (load_binding_id,record_index)'.format(_q(receipt_table)))
    print('  旧回执已关联绑定并改键')


def _dedupe_load_tables(cur, mapping_table):
    cur.execute(
        'SELECT datasource_id,target_table,MIN(id) FROM c1_load_table'
        ' GROUP BY datasource_id,target_table')
    canonical = {(ds, table): table_id for ds, table, table_id in cur.fetchall()}
    cur.execute('SELECT id,datasource_id,target_table FROM c1_load_table ORDER BY id')
    aliases = [(row_id, canonical[(ds, table)])
               for row_id, ds, table in cur.fetchall() if row_id != canonical[(ds, table)]]
    if aliases:
        # 此阶段 mapping_field 仍保留 target_column/rule_field/is_business_key，
        # 绑定已在上一步从各旧配置行生成，这里只合并目标字段元数据。
        if _column_exists(cur, mapping_table, 'target_column'):
            cur.executemany(
                'INSERT IGNORE INTO {}'
                ' (load_table_id,field_name,data_type,is_primary,has_default,sort_order)'
                ' SELECT %s,target_column,%s,0,0,MIN(sort_order) FROM {}'
                ' WHERE load_table_id=%s GROUP BY target_column'.format(
                    _q(mapping_table), _q(mapping_table)),
                [(keep, 'unknown', old) for old, keep in aliases])
        cur.executemany('UPDATE c1_load_binding SET load_table_id=%s'
                        ' WHERE load_table_id=%s', aliases)
        for old, _keep in aliases:
            cur.execute('DELETE FROM {} WHERE load_table_id=%s'.format(
                _q(mapping_table)), (old,))
            cur.execute('DELETE FROM c1_load_table WHERE id=%s', (old,))
    if not _index_exists(cur, 'c1_load_table', 'uk_load_table_target'):
        _execute(cur, 'ALTER TABLE c1_load_table ADD UNIQUE KEY'
                 ' uk_load_table_target (datasource_id,target_table)')
    print('  目标配置去重: 合并 {} 个重复配置'.format(len(aliases)))


def _finalize_mapping_and_tables(cur, mapping_table):
    _add_column(cur, mapping_table, 'data_type', 'VARCHAR(64) NULL')
    _add_column(cur, mapping_table, 'is_primary', "TINYINT NOT NULL DEFAULT '0'")
    _add_column(cur, mapping_table, 'has_default', "TINYINT NOT NULL DEFAULT '0'")
    cur.execute('UPDATE {} SET data_type=%s WHERE data_type IS NULL'.format(
        _q(mapping_table)), ('unknown',))
    # 旧 is_business_key 是业务去重键，不等于目标表物理主键，不能搬入 is_primary。
    _drop_indexes_for_columns(cur, mapping_table, {'rule_field', 'is_business_key'})
    _rename_column(cur, mapping_table, 'target_column', 'field_name',
                   'VARCHAR(128) NOT NULL')
    if _index_exists(cur, mapping_table, 'uk_table_column'):
        _execute(cur, 'ALTER TABLE {} DROP INDEX uk_table_column'.format(
            _q(mapping_table)))
    _drop_column(cur, mapping_table, 'rule_field')
    _drop_column(cur, mapping_table, 'is_business_key')
    _execute(cur, 'ALTER TABLE {} MODIFY COLUMN data_type VARCHAR(64) NOT NULL'.format(
        _q(mapping_table)))
    _execute(cur, 'ALTER TABLE {} MODIFY COLUMN is_primary TINYINT NOT NULL'
              " DEFAULT '0'".format(_q(mapping_table)))
    _execute(cur, 'ALTER TABLE {} MODIFY COLUMN has_default TINYINT NOT NULL'
              " DEFAULT '0'".format(_q(mapping_table)))
    if not _index_exists(cur, mapping_table, 'uk_mapping_field'):
        _execute(cur, 'ALTER TABLE {} ADD UNIQUE KEY uk_mapping_field'
                 ' (load_table_id,field_name)'.format(_q(mapping_table)))

    _add_column(cur, 'c1_load_table', 'updated_at',
                'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP'
                ' ON UPDATE CURRENT_TIMESTAMP')
    removed = {'rule_id', 'rule_version_id', 'source_snapshot_json', 'write_mode'}
    _drop_indexes_for_columns(cur, 'c1_load_table', removed)
    for name in sorted(removed):
        _drop_column(cur, 'c1_load_table', name)
    print('  目标字段元数据已收敛；来源映射/写入方式/业务键已迁入绑定')
    print('  注意: 旧库没有目标列类型/物理主键/默认值元数据，'
          'data_type=unknown、is_primary=0、has_default=0，需刷新目标Schema')


def _link_quarantine(cur, quarantine_table):
    key = _doc_id_column(cur, quarantine_table)
    _add_column(cur, quarantine_table, 'extract_result_id', 'BIGINT NULL')
    _add_column(cur, quarantine_table, 'load_binding_id', 'BIGINT NULL')
    cur.execute(
        'UPDATE {} q JOIN c1_extract_result e ON e.doc_id=q.{}'
        ' AND e.id=(SELECT MIN(e2.id) FROM c1_extract_result e2'
        ' WHERE e2.doc_id=q.{})'
        " SET q.extract_result_id=e.id"
        " WHERE q.stage<>'load' AND q.extract_result_id IS NULL".format(
            _q(quarantine_table), _q(key), _q(key)))
    cur.execute(
        'UPDATE {} q JOIN c1_load_binding b ON b.doc_id=q.{}'
        ' AND b.id=(SELECT MIN(b2.id) FROM c1_load_binding b2'
        ' WHERE b2.doc_id=q.{})'
        " SET q.load_binding_id=b.id"
        " WHERE q.stage='load' AND q.load_binding_id IS NULL".format(
            _q(quarantine_table), _q(key), _q(key)))
    _rename_column(cur, quarantine_table, key, 'doc_id', 'BIGINT NOT NULL')
    if _index_exists(cur, quarantine_table, 'idx_q_file'):
        _execute(cur, 'ALTER TABLE {} RENAME INDEX idx_q_file TO idx_q_doc_state'.format(
            _q(quarantine_table)))
    for name, column in (('idx_q_result', 'extract_result_id'),
                         ('idx_q_binding', 'load_binding_id')):
        if not _index_exists(cur, quarantine_table, name):
            _execute(cur, 'ALTER TABLE {} ADD KEY {} ({})'.format(
                _q(quarantine_table), name, column))
    print('  隔离记录已按阶段补全结果/绑定引用（无对应阶段引用时保持 NULL）')


def _finalize_docs_rules_artifacts(cur, doc_table, artifact_table):
    for name in ('rule_version_id', 'load_datasource_id', 'load_table_id'):
        _drop_column(cur, doc_table, name)
    if doc_table != 'c1_doc':
        _rename_table(cur, doc_table, 'c1_doc')
    for old, new in (('idx_file_sha', 'idx_doc_sha'),
                     ('idx_file_state', 'idx_doc_state')):
        if _index_exists(cur, 'c1_doc', old):
            _execute(cur, 'ALTER TABLE c1_doc RENAME INDEX {} TO {}'.format(old, new))
    if _index_exists(cur, 'c1_doc', 'idx_doc_sha') is False:
        _execute(cur, 'ALTER TABLE c1_doc ADD KEY idx_doc_sha (sha256)')
    if _index_exists(cur, 'c1_doc', 'idx_doc_state') is False:
        _execute(cur, 'ALTER TABLE c1_doc ADD KEY idx_doc_state (state)')
    _execute(cur, 'ALTER TABLE c1_doc MODIFY COLUMN state VARCHAR(32) NOT NULL'
              " DEFAULT 'pending'")
    # 旧文档状态是单流程状态；绑定/结果已回填后转换为文档级汇总语义。
    cur.execute("UPDATE c1_doc SET state='ready' WHERE state='to_extract'")
    cur.execute(
        "UPDATE c1_doc SET state='awaiting_load_confirmation'"
        " WHERE state IN ('to_review','to_load')")
    cur.execute("UPDATE c1_doc SET state='extract_failed' WHERE state='failed'")

    if _column_exists(cur, 'c1_extract_rule', 'current_version'):
        _drop_column(cur, 'c1_extract_rule', 'current_version')
    if _index_exists(cur, artifact_table, 'idx_artifact_sha'):
        _execute(cur, 'ALTER TABLE {} DROP INDEX idx_artifact_sha'.format(
            _q(artifact_table)))
    _drop_column(cur, artifact_table, 'sha256')
    _rename_column(cur, artifact_table, 'file_id', 'doc_id', 'BIGINT NOT NULL')
    if artifact_table != 'c1_parse_artifact':
        _rename_table(cur, artifact_table, 'c1_parse_artifact')
    print('  文档旧标量/规则版本号/解析产物 sha256 已清理；文档 sha256 保留')


def _validate(cur):
    errors = []
    for table in OLD_TABLES:
        if _table_exists(cur, table):
            errors.append('旧表仍存在: ' + table)
    expected = {
        'c1_doc': {'id', 'name', 'sha256', 'kind', 'size_bytes', 'content',
                   'tags', 'note', 'state', 'error', 'doc_type', 'params_json',
                   'created_at', 'updated_at'},
        'c1_extract_rule': {'id', 'name', 'description', 'output_schema_json',
                            'extraction_spec_json', 'reference_doc_ids_json',
                            'validation_report_json', 'created_at', 'updated_at'},
        'c1_parse_artifact': {'id', 'doc_id', 'name', 'kind', 'mime',
                              'size_bytes', 'content', 'created_at'},
        'c1_extract_record': {'id', 'extract_result_id', 'doc_id', 'record_index',
                              'review_state', 'review_at', 'values_json',
                              'original_json', 'review_reason_json',
                              'created_at', 'updated_at'},
        'c1_load_table': {'id', 'datasource_id', 'target_table',
                          'created_at', 'updated_at'},
        'c1_load_mapping_field': {'id', 'load_table_id', 'field_name', 'data_type',
                                  'is_primary', 'has_default', 'sort_order'},
    }
    for table, cols in expected.items():
        actual = _columns(cur, table)
        if actual != cols:
            errors.append('{} 字段不符: 缺少 {}；多余 {}'.format(
                table, sorted(cols - actual), sorted(actual - cols)))
    unique_keys = {
        'c1_extract_result': {'uk_doc_rule': ('doc_id', 'rule_id')},
        'c1_extract_record': {'uk_extract_result_record':
                              ('extract_result_id', 'record_index')},
        'c1_load_table': {'uk_load_table_target': ('datasource_id', 'target_table')},
        'c1_load_mapping_field': {'uk_mapping_field': ('load_table_id', 'field_name')},
        'c1_load_binding': {'uk_extract_result_binding': ('extract_result_id',)},
        'c1_load_receipt': {'uk_load_binding_record':
                            ('load_binding_id', 'record_index')},
    }
    for table, keys in unique_keys.items():
        indexes = _indexes(cur, table)
        for name, columns in keys.items():
            parts = indexes.get(name)
            if not parts or tuple(c for c, _ in parts) != columns:
                errors.append('{} 缺少唯一键 {}'.format(table, name))
        # information_schema 的 NON_UNIQUE 单独核验，避免同名非唯一索引误判。
        cur.execute(
            'SELECT index_name,non_unique FROM information_schema.statistics'
            ' WHERE table_schema=DATABASE() AND table_name=%s'
            ' GROUP BY index_name,non_unique', (table,))
        for name, non_unique in cur.fetchall():
            if name in keys and non_unique:
                errors.append('{} 的 {} 不是唯一索引'.format(table, name))
    checks = (
        ('c1_extract_result', 'rule_snapshot_json IS NULL'),
        ('c1_extract_record', 'extract_result_id IS NULL'),
        ('c1_load_receipt', 'load_binding_id IS NULL'),
        ('c1_extract_record', 'NOT EXISTS (SELECT 1 FROM c1_extract_result e'
         ' WHERE e.id=c1_extract_record.extract_result_id'
         ' AND e.doc_id=c1_extract_record.doc_id)'),
        ('c1_load_binding', 'NOT EXISTS (SELECT 1 FROM c1_extract_result e'
         ' WHERE e.id=c1_load_binding.extract_result_id'
         ' AND e.doc_id=c1_load_binding.doc_id)'),
        ('c1_load_binding', 'NOT EXISTS (SELECT 1 FROM c1_load_table t'
         ' WHERE t.id=c1_load_binding.load_table_id)'),
        ('c1_load_receipt', 'NOT EXISTS (SELECT 1 FROM c1_load_binding b'
         ' WHERE b.id=c1_load_receipt.load_binding_id'
         ' AND b.doc_id=c1_load_receipt.doc_id)'),
        ('c1_load_receipt', 'NOT EXISTS (SELECT 1 FROM c1_load_binding b'
         ' JOIN c1_load_table t ON t.id=b.load_table_id'
         ' WHERE b.id=c1_load_receipt.load_binding_id'
         ' AND t.datasource_id=c1_load_receipt.datasource_id'
         ' AND t.target_table=c1_load_receipt.target_table)'),
        ('c1_quarantine_record', 'extract_result_id IS NOT NULL AND NOT EXISTS'
         ' (SELECT 1 FROM c1_extract_result e'
         ' WHERE e.id=c1_quarantine_record.extract_result_id'
         ' AND e.doc_id=c1_quarantine_record.doc_id)'),
        ('c1_quarantine_record', 'load_binding_id IS NOT NULL AND NOT EXISTS'
         ' (SELECT 1 FROM c1_load_binding b'
         ' WHERE b.id=c1_quarantine_record.load_binding_id'
         ' AND b.doc_id=c1_quarantine_record.doc_id)'),
    )
    for table, where in checks:
        cur.execute('SELECT COUNT(*) FROM {} WHERE {}'.format(_q(table), where))
        count = cur.fetchone()[0]
        if count:
            errors.append('{} 异常 {} 行: {}'.format(table, count, where))
    cur.execute(
        'SELECT COUNT(*) FROM c1_extract_result e LEFT JOIN'
        ' (SELECT extract_result_id,COUNT(*) n FROM c1_extract_record'
        ' GROUP BY extract_result_id) r ON r.extract_result_id=e.id'
        ' WHERE e.record_count<>COALESCE(r.n,0)')
    if cur.fetchone()[0]:
        errors.append('抽取结果 record_count 与记录数不一致')
    if errors:
        raise RuntimeError('迁移后校验失败:\n  ' + '\n  '.join(errors))
    print('  校验通过: 旧表/旧列已清理，唯一键与引用完整，记录数一致')
    for table in NEW_TABLES:
        cur.execute('SELECT COUNT(*) FROM ' + _q(table))
        print('    {}: {} 行'.format(table, cur.fetchone()[0]))


def _is_legacy(cur, tables):
    return (bool(set(tables) & set(OLD_TABLES))
            or _table_exists(cur, 'c1_extract_rule_version')
            or _column_exists(cur, 'c1_doc', 'rule_version_id')
            or _column_exists(cur, 'c1_doc_file', 'rule_version_id')
            or _column_exists(cur, 'c1_extract_rule', 'current_version')
            or _column_exists(cur, 'c1_parse_artifact', 'sha256')
            or _column_exists(cur, 'c1_load_table', 'rule_id')
            or _column_exists(cur, 'c1_load_mapping_field', 'rule_field'))


def run(confirm=False):
    conn = db.connect()
    backup = None
    try:
        with conn.cursor() as cur:
            tables = _tables(cur)
            _preflight(cur, tables)
            print('目标库:', db.safe_detail(config.PLATFORM_DB))
            print('现有表 {} 张'.format(len(tables)))
            if not _is_legacy(cur, tables):
                _validate(cur)
                print('已是目标结构，无需迁移。')
                return
            print('迁移顺序:')
            print('  1. 合并规则当前版本；为文档历史版本建立结果和快照')
            print('  2. 暂存记录补 extract_result_id；目标字段映射/写入方式/业务键迁入绑定')
            print('  3. 回执/隔离补 ID；目标表配置去重')
            print('  4. 重命名表/字段；删除文档旧标量、规则版本表和产物 sha256')
            print('  5. 校验结构、唯一键、引用和记录数')
            if not confirm:
                print('[预演] 未写库、未生成备份。确认请加 --confirm；'
                      '确认模式会先备份全库。')
                return

            backup_dir = os.path.join(config.DATA_ROOT, 'data', 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            backup = os.path.join(
                backup_dir, 'c1_structure_pre_decouple_{}.sql'.format(stamp))
            n = _dump_sql(conn, sorted(tables), backup)
            if not os.path.getsize(backup):
                raise RuntimeError('备份文件为空，拒绝执行迁移')
            print('全库备份完成: {}（{} 行）'.format(backup, n))

            _create_target_tables(cur, tables)
            doc_table = _alias(cur, 'c1_doc_file', 'c1_doc')
            artifact_table = 'c1_parse_artifact'
            record_table = _alias(cur, 'c1_staging_record', 'c1_extract_record')
            field_table = _alias(cur, 'c1_staging_field', 'c1_extract_record_field')
            lineage_table = _alias(cur, 'c1_staging_lineage',
                                   'c1_extract_record_lineage')
            mapping_table = _alias(cur, 'c1_load_table_field',
                                   'c1_load_mapping_field')
            receipt_table = _alias(cur, 'c1_load_log', 'c1_load_receipt')
            quarantine_table = _alias(cur, 'c1_load_quarantine',
                                      'c1_quarantine_record')
            receipt_key = _doc_id_column(cur, receipt_table)

            print('[1/6] 合并规则并回填文档结果')
            _merge_rules(cur, _table_exists(cur, 'c1_extract_rule_version'),
                         _column_exists(cur, 'c1_extract_rule', 'current_version'))
            _ensure_results(cur, doc_table, record_table, receipt_table)
            conn.commit()

            print('[2/6] 回填抽取记录')
            _link_records(cur, doc_table, record_table)
            if record_table != 'c1_extract_record':
                _rename_table(cur, record_table, 'c1_extract_record')
                record_table = 'c1_extract_record'
            conn.commit()

            print('[3/6] 回填绑定和回执')
            _ensure_bindings(cur, doc_table, record_table, receipt_table,
                             receipt_key, mapping_table)
            conn.commit()
            _link_receipts(cur, receipt_table)
            if receipt_table != 'c1_load_receipt':
                _rename_table(cur, receipt_table, 'c1_load_receipt')
                receipt_table = 'c1_load_receipt'
            conn.commit()

            print('[4/6] 去重目标配置并清理配置表')
            _dedupe_load_tables(cur, mapping_table)
            conn.commit()
            _finalize_mapping_and_tables(cur, mapping_table)
            if mapping_table != 'c1_load_mapping_field':
                _rename_table(cur, mapping_table, 'c1_load_mapping_field')
            conn.commit()

            print('[5/6] 回填隔离记录并清理旧结构')
            _link_quarantine(cur, quarantine_table)
            if quarantine_table != 'c1_quarantine_record':
                _rename_table(cur, quarantine_table, 'c1_quarantine_record')
            if field_table != 'c1_extract_record_field':
                _rename_table(cur, field_table, 'c1_extract_record_field')
            if lineage_table != 'c1_extract_record_lineage':
                _rename_table(cur, lineage_table, 'c1_extract_record_lineage')
            _finalize_docs_rules_artifacts(cur, doc_table, artifact_table)
            conn.commit()
            if _table_exists(cur, 'c1_extract_rule_version'):
                _execute(cur, 'DROP TABLE c1_extract_rule_version')

            print('[6/6] 校验')
            _validate(cur)
            conn.commit()
            print('迁移完成。MySQL DDL 不可回滚，请保留备份: {}'.format(backup))
    except Exception as exc:
        conn.rollback()
        print('迁移失败: {}: {}'.format(type(exc).__name__, exc), file=sys.stderr)
        print('未提交事务已回滚；MySQL DDL 不可回滚。备份: {}'.format(
            backup or '尚未生成（预演或备份前失败）'), file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', action='store_true',
                        help='确认执行；默认只读预演。执行前强制全库备份。')
    args = parser.parse_args()
    return run(args.confirm)


if __name__ == '__main__':
    sys.exit(main())

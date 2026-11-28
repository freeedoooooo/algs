"""将入库元数据关联切换为编码，并保留全部现有数据。

用法（从 20-CV 目录）：
    python -m c1_structure.store.migrations.009_load_metadata_codes
    python -m c1_structure.store.migrations.009_load_metadata_codes --confirm

默认只读预演。确认模式先备份全库，再执行可断点续跑的 DDL/DML。
MySQL DDL 会隐式提交，失败时停止并保留备份，已完成步骤不会被回滚。
"""
import argparse
import os
import sys
from datetime import datetime

from ... import config
from .. import db
from .apply_to_dev import _dump_sql, _q


def _tables(cur):
    cur.execute('SHOW TABLES')
    return {row[0] for row in cur.fetchall()}


def _columns(cur, table):
    cur.execute('SHOW COLUMNS FROM ' + _q(table))
    return {row[0] for row in cur.fetchall()}


def _indexes(cur, table):
    cur.execute('SHOW INDEX FROM ' + _q(table))
    out = {}
    for row in cur.fetchall():
        out.setdefault(row[2], []).append((row[3], row[4]))
    return {name: tuple(column for _, column in sorted(parts))
            for name, parts in out.items()}


def _count(cur, table):
    cur.execute('SELECT COUNT(*) FROM ' + _q(table))
    return cur.fetchone()[0]


def _add_column(cur, table, definition):
    cur.execute('ALTER TABLE {} ADD COLUMN {}'.format(_q(table), definition))


def _drop_column(cur, table, column):
    cur.execute('ALTER TABLE {} DROP COLUMN {}'.format(_q(table), _q(column)))


def _drop_index(cur, table, index):
    cur.execute('ALTER TABLE {} DROP INDEX {}'.format(_q(table), _q(index)))


def _add_unique(cur, table, index, columns):
    cur.execute('ALTER TABLE {} ADD UNIQUE KEY {} ({})'.format(
        _q(table), _q(index), ','.join(_q(column) for column in columns)))


def _add_index(cur, table, index, columns):
    cur.execute('ALTER TABLE {} ADD KEY {} ({})'.format(
        _q(table), _q(index), ','.join(_q(column) for column in columns)))


def _assert_no_duplicates(cur, sql, message):
    cur.execute(sql)
    duplicates = cur.fetchall()
    if duplicates:
        raise RuntimeError('{}：{}'.format(message, duplicates[:5]))


def _migrate_datasource(cur):
    table = 'c1_load_datasource'
    columns = _columns(cur, table)
    if 'code' not in columns:
        _add_column(cur, table, "`code` varchar(100) NULL COMMENT '数据源编码（默认等于库名）'")
    cur.execute("UPDATE {} SET code=db_name WHERE code IS NULL OR code=''".format(_q(table)))
    _assert_no_duplicates(
        cur,
        'SELECT code,COUNT(*) FROM {} GROUP BY code HAVING COUNT(*)>1'.format(_q(table)),
        '数据源编码重复，请先人工修正')
    cur.execute('ALTER TABLE {} MODIFY COLUMN code varchar(100) NOT NULL'.format(_q(table)))
    indexes = _indexes(cur, table)
    if 'uk_ds_code' not in indexes:
        _add_unique(cur, table, 'uk_ds_code', ('code',))


def _migrate_table(cur):
    table = 'c1_load_table'
    columns = _columns(cur, table)
    if 'datasource_code' not in columns:
        _add_column(cur, table, "`datasource_code` varchar(100) NULL COMMENT '目标数据源编码'")
    if 'code' not in columns:
        _add_column(cur, table, "`code` varchar(255) NULL COMMENT '入库表编码：数据源编码.表名'")
    if 'datasource_id' in columns:
        cur.execute(
            'UPDATE {lt} lt JOIN {ds} ds ON ds.id=lt.datasource_id '
            'SET lt.datasource_code=ds.code,lt.code=CONCAT(ds.code,\'.\',lt.target_table) '
            'WHERE lt.datasource_code IS NULL OR lt.datasource_code=\'\' '
            'OR lt.code IS NULL OR lt.code=\'\''.format(
                lt=_q(table), ds=_q('c1_load_datasource')))
    cur.execute(
        'SELECT id FROM {} WHERE datasource_code IS NULL OR datasource_code=\'\' '
        "OR code IS NULL OR code=''".format(_q(table)))
    if cur.fetchall():
        raise RuntimeError('入库表编码回填失败，存在无法解析的数据源关联')
    _assert_no_duplicates(
        cur,
        'SELECT code,COUNT(*) FROM {} GROUP BY code HAVING COUNT(*)>1'.format(_q(table)),
        '入库表编码重复，请先人工修正')
    _assert_no_duplicates(
        cur,
        'SELECT datasource_code,target_table,COUNT(*) FROM {} '
        'GROUP BY datasource_code,target_table HAVING COUNT(*)>1'.format(_q(table)),
        '入库表目标重复，请先人工修正')
    cur.execute(
        'ALTER TABLE {} MODIFY COLUMN code varchar(255) NOT NULL,'
        ' MODIFY COLUMN datasource_code varchar(100) NOT NULL'.format(_q(table)))
    indexes = _indexes(cur, table)
    if 'uk_load_table_target' in indexes and indexes['uk_load_table_target'] != \
            ('datasource_code', 'target_table'):
        _drop_index(cur, table, 'uk_load_table_target')
        indexes.pop('uk_load_table_target', None)
    if 'uk_load_table_code' not in indexes:
        _add_unique(cur, table, 'uk_load_table_code', ('code',))
    if 'uk_load_table_target' not in indexes:
        _add_unique(cur, table, 'uk_load_table_target',
                    ('datasource_code', 'target_table'))
    indexes = _indexes(cur, table)
    if 'idx_load_table_datasource' not in indexes:
        _add_index(cur, table, 'idx_load_table_datasource', ('datasource_code',))
    cur.execute(
        'SELECT lt.id FROM {lt} lt LEFT JOIN {ds} ds ON ds.code=lt.datasource_code '
        'WHERE ds.id IS NULL'.format(lt=_q(table), ds=_q('c1_load_datasource')))
    if cur.fetchall():
        raise RuntimeError('入库表存在孤立的数据源编码')
    if 'datasource_id' in _columns(cur, table):
        _drop_column(cur, table, 'datasource_id')


def _ensure_field_table(cur, tables):
    old, new = 'c1_load_mapping_field', 'c1_load_table_field'
    has_old, has_new = old in tables, new in tables
    if has_old and has_new:
        raise RuntimeError('{} 与 {} 同时存在，拒绝迁移'.format(old, new))
    if has_old:
        cur.execute('ALTER TABLE {} RENAME TO {}'.format(_q(old), _q(new)))
        tables.remove(old)
        tables.add(new)
        return new
    if has_new:
        return new
    raise RuntimeError('未找到目标字段元数据表')


def _migrate_fields(cur, tables):
    table = _ensure_field_table(cur, tables)
    columns = _columns(cur, table)
    if 'table_code' not in columns:
        _add_column(cur, table, "`table_code` varchar(255) NULL COMMENT '所属入库表编码'")
    if 'load_table_id' in columns:
        cur.execute(
            'UPDATE {f} f JOIN {lt} lt ON lt.id=f.load_table_id '
            'SET f.table_code=lt.code '
            "WHERE f.table_code IS NULL OR f.table_code=''".format(
                f=_q(table), lt=_q('c1_load_table')))
    cur.execute(
        "SELECT id FROM {} WHERE table_code IS NULL OR table_code=''".format(_q(table)))
    if cur.fetchall():
        raise RuntimeError('目标字段表编码回填失败，存在无法解析的入库表关联')
    _assert_no_duplicates(
        cur,
        'SELECT table_code,field_name,COUNT(*) FROM {} '
        'GROUP BY table_code,field_name HAVING COUNT(*)>1'.format(_q(table)),
        '目标字段元数据重复，请先人工修正')
    cur.execute('ALTER TABLE {} MODIFY COLUMN table_code varchar(255) NOT NULL'.format(_q(table)))
    indexes = _indexes(cur, table)
    if 'uk_mapping_field' in indexes:
        _drop_index(cur, table, 'uk_mapping_field')
        indexes.pop('uk_mapping_field', None)
    if 'uk_table_field' not in indexes:
        _add_unique(cur, table, 'uk_table_field', ('table_code', 'field_name'))
    cur.execute(
        'SELECT f.id FROM {f} f LEFT JOIN {lt} lt ON lt.code=f.table_code '
        'WHERE lt.id IS NULL'.format(f=_q(table), lt=_q('c1_load_table')))
    if cur.fetchall():
        raise RuntimeError('目标字段存在孤立的入库表编码')
    if 'load_table_id' in _columns(cur, table):
        _drop_column(cur, table, 'load_table_id')


def _validate(cur):
    checks = (
        ('c1_load_table', 'SELECT lt.id FROM {lt} lt LEFT JOIN {ds} ds ON ds.code=lt.datasource_code WHERE ds.id IS NULL'),
        ('c1_load_table', "SELECT id FROM {lt} WHERE code<>CONCAT(datasource_code,'.',target_table)"),
        ('c1_load_table_field', 'SELECT f.id FROM {f} f LEFT JOIN {lt} lt ON lt.code=f.table_code WHERE lt.id IS NULL'),
    )
    for table, sql in checks:
        cur.execute(sql.format(lt=_q('c1_load_table'), ds=_q('c1_load_datasource'),
                               f=_q(table)))
        if cur.fetchall():
            raise RuntimeError('迁移后校验失败：{}'.format(table))


def run(confirm=False):
    conn = db.connect()
    backup = None
    try:
        with conn.cursor() as cur:
            tables = _tables(cur)
            required = {'c1_load_datasource', 'c1_load_table'}
            missing = required - tables
            if missing:
                raise RuntimeError('缺少基础表：{}'.format('、'.join(sorted(missing))))
            counts_before = {table: _count(cur, table) for table in
                             ('c1_load_datasource', 'c1_load_table', 'c1_load_binding')}
            field_table = ('c1_load_table_field' if 'c1_load_table_field' in tables
                           else 'c1_load_mapping_field' if 'c1_load_mapping_field' in tables
                           else None)
            if field_table is None:
                raise RuntimeError('缺少目标字段元数据表')
            counts_before[field_table] = _count(cur, field_table)
            print('目标库:', db.safe_detail(config.PLATFORM_DB))
            print('迁移计划: 数据源编码 → 入库表编码 → 字段表改名与表编码关联')
            print('当前行数:', counts_before)
            if not confirm:
                print('[预演] 未写库、未生成备份。确认请加 --confirm。')
                return 0

            backup_dir = os.path.join(config.DATA_ROOT, 'data', 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            backup = os.path.join(
                backup_dir, 'c1_structure_pre_load_metadata_codes_{}.sql'.format(stamp))
            row_count = _dump_sql(conn, sorted(tables), backup)
            if not os.path.getsize(backup):
                raise RuntimeError('备份文件为空，拒绝执行迁移')
            print('全库备份完成: {}（{} 行）'.format(backup, row_count))

            _migrate_datasource(cur)
            conn.commit()
            print('  已完成: c1_load_datasource.code')
            _migrate_table(cur)
            conn.commit()
            print('  已完成: c1_load_table.code / datasource_code')
            _migrate_fields(cur, tables)
            conn.commit()
            print('  已完成: c1_load_table_field.table_code')
            _validate(cur)

            counts_after = {
                'c1_load_datasource': _count(cur, 'c1_load_datasource'),
                'c1_load_table': _count(cur, 'c1_load_table'),
                'c1_load_table_field': _count(cur, 'c1_load_table_field'),
                'c1_load_binding': _count(cur, 'c1_load_binding'),
            }
            expected = dict(counts_before)
            if field_table != 'c1_load_table_field':
                expected['c1_load_table_field'] = expected.pop(field_table)
            if counts_after != expected:
                raise RuntimeError('迁移前后行数不一致：{} -> {}'.format(expected, counts_after))
            print('迁移完成，行数保持一致:', counts_after)
            print('备份:', backup)
            return 0
    except Exception as exc:
        conn.rollback()
        print('迁移失败: {}: {}'.format(type(exc).__name__, exc), file=sys.stderr)
        print('MySQL DDL 不可回滚；已完成步骤保持有效，可修正后重跑。'
              '备份: {}'.format(backup or '尚未生成'), file=sys.stderr)
        return 1
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', action='store_true',
                        help='确认执行；默认只读预演，确认模式先备份全库。')
    args = parser.parse_args()
    return run(args.confirm)


if __name__ == '__main__':
    raise SystemExit(main())

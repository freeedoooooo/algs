"""将 c1_load_binding 的目标表关联从数字 ID 切换为 table_code。

用法（从 20-CV 目录）：
    python -m c1_structure.store.migrations.010_binding_table_code
    python -m c1_structure.store.migrations.010_binding_table_code --confirm

默认只读预演。确认模式先备份全库，再执行可断点续跑的 DDL/DML。
"""
import argparse
import os
import sys
from datetime import datetime

from ... import config
from .. import db
from .apply_to_dev import _dump_sql, _q


def _columns(cur, table):
    cur.execute('SHOW COLUMNS FROM ' + _q(table))
    return {row[0] for row in cur.fetchall()}


def _indexes(cur, table):
    cur.execute('SHOW INDEX FROM ' + _q(table))
    return {row[2] for row in cur.fetchall()}


def _count(cur, table):
    cur.execute('SELECT COUNT(*) FROM ' + _q(table))
    return cur.fetchone()[0]


def _migrate(cur):
    table = 'c1_load_binding'
    columns = _columns(cur, table)
    old_exists = 'load_table_id' in columns
    if 'table_code' not in columns and not old_exists:
        raise RuntimeError('c1_load_binding 既无 table_code，也无可回填的 load_table_id')
    if 'table_code' not in columns:
        cur.execute(
            'ALTER TABLE {} ADD COLUMN table_code varchar(255) NULL '
            "COMMENT '目标业务表编码'".format(_q(table)))
    if old_exists:
        cur.execute(
            'UPDATE {b} b JOIN {lt} lt ON lt.id=b.load_table_id '
            "SET b.table_code=lt.code WHERE b.table_code IS NULL OR b.table_code=''".format(
                b=_q(table), lt=_q('c1_load_table')))
    cur.execute(
        'SELECT id FROM {} WHERE table_code IS NULL OR table_code=\'\''.format(_q(table)))
    if cur.fetchall():
        raise RuntimeError('绑定表编码回填失败，存在无法解析的目标表')
    cur.execute(
        'SELECT b.id FROM {b} b LEFT JOIN {lt} lt ON lt.code=b.table_code '
        'WHERE lt.id IS NULL OR b.table_code<>lt.code'.format(
            b=_q(table), lt=_q('c1_load_table')))
    if cur.fetchall():
        raise RuntimeError('绑定表编码与目标表元数据不一致')
    cur.execute(
        'ALTER TABLE {} MODIFY COLUMN table_code varchar(255) NOT NULL'.format(_q(table)))
    indexes = _indexes(cur, table)
    if 'idx_binding_table_code' not in indexes:
        cur.execute(
            'ALTER TABLE {} ADD KEY idx_binding_table_code (table_code)'.format(_q(table)))
    if old_exists:
        if 'idx_binding_load_table' in _indexes(cur, table):
            cur.execute(
                'ALTER TABLE {} DROP INDEX idx_binding_load_table'.format(_q(table)))
        cur.execute(
            'ALTER TABLE {} DROP COLUMN load_table_id'.format(_q(table)))


def run(confirm=False):
    conn = db.connect()
    backup = None
    try:
        with conn.cursor() as cur:
            for table in ('c1_load_table', 'c1_load_binding'):
                cur.execute('SHOW TABLES LIKE %s', (table,))
                if not cur.fetchone():
                    raise RuntimeError('缺少基础表：{}'.format(table))
            before = _count(cur, 'c1_load_binding')
            columns = _columns(cur, 'c1_load_binding')
            print('目标库:', db.safe_detail(config.PLATFORM_DB))
            print('迁移计划: c1_load_binding.load_table_id → table_code')
            print('当前绑定行数:', before)
            print('当前关联列:', 'table_code' if 'table_code' in columns else 'load_table_id')
            if not confirm:
                print('[预演] 未写库、未生成备份。确认请加 --confirm。')
                return 0
            cur.execute('SHOW TABLES')
            tables = [row[0] for row in cur.fetchall()]
            backup_dir = os.path.join(config.DATA_ROOT, 'data', 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            backup = os.path.join(
                backup_dir, 'c1_structure_pre_binding_table_code_{}.sql'.format(stamp))
            row_count = _dump_sql(conn, sorted(tables), backup)
            if not os.path.getsize(backup):
                raise RuntimeError('备份文件为空，拒绝执行迁移')
            print('全库备份完成: {}（{} 行）'.format(backup, row_count))
            _migrate(cur)
            conn.commit()
            after = _count(cur, 'c1_load_binding')
            if after != before:
                raise RuntimeError('迁移前后行数不一致：{} -> {}'.format(before, after))
            print('迁移完成，绑定行数保持一致:', after)
            print('备份:', backup)
            return 0
    except Exception as exc:
        conn.rollback()
        print('迁移失败: {}: {}'.format(type(exc).__name__, exc), file=sys.stderr)
        print('MySQL DDL 不可回滚；可修正后重跑。备份: {}'.format(
            backup or '尚未生成'), file=sys.stderr)
        return 1
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', action='store_true',
                        help='确认执行；默认只读预演，确认模式先备份全库。')
    return run(parser.parse_args().confirm)


if __name__ == '__main__':
    raise SystemExit(main())

"""将计算域旧表名统一迁移为 c1_calc_*，保留全部数据。

用法（从 20-CV 目录）：
    python -m c1_structure.store.migrations.008_rename_calc_tables
    python -m c1_structure.store.migrations.008_rename_calc_tables --confirm

默认只读预演。确认模式先备份全库，再使用 RENAME TABLE 改名；可重复执行。
MySQL DDL 会隐式提交，失败时停止并保留备份，已完成的改名不会被回滚。
"""
import argparse
import os
import sys
from datetime import datetime

from ... import config
from .. import db
from .apply_to_dev import _dump_sql, _q


RENAMES = (
    ('c1_index_info', 'c1_calc_index_info'),
    ('c1_index_value', 'c1_calc_index_value'),
    ('c1_rule_info', 'c1_calc_rule_info'),
    ('c1_rule_value', 'c1_calc_rule_value'),
    ('c1_frame_info', 'c1_calc_frame_info'),
    ('c1_frame_value', 'c1_calc_frame_value'),
    ('c1_compute_graph_layout', 'c1_calc_graph_layout'),
)


def _tables(cur):
    cur.execute('SHOW TABLES')
    return {row[0] for row in cur.fetchall()}


def _plan(tables):
    plan = []
    for old, new in RENAMES:
        has_old, has_new = old in tables, new in tables
        if has_old and has_new:
            raise RuntimeError('旧表 {} 与新表 {} 同时存在，拒绝迁移'.format(
                old, new))
        if has_old:
            plan.append((old, new, 'rename'))
        elif has_new:
            plan.append((old, new, 'done'))
        else:
            plan.append((old, new, 'missing'))
    return plan


def _count(cur, table):
    cur.execute('SELECT COUNT(*) FROM ' + _q(table))
    return cur.fetchone()[0]


def _rename(cur, old, new):
    cur.execute('ALTER TABLE {} RENAME TO {}'.format(_q(old), _q(new)))


def run(confirm=False):
    conn = db.connect()
    backup = None
    try:
        with conn.cursor() as cur:
            tables = _tables(cur)
            plan = _plan(tables)
            renames = [(old, new) for old, new, status in plan
                       if status == 'rename']
            print('目标库:', db.safe_detail(config.PLATFORM_DB))
            print('迁移计划:')
            for old, new, status in plan:
                label = {'rename': '改名', 'done': '已是新名',
                         'missing': '两者均不存在'}[status]
                count = ''
                if status != 'missing':
                    table = old if status == 'rename' else new
                    count = '（{} 行）'.format(_count(cur, table))
                print('  {}: {} -> {}{}'.format(label, old, new, count))
            if not renames:
                print('无需迁移。')
                return 0
            if not confirm:
                print('[预演] 未写库、未生成备份。确认请加 --confirm。')
                return 0

            backup_dir = os.path.join(config.DATA_ROOT, 'data', 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            backup = os.path.join(
                backup_dir, 'c1_structure_pre_calc_rename_{}.sql'.format(stamp))
            row_count = _dump_sql(conn, sorted(tables), backup)
            if not os.path.getsize(backup):
                raise RuntimeError('备份文件为空，拒绝执行迁移')
            print('全库备份完成: {}（{} 行）'.format(backup, row_count))

            for old, new in renames:
                before = _count(cur, old)
                _rename(cur, old, new)
                after = _count(cur, new)
                if before != after:
                    raise RuntimeError('{} 改名为 {} 后行数不一致：{} -> {}'.format(
                        old, new, before, after))
                tables.remove(old)
                tables.add(new)
                print('  已改名: {} -> {}（{} 行）'.format(
                    old, new, after))

            final_plan = _plan(tables)
            if any(status == 'rename' for _, _, status in final_plan):
                raise RuntimeError('迁移后仍有计算表未使用新名')
            completed = sum(status == 'done' for _, _, status in final_plan)
            print('迁移完成，{}/7 张计算表已使用新名，数据均已保留。备份: {}'.format(
                completed, backup))
            return 0
    except Exception as exc:
        conn.rollback()
        print('迁移失败: {}: {}'.format(type(exc).__name__, exc), file=sys.stderr)
        print('MySQL DDL 不可回滚；已完成的改名保持有效，可修正后重跑。'
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

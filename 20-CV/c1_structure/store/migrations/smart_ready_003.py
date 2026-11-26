"""M2/M3/M5 一次性迁移：为智能化升级补齐三处可空列。

  · c1_doc_file.doc_type            单据类型（归类 Agent 写入，与 kind 解耦）
  · c1_staging_record.review_reason_json  校验标记（字段→issue 列表）
  · c1_staging_field.confidence / reason  字段级 Agent 信号

全部可空、默认 NULL，存量数据零影响；对应 001 基线已同步写入。
流程（保守顺序，失败即停）：预演识别列状态 → 备份三表 → 加列 → 校验。

用法（在 20-CV 目录）：python -m c1_structure.store.migrations.smart_ready_003
                     python -m c1_structure.store.migrations.smart_ready_003 --confirm
"""
import argparse
import os
from datetime import datetime

from ... import config
from .. import db
from .apply_to_dev import _dump_sql, _q

TABLES = ('c1_doc_file', 'c1_staging_record', 'c1_staging_field')
ADDS = (
    ('c1_doc_file', 'doc_type',
     "ALTER TABLE {} ADD COLUMN doc_type VARCHAR(64) NULL"
     " COMMENT '单据类型（归类 Agent 写入，与载体 kind 解耦）'"),
    ('c1_staging_record', 'review_reason_json',
     "ALTER TABLE {} ADD COLUMN review_reason_json JSON NULL"
     " COMMENT '校验标记（字段→issue 列表），只标记不改值'"),
    ('c1_staging_field', 'confidence',
     "ALTER TABLE {} ADD COLUMN confidence FLOAT NULL"
     " COMMENT '字段级置信度（Agent 信号，可空）'"),
    ('c1_staging_field', 'reason',
     "ALTER TABLE {} ADD COLUMN reason VARCHAR(255) NULL"
     " COMMENT '字段级判定理由（Agent 信号，可空）'"),
)


def _column_exists(cur, table, name):
    cur.execute('SELECT COUNT(*) FROM information_schema.columns'
                ' WHERE table_schema=DATABASE() AND table_name=%s'
                ' AND column_name=%s', (table, name))
    return cur.fetchone()[0] > 0


def run(confirm=False):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            missing = [(t, c) for t, c, _ in ADDS
                       if not _column_exists(cur, t, c)]
            print('待加列: {}'.format(
                ', '.join('{}.{}'.format(t, c) for t, c in missing) or '无'))
            if not confirm:
                print('预演：不写库。加 --confirm 执行。')
                return
            backup_dir = os.path.join(config.DATA_ROOT, 'data', 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup = os.path.join(
                backup_dir, 'c1_structure_pre_smart_ready_{}.sql'.format(stamp))
            n = _dump_sql(conn, TABLES, backup)
            print('备份完成: {}（{} 行）'.format(backup, n))

            for table, col, ddl in ADDS:
                if (table, col) not in missing:
                    continue
                sql = ddl.format(_q(table))
                cur.execute(sql)
                print('执行: ' + sql.split(' COMMENT')[0])

            cur.execute('SELECT COUNT(*) FROM c1_doc_file'
                        ' WHERE doc_type IS NOT NULL')
            print('校验: doc_type 非空 {} 行（预期 0，存量未分类）'.format(
                cur.fetchone()[0]))
            for table, col, _ddl in ADDS:
                if not _column_exists(cur, table, col):
                    raise RuntimeError('加列失败: {}.{}'.format(table, col))
            conn.commit()
            print('完成：4 列已就绪，全部可空，存量数据未改动。')
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--confirm', action='store_true')
    args = ap.parse_args()
    run(args.confirm)


if __name__ == '__main__':
    main()

"""S2 一次性迁移：入库映射保存抽取输出快照，解除 rule_id 硬耦合。

流程（保守顺序，失败即停）：
  0. 识别列/索引状态
  1. 备份 c1_load_table + c1_load_table_field 到 <DATA_ROOT>/data/backup/
  2. DDL：加 rule_version_id / source_snapshot_json，rule_id 改可空，删唯一键
  3. 回填：按映射引用的抽取规则当前版本生成字段+类型快照
  4. 校验：快照非空、映射 rule_field 全部落在快照字段内

用法（在 20-CV 目录）：python -m c1_structure.store.migrations.snapshot_decouple_002
                     python -m c1_structure.store.migrations.snapshot_decouple_002 --confirm
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime

from ... import config
from .. import db
from .apply_to_dev import _dump_sql, _q

TABLE = 'c1_load_table'
FIELDS = 'c1_load_table_field'


def _column_exists(cur, name):
    cur.execute('SELECT COUNT(*) FROM information_schema.columns'
                ' WHERE table_schema=DATABASE() AND table_name=%s'
                ' AND column_name=%s', (TABLE, name))
    return cur.fetchone()[0] > 0


def _index_exists(cur, name):
    cur.execute('SELECT COUNT(*) FROM information_schema.statistics'
                ' WHERE table_schema=DATABASE() AND table_name=%s'
                ' AND index_name=%s', (TABLE, name))
    return cur.fetchone()[0] > 0


def _j(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _snapshot(cur, rule_id):
    """从规则当前版本取输出契约：字段名+类型，附参考版本用于运维回溯。"""
    cur.execute(
        'SELECT tv.id, tv.schema_json, tv.mapping_json, tv.version, t.name'
        ' FROM c1_extract_rule_version tv'
        ' JOIN c1_extract_rule t ON t.id=tv.rule_id'
        ' WHERE tv.rule_id=%s AND tv.version=t.current_version', (rule_id,))
    row = cur.fetchone()
    if not row:
        return None
    vid, sj, mj, ver, name = row
    sj, mj = _j(sj), _j(mj)
    fields = []
    if isinstance(sj, dict):
        for f in sj.get('fields') or []:
            if isinstance(f, dict) and f.get('name'):
                fields.append({'name': f['name'], 'type': f.get('type') or 'text'})
    if not fields and isinstance(mj, dict):
        for f in mj.get('fields') or []:
            if isinstance(f, dict) and f.get('target'):
                fields.append({'name': f['target'],
                               'type': f.get('type') or 'text'})
    if not fields:
        return None
    payload = {'schema_version': 1, 'rule_id': rule_id,
               'rule_version_id': vid, 'rule_name': name,
               'rule_version': ver, 'fields': fields}
    payload['hash'] = hashlib.sha256(
        json.dumps(fields, sort_keys=True, ensure_ascii=False)
        .encode('utf-8')).hexdigest()[:16]
    return payload


def run(confirm=False):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            snapshot_col = _column_exists(cur, 'source_snapshot_json')
            version_col = _column_exists(cur, 'rule_version_id')
            uk = _index_exists(cur, 'uk_ds_rule_table')
            cur.execute('SELECT COUNT(*) FROM ' + _q(TABLE))
            total = cur.fetchone()[0]
            print('映射行数: {}；快照列: {}；版本列: {}；唯一键: {}'.format(
                total, snapshot_col, version_col, uk))
            if not confirm:
                print('预演：不写库。加 --confirm 执行。')
                return
            backup_dir = os.path.join(config.DATA_ROOT, 'data', 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup = os.path.join(
                backup_dir, 'c1_structure_pre_snapshot_{}.sql'.format(stamp))
            n = _dump_sql(conn, (TABLE, FIELDS), backup)
            print('备份完成: {}（{} 行）'.format(backup, n))

            ddl = []
            if not snapshot_col:
                ddl.append('ALTER TABLE {} ADD COLUMN source_snapshot_json TEXT'
                           " NULL COMMENT '抽取输出快照：字段名+类型+参考规则版本'".format(_q(TABLE)))
            if not version_col:
                ddl.append('ALTER TABLE {} ADD COLUMN rule_version_id BIGINT'
                           " NULL COMMENT '参考抽取规则版本 id（仅回溯）'".format(_q(TABLE)))
            ddl.append('ALTER TABLE {} MODIFY COLUMN rule_id BIGINT NULL'
                       " COMMENT '参考抽取规则 id（仅配置期参考）'".format(_q(TABLE)))
            if uk:
                ddl.append('ALTER TABLE {} DROP INDEX uk_ds_rule_table'.format(
                    _q(TABLE)))
            for sql in ddl:
                cur.execute(sql)
                print('执行: ' + sql.split(' COMMENT')[0])

            cur.execute('SELECT id, rule_id FROM ' + _q(TABLE))
            rows = cur.fetchall()
            filled = skipped = 0
            for lt_id, rule_id in rows:
                snap = _snapshot(cur, rule_id) if rule_id else None
                if not snap:
                    skipped += 1
                    continue
                cur.execute('UPDATE ' + _q(TABLE) +
                            ' SET source_snapshot_json=%s, rule_version_id=%s'
                            ' WHERE id=%s',
                            (json.dumps(snap, ensure_ascii=False),
                             snap['rule_version_id'], lt_id))
                filled += 1
            conn.commit()
            print('回填: 快照 {} 条；跳过（原始透传/缺规则）{} 条'.format(
                filled, skipped))

            cur.execute('SELECT COUNT(*) FROM ' + _q(TABLE) +
                        ' WHERE source_snapshot_json IS NULL')
            missing = cur.fetchone()[0]
            bad = 0
            cur.execute('SELECT lt.id, lt.source_snapshot_json, f.rule_field'
                        ' FROM ' + _q(TABLE) + ' lt JOIN ' + _q(FIELDS) + ' f'
                        ' ON f.load_table_id=lt.id')
            for lt_id, snap_text, rule_field in cur.fetchall():
                snap = _j(snap_text)
                names = {f.get('name') for f in (snap or {}).get('fields') or []}
                if rule_field not in names:
                    bad += 1
                    print('校验异常: 映射 {} 字段 {} 不在快照中'.format(
                        lt_id, rule_field))
            print('校验: 缺快照 {} 条；字段越界 {} 条'.format(missing, bad))
            if missing or bad:
                raise RuntimeError('快照迁移校验失败，请检查上述映射')
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--confirm', action='store_true')
    args = ap.parse_args()
    run(args.confirm)


if __name__ == '__main__':
    main()

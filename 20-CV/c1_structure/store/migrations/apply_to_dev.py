"""把正式库 c1_structure_dev 从旧模型升级到 file_id 模型（人工一次性执行）。

流程（保守顺序，任何一步失败即中止，不继续破坏）：
  0. 连通性 + 表结构识别（旧表/新表）
  1. 全库逻辑备份到 <DATA_ROOT>/data/backup/<db>_pre_file_<时间戳>.sql
     （用 pymysql 导出 CREATE TABLE + INSERT，不依赖 mysqldump）
  2. 备份配置表数据在内存（5 张纯配置表）
  3. DROP 旧运行表（c1_task / c1_task_file 及所有 task_file_id 键表）
  4. 执行 001_file_baseline.sql（新建 12 表，IF NOT EXISTS）
  5. 配置表数据回灌（INSERT IGNORE，保留原 id）
  6. 校验：12 表 / 无 c1_task / 配置行数守恒

用法：python -m store.migrations.apply_to_dev --confirm
不带 --confirm 只做预演（打印将要执行的动作，不写库）。
"""
import argparse
import io
import os
import sys
import time
from datetime import datetime

from ... import config
from .. import db

# 纯配置表（用户要求保留）
CONFIG_TABLES = ('c1_extract_rule', 'c1_extract_rule_version',
                 'c1_load_datasource', 'c1_load_table', 'c1_load_table_field')
# 旧模型的全部表（运行数据，用户裁决清空）
OLD_TABLES = ('c1_doc_file', 'c1_task', 'c1_task_file', 'c1_parse_artifact',
              'c1_staging_record', 'c1_staging_field', 'c1_staging_lineage',
              'c1_load_log', 'c1_load_quarantine')
BASELINE = os.path.join(os.path.dirname(__file__), '001_file_baseline.sql')


def _q(name):
    return '`' + str(name).replace('`', '``') + '`'


def _existing_tables(cur):
    cur.execute('SHOW TABLES')
    return set(r[0] for r in cur.fetchall())


def _dump_sql(conn, tables, path):
    """逻辑备份：每表 CREATE TABLE + 全部 INSERT（值参数化转义）。"""
    n = 0
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write('-- c1_structure pre-file-model backup\n')
        f.write('-- generated: {}\n\n'.format(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        with conn.cursor() as cur:
            for t in tables:
                cur.execute('SHOW CREATE TABLE ' + _q(t))
                ddl = cur.fetchone()[1]
                f.write('DROP TABLE IF EXISTS {};\n{};\n'.format(_q(t), ddl))
                cur.execute('SELECT * FROM ' + _q(t))
                rows = cur.fetchall()
                if rows:
                    cur.execute('SHOW COLUMNS FROM ' + _q(t))
                    cols = [r[0] for r in cur.fetchall()]
                    colsql = ','.join(_q(c) for c in cols)
                    ph = ','.join(['%s'] * len(cols))
                    for row in rows:
                        vals = []
                        for v in row:
                            if v is None:
                                vals.append('NULL')
                            elif isinstance(v, bytes):
                                vals.append('_binary\'{}\''.format(
                                    v.decode('latin-1').replace('\\', '\\\\')
                                     .replace("'", "\\'")))
                            elif isinstance(v, (int, float)):
                                vals.append(str(v))
                            else:
                                vals.append("'{}'".format(
                                    str(v).replace('\\', '\\\\')
                                         .replace("'", "\\'")))
                        f.write('INSERT INTO {} ({}) VALUES ({});\n'.format(
                            _q(t), colsql, ','.join(vals)))
                        n += 1
                f.write('\n')
    return n


def _statements(sql):
    out = []
    for line in sql.splitlines():
        if line.strip().startswith('--'):
            continue
        out.append(line)
    return [s.strip() for s in '\n'.join(out).split(';') if s.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--confirm', action='store_true')
    args = ap.parse_args()

    conn = db.connect()
    try:
        with conn.cursor() as cur:
            tables = _existing_tables(cur)
        print('目标库:', db.safe_detail(config.PLATFORM_DB))
        print('现有表({}): {}'.format(len(tables), ', '.join(sorted(tables))))
        old = [t for t in OLD_TABLES if t in tables]
        missing_new = [t for t in ('c1_load_quarantine',) if t not in tables]
        print('将清理的旧表:', ', '.join(old) or '(无)')
        print('备份目录:', config.DATA_DIR)
        if not args.confirm:
            print('\n[预演] 未写库。确认请加 --confirm')
            return 0
        if not old:
            print('\n未发现旧表，可能已升级；为安全起见不执行DROP。')
            return 1

        # 1. 全库备份
        bdir = os.path.join(config.DATA_DIR, 'backup')
        if not os.path.isdir(bdir):
            os.makedirs(bdir)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        bpath = os.path.join(bdir, 'c1_structure_dev_pre_file_{}.sql'.format(stamp))
        print('\n[1/5] 备份全部表 →', bpath)
        n = _dump_sql(conn, sorted(tables), bpath)
        print('  备份 {} 行，{} 字节'.format(n, os.path.getsize(bpath)))

        # 2. 备份配置表内容（内存）
        print('[2/5] 内存暂存配置表')
        backup = {}
        with conn.cursor() as cur:
            for t in CONFIG_TABLES:
                if t not in tables:
                    backup[t] = ([], [])
                    continue
                cur.execute('SHOW COLUMNS FROM ' + _q(t))
                cols = [r[0] for r in cur.fetchall()]
                cur.execute('SELECT * FROM ' + _q(t) + ' ORDER BY id')
                backup[t] = (cols, cur.fetchall())
                print('  {}: {} 行'.format(t, len(backup[t][1])))

        # 3. DROP 旧表
        print('[3/5] DROP 旧表')
        with conn.cursor() as cur:
            for t in old:
                cur.execute('DROP TABLE IF EXISTS ' + _q(t))
                print('  dropped', t)
            conn.commit()

        # 4. 执行新基线
        print('[4/5] 执行 001_file_baseline.sql')
        sql = io.open(BASELINE, encoding='utf-8').read()
        with conn.cursor() as cur:
            for stmt in _statements(sql):
                cur.execute(stmt)
            conn.commit()

        # 5. 配置回灌
        print('[5/5] 配置表回灌')
        with conn.cursor() as cur:
            for t in CONFIG_TABLES:
                cols, rows = backup[t]
                if not rows:
                    continue
                ph = ','.join(['%s'] * len(cols))
                cur.executemany(
                    'INSERT IGNORE INTO {} ({}) VALUES ({})'.format(
                        _q(t), ','.join(_q(c) for c in cols), ph), rows)
                print('  {}: {} 行'.format(t, len(rows)))
            conn.commit()

        # 校验
        with conn.cursor() as cur:
            cur.execute('SHOW TABLES')
            final = set(r[0] for r in cur.fetchall())
            print('\n[校验] 表数:', len(final))
            print('  c1_task 存在:', any(x.startswith('c1_task') for x in final))
            for t in CONFIG_TABLES:
                cur.execute('SELECT COUNT(*) FROM ' + _q(t))
                print('  {}: {} 行'.format(t, cur.fetchone()[0]))
        print('\n升级完成。备份文件:', bpath)
        print('注意：8765 上运行的仍是旧代码，需重启加载新代码后接口才恢复。')
        return 0
    except Exception as e:
        conn.rollback()
        print('\n失败:', type(e).__name__, e)
        print('已回滚未提交事务；备份文件（若已生成）保留。')
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())

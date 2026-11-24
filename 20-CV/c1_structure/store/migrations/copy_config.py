"""配置表迁移：从旧库复制抽取规则/入库配置到新库（只增不改，不碰运行数据）。

用法（在包根执行，用 paddle python）：
    python -m store.migrations.copy_config --src mysql://.../c1_structure_dev \
                                            --dst mysql://.../c1_structure_v2

只复制 5 张纯配置表：c1_extract_rule / c1_extract_rule_version /
c1_load_datasource / c1_load_table / c1_load_table_field。
不复制：c1_doc_file 及任何产物/暂存/回执/隔离（用户裁决存量清空）。
规则/数据源 ID 保留原值，因 load_table.rule_id 等有交叉引用；目标库须为空配置表。
"""
import argparse
import pymysql
from urllib.parse import urlparse

TABLES = ('c1_extract_rule', 'c1_extract_rule_version', 'c1_load_datasource',
          'c1_load_table', 'c1_load_table_field')


def connect(dsn):
    u = urlparse(dsn)
    return pymysql.connect(host=u.hostname, port=u.port or 3306,
                           user=u.username, password=u.password,
                           db=u.path.lstrip('/'), charset='utf8mb4')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--dst', required=True)
    args = ap.parse_args()

    src, dst = connect(args.src), connect(args.dst)
    try:
        with src.cursor() as cs, dst.cursor() as cd:
            total = 0
            for t in TABLES:
                cs.execute('SELECT * FROM `{}` ORDER BY id'.format(t))
                rows = cs.fetchall()
                cd.execute('SELECT COUNT(*) FROM `{}`'.format(t))
                if cd.fetchone()[0]:
                    raise SystemExit('目标表 {} 非空，拒绝覆盖（请先用空库）'.format(t))
                if not rows:
                    print('{}: 0 行（跳过）'.format(t))
                    continue
                cs.execute('SHOW COLUMNS FROM `{}`'.format(t))
                cols = [r[0] for r in cs.fetchall()]
                ph = ','.join(['%s'] * len(cols))
                cd.executemany(
                    'INSERT INTO `{}` ({}) VALUES ({})'.format(
                        t, ','.join('`{}`'.format(c) for c in cols), ph), rows)
                total += len(rows)
                print('{}: {} 行'.format(t, len(rows)))
            dst.commit()
            print('配置迁移完成，共 {} 行'.format(total))
    finally:
        src.close()
        dst.close()


if __name__ == '__main__':
    main()

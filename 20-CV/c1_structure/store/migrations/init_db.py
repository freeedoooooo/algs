"""在指定空库执行基线 DDL（正确处理 -- 注释与分号）。

用法：
    python -m store.migrations.init_db --dsn mysql://user:pw@host:port/db \
                                       --sql store/migrations/001_file_baseline.sql

仅用于空库；不 DROP、不 TRUNCATE，靠 IF NOT EXISTS 幂等。
"""
import argparse
import re
import pymysql
from urllib.parse import urlparse


def strip_comments(sql):
    out = []
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith('--'):
            continue
        out.append(line)
    return '\n'.join(out)


def statements(sql):
    body = strip_comments(sql)
    return [s.strip() for s in body.split(';') if s.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dsn', required=True)
    ap.add_argument('--sql', required=True)
    args = ap.parse_args()

    dsn = urlparse(args.dsn)
    conn = pymysql.connect(host=dsn.hostname, port=dsn.port or 3306,
                           user=dsn.username, password=dsn.password,
                           db=dsn.path.lstrip('/'), charset='utf8mb4')
    try:
        sql = open(args.sql, encoding='utf-8').read()
        stmts = statements(sql)
        with conn.cursor() as cur:
            for i, stmt in enumerate(stmts, 1):
                cur.execute(stmt)
            print('executed {} statements'.format(len(stmts)))
            cur.execute('SHOW TABLES')
            tables = sorted(r[0] for r in cur.fetchall())
            print('tables({}): {}'.format(len(tables), ', '.join(tables)))
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    main()

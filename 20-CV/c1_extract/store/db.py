"""
store/db.py — 薄驱动接缝（JDBC 式）+ conn_ref 解析 + 迁移执行器。

接口只有 connect(ref) → DB-API 连接；catalog / loader 只用 DB-API 通用能力
（cursor / execute / commit / rollback），换库 = 新增驱动实现 + 迁移方言。
首个实现 PyMySQL（锁版本见 requirements）；MySQL 8 caching_sha2_password
非 SSL 首次认证需 cryptography（已锁）。

凭据引用制：conn_ref 是名字不是密码；解析顺序 env → data/secrets.json（git 排除）。
凭据永不落日志 / 不回显（错误信息只带 host/库名）。
"""
import os
import re
import json
import glob
import threading
from urllib.parse import urlsplit, unquote

from .. import config

_LOCK = threading.Lock()
_READY = set()          # 已完成迁移的 (ref, database)


def resolve_conn(ref):
    """conn_ref → DSN。未配置抛 LookupError（调用方显式报错）。"""
    v = os.getenv(ref)
    if not v:
        p = os.path.join(config.DATA_DIR, 'secrets.json')
        if os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                v = (json.load(f) or {}).get(ref)
    if not v:
        raise LookupError('凭据引用 {} 未配置（环境变量或 data/secrets.json）'
                          .format(ref))
    return v


def _parts(dsn):
    u = urlsplit(dsn)
    if u.scheme != 'mysql':
        raise ValueError('首个驱动实现仅支持 mysql:// DSN')
    return {
        'host': u.hostname, 'port': u.port or 3306,
        'user': unquote(u.username or ''),
        'password': unquote(u.password or ''),
        'database': (u.path or '').lstrip('/'),
    }


def safe_detail(ref):
    """脱敏连接描述（仅 host/库名），供测试连接回显与日志。"""
    try:
        p = _parts(resolve_conn(ref))
        return '{}:{}/{}'.format(p['host'], p['port'], p['database'])
    except Exception as e:
        return str(e)


def connect(ref=None, autocommit=False, migrate=True):
    """DB-API 连接。平台库首次调用自动跑迁移（幂等）；pymysql 懒导入。
    migrate=False 用于目标业务库（P2 入库）——绝不把平台表建进人家库。"""
    import pymysql
    ref = ref or config.PLATFORM_DB_REF
    p = _parts(resolve_conn(ref))
    conn = pymysql.connect(
        host=p['host'], port=p['port'], user=p['user'],
        password=p['password'], database=p['database'],
        charset='utf8mb4', autocommit=autocommit, connect_timeout=5)
    if not migrate:
        return conn
    key = (ref, p['database'])
    if key not in _READY:
        with _LOCK:
            if key not in _READY:
                _migrate(conn)
                _READY.add(key)
    return conn


def connect_direct(p, autocommit=False):
    """显式参数直连（P2b load 数据源行），不跑迁移——绝不把平台表建进目标库。
    p={host,port,user,password,database}；连接参数与 connect() 一致。"""
    import pymysql
    return pymysql.connect(
        host=p['host'], port=int(p['port'] or 3306), user=p['user'],
        password=p['password'], database=p['database'],
        charset='utf8mb4', autocommit=autocommit, connect_timeout=5)


def _migrate(conn):
    """编号脚本 + schema_version 表；按序应用未跑过的迁移。"""
    with conn.cursor() as cur:
        cur.execute('CREATE TABLE IF NOT EXISTS schema_version ('
                    'version INT PRIMARY KEY, '
                    'applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP'
                    ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4')
        cur.execute('SELECT version FROM schema_version')
        done = {r[0] for r in cur.fetchall()}
    files = sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'migrations', '*.sql')))
    for path in files:
        m = re.match(r'(\d+)', os.path.basename(path))
        if not m:
            continue
        ver = int(m.group(1))
        if ver in done:
            continue
        with open(path, encoding='utf-8') as f:
            sql = f.read()
        with conn.cursor() as cur:
            for stmt in sql.split(';'):
                if stmt.strip():
                    cur.execute(stmt)
            cur.execute('INSERT INTO schema_version (version) VALUES (%s)',
                        (ver,))
        conn.commit()
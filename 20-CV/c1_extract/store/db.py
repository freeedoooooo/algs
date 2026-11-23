"""
store/db.py — 薄驱动接缝（JDBC 式）+ DSN 解析。

接口只有 connect(dsn) → DB-API 连接；catalog / loader 只用 DB-API 通用能力
（cursor / execute / commit / rollback），换库 = 新增驱动实现。
首个实现 PyMySQL（锁版本见 requirements）；MySQL 8 caching_sha2_password
非 SSL 首次认证需 cryptography（已锁）。

建表/升级不自动执行：migrations/001_baseline.sql 是人工安装脚本，
部署或改表结构时由人对着库跑（2026-11-21 裁决：删自动迁移门禁）。

DSN 来源：config.PLATFORM_DB（环境变量 C1_EXTRACT_DB 优先，默认值直接写在
config.py，2026-11-23 裁决：退役 secrets.json 引用制）。
回显永不带密码（错误信息只带 host/库名）。
"""
import os
import time
import threading
from urllib.parse import urlsplit, unquote

from .. import config

_TL = threading.local()      # 平台库线程局部连接（见 connect() 文档）
_IDLE_PING_S = 5.0           # 闲置超过该秒数，归还前先 ping 验活


def resolve_conn(dsn):
    """DSN 直通（config.PLATFORM_DB 即 DSN，env C1_EXTRACT_DB 已在 config 展开）。

    未配置抛 LookupError（调用方显式报错）。"""
    if not dsn:
        raise LookupError('平台库 DSN 未配置（config.PLATFORM_DB 或环境变量 C1_EXTRACT_DB）')
    return dsn


def _parts(dsn):
    u = urlsplit(dsn)
    if u.scheme != 'mysql':
        raise ValueError('当前版本仅支持 mysql:// 连接串')
    return {
        'host': u.hostname, 'port': u.port or 3306,
        'user': unquote(u.username or ''),
        'password': unquote(u.password or ''),
        'database': (u.path or '').lstrip('/'),
    }


def safe_detail(dsn):
    """脱敏连接描述（仅 host/库名），供测试连接回显与日志。"""
    try:
        p = _parts(resolve_conn(dsn))
        return '{}:{}/{}'.format(p['host'], p['port'], p['database'])
    except Exception as e:
        return str(e)


class _Borrowed:
    """连接代理：归还行为由 on_release 决定（复用套接字或真关闭）。"""

    def __init__(self, conn, on_release):
        object.__setattr__(self, '_conn', conn)
        object.__setattr__(self, '_on_release', on_release)
        object.__setattr__(self, '_released', False)

    def cursor(self, *a, **k):
        return self._conn.cursor(*a, **k)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._released:
            object.__setattr__(self, '_released', True)
            self._on_release()

    def __getattr__(self, k):
        return getattr(self._conn, k)


def _new_conn(dsn, autocommit):
    import pymysql
    p = _parts(resolve_conn(dsn))
    return pymysql.connect(
        host=p['host'], port=p['port'], user=p['user'],
        password=p['password'], database=p['database'],
        charset='utf8mb4', autocommit=autocommit, connect_timeout=5)


def connect(dsn=None, autocommit=False):
    """DB-API 连接（纯连接，不建表不迁移）；pymysql 懒导入。

    平台库默认参数走**线程局部连接复用**（库在远端，一次连接约 250ms）：
    close()＝「归还」——回滚未竟事务、保留套接字给本线程下一次取用；
    取用未还期间再次 connect()（嵌套）自动退回独立连接，事务互扰为零；
    闲置 >5s 的缓存连接归还前 ping 验活，断连即弃、下次重建（VPN 漂移自愈）。
    每次取用归还后回滚 ⇒ 下一条语句开新事务，读数永远是新鲜快照
    （REPEATABLE READ 不会跨取用泄漏）。
    """
    dsn = dsn or config.PLATFORM_DB
    if autocommit or dsn != config.PLATFORM_DB:
        return _new_conn(dsn, autocommit)
    st = getattr(_TL, 'st', None)
    if st is None:
        st = _TL.st = {'conn': None, 'depth': 0, 'at': 0.0}
    if st['depth']:                       # 嵌套取用：独立新连接，用完真关
        st['depth'] += 1
        nc = _new_conn(dsn, autocommit)

        def _release_nested():
            st['depth'] -= 1
            try:
                nc.close()
            except Exception:
                pass
        return _Borrowed(nc, _release_nested)
    c = st['conn']
    if c is not None and time.monotonic() - st['at'] > _IDLE_PING_S:
        try:
            c.ping(reconnect=True)
        except Exception:
            try:
                c.close()
            except Exception:
                pass
            st['conn'] = c = None
    if c is None:
        c = st['conn'] = _new_conn(dsn, autocommit)
    st['depth'] += 1

    def _release():
        st['depth'] -= 1
        st['at'] = time.monotonic()
        try:
            c.rollback()                  # 未竟事务清零；套接字留下复用
        except Exception:
            try:
                c.close()
            except Exception:
                pass
            if st['conn'] is c:
                st['conn'] = None         # 死连接摘除，下次取用重建
    return _Borrowed(c, _release)


def connect_direct(p, autocommit=False):
    """显式参数直连（P2b load 数据源行）——目标业务库，绝不把平台表建进人家库。
    p={host,port,user,password,database}；连接参数与 connect() 一致。"""
    import pymysql
    return pymysql.connect(
        host=p['host'], port=int(p['port'] or 3306), user=p['user'],
        password=p['password'], database=p['database'],
        charset='utf8mb4', autocommit=autocommit, connect_timeout=5)
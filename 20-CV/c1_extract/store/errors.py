"""
store/errors.py — 存储层类型化业务错误：code 直接映射 HTTP 状态码。

DB 连接/SQL 失败不在此列——pymysql.MySQLError / OSError 原样上抛，
由 Web 层异常处理器统一 503；编程错误上抛 500。业务错误不再靠
消息子串分类（旧 '越界' in msg → 404 的脆弱约定已退役）。
"""


class StoreError(Exception):
    code = 400

    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg


class BadRequest(StoreError):
    code = 400


class NotFound(StoreError):
    code = 404


class Conflict(StoreError):
    code = 409
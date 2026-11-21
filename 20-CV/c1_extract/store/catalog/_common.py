"""catalog 域共享小工具：行→dict 投影、JSON 列反序列化。"""
import json


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _j(v):
    if isinstance(v, (str, bytes)):
        return json.loads(v)
    return v
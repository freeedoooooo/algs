"""store/value_common.py — 计算层（index/rule/frame）repo 共享小工具。

- canonical(obj)：稳定 JSON 序列化（键排序、无空格），保证哈希可复算。
- spec_hash(spec) / value_hash(spec_hash, payload)：定义快照与结果摘要。
- rows(cur) / unjson(v)：行投影与 JSON 列反序列化（与 catalog._common 同语义）。

哈希口径一旦改变，历史结果将无法复现——修改前须评估兼容性。
"""
import hashlib
import json


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'))


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def spec_hash(spec):
    """定义快照哈希：spec 为语义字段字典（不含 id/name/version 标签字段）。"""
    return _sha(canonical(spec))


def value_hash(def_hash, payload):
    """结果哈希：定义快照哈希 + 输入/依赖快照的稳定序列化。"""
    return _sha(str(def_hash) + '|' + canonical(payload))


def rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def unjson(v):
    if isinstance(v, (str, bytes)):
        return json.loads(v)
    return v


def dump(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else None

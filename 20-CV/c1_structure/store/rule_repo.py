"""store/rule_repo.py — 业务规则域（c1_rule_info / c1_rule_value）。

简化设计（2026-11-26）：定义同名唯一、无版本、无哈希；结果只存依赖 ID 与实际值。
"""
from . import db
from .errors import BadRequest, NotFound
from .value_common import rows, unjson, dump

_OPS = ('gt', 'gte', 'lt', 'lte', 'eq', 'ne', 'between')
_COMBINE = ('all', 'any')
_INFO_COLS = ('id', 'name', 'index_refs_json', 'conditions_json',
              'combine', 'created_at', 'updated_at')
_VALUE_COLS = ('id', 'rule_id', 'rule_value', 'computed_at')


def _validate(name, index_refs, conditions, combine):
    name = str(name or '').strip()
    if not name:
        raise BadRequest('规则名不能为空')
    if not isinstance(index_refs, list) or not index_refs:
        raise BadRequest('须引用至少一个指标')
    for ref in index_refs:
        if not isinstance(ref, dict) or not ref.get('index_id') \
                or not ref.get('alias'):
            raise BadRequest('指标引用须含 index_id 与 alias')
        try:
            ref['index_id'] = int(ref['index_id'])
        except (TypeError, ValueError):
            raise BadRequest('指标引用 ID 须为整数')
    if not isinstance(conditions, list) or not conditions:
        raise BadRequest('须配置至少一个条件')
    for c in conditions:
        if not isinstance(c, dict) or c.get('op') not in _OPS \
                or not c.get('alias'):
            raise BadRequest('条件须含 alias 与 op（' + '/'.join(_OPS) + '）')
        if 'threshold' not in c:
            raise BadRequest('条件缺 threshold')
    if combine not in _COMBINE:
        raise BadRequest('组合方式仅支持：' + '/'.join(_COMBINE))
    aliases = {r['alias'] for r in index_refs}
    for c in conditions:
        if c['alias'] not in aliases:
            raise BadRequest('条件引用了未定义的指标别名：' + str(c['alias']))
    return name, index_refs, conditions, combine


def list_defs():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                        ' FROM c1_rule_info ORDER BY id')
            out = rows(cur)
        for r in out:
            r['index_refs_json'] = unjson(r['index_refs_json'])
            r['conditions_json'] = unjson(r['conditions_json'])
        return out
    finally:
        conn.close()


def get_def(rule_id=None, name=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if rule_id is not None:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_rule_info WHERE id=%s', (rule_id,))
            elif name:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_rule_info WHERE name=%s', (name,))
            else:
                return None
            got = rows(cur)
        if not got:
            return None
        r = got[0]
        for k in ('index_refs_json', 'conditions_json'):
            r[k] = unjson(r[k])
        return r
    finally:
        conn.close()


def save_def(name, index_refs, conditions, combine='all', rule_id=None):
    name, index_refs, conditions, combine = _validate(
        name, index_refs, conditions, combine)
    vals = (dump(index_refs), dump(conditions), combine)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if rule_id:
                cur.execute('SELECT id FROM c1_rule_info WHERE id=%s',
                            (rule_id,))
                if not cur.fetchone():
                    raise NotFound('规则定义不存在')
                cur.execute('UPDATE c1_rule_info SET index_refs_json=%s,'
                            ' conditions_json=%s,combine=%s WHERE id=%s',
                            vals + (rule_id,))
                did = rule_id
            else:
                cur.execute('SELECT id FROM c1_rule_info WHERE name=%s',
                            (name,))
                hit = cur.fetchone()
                if hit:
                    did = hit[0]
                    cur.execute('UPDATE c1_rule_info SET index_refs_json=%s,'
                                ' conditions_json=%s,combine=%s WHERE id=%s',
                                vals + (did,))
                else:
                    cur.execute(
                        'INSERT INTO c1_rule_info'
                        ' (name,index_refs_json,conditions_json,combine)'
                        ' VALUES (%s,%s,%s,%s)', (name,) + vals)
                    did = cur.lastrowid
            conn.commit()
            return did
    finally:
        conn.close()


create_def = save_def


def delete_def(rule_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_rule_info WHERE id=%s', (rule_id,))
            if not cur.fetchone():
                raise NotFound('规则定义不存在')
            cur.execute('DELETE FROM c1_rule_value WHERE rule_id=%s', (rule_id,))
            cur.execute('DELETE FROM c1_rule_info WHERE id=%s', (rule_id,))
            from .compute_layout_repo import delete_for_def
            delete_for_def(cur, 'rule', rule_id)
            conn.commit()
    finally:
        conn.close()


def add_value(rule_id, rule_value):
    """写规则结果：只存定义 ID + 结果值。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_rule_info WHERE id=%s', (rule_id,))
            if not cur.fetchone():
                raise NotFound('规则定义不存在')
            cur.execute('INSERT INTO c1_rule_value (rule_id,rule_value)'
                        ' VALUES (%s,%s)', (rule_id, str(rule_value)))
            vid = cur.lastrowid
            conn.commit()
            return vid
    finally:
        conn.close()


def get_value(value_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + ','.join(_VALUE_COLS) +
                        ' FROM c1_rule_value WHERE id=%s', (value_id,))
            got = rows(cur)
        return got[0] if got else None
    finally:
        conn.close()


def list_values(rule_id=None, limit=200):
    sql = 'SELECT ' + ','.join(_VALUE_COLS) + ' FROM c1_rule_value'
    args = []
    if rule_id is not None:
        sql += ' WHERE rule_id=%s'
        args.append(rule_id)
    sql += ' ORDER BY id DESC LIMIT %s'
    args.append(max(1, min(500, int(limit or 200))))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return rows(cur)
    finally:
        conn.close()

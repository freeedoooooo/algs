"""store/rule_repo.py — 业务规则域（c1_rule_info / c1_rule_value）。

本模块的 rule 专指计算层业务规则，与抽取规则 c1_extract_rule 无关。
定义版本行同表不可变；值行携带 index_value_ids_json（血缘上溯）+ detail_json。
"""
from . import db
from .errors import BadRequest, Conflict, NotFound
from .value_common import (rows, unjson, dump, spec_hash as _spec_hash,
                           value_hash as _value_hash)

_OPS = ('gt', 'gte', 'lt', 'lte', 'eq', 'ne', 'between')
_COMBINE = ('all', 'any')
_INFO_COLS = ('id', 'name', 'version', 'index_refs_json', 'conditions_json',
              'combine', 'spec_hash', 'created_at')
_VALUE_COLS = ('id', 'rule_id', 'rule_version', 'index_value_ids_json',
               'outcome', 'detail_json', 'result_hash', 'computed_at')


def _spec(index_refs, conditions, combine):
    return {'index_refs': index_refs, 'conditions': conditions,
            'combine': combine}


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
            ref['version'] = int(ref.get('version') or 0)
        except (TypeError, ValueError):
            raise BadRequest('指标引用 ID/版本须为整数')
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
            cur.execute(
                'SELECT r.id, r.name, r.version, r.index_refs_json,'
                ' r.conditions_json, r.combine, r.spec_hash, r.created_at,'
                ' (SELECT MAX(x.version) FROM c1_rule_info x'
                '   WHERE x.name=r.name) AS latest_version,'
                ' (SELECT COUNT(*) FROM c1_rule_info x'
                '   WHERE x.name=r.name) AS version_count'
                ' FROM c1_rule_info r'
                ' WHERE r.version=(SELECT MAX(x.version) FROM c1_rule_info x'
                '                  WHERE x.name=r.name)'
                ' ORDER BY r.id')
            out = rows(cur)
        for r in out:
            r['index_refs_json'] = unjson(r['index_refs_json'])
            r['conditions_json'] = unjson(r['conditions_json'])
        return out
    finally:
        conn.close()


def get_def(rule_id=None, name=None, version=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if rule_id is not None:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_rule_info WHERE id=%s', (rule_id,))
            elif name:
                if version is not None:
                    cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                                ' FROM c1_rule_info WHERE name=%s AND version=%s',
                                (name, version))
                else:
                    cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                                ' FROM c1_rule_info WHERE name=%s'
                                ' ORDER BY version DESC LIMIT 1', (name,))
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


def list_versions(name):
    if get_def(name=name) is None:
        raise NotFound('规则定义不存在')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, version, created_at, spec_hash'
                        ' FROM c1_rule_info WHERE name=%s ORDER BY version DESC',
                        (name,))
            return rows(cur)
    finally:
        conn.close()


def create_def(name, index_refs, conditions, combine='all'):
    name, index_refs, conditions, combine = _validate(
        name, index_refs, conditions, combine)
    sh = _spec_hash(_spec(index_refs, conditions, combine))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT MAX(version) FROM c1_rule_info WHERE name=%s',
                        (name,))
            v = (cur.fetchone()[0] or 0) + 1
            cur.execute('SELECT id FROM c1_rule_info WHERE name=%s AND spec_hash=%s',
                        (name, sh))
            if cur.fetchone():
                raise Conflict('规则定义未变化，无需新建版本')
            cur.execute(
                'INSERT INTO c1_rule_info'
                ' (name,version,index_refs_json,conditions_json,combine,spec_hash)'
                ' VALUES (%s,%s,%s,%s,%s,%s)',
                (name, v, dump(index_refs), dump(conditions), combine, sh))
            did = cur.lastrowid
            conn.commit()
            return did
    finally:
        conn.close()


def delete_def(rule_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name FROM c1_rule_info WHERE id=%s', (rule_id,))
            got = cur.fetchone()
            if not got:
                raise NotFound('规则定义不存在')
            name = got[0]
            cur.execute('SELECT COUNT(*) FROM c1_rule_value WHERE rule_id=%s',
                        (rule_id,))
            if cur.fetchone()[0]:
                raise Conflict('该规则已有计算结果，禁止删除')
            cur.execute('DELETE FROM c1_rule_info WHERE name=%s', (name,))
            conn.commit()
    finally:
        conn.close()


def add_value(rule_id, rule_version, def_hash, index_value_ids, outcome,
              detail):
    """写规则值：依赖 ID 列表 + 逐条件明细进快照，供追溯展开。"""
    vh = _value_hash(def_hash, {'index_value_ids': index_value_ids,
                                'detail': detail, 'outcome': outcome})
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_rule_info WHERE id=%s AND version=%s',
                        (rule_id, rule_version))
            if not cur.fetchone():
                raise NotFound('规则定义版本不存在')
            cur.execute(
                'INSERT IGNORE INTO c1_rule_value'
                ' (rule_id,rule_version,index_value_ids_json,outcome,'
                '  detail_json,result_hash) VALUES (%s,%s,%s,%s,%s,%s)',
                (rule_id, rule_version, dump(index_value_ids), outcome,
                 dump(detail), vh))
            if cur.rowcount:
                vid = cur.lastrowid
                conn.commit()
                return vid, vh, True
            cur.execute('SELECT id FROM c1_rule_value WHERE rule_id=%s'
                        ' AND rule_version=%s AND result_hash=%s',
                        (rule_id, rule_version, vh))
            return cur.fetchone()[0], vh, False
    finally:
        conn.close()


def get_value(value_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + ','.join(_VALUE_COLS) +
                        ' FROM c1_rule_value WHERE id=%s', (value_id,))
            got = rows(cur)
        if not got:
            return None
        r = got[0]
        for k in ('index_value_ids_json', 'detail_json'):
            r[k] = unjson(r[k])
        return r
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
            out = rows(cur)
        for r in out:
            for k in ('index_value_ids_json', 'detail_json'):
                r[k] = unjson(r[k])
        return out
    finally:
        conn.close()

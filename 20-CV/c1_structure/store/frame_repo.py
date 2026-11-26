"""store/frame_repo.py — 框架域（c1_frame_info / c1_frame_value）。

框架关联业务规则并组合出结论；值行携带 rule_value_ids_json（血缘上溯）
与逐规则贡献明细，是追溯链顶点。
"""
from decimal import Decimal

from . import db
from .errors import BadRequest, Conflict, NotFound
from .value_common import (rows, unjson, dump, spec_hash as _spec_hash,
                           value_hash as _value_hash)

_COMBINE = ('weighted', 'all_pass', 'any_pass', 'veto')
_INFO_COLS = ('id', 'name', 'version', 'rule_refs_json', 'combine',
              'threshold', 'spec_hash', 'created_at')
_VALUE_COLS = ('id', 'frame_id', 'frame_version', 'rule_value_ids_json',
               'outcome', 'score_text', 'detail_json', 'result_hash',
               'computed_at')


def _spec(rule_refs, combine, threshold):
    return {'rule_refs': rule_refs, 'combine': combine,
            'threshold': str(threshold) if threshold is not None else None}


def _validate(name, rule_refs, combine, threshold):
    name = str(name or '').strip()
    if not name:
        raise BadRequest('框架名不能为空')
    if not isinstance(rule_refs, list) or not rule_refs:
        raise BadRequest('须关联至少一个规则')
    for ref in rule_refs:
        if not isinstance(ref, dict) or not ref.get('rule_id'):
            raise BadRequest('规则引用须含 rule_id')
        try:
            ref['rule_id'] = int(ref['rule_id'])
            ref['version'] = int(ref.get('version') or 0)
            ref['weight'] = Decimal(str(ref.get('weight', 1)))
        except (TypeError, ValueError, ArithmeticError):
            raise BadRequest('规则引用 rule_id/version/weight 非法')
        ref['weight'] = str(ref['weight'])
        ref['veto'] = bool(ref.get('veto'))
    if combine not in _COMBINE:
        raise BadRequest('组合方式仅支持：' + '/'.join(_COMBINE))
    if combine == 'weighted':
        if threshold is None:
            raise BadRequest('weighted 模式须给 threshold')
        try:
            threshold = Decimal(str(threshold))
        except (TypeError, ValueError, ArithmeticError):
            raise BadRequest('threshold 须为数值')
        threshold = str(threshold)
    return name, rule_refs, combine, threshold


def list_defs():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT f.id, f.name, f.version, f.rule_refs_json, f.combine,'
                ' f.threshold, f.spec_hash, f.created_at,'
                ' (SELECT MAX(x.version) FROM c1_frame_info x'
                '   WHERE x.name=f.name) AS latest_version,'
                ' (SELECT COUNT(*) FROM c1_frame_info x'
                '   WHERE x.name=f.name) AS version_count'
                ' FROM c1_frame_info f'
                ' WHERE f.version=(SELECT MAX(x.version) FROM c1_frame_info x'
                '                  WHERE x.name=f.name)'
                ' ORDER BY f.id')
            out = rows(cur)
        for r in out:
            r['rule_refs_json'] = unjson(r['rule_refs_json'])
            if r['threshold'] is not None:
                r['threshold'] = str(r['threshold'])
        return out
    finally:
        conn.close()


def get_def(frame_id=None, name=None, version=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if frame_id is not None:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_frame_info WHERE id=%s', (frame_id,))
            elif name:
                if version is not None:
                    cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                                ' FROM c1_frame_info WHERE name=%s AND version=%s',
                                (name, version))
                else:
                    cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                                ' FROM c1_frame_info WHERE name=%s'
                                ' ORDER BY version DESC LIMIT 1', (name,))
            else:
                return None
            got = rows(cur)
        if not got:
            return None
        r = got[0]
        r['rule_refs_json'] = unjson(r['rule_refs_json'])
        if r['threshold'] is not None:
            r['threshold'] = str(r['threshold'])
        return r
    finally:
        conn.close()


def list_versions(name):
    if get_def(name=name) is None:
        raise NotFound('框架定义不存在')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, version, created_at, spec_hash'
                        ' FROM c1_frame_info WHERE name=%s ORDER BY version DESC',
                        (name,))
            return rows(cur)
    finally:
        conn.close()


def create_def(name, rule_refs, combine='weighted', threshold=None):
    name, rule_refs, combine, threshold = _validate(
        name, rule_refs, combine, threshold)
    sh = _spec_hash(_spec(rule_refs, combine, threshold))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT MAX(version) FROM c1_frame_info WHERE name=%s',
                        (name,))
            v = (cur.fetchone()[0] or 0) + 1
            cur.execute('SELECT id FROM c1_frame_info WHERE name=%s AND spec_hash=%s',
                        (name, sh))
            if cur.fetchone():
                raise Conflict('框架定义未变化，无需新建版本')
            cur.execute(
                'INSERT INTO c1_frame_info'
                ' (name,version,rule_refs_json,combine,threshold,spec_hash)'
                ' VALUES (%s,%s,%s,%s,%s,%s)',
                (name, v, dump(rule_refs), combine, threshold, sh))
            did = cur.lastrowid
            conn.commit()
            return did
    finally:
        conn.close()


def delete_def(frame_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name FROM c1_frame_info WHERE id=%s', (frame_id,))
            got = cur.fetchone()
            if not got:
                raise NotFound('框架定义不存在')
            name = got[0]
            cur.execute('SELECT COUNT(*) FROM c1_frame_value WHERE frame_id=%s',
                        (frame_id,))
            if cur.fetchone()[0]:
                raise Conflict('该框架已有计算结果，禁止删除')
            cur.execute('DELETE FROM c1_frame_info WHERE name=%s', (name,))
            conn.commit()
    finally:
        conn.close()


def add_value(frame_id, frame_version, def_hash, rule_value_ids, outcome,
              detail, score_text=None):
    vh = _value_hash(def_hash, {'rule_value_ids': rule_value_ids,
                                'detail': detail, 'outcome': outcome,
                                'score': score_text})
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_frame_info WHERE id=%s AND version=%s',
                        (frame_id, frame_version))
            if not cur.fetchone():
                raise NotFound('框架定义版本不存在')
            cur.execute(
                'INSERT IGNORE INTO c1_frame_value'
                ' (frame_id,frame_version,rule_value_ids_json,outcome,'
                '  score_text,detail_json,result_hash)'
                ' VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (frame_id, frame_version, dump(rule_value_ids), outcome,
                 score_text, dump(detail), vh))
            if cur.rowcount:
                return cur.lastrowid, vh, True
            cur.execute('SELECT id FROM c1_frame_value WHERE frame_id=%s'
                        ' AND frame_version=%s AND result_hash=%s',
                        (frame_id, frame_version, vh))
            return cur.fetchone()[0], vh, False
    finally:
        conn.close()


def get_value(value_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + ','.join(_VALUE_COLS) +
                        ' FROM c1_frame_value WHERE id=%s', (value_id,))
            got = rows(cur)
        if not got:
            return None
        r = got[0]
        for k in ('rule_value_ids_json', 'detail_json'):
            r[k] = unjson(r[k])
        return r
    finally:
        conn.close()


def list_values(frame_id=None, limit=200):
    sql = 'SELECT ' + ','.join(_VALUE_COLS) + ' FROM c1_frame_value'
    args = []
    if frame_id is not None:
        sql += ' WHERE frame_id=%s'
        args.append(frame_id)
    sql += ' ORDER BY id DESC LIMIT %s'
    args.append(max(1, min(500, int(limit or 200))))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            out = rows(cur)
        for r in out:
            for k in ('rule_value_ids_json', 'detail_json'):
                r[k] = unjson(r[k])
        return out
    finally:
        conn.close()

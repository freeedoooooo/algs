"""store/frame_repo.py — 框架域（c1_calc_frame_info / c1_calc_frame_value）。

简化设计（2026-11-26）：定义同名唯一、无版本、无哈希；结果只存依赖 ID 与结论。
"""
from decimal import Decimal

from . import db
from .errors import BadRequest, NotFound
from .value_common import rows, unjson, dump

_COMBINE = ('weighted', 'all_pass', 'any_pass', 'veto')
_INFO_COLS = ('id', 'name', 'rule_refs_json', 'combine', 'threshold',
              'created_at', 'updated_at')
_VALUE_COLS = ('id', 'frame_id', 'frame_value', 'computed_at')


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
            Decimal(str(ref.get('weight', 1)))
        except (TypeError, ValueError, ArithmeticError):
            raise BadRequest('规则引用 rule_id/weight 非法')
        ref['weight'] = str(ref.get('weight', 1))
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
            cols = ['i.' + c for c in _INFO_COLS]
            cols += ['v.id AS value_id', 'v.frame_value', 'v.computed_at']
            cur.execute(
                'SELECT ' + ','.join(cols) +
                ' FROM c1_calc_frame_info i'
                ' LEFT JOIN (SELECT frame_id,MAX(id) AS value_id'
                '            FROM c1_calc_frame_value GROUP BY frame_id) latest'
                '   ON latest.frame_id=i.id'
                ' LEFT JOIN c1_calc_frame_value v ON v.id=latest.value_id'
                ' ORDER BY i.id')
            out = rows(cur)
        for r in out:
            r['rule_refs_json'] = unjson(r['rule_refs_json'])
            if r['threshold'] is not None:
                r['threshold'] = str(r['threshold'])
            value_id = r.pop('value_id')
            r['_latest'] = None if value_id is None else {
                'id': value_id, 'frame_id': r['id'],
                'frame_value': r['frame_value'],
                'computed_at': r['computed_at']}
            r.pop('frame_value')
            r.pop('computed_at')
        return out
    finally:
        conn.close()


def get_def(frame_id=None, name=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if frame_id is not None:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_calc_frame_info WHERE id=%s', (frame_id,))
            elif name:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_calc_frame_info WHERE name=%s', (name,))
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


def save_def(name, rule_refs, combine='weighted', threshold=None,
             frame_id=None):
    name, rule_refs, combine, threshold = _validate(
        name, rule_refs, combine, threshold)
    vals = (dump(rule_refs), combine, threshold)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if frame_id:
                cur.execute('SELECT id FROM c1_calc_frame_info WHERE id=%s',
                            (frame_id,))
                if not cur.fetchone():
                    raise NotFound('框架定义不存在')
                cur.execute('UPDATE c1_calc_frame_info SET rule_refs_json=%s,'
                            ' combine=%s,threshold=%s WHERE id=%s',
                            vals + (frame_id,))
                did = frame_id
            else:
                cur.execute('SELECT id FROM c1_calc_frame_info WHERE name=%s',
                            (name,))
                hit = cur.fetchone()
                if hit:
                    did = hit[0]
                    cur.execute('UPDATE c1_calc_frame_info SET rule_refs_json=%s,'
                                ' combine=%s,threshold=%s WHERE id=%s',
                                vals + (did,))
                else:
                    cur.execute(
                        'INSERT INTO c1_calc_frame_info'
                        ' (name,rule_refs_json,combine,threshold)'
                        ' VALUES (%s,%s,%s,%s)', (name,) + vals)
                    did = cur.lastrowid
            conn.commit()
            return did
    finally:
        conn.close()


create_def = save_def


def delete_def(frame_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_calc_frame_info WHERE id=%s', (frame_id,))
            if not cur.fetchone():
                raise NotFound('框架定义不存在')
            cur.execute('DELETE FROM c1_calc_frame_value WHERE frame_id=%s',
                        (frame_id,))
            cur.execute('DELETE FROM c1_calc_frame_info WHERE id=%s', (frame_id,))
            from .compute_layout_repo import delete_for_def
            delete_for_def(cur, 'frame', frame_id)
            conn.commit()
    finally:
        conn.close()


def add_value(frame_id, frame_value):
    """写框架结果：只存定义 ID + 结果值。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_calc_frame_info WHERE id=%s', (frame_id,))
            if not cur.fetchone():
                raise NotFound('框架定义不存在')
            cur.execute('INSERT INTO c1_calc_frame_value (frame_id,frame_value)'
                        ' VALUES (%s,%s)', (frame_id, str(frame_value)))
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
                        ' FROM c1_calc_frame_value WHERE id=%s', (value_id,))
            got = rows(cur)
        return got[0] if got else None
    finally:
        conn.close()


def list_values(frame_id=None, limit=200):
    sql = 'SELECT ' + ','.join(_VALUE_COLS) + ' FROM c1_calc_frame_value'
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
            return rows(cur)
    finally:
        conn.close()

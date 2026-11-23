"""目录库 · 抽取规则域（c1_rule / c1_rule_version）。

版本＝三段 JSON 不可变快照；编辑＝新版本＋current 前移，
旧任务引用旧版本不受影响。被任务引用的抽取规则禁删。
"""
import json

from .. import db
from ..errors import BadRequest, Conflict, NotFound
from ._common import _j, _rows


def list_rules():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            # current_version_id：前端下拉直接提交版本 id，不用再查一次
            cur.execute(
                'SELECT t.id, t.name, t.description, t.current_version,'
                ' (SELECT tv.id FROM c1_rule_version tv'
                '   WHERE tv.rule_id=t.id'
                '     AND tv.version=t.current_version) AS current_version_id,'
                ' (SELECT COUNT(*) FROM c1_rule_version tv'
                '   WHERE tv.rule_id=t.id) AS version_count,'
                ' t.updated_at'
                ' FROM c1_rule t ORDER BY t.id')
            return _rows(cur)
    finally:
        conn.close()


def get_rule_version(version_id=None, name=None):
    """按 id / 抽取规则名取版本；都不给则取第一个抽取规则的当前版本（名可改，不硬编码）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if version_id is not None:
                cur.execute(
                    'SELECT tv.id, tv.rule_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM c1_rule_version tv JOIN c1_rule t'
                    ' ON t.id = tv.rule_id WHERE tv.id=%s', (version_id,))
            elif name:
                cur.execute(
                    'SELECT tv.id, tv.rule_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM c1_rule_version tv JOIN c1_rule t'
                    ' ON t.id = tv.rule_id'
                    ' WHERE t.name=%s AND tv.version=t.current_version',
                    (name,))
            else:
                cur.execute(
                    'SELECT tv.id, tv.rule_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM c1_rule_version tv JOIN c1_rule t'
                    ' ON t.id = tv.rule_id'
                    ' WHERE tv.version=t.current_version'
                    ' ORDER BY t.id LIMIT 1')
            rows = _rows(cur)
        if not rows:
            return None
        r = rows[0]
        for k in ('schema_json', 'mapping_json', 'transform_json'):
            r[k] = _j(r[k])
        return r
    finally:
        conn.close()


def _tpl_exists(cur, rule_id):
    cur.execute('SELECT id FROM c1_rule WHERE id=%s', (rule_id,))
    if not cur.fetchone():
        raise NotFound('抽取规则不存在')


def _tpl_payload(schema, mapping, transform):
    for v in (schema, mapping, transform):
        if v is not None and not isinstance(v, dict):
            raise BadRequest('规则定义须为 JSON 对象')
    return (json.dumps(schema), json.dumps(mapping), json.dumps(transform))


def get_rule(rule_id):
    """抽取规则元数据＋当前版本三段 JSON（编辑器加载用）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, rule_id)
            cur.execute(
                'SELECT t.id, t.name, t.description, t.current_version,'
                ' tv.id AS current_version_id, tv.schema_json,'
                ' tv.mapping_json, tv.transform_json'
                ' FROM c1_rule t LEFT JOIN c1_rule_version tv'
                ' ON tv.rule_id=t.id AND tv.version=t.current_version'
                ' WHERE t.id=%s', (rule_id,))
            r = _rows(cur)[0]
        for k in ('schema_json', 'mapping_json', 'transform_json'):
            r[k] = _j(r[k])
        return r
    finally:
        conn.close()


def create_rule(name, description=None, schema=None, mapping=None,
                    transform=None):
    """建抽取规则＋v1 不可变快照＋current=1；重名 Conflict。返回版本 id。"""
    name = str(name or '').strip()
    if not name:
        raise BadRequest('规则名不能为空')
    sj, mj, tj = _tpl_payload(schema, mapping, transform)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_rule WHERE name=%s', (name,))
            if cur.fetchone():
                raise Conflict('规则名已存在')
            cur.execute('INSERT INTO c1_rule (name, description,'
                        ' current_version) VALUES (%s,%s,1)',
                        (name, description))
            tid = cur.lastrowid
            cur.execute('INSERT INTO c1_rule_version'
                        ' (rule_id, version, schema_json, mapping_json,'
                        ' transform_json) VALUES (%s,1,%s,%s,%s)',
                        (tid, sj, mj, tj))
            vid = cur.lastrowid
            conn.commit()
            return vid
    finally:
        conn.close()


def create_version(rule_id, schema=None, mapping=None, transform=None):
    """编辑＝新版本不可变快照＋current 前移（旧任务引用旧版本不受影响）。"""
    sj, mj, tj = _tpl_payload(schema, mapping, transform)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, rule_id)
            cur.execute('SELECT COALESCE(MAX(version),0) FROM'
                        ' c1_rule_version WHERE rule_id=%s',
                        (rule_id,))
            v = cur.fetchone()[0] + 1
            cur.execute('INSERT INTO c1_rule_version'
                        ' (rule_id, version, schema_json, mapping_json,'
                        ' transform_json) VALUES (%s,%s,%s,%s,%s)',
                        (rule_id, v, sj, mj, tj))
            vid = cur.lastrowid
            cur.execute('UPDATE c1_rule SET current_version=%s'
                        ' WHERE id=%s', (v, rule_id))
            conn.commit()
            return vid
    finally:
        conn.close()


def update_rule(rule_id, name=None, description=None,
                    current_version=None):
    """改名/说明不建新版本；current_version 须已存在否则 BadRequest。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, rule_id)
            if name is not None:
                name = str(name).strip()
                if not name:
                    raise BadRequest('规则名不能为空')
                cur.execute('SELECT id FROM c1_rule'
                            ' WHERE name=%s AND id<>%s', (name, rule_id))
                if cur.fetchone():
                    raise Conflict('规则名已存在')
                cur.execute('UPDATE c1_rule SET name=%s WHERE id=%s',
                            (name, rule_id))
            if description is not None:
                cur.execute('UPDATE c1_rule SET description=%s'
                            ' WHERE id=%s', (description, rule_id))
            if current_version is not None:
                cur.execute('SELECT id FROM c1_rule_version'
                            ' WHERE rule_id=%s AND version=%s',
                            (rule_id, current_version))
                if not cur.fetchone():
                    raise BadRequest('指定版本不存在')
                cur.execute('UPDATE c1_rule SET current_version=%s'
                            ' WHERE id=%s', (current_version, rule_id))
            conn.commit()
    finally:
        conn.close()


def delete_rule(rule_id):
    """被任务引用（任一版本）禁删 Conflict；无引用先删 versions 再删抽取规则。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, rule_id)
            cur.execute('SELECT COUNT(*) FROM c1_task WHERE'
                        ' rule_version_id IN (SELECT id FROM'
                        ' c1_rule_version WHERE rule_id=%s)',
                        (rule_id,))
            if cur.fetchone()[0]:
                raise Conflict('该抽取规则已被任务引用，禁止删除')
            cur.execute('DELETE FROM c1_rule_version'
                        ' WHERE rule_id=%s', (rule_id,))
            cur.execute('DELETE FROM c1_rule WHERE id=%s',
                        (rule_id,))
            conn.commit()
    finally:
        conn.close()


def list_versions(rule_id):
    """版本倒序＋是否当前（版本历史/设当前用）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, rule_id)
            cur.execute('SELECT tv.id, tv.version, tv.created_at,'
                        ' (tv.version=t.current_version) AS is_current'
                        ' FROM c1_rule_version tv'
                        ' JOIN c1_rule t ON t.id=tv.rule_id'
                        ' WHERE tv.rule_id=%s ORDER BY tv.version DESC',
                        (rule_id,))
            return _rows(cur)
    finally:
        conn.close()
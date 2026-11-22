"""目录库 · 模板域（extract_template / extract_template_version）。

版本＝三段 JSON 不可变快照；编辑＝新版本＋current 前移，
旧任务引用旧版本不受影响。被任务引用的模板禁删。
"""
import json

from .. import db
from ..errors import BadRequest, Conflict, NotFound
from ._common import _j, _rows


def list_templates():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            # current_version_id：前端下拉直接提交版本 id，不用再查一次
            cur.execute(
                'SELECT t.id, t.name, t.description, t.current_version,'
                ' (SELECT tv.id FROM extract_template_version tv'
                '   WHERE tv.template_id=t.id'
                '     AND tv.version=t.current_version) AS current_version_id,'
                ' (SELECT COUNT(*) FROM extract_template_version tv'
                '   WHERE tv.template_id=t.id) AS version_count,'
                ' t.updated_at'
                ' FROM extract_template t ORDER BY t.id')
            return _rows(cur)
    finally:
        conn.close()


def get_template_version(version_id=None, name=None):
    """按 id / 模板名取版本；都不给则取第一个模板的当前版本（名可改，不硬编码）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if version_id is not None:
                cur.execute(
                    'SELECT tv.id, tv.template_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM extract_template_version tv JOIN extract_template t'
                    ' ON t.id = tv.template_id WHERE tv.id=%s', (version_id,))
            elif name:
                cur.execute(
                    'SELECT tv.id, tv.template_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM extract_template_version tv JOIN extract_template t'
                    ' ON t.id = tv.template_id'
                    ' WHERE t.name=%s AND tv.version=t.current_version',
                    (name,))
            else:
                cur.execute(
                    'SELECT tv.id, tv.template_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM extract_template_version tv JOIN extract_template t'
                    ' ON t.id = tv.template_id'
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


def _tpl_exists(cur, template_id):
    cur.execute('SELECT id FROM extract_template WHERE id=%s', (template_id,))
    if not cur.fetchone():
        raise NotFound('模板不存在')


def _tpl_payload(schema, mapping, transform):
    for v in (schema, mapping, transform):
        if v is not None and not isinstance(v, dict):
            raise BadRequest('模板定义须为 JSON 对象')
    return (json.dumps(schema), json.dumps(mapping), json.dumps(transform))


def get_template(template_id):
    """模板元数据＋当前版本三段 JSON（编辑器加载用）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            cur.execute(
                'SELECT t.id, t.name, t.description, t.current_version,'
                ' tv.id AS current_version_id, tv.schema_json,'
                ' tv.mapping_json, tv.transform_json'
                ' FROM extract_template t LEFT JOIN extract_template_version tv'
                ' ON tv.template_id=t.id AND tv.version=t.current_version'
                ' WHERE t.id=%s', (template_id,))
            r = _rows(cur)[0]
        for k in ('schema_json', 'mapping_json', 'transform_json'):
            r[k] = _j(r[k])
        return r
    finally:
        conn.close()


def create_template(name, description=None, schema=None, mapping=None,
                    transform=None):
    """建模板＋v1 不可变快照＋current=1；重名 Conflict。返回版本 id。"""
    name = str(name or '').strip()
    if not name:
        raise BadRequest('模板名不能为空')
    sj, mj, tj = _tpl_payload(schema, mapping, transform)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_template WHERE name=%s', (name,))
            if cur.fetchone():
                raise Conflict('模板名已存在')
            cur.execute('INSERT INTO extract_template (name, description,'
                        ' current_version) VALUES (%s,%s,1)',
                        (name, description))
            tid = cur.lastrowid
            cur.execute('INSERT INTO extract_template_version'
                        ' (template_id, version, schema_json, mapping_json,'
                        ' transform_json) VALUES (%s,1,%s,%s,%s)',
                        (tid, sj, mj, tj))
            vid = cur.lastrowid
            conn.commit()
            return vid
    finally:
        conn.close()


def create_version(template_id, schema=None, mapping=None, transform=None):
    """编辑＝新版本不可变快照＋current 前移（旧任务引用旧版本不受影响）。"""
    sj, mj, tj = _tpl_payload(schema, mapping, transform)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            cur.execute('SELECT COALESCE(MAX(version),0) FROM'
                        ' extract_template_version WHERE template_id=%s',
                        (template_id,))
            v = cur.fetchone()[0] + 1
            cur.execute('INSERT INTO extract_template_version'
                        ' (template_id, version, schema_json, mapping_json,'
                        ' transform_json) VALUES (%s,%s,%s,%s,%s)',
                        (template_id, v, sj, mj, tj))
            vid = cur.lastrowid
            cur.execute('UPDATE extract_template SET current_version=%s'
                        ' WHERE id=%s', (v, template_id))
            conn.commit()
            return vid
    finally:
        conn.close()


def update_template(template_id, name=None, description=None,
                    current_version=None):
    """改名/说明不建新版本；current_version 须已存在否则 BadRequest。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            if name is not None:
                name = str(name).strip()
                if not name:
                    raise BadRequest('模板名不能为空')
                cur.execute('SELECT id FROM extract_template'
                            ' WHERE name=%s AND id<>%s', (name, template_id))
                if cur.fetchone():
                    raise Conflict('模板名已存在')
                cur.execute('UPDATE extract_template SET name=%s WHERE id=%s',
                            (name, template_id))
            if description is not None:
                cur.execute('UPDATE extract_template SET description=%s'
                            ' WHERE id=%s', (description, template_id))
            if current_version is not None:
                cur.execute('SELECT id FROM extract_template_version'
                            ' WHERE template_id=%s AND version=%s',
                            (template_id, current_version))
                if not cur.fetchone():
                    raise BadRequest('指定版本不存在')
                cur.execute('UPDATE extract_template SET current_version=%s'
                            ' WHERE id=%s', (current_version, template_id))
            conn.commit()
    finally:
        conn.close()


def delete_template(template_id):
    """被任务引用（任一版本）禁删 Conflict；无引用先删 versions 再删模板。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            cur.execute('SELECT COUNT(*) FROM extract_task WHERE'
                        ' template_version_id IN (SELECT id FROM'
                        ' extract_template_version WHERE template_id=%s)',
                        (template_id,))
            if cur.fetchone()[0]:
                raise Conflict('该模板已被任务引用，禁止删除')
            cur.execute('DELETE FROM extract_template_version'
                        ' WHERE template_id=%s', (template_id,))
            cur.execute('DELETE FROM extract_template WHERE id=%s',
                        (template_id,))
            conn.commit()
    finally:
        conn.close()


def list_versions(template_id):
    """版本倒序＋是否当前（版本历史/设当前用）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            cur.execute('SELECT tv.id, tv.version, tv.created_at,'
                        ' (tv.version=t.current_version) AS is_current'
                        ' FROM extract_template_version tv'
                        ' JOIN extract_template t ON t.id=tv.template_id'
                        ' WHERE tv.template_id=%s ORDER BY tv.version DESC',
                        (template_id,))
            return _rows(cur)
    finally:
        conn.close()
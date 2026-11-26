"""store/compute_layout_repo.py — 计算流程图节点坐标持久化。"""
import math

from . import db
from .errors import BadRequest, NotFound
from .value_common import rows

_TABLES = {
    'index': 'c1_index_info',
    'rule': 'c1_rule_info',
    'frame': 'c1_frame_info',
}
_MISSING_TABLE = 1146


def _missing_table(exc):
    return bool(exc.args and exc.args[0] == _MISSING_TABLE)


def _item(item):
    if not isinstance(item, dict):
        raise BadRequest('布局项须为对象')
    scope = item.get('scope')
    if scope not in _TABLES:
        raise BadRequest('布局 scope 仅支持 index/rule/frame')
    did = item.get('id')
    if isinstance(did, bool):
        raise BadRequest('布局定义 ID 须为正整数')
    try:
        did = int(did)
    except (TypeError, ValueError):
        raise BadRequest('布局定义 ID 须为正整数')
    try:
        exact_id = float(item.get('id')) == did
    except (TypeError, ValueError):
        exact_id = False
    if did <= 0 or not exact_id:
        raise BadRequest('布局定义 ID 须为正整数')
    coords = []
    for key in ('x', 'y'):
        value = item.get(key)
        if isinstance(value, bool):
            raise BadRequest('布局坐标须为有限数值')
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise BadRequest('布局坐标须为有限数值')
        if not math.isfinite(value) or abs(value) > 1000000:
            raise BadRequest('布局坐标须为 -1000000 到 1000000 之间的数值')
        coords.append(value)
    return {'scope': scope, 'id': did, 'x': coords[0], 'y': coords[1]}


def normalize_items(items):
    if not isinstance(items, list):
        raise BadRequest('布局 items 须为数组')
    if len(items) > 1000:
        raise BadRequest('单次最多保存 1000 个节点布局')
    out, seen = [], set()
    for raw in items:
        item = _item(raw)
        key = (item['scope'], item['id'])
        if key in seen:
            raise BadRequest('布局项存在重复节点')
        seen.add(key)
        out.append(item)
    return out


def list_layout():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute('SELECT scope,def_id,pos_x,pos_y'
                            ' FROM c1_compute_graph_layout')
                items = rows(cur)
            except Exception as exc:
                if not _missing_table(exc):
                    raise
                return {'available': False, 'items': []}
        for item in items:
            item['id'] = item.pop('def_id')
            item['x'] = item.pop('pos_x')
            item['y'] = item.pop('pos_y')
        return {'available': True, 'items': items}
    finally:
        conn.close()


def save_layout(items):
    items = normalize_items(items)
    if not items:
        return {'available': True, 'saved': 0}
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            try:
                for scope in _TABLES:
                    ids = [i['id'] for i in items if i['scope'] == scope]
                    if not ids:
                        continue
                    marks = ','.join(['%s'] * len(ids))
                    cur.execute('SELECT id FROM ' + _TABLES[scope] +
                                ' WHERE id IN (' + marks + ')', ids)
                    found = {r[0] for r in cur.fetchall()}
                    missing = sorted(set(ids) - found)
                    if missing:
                        raise NotFound('节点定义不存在：' + str(missing))
                cur.executemany(
                    'INSERT INTO c1_compute_graph_layout'
                    ' (scope,def_id,pos_x,pos_y) VALUES (%s,%s,%s,%s)'
                    ' ON DUPLICATE KEY UPDATE pos_x=VALUES(pos_x),'
                    ' pos_y=VALUES(pos_y),updated_at=CURRENT_TIMESTAMP',
                    [(i['scope'], i['id'], i['x'], i['y']) for i in items])
            except Exception as exc:
                if _missing_table(exc):
                    raise BadRequest(
                        '节点布局表尚未安装，请由数据库管理员执行 '
                        'store/migrations/005_compute_graph_layout.sql')
                raise
            conn.commit()
        return {'available': True, 'saved': len(items)}
    finally:
        conn.close()


def delete_for_def(cur, scope, def_id):
    """删除定义时同事务清理；旧库尚未安装布局表不阻断原删除流程。"""
    try:
        cur.execute('DELETE FROM c1_compute_graph_layout'
                    ' WHERE scope=%s AND def_id=%s', (scope, def_id))
    except Exception as exc:
        if not _missing_table(exc):
            raise

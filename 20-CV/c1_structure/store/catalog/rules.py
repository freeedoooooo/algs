"""目录库 · 单行抽取规则（c1_extract_rule）。

规则没有版本表。get_rule 返回可直接复制到 c1_extract_result 的完整规则
快照；历史结果只读取自己的 rule_snapshot_json，不随规则编辑变化。
"""
import json

from .. import db
from ..errors import BadRequest, Conflict, NotFound
from ._common import _j, _rows

_COLS = ('id, name, description, output_schema_json, extraction_spec_json,'
         ' reference_doc_ids_json, validation_report_json, created_at, updated_at')
_JSON_COLS = ('output_schema_json', 'extraction_spec_json',
              'reference_doc_ids_json', 'validation_report_json')


def _decode(row):
    if row:
        for key in _JSON_COLS:
            row[key] = _j(row.get(key))
    return row


def _exists(cur, rule_id):
    cur.execute('SELECT id FROM c1_extract_rule WHERE id=%s', (rule_id,))
    if not cur.fetchone():
        raise NotFound('抽取规则不存在')


def _json_object(value, label):
    if value is not None and not isinstance(value, dict):
        raise BadRequest('{}须为 JSON 对象'.format(label))
    return json.dumps(value or {}, ensure_ascii=False)


def list_rules():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + _COLS +
                        ' FROM c1_extract_rule ORDER BY id')
            return [_decode(row) for row in _rows(cur)]
    finally:
        conn.close()


def get_rule(rule_id=None, name=None):
    """完整规则快照；rule_id 优先，可按唯一名称查询。不存在返回 None。"""
    if rule_id is None and not name:
        raise BadRequest('请指定 rule_id 或规则名')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if rule_id is not None:
                cur.execute('SELECT ' + _COLS +
                            ' FROM c1_extract_rule WHERE id=%s', (rule_id,))
            else:
                cur.execute('SELECT ' + _COLS +
                            ' FROM c1_extract_rule WHERE name=%s', (name,))
            rows = _rows(cur)
        return _decode(rows[0]) if rows else None
    finally:
        conn.close()


def create_rule(name, description=None, output_schema_json=None,
                extraction_spec_json=None, reference_doc_ids_json=None,
                validation_report_json=None):
    """创建一条完整规则，返回 rule_id（不是版本 ID）。"""
    name = str(name or '').strip()
    if not name:
        raise BadRequest('规则名不能为空')
    schema = _json_object(output_schema_json, '输出字段契约')
    spec = _json_object(extraction_spec_json, '抽取规则定义')
    refs = reference_doc_ids_json
    if refs is not None and not isinstance(refs, (list, tuple)):
        raise BadRequest('参考文档 ID 须为数组')
    report = _json_object(validation_report_json, '校验报告')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_extract_rule WHERE name=%s', (name,))
            if cur.fetchone():
                raise Conflict('规则名已存在')
            cur.execute(
                'INSERT INTO c1_extract_rule (name, description,'
                ' output_schema_json, extraction_spec_json,'
                ' reference_doc_ids_json, validation_report_json)'
                ' VALUES (%s,%s,%s,%s,%s,%s)',
                (name, description, schema, spec,
                 json.dumps(list(refs or []), ensure_ascii=False), report))
            rule_id = cur.lastrowid
            conn.commit()
            return rule_id
    finally:
        conn.close()


def update_rule(rule_id, name=None, description=None,
                output_schema_json=None, extraction_spec_json=None,
                reference_doc_ids_json=None, validation_report_json=None):
    """原地更新规则；已生成结果继续使用各自快照。"""
    updates, args = [], []
    if name is not None:
        name = str(name).strip()
        if not name:
            raise BadRequest('规则名不能为空')
        updates.append('name=%s')
        args.append(name)
    if description is not None:
        updates.append('description=%s')
        args.append(description)
    for key, value, label in (
            ('output_schema_json', output_schema_json, '输出字段契约'),
            ('extraction_spec_json', extraction_spec_json, '抽取规则定义'),
            ('validation_report_json', validation_report_json, '校验报告')):
        if value is not None:
            updates.append(key + '=%s')
            args.append(_json_object(value, label))
    if reference_doc_ids_json is not None:
        if not isinstance(reference_doc_ids_json, (list, tuple)):
            raise BadRequest('参考文档 ID 须为数组')
        updates.append('reference_doc_ids_json=%s')
        args.append(json.dumps(list(reference_doc_ids_json), ensure_ascii=False))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _exists(cur, rule_id)
            if name is not None:
                cur.execute('SELECT id FROM c1_extract_rule'
                            ' WHERE name=%s AND id<>%s', (name, rule_id))
                if cur.fetchone():
                    raise Conflict('规则名已存在')
            if updates:
                args.append(rule_id)
                cur.execute('UPDATE c1_extract_rule SET ' +
                            ', '.join(updates) + ' WHERE id=%s', args)
            conn.commit()
    finally:
        conn.close()


def delete_rule(rule_id):
    """被任一抽取结果引用时禁删；规则编辑不会改写历史快照。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _exists(cur, rule_id)
            cur.execute('SELECT COUNT(*) FROM c1_extract_result'
                        ' WHERE rule_id=%s', (rule_id,))
            if cur.fetchone()[0]:
                raise Conflict('该抽取规则已被资料结果引用，禁止删除')
            cur.execute('DELETE FROM c1_extract_rule WHERE id=%s', (rule_id,))
            conn.commit()
    finally:
        conn.close()

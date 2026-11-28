"""catalog 域共享小工具：行投影、JSON 列反序列化与规则快照投影。"""
import json


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _j(v):
    if isinstance(v, (str, bytes)):
        return json.loads(v)
    return v


def rule_snapshot_parts(snapshot):
    """兼容快照使用列名或嵌套键；返回输出契约、抽取定义、展示元数据。"""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    schema = snapshot.get('output_schema_json')
    if schema is None:
        schema = snapshot.get('output_schema')
    spec = snapshot.get('extraction_spec_json')
    if spec is None:
        spec = snapshot.get('extraction_spec')
    return schema if isinstance(schema, dict) else {}, \
        spec if isinstance(spec, dict) else {}, snapshot


def snapshot_field_names(snapshot):
    """规则快照中的中文字段契约；无固定契约时由调用方回退到实际记录。"""
    schema, spec, _ = rule_snapshot_parts(snapshot)
    names = []
    for field in schema.get('fields') or []:
        if isinstance(field, dict) and field.get('name'):
            names.append(str(field['name']))
    if not names:
        for field in spec.get('fields') or []:
            if isinstance(field, dict) and field.get('target'):
                names.append(str(field['target']))
    return list(dict.fromkeys(names))

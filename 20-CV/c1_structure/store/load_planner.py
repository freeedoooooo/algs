"""入库规划：中文字段 → 现有表推荐 / 目标表字段映射（无写库副作用）。"""
import hashlib
import json

from . import catalog, content, loader, semantic_load

INTENT_JSON = 'auto-intent.json'
LOAD_PLAN_JSON = 'auto-load-plan.json'


def normalize_intent(intent):
    """兼容扁平与文档中的 load 嵌套意图，统一内部契约。"""
    out = dict(intent) if isinstance(intent, dict) else {}
    load = out.get('load') if isinstance(out.get('load'), dict) else {}
    if not out.get('description') and not out.get('prompt'):
        out['description'] = out.get('natural_language') or ''
    for key in ('table', 'datasource_id', 'field_map', 'write_mode',
                'business_key'):
        if out.get(key) in (None, '') and load.get(key) not in (None, ''):
            out[key] = load[key]
    if out.get('table') and not out.get('target_table'):
        out['target_table'] = out['table']
    return out


def _target_name(value):
    return str(value or '').strip().split('.')[-1]


def build_plan(record_set, intent, table_schemas, *, warnings=None):
    """纯函数规划；table_schemas 由调用方从现有数据源读取。"""
    intent = normalize_intent(intent)
    warnings = list(warnings or [])
    profile = semantic_load.record_profile(record_set)
    if not profile['record_count'] or not profile['fields']:
        return {'status': 'no_records', 'message': '没有可入库的抽取记录',
                'target': None, 'mapping': None,
                'recommendations': [], 'warnings': warnings}

    schemas = list(table_schemas or [])
    target_table = _target_name(intent.get('target_table') or intent.get('table'))
    datasource_id = intent.get('datasource_id')
    try:
        datasource_id = int(datasource_id) if datasource_id not in (None, '') else None
    except (TypeError, ValueError):
        datasource_id = None
        warnings.append('datasource_id 不是整数，已按未指定数据源处理')

    matches = [s for s in schemas
               if target_table and str(s.get('name') or '').casefold()
               == target_table.casefold()
               and (datasource_id is None
                    or s.get('datasource_id') == datasource_id)]
    explicit = intent.get('field_map') or intent.get('field_aliases') or {}
    explicit = {str(k): str(v) for k, v in explicit.items()} \
        if isinstance(explicit, dict) else {}
    description = str(intent.get('description') or intent.get('prompt') or '')

    if not target_table:
        recommendations = semantic_load.recommend_tables(
            record_set, schemas, intent=description)
        return {'status': 'waiting_target',
                'message': '未指定目标表，已推荐现有表，等待用户选择',
                'target': None, 'mapping': None,
                'recommendations': recommendations, 'warnings': warnings}

    if not matches:
        recommendations = semantic_load.recommend_tables(
            record_set, schemas, intent=description)
        return {'status': 'target_missing',
                'message': '指定目标表不存在，未自动入库',
                'target': {'datasource_id': datasource_id,
                           'table': target_table},
                'mapping': None, 'recommendations': recommendations,
                'warnings': warnings}

    if len(matches) > 1:
        return {'status': 'target_ambiguous',
                'message': '多个数据源存在同名目标表，请指定 datasource_id',
                'target': {'datasource_id': datasource_id,
                           'table': target_table},
                'mapping': None,
                'recommendations': [
                    {'table': s.get('name'),
                     'datasource_id': s.get('datasource_id'),
                     'score': 1.0, 'matched_fields': [],
                     'missing_fields': [], 'ambiguous_fields': {},
                     'suggested_mapping': {}, 'reasons': ['同名目标表']}
                    for s in matches],
                'warnings': warnings}

    schema = matches[0]
    mapping = semantic_load.map_fields(record_set, schema, explicit=explicit)
    valid_columns = {str(c.get('name')) for c in schema.get('columns') or []}
    field_names = {f['name'] for f in profile['fields']}
    invalid_explicit = {
        name: column for name, column in explicit.items()
        if name not in field_names or column not in valid_columns}
    explicit_targets = list(explicit.values())
    duplicated = {column for column in explicit_targets
                  if explicit_targets.count(column) > 1}
    invalid_explicit.update({name: column for name, column in explicit.items()
                             if column in duplicated})
    if invalid_explicit:
        mapping['complete'] = False
        mapping['invalid_explicit'] = invalid_explicit
    target = {'datasource_id': schema.get('datasource_id'),
              'table': schema.get('name')}
    if not mapping['complete']:
        return {'status': 'mapping_incomplete',
                'message': '中文字段未能完整映射到目标列，未自动入库',
                'target': target, 'mapping': mapping,
                'recommendations': [], 'warnings': warnings}
    return {'status': 'ready', 'message': '目标表与字段映射已就绪',
            'target': target, 'mapping': mapping,
            'recommendations': [], 'warnings': warnings}


def plan_for_file(file_id, intent):
    """读取 records 与现有业务库表结构，生成并保存入库规划。"""
    record_set = content.get_records(file_id)
    intent = normalize_intent(intent)
    datasources = catalog.list_datasources()
    warnings, schemas = [], []
    requested_ds = (intent or {}).get('datasource_id') \
        if isinstance(intent, dict) else None
    for ds in datasources:
        if requested_ds not in (None, '') and str(ds['id']) != str(requested_ds):
            continue
        try:
            schemas.extend(loader.list_table_schemas(ds))
        except Exception:
            if requested_ds not in (None, ''):
                raise
            warnings.append('数据源 {} 暂不可用，已跳过'.format(ds.get('name')
                                                       or ds.get('id')))
    plan = build_plan(record_set, intent or {}, schemas, warnings=warnings)
    save_plan(file_id, plan)
    return plan


def save_intent(file_id, intent):
    from . import artifact
    return artifact.save_json(file_id, INTENT_JSON, intent or {})


def get_intent(file_id):
    from . import artifact
    return artifact.get_json(file_id, INTENT_JSON) or {}


def save_plan(file_id, plan):
    from . import artifact
    return artifact.save_json(file_id, LOAD_PLAN_JSON, plan)


def get_plan(file_id):
    from . import artifact
    return artifact.get_json(file_id, LOAD_PLAN_JSON)


def snapshot_from_mapping(mapping):
    fields = [{'name': f['name'], 'type': f.get('type') or 'text'}
              for f in (mapping or {}).get('fields') or []]
    digest = hashlib.sha256(json.dumps(
        fields, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:16]
    return {'schema_version': 1, 'fields': fields, 'hash': digest}

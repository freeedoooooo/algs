"""入库规划：中文字段 → 现有表推荐 / 目标表字段映射（无写库副作用）。"""
import hashlib
import json
import logging

from . import catalog, content_db, loader, semantic_load

logger = logging.getLogger(__name__)

INTENT_JSON = 'auto-intent.json'


def normalize_intent(intent):
    """兼容扁平与文档中的 load 嵌套意图，统一内部契约。"""
    out = dict(intent) if isinstance(intent, dict) else {}
    load = out.get('load') if isinstance(out.get('load'), dict) else {}
    if not out.get('description') and not out.get('prompt'):
        out['description'] = out.get('natural_language') or ''
    for key in ('table', 'datasource_id', 'datasource_code', 'table_code',
                'field_map', 'write_mode', 'business_key', 'business_keys'):
        if out.get(key) in (None, '') and load.get(key) not in (None, ''):
            out[key] = load[key]
    if out.get('table_code') and not out.get('target_table'):
        ds_code, sep, table_name = str(out['table_code']).rpartition('.')
        if sep:
            out.setdefault('datasource_code', ds_code)
            out['target_table'] = table_name
    if out.get('table') and not out.get('target_table'):
        out['target_table'] = out['table']
    return out


def _target_name(value):
    return str(value or '').strip().split('.')[-1]


def _build_plan(record_set, intent, table_schemas, *, warnings=None):
    """纯函数规划；table_schemas 由调用方从现有数据源读取。"""
    intent = normalize_intent(intent)
    warnings = list(warnings or [])
    profile = semantic_load.record_profile(record_set)
    if not profile['record_count'] or not profile['fields']:
        return {'status': 'no_records', 'message': '没有可入库的抽取记录',
                'target': None, 'mapping': None,
                'recommendations': [], 'warnings': warnings}

    schemas = [s for s in (table_schemas or [])
               if loader.is_business_table((s or {}).get('name'))]
    target_table = _target_name(intent.get('target_table') or intent.get('table'))
    datasource_code = str(intent.get('datasource_code') or '').strip() or None
    datasource_id = intent.get('datasource_id')
    try:
        datasource_id = int(datasource_id) if datasource_id not in (None, '') else None
    except (TypeError, ValueError):
        datasource_id = None
        warnings.append('datasource_id 不是整数，已按未指定数据源处理')
    requested_table_code = str(intent.get('table_code') or '').strip() or None

    matches = [s for s in schemas
               if (requested_table_code and s.get('table_code') == requested_table_code)
               or (target_table and str(s.get('name') or '').casefold()
                   == target_table.casefold()
                   and (datasource_code is None
                        or str(s.get('datasource_code') or '').casefold()
                        == datasource_code.casefold())
                   and (datasource_code is not None or datasource_id is None
                        or s.get('datasource_id') == datasource_id))]
    explicit_value = intent.get('field_map')
    if not isinstance(explicit_value, dict):
        explicit_value = intent.get('field_aliases')
    explicit_provided = isinstance(explicit_value, dict)
    explicit = {str(k).strip(): str(v).strip()
                for k, v in (explicit_value or {}).items()
                if str(k).strip() and str(v or '').strip()} \
        if explicit_provided else {}
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
                           'datasource_code': datasource_code,
                           'table': target_table,
                           'table_code': requested_table_code},
                'mapping': None, 'recommendations': recommendations,
                'warnings': warnings}

    if len(matches) > 1:
        return {'status': 'target_ambiguous',
                'message': '多个数据源存在同名目标表，请指定 datasource_code 或 table_code',
                'target': {'datasource_id': datasource_id,
                           'datasource_code': datasource_code,
                           'table': target_table,
                           'table_code': requested_table_code},
                'mapping': None,
                'recommendations': [
                    {'table': s.get('name'),
                     'datasource_id': s.get('datasource_id'),
                     'datasource_code': s.get('datasource_code'),
                     'table_code': s.get('table_code'),
                     'score': 1.0, 'matched_fields': [],
                     'missing_fields': [], 'ambiguous_fields': {},
                     'suggested_mapping': {}, 'reasons': ['同名目标表']}
                    for s in matches],
                'warnings': warnings}

    schema = matches[0]
    mapping = semantic_load.map_fields(
        record_set, schema, explicit=explicit, auto_map=not explicit_provided)
    valid_columns = {str(c.get('name')) for c in mapping['available_columns']}
    field_names = {f['name'] for f in profile['fields']}
    invalid_explicit = {
        name: column for name, column in explicit.items()
        if name not in field_names or column not in valid_columns}
    explicit_targets = list(explicit.values())
    duplicated = {column for column in explicit_targets
                  if explicit_targets.count(column) > 1}
    invalid_explicit.update({name: column for name, column in explicit.items()
                             if column in duplicated})
    write_mode = str(intent.get('write_mode') or mapping.get('write_mode') or 'insert')
    business_keys = intent.get('business_keys')
    if business_keys is None:
        business_keys = intent.get('business_key')
    if business_keys is None:
        business_keys = mapping.get('business_key') or []
    if isinstance(business_keys, str):
        business_keys = [business_keys]
    mapping['write_mode'] = write_mode
    mapping['business_key'] = list(business_keys or [])
    config_error = ''
    if write_mode not in ('insert', 'upsert', 'update'):
        config_error = '非法写入方式：{}'.format(write_mode)
    elif write_mode in ('upsert', 'update') and not mapping['business_key']:
        config_error = '{} 方式须选择业务键'.format(write_mode)
    elif set(mapping['business_key']) - set(mapping['field_map'].values()):
        config_error = '业务键必须出现在字段映射的目标列中'
    if invalid_explicit:
        mapping['complete'] = False
        mapping['invalid_explicit'] = invalid_explicit
    elif config_error:
        mapping['complete'] = False
        mapping['config_error'] = config_error
    else:
        mapping['complete'] = bool(mapping['field_map'])
    target = {'datasource_id': schema.get('datasource_id'),
              'datasource_code': schema.get('datasource_code'),
              'table': schema.get('name'),
              'table_code': schema.get('table_code')}
    if not mapping['complete']:
        message = ('存在无效或重复的字段映射，请检查数据库列' if invalid_explicit
                   else config_error or
                   '请至少为一个中文字段选择数据库列；留空字段不入库')
        return {'status': 'mapping_incomplete',
                'message': message,
                'target': target, 'mapping': mapping,
                'recommendations': [], 'warnings': warnings}
    return {'status': 'ready',
            'message': '目标表与字段映射已就绪；留空字段不会入库',
            'target': target, 'mapping': mapping,
            'recommendations': [], 'warnings': warnings}


def build_plan(record_set, intent, table_schemas, *, warnings=None):
    """结果维度规划入口：可传 records 信封或 extract_result_id。"""
    if not isinstance(record_set, dict):
        record_set = content_db.get_records(record_set)
        if record_set is None:
            from .errors import NotFound
            raise NotFound('抽取结果不存在')
    plan = _build_plan(record_set, intent, table_schemas, warnings=warnings)
    plan['extract_result_id'] = (record_set or {}).get('extract_result_id')
    plan['doc_id'] = (record_set or {}).get('doc_id')
    return plan


def plan_for_extract_result(extract_result_id, datasource_id=None,
                            table_intent=None, datasource_code=None):
    """读取单结果记录与现有业务库结构，生成并保存该结果的入库规划。"""
    logger.info('开始表推荐与字段映射：extract_result_id=%s', extract_result_id)
    record_set = content_db.get_records(extract_result_id)
    if record_set is None:
        from .errors import NotFound
        raise NotFound('抽取结果不存在')
    if isinstance(table_intent, dict):
        intent = normalize_intent(table_intent)
    else:
        intent = normalize_intent({
            'description': str(table_intent or ''),
            'target_table': str(table_intent or '') or None,
        })
    if datasource_id is not None:
        intent['datasource_id'] = datasource_id
    if datasource_code not in (None, ''):
        intent['datasource_code'] = datasource_code
    binding = catalog.get_binding(extract_result_id=extract_result_id)
    if binding and not intent.get('target_table') and not intent.get('table_code'):
        intent.update({
            'target_table': binding['target_table'],
            'table_code': binding['table_code'],
            'datasource_code': binding['datasource_code'],
            'field_map': binding['field_map_json'],
            'write_mode': binding['write_mode'],
            'business_keys': binding['business_keys_json'],
        })
    warnings, schemas = [], []
    requested_ds_code = str(intent.get('datasource_code') or '').strip() or None
    requested_ds_id = intent.get('datasource_id')
    for ds in catalog.list_datasources():
        if requested_ds_code is not None and str(ds.get('code') or '').casefold() \
                != requested_ds_code.casefold():
            continue
        if requested_ds_code is None and requested_ds_id not in (None, '') \
                and str(ds['id']) != str(requested_ds_id):
            continue
        try:
            schemas.extend(loader.list_table_schemas(ds))
        except Exception as exc:
            if requested_ds_code is not None or requested_ds_id not in (None, ''):
                raise
            warnings.append('数据源 {} 暂不可用，已跳过'.format(
                ds.get('name') or ds.get('code') or ds.get('id')))
            logger.warning('业务表结构读取失败：datasource_code=%s error=%s',
                           ds.get('code') or ds.get('id'), type(exc).__name__)
    plan = build_plan(extract_result_id, intent, schemas, warnings=warnings)
    save_plan(extract_result_id, plan)
    logger.info('入库规划完成：extract_result_id=%s status=%s',
                extract_result_id, plan.get('status'))
    return plan


def save_intent(file_id, intent):
    from . import artifact
    return artifact.save_json(file_id, INTENT_JSON, intent or {})


def get_intent(file_id):
    from . import artifact
    return artifact.get_json(file_id, INTENT_JSON) or {}


def _plan_artifact_name(extract_result_id):
    record_set = content_db.get_records(extract_result_id)
    if record_set is None:
        from .errors import NotFound
        raise NotFound('抽取结果不存在')
    return record_set['doc_id'], 'load-plans/{}.json'.format(extract_result_id)


def save_plan(extract_result_id, plan):
    from . import artifact
    doc_id, name = _plan_artifact_name(extract_result_id)
    return artifact.save_json(doc_id, name, plan)


def get_plan(extract_result_id):
    from . import artifact
    _doc_id, name = _plan_artifact_name(extract_result_id)
    return artifact.get_json(_doc_id, name)


def snapshot_from_mapping(mapping):
    field_map = (mapping or {}).get('field_map') or {}
    fields = [{'name': f['name'], 'type': f.get('type') or 'text'}
              for f in (mapping or {}).get('fields') or []
              if f['name'] in field_map]
    digest = hashlib.sha256(json.dumps(
        fields, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:16]
    return {'schema_version': 1, 'fields': fields, 'hash': digest}

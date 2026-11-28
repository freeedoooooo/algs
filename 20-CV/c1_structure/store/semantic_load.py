"""中文字段到现有目标表的推荐与映射（纯函数，无 DB / LLM I/O）。"""
import re
import unicodedata
from datetime import datetime


_ALIAS_GROUPS = (
    (('编号', '代码', '编码', 'id', 'code', 'no', 'number'), 1.0),
    (('日期', 'date'), 1.0),
    (('时间', '时刻', 'time'), 0.9),
    (('名称', 'name', 'title'), 1.0),
    (('描述', '说明', '内容', 'desc', 'description', 'remark', 'note'), 0.9),
    (('类型', '类别', 'type', 'category'), 0.9),
    (('状态', 'status', 'state'), 0.9),
    (('数量', 'qty', 'quantity', 'count'), 0.9),
    (('金额', '单价', '价格', '费用', 'amount', 'price', 'fee'), 0.9),
    (('单位', 'unit'), 0.8),
    (('设备', 'equipment', 'device', 'asset'), 1.0),
    (('巡检', '巡查', '点检', 'inspection', 'patrol'), 1.0),
    (('维修', '检修', 'repair', 'maintenance'), 1.0),
    (('异常', '故障', '缺陷', '问题', 'abnormal', 'fault', 'defect', 'issue'), 1.0),
    (('处理', '处置', '整改', 'handle', 'action'), 0.9),
    (('结论', '结果', '结论', 'result', 'conclusion'), 0.9),
    (('人员', '员工', '操作员', 'user', 'operator', 'staff'), 0.9),
    (('部门', '车间', '班组', 'department', 'team'), 0.9),
    (('位置', '地点', 'location', 'place', 'position'), 0.9),
    (('厂家', '厂商', '供应商', 'vendor', 'supplier', 'manufacturer'), 0.9),
    (('型号', '规格', 'model', 'specification', 'spec'), 0.9),
    (('图片', '照片', '附件', 'image', 'photo', 'attachment'), 0.8),
    (('备注', '注释', 'comment'), 0.7),
)

_TYPE_ALIASES = {
    'text': {'text', 'varchar', 'char', 'tinytext', 'mediumtext', 'longtext'},
    'integer': {'tinyint', 'smallint', 'mediumint', 'int', 'integer', 'bigint', 'bit'},
    'decimal': {'decimal', 'numeric', 'float', 'double', 'real'},
    'date': {'date'},
    'datetime': {'datetime', 'timestamp'},
    'boolean': {'bool', 'boolean'},
}


def normalize_text(value):
    text = unicodedata.normalize('NFKC', str(value or '')).lower()
    return re.sub(r'[\s_\-()（）\[\]【】:：/\\.,，。]+', '', text)


def _terms(value):
    raw = unicodedata.normalize('NFKC', str(value or '')).lower()
    compact = normalize_text(raw)
    terms = {compact} if compact else set()
    terms.update(re.findall(r'[a-z][a-z0-9]*', raw))
    for aliases, _weight in _ALIAS_GROUPS:
        if any(normalize_text(alias) in compact for alias in aliases):
            terms.update(normalize_text(alias) for alias in aliases)
    return {term for term in terms if term}


def _mentions_table(intent, table_name):
    raw_name = str(table_name or '').strip()
    if not raw_name:
        return False
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', raw_name):
        return bool(re.search(r'(?<![A-Za-z0-9_])' + re.escape(raw_name)
                              + r'(?![A-Za-z0-9_])', str(intent or ''),
                              flags=re.IGNORECASE))
    return normalize_text(raw_name) in normalize_text(intent)


def _concepts(value):
    compact = normalize_text(value)
    return {i for i, (aliases, _weight) in enumerate(_ALIAS_GROUPS)
            if any(normalize_text(alias) in compact for alias in aliases)}


def _name_score(source, target):
    left, right = normalize_text(source), normalize_text(target)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    score = 0.0
    if left in right or right in left:
        score = max(score, 0.86 if min(len(left), len(right)) >= 2 else 0.55)
    lt, rt = _terms(source), _terms(target)
    if lt and rt:
        overlap = len(lt & rt)
        if overlap:
            score = max(score, 0.55 + 0.35 * overlap / max(1, len(lt | rt)))
    lc, rc = _concepts(source), _concepts(target)
    if lc and rc:
        overlap = len(lc & rc)
        if overlap:
            weighted = sum(_ALIAS_GROUPS[i][1] for i in lc & rc)
            total = sum(_ALIAS_GROUPS[i][1] for i in lc | rc)
            score = max(score, 0.45 + 0.45 * weighted / max(total, 0.01))
    return round(min(score, 0.99), 4)


def infer_value_type(values):
    seen = False
    kinds = set()
    for value in values:
        if value is None or str(value).strip() == '':
            continue
        seen = True
        text = str(value).strip()
        if re.fullmatch(r'[+-]?\d+', text):
            kinds.add('integer')
            continue
        if re.fullmatch(r'[+-]?(?:\d+\.\d*|\d*\.\d+)', text):
            kinds.add('decimal')
            continue
        try:
            datetime.fromisoformat(text.replace('Z', '+00:00'))
            kinds.add('datetime' if 'T' in text or ' ' in text else 'date')
            continue
        except ValueError:
            pass
        if text.lower() in {'true', 'false', '是', '否', 'y', 'n'}:
            kinds.add('boolean')
            continue
        kinds.add('text')
    if not seen:
        return 'text'
    if kinds <= {'integer'}:
        return 'integer'
    if kinds <= {'integer', 'decimal'}:
        return 'decimal'
    if kinds <= {'date'}:
        return 'date'
    if kinds <= {'datetime'}:
        return 'datetime'
    if kinds <= {'boolean'}:
        return 'boolean'
    return 'text'


def _type_compatible(value_type, column_type):
    allowed = _TYPE_ALIASES.get(value_type, {'text'})
    actual = str(column_type or '').lower()
    if actual in allowed:
        return 1.0
    if value_type == 'integer' and actual in _TYPE_ALIASES['decimal']:
        return 0.9
    if value_type in {'date', 'datetime'} and actual in {'varchar', 'char', 'text'}:
        return 0.55
    if value_type == 'text' and actual in _TYPE_ALIASES['date'] | _TYPE_ALIASES['datetime']:
        return 0.35
    return 0.2


def record_profile(record_set):
    files = (record_set or {}).get('files') or []
    records = [r for f in files for r in (f.get('records') or [])]
    names = []
    samples = {}
    for record in records:
        for name, value in (record.get('values') or {}).items():
            if name not in samples:
                names.append(name)
                samples[name] = []
            if len(samples[name]) < 20:
                samples[name].append(value)
    return {
        'fields': [
            {'name': name, 'type': infer_value_type(samples.get(name) or []),
             'samples': samples.get(name) or []}
            for name in names
        ],
        'record_count': len(records),
    }


def _column_score(field, column):
    names = [column.get('name')]
    if column.get('comment'):
        names.append(str(column['comment']))
    name_score = max(_name_score(field['name'], name) for name in names)
    type_score = _type_compatible(field.get('type') or 'text',
                                  column.get('type') or column.get('data_type'))
    return round(0.88 * name_score + 0.12 * type_score, 4)


_RESERVED_COLUMNS = {'file_id', 'record_id'}


def map_fields(record_set, table_schema, *, explicit=None, auto_map=True):
    """返回字段映射草稿；auto_map=False 时只使用显式映射。"""
    explicit = explicit or {}
    profile = record_profile(record_set)
    columns = [column for column in table_schema.get('columns') or []
               if str(column.get('name') or '').casefold() not in _RESERVED_COLUMNS]
    pairs = []
    for field in profile['fields']:
        for column in columns:
            pairs.append((_column_score(field, column), field['name'],
                          column['name']))
    pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_columns = set()
    chosen = {}
    for score, field, column in pairs:
        if not auto_map or field in chosen or field in explicit or column in used_columns:
            continue
        if score < 0.72:
            continue
        chosen[field] = {'target_column': column, 'confidence': score}
        used_columns.add(column)

    ambiguous = {}
    for field in profile['fields']:
        if field['name'] in chosen or field['name'] in explicit:
            continue
        ranked = sorted(
            [{'target_column': column, 'confidence': score}
             for score, name, column in pairs if name == field['name']],
            key=lambda item: -item['confidence'])[:3]
        if ranked and ranked[0]['confidence'] >= 0.45:
            ambiguous[field['name']] = ranked
        chosen.pop(field['name'], None)

    field_map = {name: str(column) for name, column in explicit.items()}
    confidence = {name: 1.0 for name in explicit}
    for name, item in chosen.items():
        field_map[name] = item['target_column']
        confidence[name] = item['confidence']
    mapped_names = set(field_map)
    unmapped = [f['name'] for f in profile['fields'] if f['name'] not in mapped_names]

    mapped_columns = set(field_map.values())
    key_candidates = []
    for index in table_schema.get('indexes') or []:
        cols = [str(c) for c in (index.get('columns') or []) if c]
        if index.get('unique') and cols and set(cols) <= mapped_columns:
            key_candidates.append(cols)
    if not key_candidates:
        primary = [str(c.get('name')) for c in columns if c.get('primary')]
        if primary and set(primary) <= mapped_columns:
            key_candidates.append(primary)
        else:
            single = [str(c.get('name')) for c in columns
                      if c.get('unique') and str(c.get('name')) in mapped_columns]
            if len(single) == 1:
                key_candidates.append(single)
    key_candidates.sort(key=lambda cols: (len(cols), cols))
    business_key = key_candidates[0] if key_candidates else []
    return {
        'target_table': table_schema.get('name'),
        'field_map': field_map,
        'confidence': confidence,
        'unmapped_fields': unmapped,
        'ambiguous_fields': ambiguous,
        'available_columns': [dict(column) for column in columns],
        'business_key': business_key,
        'write_mode': 'upsert' if business_key else 'insert',
        'complete': not unmapped and not ambiguous,
        'fields': profile['fields'],
        'record_count': profile['record_count'],
    }


def recommend_tables(record_set, table_schemas, *, intent='', limit=5,
                     min_score=0.2):
    profile = record_profile(record_set)
    field_names = [f['name'] for f in profile['fields']]
    if not field_names:
        return []
    intent_terms = _terms(intent)
    results = []
    for table in table_schemas or []:
        mapping = map_fields(record_set, table)
        mapped = [name for name in field_names if name in mapping['field_map']]
        if not mapped:
            continue
        coverage = len(mapped) / len(field_names)
        confidences = [mapping['confidence'][name] for name in mapped]
        avg_conf = sum(confidences) / len(confidences)
        table_text = '{} {}'.format(table.get('name') or '',
                                    table.get('comment') or '')
        table_terms = _terms(table_text)
        intent_score = (len(intent_terms & table_terms) / len(intent_terms)
                        if intent_terms else 0.0)
        ambiguous_penalty = len(mapping['ambiguous_fields']) / len(field_names)
        base_score = (0.50 * coverage + 0.30 * avg_conf + 0.15 * intent_score
                      - 0.05 * ambiguous_penalty)
        explicit_match = _mentions_table(intent, table.get('name'))
        complete = not mapping['unmapped_fields'] and not mapping['ambiguous_fields']
        score = base_score + (0.12 if explicit_match else 0.0) \
            + (0.04 if complete else 0.0)
        score = round(max(0.0, min(1.0, score)), 4)
        if score < min_score:
            continue
        results.append({
            'table': table.get('name'),
            'datasource_id': table.get('datasource_id'),
            'score': score,
            'matched_fields': mapped,
            'missing_fields': mapping['unmapped_fields'],
            'ambiguous_fields': mapping['ambiguous_fields'],
            'suggested_mapping': mapping['field_map'],
            'reasons': _recommendation_reasons(
                coverage, avg_conf, intent_score, explicit_match, complete),
        })
    results.sort(key=lambda item: (-item['score'], str(item['table'])))
    return results[:limit]


def _recommendation_reasons(coverage, confidence, intent_score,
                           explicit_match=False, complete=False):
    reasons = []
    if explicit_match:
        reasons.append('需求中明确提到目标表名')
    if complete:
        reasons.append('字段可完整映射')
    if coverage >= 0.8:
        reasons.append('中文字段覆盖率高')
    elif coverage >= 0.5:
        reasons.append('部分中文字段匹配')
    if confidence >= 0.8:
        reasons.append('列名或列注释匹配明确')
    if intent_score > 0:
        reasons.append('表名或表注释与业务描述相关')
    return reasons or ['存在可用字段匹配']

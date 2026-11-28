"""单行抽取规则的确定性复用筛选（只读文档，不访问数据库）。

候选规则依次通过语义相似度、输出字段集合、表选择器/表头和当前文档干跑
门禁；任一干跑不达标就继续尝试其他候选，而不是复用失败规则。
"""
import json
import re

from .. import collect
from . import validate

MIN_SIMILARITY = 0.86
MIN_ANCHOR_COVERAGE = 0.95


def _normalize(value):
    return re.sub(r'\s+', '', str(value or '')).casefold()


def _terms(value):
    text = _normalize(value)
    terms = set(re.findall(r'[a-z0-9_]+', text))
    for run in re.findall(r'[\u4e00-\u9fff]+', text):
        if len(run) == 1:
            terms.add(run)
        else:
            terms.update(run[i:i + 2] for i in range(len(run) - 1))
    return terms


def similarity(description, rule):
    """描述完全一致返回 1；其余按词项 F1，避免短描述被偶然包含误判。"""
    left, right = _normalize(description), _normalize(rule)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    a, b = _terms(left), _terms(right)
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / float(len(a) + len(b))


def _json_object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    return value if isinstance(value, dict) else None


def _field_names(fields, key):
    if not isinstance(fields, list) or not fields:
        return None
    names = []
    for field in fields:
        if not isinstance(field, dict):
            return None
        name = str(field.get(key) or '').strip()
        if not name:
            return None
        names.append(name)
    if len(set(names)) != len(names):
        return None
    return set(names)


def _requested_fields(output_fields):
    if isinstance(output_fields, str):
        output_fields = [output_fields]
    try:
        values = list(output_fields)
    except TypeError:
        raise ValueError('output_fields 须为逻辑字段名集合')
    names = set()
    for value in values:
        if isinstance(value, dict):
            value = value.get('name') or value.get('target')
        name = str(value or '').strip()
        if not name:
            raise ValueError('output_fields 含空逻辑字段名')
        names.add(name)
    return names


def _rule_parts(rule):
    """读取单行规则的 JSON，并核对输出契约与抽取字段集合一致。"""
    if not isinstance(rule, dict):
        return None
    schema = _json_object(rule.get('output_schema_json'))
    spec = _json_object(rule.get('extraction_spec_json'))
    if schema is None or spec is None or validate.validate_spec(spec):
        return None
    schema_names = _field_names(schema.get('fields'), 'name')
    spec_names = _field_names(spec.get('fields'), 'target')
    if not schema_names or schema_names != spec_names:
        return None
    return schema, spec, schema_names


def _headers(table):
    return [str(header or '') for header in table.get('headers') or []]


def _selected_tables(selector, candidates):
    """与抽取引擎一致的 index/header_contains/scope=all/region 选择优先级。"""
    index = selector.get('index')
    if isinstance(index, int) and not isinstance(index, bool):
        return [candidates[index]] if 0 <= index < len(candidates) else []
    keyword = selector.get('header_contains')
    if keyword:
        for candidate in candidates:
            if str(keyword) in ' '.join(_headers(candidate[0])):
                return [candidate]
        return []
    if selector.get('scope') == 'all' or selector.get('region'):
        return list(candidates)
    return []


def _column_matches(selector, table):
    if not isinstance(selector, dict):
        return False
    headers = _headers(table)
    name = selector.get('name')
    if name is not None:
        return name in headers
    index = selector.get('index')
    if isinstance(index, int) and not isinstance(index, bool):
        return 0 <= index < len(headers)
    keyword = selector.get('header_contains')
    if keyword:
        return any(str(keyword) in header for header in headers)
    pattern = selector.get('header_regex')
    if pattern:
        try:
            return any(re.search(str(pattern), header) for header in headers)
        except re.error:
            return False
    return False


def _spec_matches_doc(spec, doc):
    """显式记录来源必须存在，且所有表/列选择器都能命中当前文档结构。"""
    selectors = spec.get('tables')
    if not isinstance(selectors, list) or not selectors:
        return False
    records = spec.get('records')
    if not isinstance(records, dict):
        return False
    source_ref = records.get('source_ref')
    record_refs = [str(sel.get('ref') or 'main') for sel in selectors
                   if isinstance(sel, dict) and sel.get('role') == 'record_source']
    if not source_ref or source_ref not in record_refs:
        return False

    candidates = collect._candidate_tables(doc or {})
    by_ref = {}
    for selector in selectors:
        if not isinstance(selector, dict):
            return False
        picked = _selected_tables(selector, candidates)
        if not picked:
            return False
        # index 与表头条件同时给出时，不能只满足索引而忽略表头契约。
        if selector.get('index') is not None and selector.get('header_contains'):
            if str(selector['header_contains']) not in ' '.join(
                    _headers(picked[0][0])):
                return False
        scope = selector.get('scope')
        if scope in ('page', 'stitched') and not any(
                candidate[1] == scope for candidate in picked):
            return False
        by_ref[str(selector.get('ref') or 'main')] = picked

    for field in spec.get('fields') or []:
        for step in field.get('pipeline') or []:
            if not isinstance(step, dict) or step.get('op') not in (
                    'cell', 'sum', 'count'):
                continue
            source = step.get('source')
            tables = by_ref.get(source) if source else by_ref.get(source_ref)
            column = step.get('column')
            if not tables or (column and not any(
                    _column_matches(column, table[0]) for table in tables)):
                return False
    return True


def best_candidate(description, rules, doc=None, *, output_fields=None,
                   threshold=MIN_SIMILARITY):
    """返回通过全部门禁的单行规则候选；无候选或 doc 缺失时不复用。

    output_fields 为期望的逻辑字段名集合（字符串、{name/target} 或二者混合）。
    省略时从需求描述中提取候选库字段名，无法确定字段集合则保守拒绝。
    返回行保留原 JSON 字段，并附解析后的 output_schema/extraction_spec。
    """
    if doc is None:
        raise ValueError('规则复用需要当前文档 doc 以执行干跑')

    prepared = []
    for rule in rules or []:
        parts = _rule_parts(rule)
        if parts is not None:
            prepared.append((rule, parts))
    if not prepared:
        return None

    if output_fields is None:
        known_names = set().union(*(parts[2] for _rule, parts in prepared))
        description_text = _normalize(description)
        requested = {name for name in known_names
                     if _normalize(name) in description_text}
    else:
        requested = _requested_fields(output_fields)
    if not requested:
        return None

    ranked = []
    for rule, (schema, spec, names) in prepared:
        if names != requested or not _spec_matches_doc(spec, doc):
            continue
        score = similarity(description, rule.get('description'))
        if score >= threshold:
            ranked.append((score, str(rule.get('updated_at') or ''), rule,
                           schema, spec))
    ranked.sort(key=lambda item: (-item[0], item[1],
                                  str(item[2].get('id') or '')), reverse=True)

    for score, _updated, rule, schema, spec in ranked:
        diag = validate.dry_run(spec, doc)
        if not acceptable(diag):
            continue
        return dict(rule, reuse_score=round(score, 4),
                    output_schema=schema, extraction_spec=spec)
    return None


def acceptable(diag):
    """无标准答案时使用保守门禁：有记录、无全空字段、锚点覆盖达标。"""
    if not isinstance(diag, dict) or diag.get('error'):
        return False
    if not diag.get('records_n') or diag.get('empty_fields'):
        return False
    return (diag.get('anchor_coverage') or 0.0) >= MIN_ANCHOR_COVERAGE

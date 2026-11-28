"""生成结果的确定性校验：静态 spec 校验 + 内存干跑 + 中间层对拍。

只读、不写 DB；干跑调 collect.build_logic（纯函数），绝不调 service.run_extract
（后者 _purge 先删后插会抹掉中间层人工成果）。
"""
import json
from decimal import Decimal, InvalidOperation

from .. import collect
from ..collect_logic import build_logic
from ..collect_logic.registry import OPS
from ..collect_logic.spatial import normalize_rect

REQUIRED_TOP = ('spec_version', 'fields')


def _region_issues(region, where):
    if region is None:
        return []
    if not isinstance(region, dict):
        return ['{} 须为对象'.format(where)]
    issues = []
    try:
        normalize_rect(region.get('rect'))
    except ValueError as exc:
        issues.append('{}: {}'.format(where, exc))
    page = region.get('page')
    if page is not None and (isinstance(page, bool)
                             or not isinstance(page, int) or page < 1):
        issues.append('{}.page 须为正整数'.format(where))
    if region.get('space') not in (None, 'source', 'rectified'):
        issues.append('{}.space 仅支持 source/rectified'.format(where))
    return issues


def validate_spec(spec):
    """静态校验生成 spec：返回 issues 列表（空=合法）。"""
    issues = []
    if not isinstance(spec, dict):
        return ['spec 须为 JSON 对象']
    if spec.get('spec_version') != 2:
        issues.append('spec_version 须为 2')
    for key in REQUIRED_TOP:
        if key not in spec:
            issues.append('缺少顶层字段: {}'.format(key))
    fields = spec.get('fields')
    if not isinstance(fields, list) or not fields:
        issues.append('fields 须为非空数组')
        return issues
    for i, sel in enumerate(spec.get('tables') or []):
        if isinstance(sel, dict):
            issues.extend(_region_issues(
                sel.get('region'), 'tables[{}].region'.format(i)))
    seen = set()
    for i, f in enumerate(fields):
        if not isinstance(f, dict):
            issues.append('fields[{}] 须为对象'.format(i))
            continue
        target = str(f.get('target') or '')
        if not target:
            issues.append('fields[{}].target 不能为空'.format(i))
        elif target in seen:
            issues.append('target 重复: {}'.format(target))
        seen.add(target)
        pipeline = f.get('pipeline') or []
        if not isinstance(pipeline, list):
            issues.append('{} .pipeline 须为数组'.format(target))
            continue
        for step in pipeline:
            op = (step or {}).get('op') if isinstance(step, dict) else None
            if op not in OPS:
                issues.append('{} 未知算子: {}'.format(target, op))
            if isinstance(step, dict):
                issues.extend(_region_issues(
                    step.get('region'), '{}.pipeline.region'.format(target)))
        for v in f.get('validate') or []:
            from ..collect_logic.ops.validate import VALIDATORS
            op = (v or {}).get('op') if isinstance(v, dict) else None
            if op not in VALIDATORS:
                issues.append('{} 未知校验算子: {}'.format(target, op))
    return issues


def dry_run(spec, doc):
    """在内存里用生成规则跑 doc，返回字段命中/锚点诊断（不写库）。"""
    tpl = {'mapping_json': spec}
    try:
        recs = build_logic(doc, tpl)
    except Exception as exc:
        return {'error': '{}: {}'.format(type(exc).__name__, exc),
                'records': [], 'field_hits': {}, 'anchor_coverage': 0.0}
    fields = [str(f.get('target')) for f in spec.get('fields') or []
              if isinstance(f, dict) and f.get('target')]
    hits = {k: 0 for k in fields}
    anchored = {k: 0 for k in fields}
    for rec in recs:
        for k in fields:
            v = (rec.get('values') or {}).get(k)
            if v is not None and str(v).strip():
                hits[k] += 1
                if (rec.get('lineage') or {}).get(k):
                    anchored[k] += 1
    n = len(recs)
    coverage = (sum(anchored.values()) / float(n * len(fields))
                if n and fields else 0.0)
    return {'records': recs, 'records_n': n, 'field_hits': hits,
            'anchor_coverage': round(coverage, 4),
            'empty_fields': [k for k, c in hits.items() if c == 0]}


def _values_equal(actual, expect):
    if str(actual or '') == str(expect or ''):
        return True
    if isinstance(actual, bool) or isinstance(expect, bool):
        return False
    if not isinstance(actual, (int, float)) and not isinstance(expect, (int, float)):
        return False
    try:
        return Decimal(str(actual).strip()) == Decimal(str(expect).strip())
    except (InvalidOperation, ValueError):
        return False


def compare_targets(recs, targets):
    """与中间层 confirmed/edited 记录逐字段对拍（纯函数）。"""
    if not targets:
        return {'targets_n': 0, 'field_accuracy': None,
                'count_match': None, 'diffs': []}
    count_match = len(recs) == len(targets)
    diffs = []
    total = same = 0
    for i, target in enumerate(targets):
        got = (recs[i].get('values') if i < len(recs) else None) or {}
        for k, expect in (target.get('values') or {}).items():
            total += 1
            actual = got.get(k)
            if _values_equal(actual, expect):
                same += 1
            else:
                if len(diffs) < 20:
                    diffs.append({'index': i, 'field': k,
                                  'expected': expect, 'actual': actual})
    return {'targets_n': len(targets), 'count_match': count_match,
            'field_accuracy': round(same / float(total), 4) if total else None,
            'compared_fields': total, 'diffs': diffs}


def to_json(value):
    """诊断序列化兜底（records 含 bbox list，可直接 json）。"""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))

"""规则复用的确定性筛选：高相似需求 + 当前文档干跑达标才复用。"""
import re

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


def best_candidate(description, rules, *, threshold=MIN_SIMILARITY):
    """只返回超过阈值的当前版本候选，按分数和更新时间稳定排序。"""
    ranked = []
    for rule in rules or []:
        if not rule.get('current_version_id'):
            continue
        score = similarity(description, rule.get('description'))
        if score >= threshold:
            ranked.append((score, str(rule.get('updated_at') or ''),
                           rule))
    ranked.sort(key=lambda item: (-item[0], item[1],
                                  str(item[2].get('id') or '')), reverse=True)
    if not ranked:
        return None
    score, _updated, rule = ranked[0]
    return dict(rule, reuse_score=round(score, 4))


def acceptable(diag):
    """无标准答案时使用保守门禁：有记录、无全空字段、锚点覆盖达标。"""
    if not isinstance(diag, dict) or diag.get('error'):
        return False
    if not diag.get('records_n') or diag.get('empty_fields'):
        return False
    return (diag.get('anchor_coverage') or 0.0) >= MIN_ANCHOR_COVERAGE

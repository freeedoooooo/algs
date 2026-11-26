"""规则生成提示词 v2：自然语言驱动（用户写需求，AI 推断字段与模式）。

与 v1 共用系统层硬约束（血缘、算子白名单、JSON 契约），仅把
"目标字段从用户给定"改为"从用户提示词推断"。候选物理列名（选了参考
业务表时）作为 target 白名单注入，保证输出与入库映射对齐。
"""
from . import rule_author_v1
from ._schema import schema_text

PROMPT_VERSION = 'v2'

# 复用 v1 系统约束，只替换第 1 条（v1 要求 target 与用户字段逐字一致，
# v2 改为：从提示词推断，且必须落在候选列名集合内）。
_SYSTEM_RULES = rule_author_v1.RULES.replace(
    '1. spec_version 必须为 2；fields 的 target 必须与"目标字段"中给出的列名逐字一致，不得改名、增删。',
    '1. spec_version 必须为 2；target 字段名从"用户需求"中推断，'
    '若给出候选物理列名，则 target 必须逐字取自候选集合，不得自造。')

_EXTRA_RULES = '''
自然语言模式补充规则：
7. 从「用户需求」推断需要哪些字段（target + type + description），不要遗漏，也不要添加用户没提到的字段。
8. 自行判断记录切分策略 records.strategy：
   表格逐行数据→row；证照/表单的「标签:值」版式→key_value；按某字段分组的多行→group_by；纯文本正文→one_per_page。
9. 自行判断每个字段的首个取值算子 pipeline[0].op：
   表格列→cell；文本标签旁取值→kv；版面块→block；整页正文→page_text。
10. 参考样例值形态选择变换算子：千分位/货币→number(strip)，多余空格→trim，日期→date，固定格式→regex。
'''.strip()


def render(ctx, user_prompt, refs=None, column_candidates=None):
    """ctx=doc_to_context；user_prompt=用户需求；column_candidates=物理列名白名单。"""
    from ..context import render_context
    if not str(user_prompt or '').strip():
        raise ValueError('自然语言模式需要 user_prompt')
    cand = [str(c) for c in (column_candidates or []) if str(c or '').strip()]
    cand_text = ('候选物理列名（target 必须逐字取自这里）：\n'
                 + '、'.join(cand)) if cand else (
                     '未提供参考业务表：target 按字段语义用中文自命名。')
    ref_line = ''
    if refs:
        ref_line = '\n参考来源：{}\n'.format(
            '; '.join('{}={}'.format(k, v) for k, v in refs.items() if v))
    system = _SYSTEM_RULES.format(version=PROMPT_VERSION) + '\n\n' + _EXTRA_RULES
    return ('{}\n\n用户需求：\n{}\n{}\n{}\n\n解析上下文：\n{}\n\n'
            '返回 JSON 结构：\n{}\n').format(
                system, str(user_prompt).strip(), cand_text, ref_line,
                render_context(ctx), schema_text())

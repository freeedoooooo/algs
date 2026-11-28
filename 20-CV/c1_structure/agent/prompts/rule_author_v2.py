"""规则生成提示词 v2：自然语言驱动（用户写需求，AI 推断字段与模式）。

与 v1 共用系统层硬约束（血缘、算子白名单、JSON 契约），仅把
"目标字段从用户给定"改为"从用户提示词推断"。规则只输出中文逻辑字段，
数据库物理列映射属于后续入库绑定，不进入抽取规则。
"""
from . import rule_author_v1
from ._schema import schema_text

PROMPT_VERSION = 'v2'

# 复用 v1 系统约束，只替换第 1 条（v1 要求 target 与用户字段逐字一致，
# v2 改为：从提示词推断中文逻辑字段，不参考数据库物理列）。
_SYSTEM_RULES = rule_author_v1.RULES.replace(
    '1. spec_version 必须为 2；fields 的 target 必须与"目标字段"中给出的逻辑字段名逐字一致，不得改名、增删。',
    '1. spec_version 必须为 2；target 字段名从"用户需求"中推断，使用中文语义名，'
    '不得使用数据库物理列名。')

_EXTRA_RULES = '''
自然语言模式补充规则：
7. 从「用户需求」推断需要哪些字段（target + type + description），不要遗漏，也不要添加用户没提到的字段。
   type 使用 string/number/date/bool，并保留到输出字段契约，不得统一改成 string。
8. 自行判断记录切分策略 records.strategy：
   表格逐行数据→row；证照/表单的「标签:值」版式→key_value；按某字段分组的多行→group_by；纯文本正文→one_per_page。
   记录驱动表必须声明 tables[].role=record_source，并在 records.source_ref 中引用对应表 ref。
9. 自行判断每个字段的首个取值算子 pipeline[0].op：
   表格列→cell；文本标签旁取值→kv；版面块→block；整页正文→page_text。
10. 参考样例值形态选择变换算子：千分位/货币→number(strip)，多余空格→trim，日期→date，固定格式→regex。
11. 用户指定页码或页面区域时，使用文档地图里的 page/rect 生成 region；区域内文字用 region_text，
    表格用 tables[].region 或 block/kv 的 region 过滤。标签旁取值优先 kv，不要跨区域串值。
12. 参考附件仅用于理解字段语义、版式和取值方式；最终 spec 的表 ref、页码和区域必须来自主文档，
    不得把参考附件中的 ref 混入规则，也不得为参考附件生成抽取结果。
13. 规则不包含版本号、数据库表名、物理列映射或入库绑定；只描述中文逻辑字段与 extraction_spec_json。
'''.strip()

_MULTIPLE_RULES = '''
多条规则模式：
- 只返回 {"rules": [...]}，rules 须为非空数组，不得直接返回单条 spec。
- 每条规则包含中文 name、可选 description、独立完整的 spec、可选 schema。
- 每条规则都须单独满足 spec_version=2、source 血缘和多表 record_source/source_ref 约束。
- 不得把多条规则合并成一个 spec，也不得省略 rules 中的 name。
'''


def render(ctx, user_prompt, refs=None, reference_docs=None,
           multiple_rules=False):
    """ctx=doc_to_context；user_prompt=用户需求；reference_docs=参考附件。"""
    from ..context import render_context, render_reference_docs
    if not str(user_prompt or '').strip():
        raise ValueError('自然语言模式需要 user_prompt')
    ref_line = ''
    if refs:
        ref_line = '\n参考来源：{}\n'.format(
            '; '.join('{}={}'.format(k, v) for k, v in refs.items() if v))
    reference_text = render_reference_docs(reference_docs)
    if reference_text:
        reference_text = '\n\n参考附件上下文（全部附件，仅供主文档规则参考）：\n' + reference_text
    system = _SYSTEM_RULES.format(version=PROMPT_VERSION) + '\n\n' + _EXTRA_RULES
    if multiple_rules:
        system += '\n\n' + _MULTIPLE_RULES
    return ('{}\n\n用户需求：\n{}\n{}\n\n主文档解析上下文：\n{}\n{}\n\n'
            '返回 JSON 结构：\n{}\n').format(
                system, str(user_prompt).strip(), ref_line,
                render_context(ctx), reference_text,
                schema_text(multiple_rules=multiple_rules))

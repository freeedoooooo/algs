"""规则生成提示词 v1：封闭算子词表 + 锚点约束 + 严格 JSON 输出。"""
from ._schema import schema_text

PROMPT_VERSION = 'v1'

RULES = '''你是文档结构化规则生成器。只返回 JSON，不要解释。

硬性约束：
1. spec_version 必须为 2；fields 的 target 必须与"目标字段"中给出的列名逐字一致，不得改名、增删。
2. 每个 field.pipeline 的第一个算子必须是 source 类：
   cell / kv / row / block / page_text / region_text —— 否则产出的值没有逐格血缘，会被判废。
3. tables[].ref 用上下文里的表 ref（如 t0）；列选择器 column 用 name/index/header_contains/header_regex，
   header_contains 的值必须在上下文"列名"中真实出现，不得编造。
   需要限定区域时，在 tables[] 或 block/kv/region_text 算子上使用 region：
   {{page: 页码, rect: [左,上,右,下], space: source|rectified}}，rect 必须取文档地图中的归一化坐标。
4. 只用下列算子：cell kv row block page_text region_text / trim cut replace regex number date /
   concat template coalesce lookup / if switch / sum count join link。
   validate 只用 required regex enum range cross_field，cross_field 的比较符字段名是 cmp（不是 op）。
5. 不确定就留空 pipeline 或省略 validate，不要猜列名、不要编造正则。
6. 本提示词版本：{version}。
'''


def render(ctx, fields, refs=None):
    """ctx=doc_to_context 结果；fields=[{target,description}]；refs=参考来源。"""
    from ..context import render_context
    targets = '\n'.join(
        '- {}: {}'.format(f.get('target'), f.get('description') or '')
        for f in fields or [])
    ref_line = ''
    if refs:
        ref_line = '\n参考来源：{}\n'.format(
            '; '.join('{}={}'.format(k, v) for k, v in refs.items() if v))
    return ('{}\n\n目标字段：\n{}\n{}\n解析上下文：\n{}\n\n'
            '返回 JSON 结构：\n{}\n').format(
                RULES.format(version=PROMPT_VERSION), targets, ref_line,
                render_context(ctx), schema_text())

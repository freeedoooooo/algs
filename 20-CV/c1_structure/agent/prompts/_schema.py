"""生成目标 JSON Schema：单一真相源，同时供 prompt 文本与 validate_spec 参考。

与 agent/validate.py 的静态校验分工：本 schema 描述"模型该返回什么"，
validate_spec 做"实际返回是否合法"的硬校验（op 词表来自 OPS，不在此重复）。
"""
import json

FIELD_SCHEMA = {
    'target': '目标列名（必须与用户给的 fields.target 完全一致）',
    'type': 'string | number | date | bool',
    'pipeline': [
        {'op': 'cell | kv | row | block | page_text | region_text',
         'source': '表 ref（如 t0），source 算子必填',
         'column': '列选择器：name/index/header_contains/header_regex',
         'region': '可选：{page: 1, rect: [x0,y0,x1,y1], space: source|rectified}，坐标为归一化值'},
        {'op': 'trim | cut | replace | regex | number | date | concat | '
               'template | coalesce | lookup | if | switch | sum | count | '
               'join | link', '参数': '见算子定义'},
    ],
    'validate': '可选：[{op: required|regex|enum|range|cross_field, ...}]',
}


def generation_schema():
    """模型输出契约（供 prompt 展示；实际校验在 agent.validate.validate_spec）。"""
    return {
        'spec_version': 2,
        'tables': [{'ref': 't0', 'index': 0,
                    'region': '可选：{page: 1, rect: [x0,y0,x1,y1]}'}],
        'records': {'strategy': 'row | key_value | group_by | one_per_page'},
        'fields': [FIELD_SCHEMA],
    }


def schema_text():
    return json.dumps(generation_schema(), ensure_ascii=False, indent=2)

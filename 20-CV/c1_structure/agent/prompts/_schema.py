"""生成目标 JSON Schema：单一真相源，同时供 prompt 文本与 validate_spec 参考。

与 agent/validate.py 的静态校验分工：本 schema 描述"模型该返回什么"，
validate_spec 做"实际返回是否合法"的硬校验（op 词表来自 OPS，不在此重复）。
"""
import json

FIELD_SCHEMA = {
    'target': '逻辑字段名（使用中文语义名，不使用数据库物理列名）',
    'type': 'string | number | date | bool',
    'description': '可选：字段语义说明，不包含数据库列映射',
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


def generation_schema(multiple_rules=False):
    """模型输出契约（供 prompt 展示；实际校验在 agent.validate.validate_spec）。"""
    spec = {
        'spec_version': 2,
        'tables': [{'ref': 't0', 'role': 'record_source',
                    'index': 0,
                    'region': '可选：{page: 1, rect: [x0,y0,x1,y1]}'}],
        'records': {'strategy': 'row | key_value | group_by | one_per_page',
                    'source_ref': '记录驱动表 ref，必须指向 role=record_source'},
        'fields': [FIELD_SCHEMA],
    }
    if not multiple_rules:
        return spec
    return {'rules': [{
        'name': '规则名称（中文，不含版本号）',
        'description': '可选：规则用途说明',
        'spec': spec,
        'schema': '可选：字段契约；最终以 spec 推导的逻辑字段 schema 为准',
    }]}


def schema_text(multiple_rules=False):
    return json.dumps(generation_schema(multiple_rules), ensure_ascii=False, indent=2)

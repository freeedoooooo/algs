"""adapter/ — 防腐层：引擎结构 → 自有标准 cvdoc 的唯一翻译点。

pipeline 内部工作形态（pageRec）不出本包；页面 / 报告 / collect 只认 cvdoc。
换引擎 = 新增一个适配器实现 + 路线接入，下游零改动。
"""
from .base import SCHEMA, RECORDS_SCHEMA, adapt, hydrate  # noqa: F401
"""compute — 计算层：指标（index）→ 规则（rule）→ 框架（frame）。

极简设计：engine.py 只做运算返回结果文本；orchestrate.py 负责从定义推导
依赖、落库、元数据链与复核；app.py 只做请求校验。
"""
from .engine import compute_index, compute_rule, compute_frame, source_preview, source_documents
from .orchestrate import (execute_index, execute_rule, execute_frame,
                          parse_lineage, replay_value)

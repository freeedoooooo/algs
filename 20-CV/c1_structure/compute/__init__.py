"""compute — 计算层：指标（index）→ 规则（rule）→ 框架（frame）。

纯计算逻辑与 DB 写入分离：engine.py 只做运算并构造输入/依赖快照，
repo 负责幂等落库；app.py 编排两者。
"""
from .engine import (run_index, run_rule, run_frame, replay_index,
                     MAX_INPUT_ROWS)
from .orchestrate import (execute_index, execute_rule, execute_frame,
                          parse_lineage)

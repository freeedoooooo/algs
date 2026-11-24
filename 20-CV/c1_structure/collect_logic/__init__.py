"""collect_logic — spec_version=2 抽取逻辑引擎（纯函数，无 DB / 无 I/O）。

C2：代码内 OPS 注册表 + 取值/变换族（含非表格 kv）；规则配置在调用处构造。
config 描述业务、代码定义能力；不插件化、不 exec 字符串。
"""
from .registry import OPS, OP_KINDS
from . import ops  # noqa: F401  导入即注册全部算子
from .engine import apply_pipeline, build_logic

__all__ = ['OPS', 'OP_KINDS', 'apply_pipeline', 'build_logic']

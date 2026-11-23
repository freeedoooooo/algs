"""mvp/pipeline — 提取流水线包，对外只暴露 parse_one()。"""
from .runner import parse_one

__all__ = ['parse_one']

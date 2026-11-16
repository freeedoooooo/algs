"""mvp/pipeline — 提取流水线包，对外只暴露 extract_one()。"""
from .runner import extract_one

__all__ = ['extract_one']

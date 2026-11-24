"""导入即注册所有抽取算子。新增算子只改这里，不改引擎。"""
from . import source, transform, kv, compose, logic, aggregate  # noqa: F401

__all__ = ['source', 'transform', 'kv', 'compose', 'logic', 'aggregate']

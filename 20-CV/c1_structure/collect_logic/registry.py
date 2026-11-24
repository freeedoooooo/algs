"""算子注册表：能力由代码定义，规则 JSON 只描述用哪些算子、什么顺序、什么参数。

kind='source' 的算子负责从 doc 取值并产生锚点；其余算子只变换上游值/锚点。
C2 不做 spec 结构校验（已砍），未知 op 在引擎执行时显式报错。
"""

OPS = {}
OP_KINDS = {}


def register(name, kind='transform'):
    """注册纯函数算子。重复注册视为编程错误，直接拒绝。"""
    def deco(fn):
        if name in OPS:
            raise ValueError('抽取算子重复注册: {}'.format(name))
        OPS[name] = fn
        OP_KINDS[name] = kind
        return fn
    return deco

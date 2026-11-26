"""受限 ReAct 调度器：封闭工具白名单 + 轮次预算 + 确定性终止。

与无界 ReAct 的区别（审计场景必须）：
  1. 工具集是代码注册的封闭集合，LLM 只能从中选，越界直接拒绝；
  2. 终止由确定性验证器判定（达标函数），LLM 说"完成"不算数；
  3. 轮次有硬上限（默认 6），耗尽预算带轨迹交人工；
  4. 每轮工具调用与结果全部留痕，可回放。

LLM 每轮返回结构化决策：{"tool": 工具名, "args": {...}, "thought": 说明}。
编排器执行工具 → 把结果作为 observation 回喂 → 下一轮，直到 done 或预算耗尽。
"""
import json

from .llm import LLMSchemaFail


class ReActBudgetExhausted(Exception):
    """轮次预算耗尽，未能达标。"""


class ReActToolDenied(Exception):
    """LLM 请求了白名单外的工具。"""


class ReActResult:
    def __init__(self, value, done, rounds, trace):
        self.value = value
        self.done = done
        self.rounds = rounds
        self.trace = trace

    def as_dict(self):
        return {'value': self.value, 'done': self.done,
                'rounds': self.rounds, 'trace': self.trace}


class ReActLoop:
    """受限 ReAct 循环。

    tools      : {name: callable(args) -> dict} 封闭白名单
    is_done    : (state, observation) -> bool 确定性达标判定
    llm_fn     : (prompt, state) -> dict 决策函数（可注入，测试用）
    max_rounds : 硬上限
    """

    def __init__(self, tools, is_done, llm_fn, max_rounds=6):
        self.tools = dict(tools or {})
        self.is_done = is_done
        self.llm_fn = llm_fn
        self.max_rounds = max(1, int(max_rounds))
        if not self.tools:
            raise ValueError('ReAct 工具集不能为空')

    def run(self, goal, initial=None):
        state = dict(initial or {})
        trace = []
        observation = {'goal': goal, 'state': state}
        for round_no in range(1, self.max_rounds + 1):
            decision = self.llm_fn(observation, state)
            if not isinstance(decision, dict):
                raise LLMSchemaFail('ReAct 决策须为 JSON 对象')
            tool = decision.get('tool')
            args = decision.get('args') or {}
            if tool == 'finish':
                done = bool(self.is_done(state, observation))
                trace.append({'round': round_no, 'tool': 'finish',
                              'thought': decision.get('thought'),
                              'done': done})
                if done:
                    return ReActResult(state.get('result'), True,
                                       round_no, trace)
                observation = {'not_done': '验证器判定未达标，请继续',
                               'state': state}
                continue
            if tool not in self.tools:
                raise ReActToolDenied(
                    '工具不在白名单: {}；可用: {}'.format(
                        tool, ', '.join(sorted(self.tools))))
            result = self.tools[tool](args)
            if not isinstance(result, dict):
                raise LLMSchemaFail('工具 {} 须返回 dict'.format(tool))
            state.update({k: v for k, v in result.items()
                          if k not in ('round', 'tool')})
            trace.append({'round': round_no, 'tool': tool, 'args': args,
                          'thought': decision.get('thought'),
                          'result': result})
            observation = {'tool': tool, 'observation': result, 'state': state}
            if self.is_done(state, observation):
                return ReActResult(state.get('result'), True, round_no, trace)
        return ReActResult(state.get('result'), False, self.max_rounds, trace)


def render_tools(tools):
    """工具白名单文本（供 prompt 展示）。"""
    lines = []
    for name, fn in sorted((tools or {}).items()):
        doc = (fn.__doc__ or '').strip().split('\n')[0]
        lines.append('- {}: {}'.format(name, doc))
    return '\n'.join(lines)

"""P0.5 样本触发实测（只读；不写库、不启端口、不碰 8765）。

背景：环境无真实 LLM 端点（C1_LLM_* 未配置）。本脚本用可注入 fake LLM
配合真实资料（file_id=1，24 条 confirmed 中间层记录）验证 ReAct 机制：
  A. 首轮"选错列名" → 一次性生成命中率 0（样本触发条件成立）
  B. 受限 ReAct：inspect_tables → revise_spec → 达标（字段一致率 100%）
  C. 中间层未被触碰（file_id=1 仍 24 条 confirmed）
  D. 禁止工具被拒（安全边界）

用法：python c1_structure/tests/verify_p05_react.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from c1_structure.agent import llm, rule_author
from c1_structure.agent.react import ReActToolDenied
from c1_structure.store import content

FILE_ID = 1
# 资料 1 中间层有 account_1(借) / account_2(余额) 两字段，必须一并生成才可达标
FIELDS = [{'target': 'account_1', 'description': '借方发生额'},
          {'target': 'account_2', 'description': '余额'}]
GOOD_COLS = ['借', '余额']
BAD_COLS = ['不存在的列A', '不存在的列B']


def spec_with(cols):
    return {'spec_version': 2, 'fields': [
        {'target': target,
         'pipeline': [{'op': 'cell', 'source': 'main',
                       'column': {'name': col}, 'row': 'current'}]}
        for target, col in zip(['account_1', 'account_2'], cols)]}


def main():
    doc = content.get_extract(FILE_ID)
    fake_content = content
    if doc is None:
        print('SKIP: file_id={} 无解析产物'.format(FILE_ID))
        return 0

    targets = rule_author._targets_from_middle(fake_content, FILE_ID)
    print('样本：file_id={}，中间层已确认 {} 条'.format(FILE_ID, len(targets)))
    if not targets:
        print('SKIP: 无 confirmed/edited 记录，无法对拍')
        return 0

    # A. 一次性生成（故意选错列）→ 命中率基线
    def llm_oneshot(prompt, _spec):
        return spec_with(BAD_COLS)

    one = rule_author.generate_rule(
        doc, FIELDS, llm_fn=llm_oneshot, targets=targets)
    acc_one = one.diagnostics['compare']['field_accuracy']
    print('A. 一次性生成：字段一致率={}，空字段={}'.format(
        acc_one, one.diagnostics['empty_fields']))

    # B. 受限 ReAct：看表 → 改列 → 达标
    steps = []

    def llm_react(prompt_or_obs, spec_or_state):
        if isinstance(prompt_or_obs, str):
            return spec_with(BAD_COLS)          # 首轮仍选错，触发迭代
        step = len(steps)
        steps.append(1)
        if step == 0:
            return {'tool': 'inspect_tables', 'args': {},
                    'thought': '先查真实表头'}
        if step == 1:
            return {'tool': 'revise_spec',
                    'args': {'spec': spec_with(GOOD_COLS)},
                    'thought': '改用真实列「借」'}
        return {'tool': 'finish', 'thought': '验证器应已判定达标'}

    result = rule_author.generate_rule_react(
        doc, FIELDS, llm_fn=llm_react, targets=targets, max_rounds=6)
    cmp = result.diagnostics['compare']
    print('B. ReAct：触发={}，轮次={}，达标={}，一致率={}'.format(
        result.meta['react_triggered'], result.meta['react_rounds'],
        result.meta['react_done'], cmp['field_accuracy']))
    print('   轨迹：{}'.format(
        ' → '.join(t['tool'] for t in result.meta['react_trace'])))

    # C. 中间层完好
    after = rule_author._targets_from_middle(fake_content, FILE_ID)
    print('C. 中间层：{} 条（前后一致={}）'.format(
        len(after), len(after) == len(targets)))

    # D. 越界工具被拒
    def llm_denied(prompt_or_obs, spec_or_state):
        if isinstance(prompt_or_obs, str):
            return spec_with(BAD_COLS)
        return {'tool': 'drop_table', 'args': {}}

    denied = False
    try:
        rule_author.generate_rule_react(
            doc, FIELDS, llm_fn=llm_denied, targets=targets, max_rounds=2)
    except ReActToolDenied:
        denied = True
    print('D. 越界工具被拒：{}'.format(denied))

    ok = (acc_one == 0.0 and result.meta['react_done']
          and cmp['field_accuracy'] == 1.0
          and len(after) == len(targets) and denied)
    print('结论：P0.5 机制{}（样本触发条件成立，迭代可达标）'.format(
        '有效' if ok else '未达标'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

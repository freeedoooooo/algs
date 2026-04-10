# algs

## 当前整理目标

这个仓库当前按照 `solutions-python/TOP100_MAINLAND_INTERVIEW.md` 里的题目顺序推进 LeetCode 题解整理，并以 `solutions-python/LEETCODE_EXPLANATION_TEMPLATE.md` 作为统一解析模板。

每次推进时，默认执行下面这套流程：

1. 参考 `solutions-python/TOP100_MAINLAND_INTERVIEW.md` 中的题目顺序确定当前题目。
2. 结合 `solutions-python/java2python/TASK_LIST.md` 的任务队列，找到还没完成的下一题。
3. 为该题生成一个独立的 Jupyter Notebook，放在 `solutions-python/java2python/` 目录下。
4. Notebook 内容遵循题解模板，至少包含：
   - 题目基本信息
   - 一句话总结
   - 题目理解与约束分析
   - 朴素思路到优化思路
   - 核心算法讲解
   - Python 代码
   - 复杂度分析
   - 易错点
   - 面试讲解话术
   - 实际应用场景
   - 可运行 demo
5. 每完成一道题，都要把对应清单中的 `进度` 列标记为 `✅`。

## 本仓库中相关文件的分工

- [solutions-python/TOP100_MAINLAND_INTERVIEW.md](/D:/PROJECT/Project_HU/freeedoooooo/algs/solutions-python/TOP100_MAINLAND_INTERVIEW.md)
  作为总清单，记录 Top100 题目、顺序、优先级、题型与进度。
- [solutions-python/LEETCODE_EXPLANATION_TEMPLATE.md](/D:/PROJECT/Project_HU/freeedoooooo/algs/solutions-python/LEETCODE_EXPLANATION_TEMPLATE.md)
  作为题解 notebook 的统一结构模板。
- [solutions-python/java2python/TASK_LIST.md](/D:/PROJECT/Project_HU/freeedoooooo/algs/solutions-python/java2python/TASK_LIST.md)
  作为当前 Python notebook 任务队列，记录哪些题已经实际产出 notebook。
- [solutions-python/java2python](/D:/PROJECT/Project_HU/freeedoooooo/algs/solutions-python/java2python)
  存放逐题整理后的 Python 解析 notebook。
- [solutions-java](/D:/PROJECT/Project_HU/freeedoooooo/algs/solutions-java)
  提供现有 Java 解法，可作为迁移到 Python 和补充讲解时的参考实现。

## 执行约定

- 按顺序推进，不跳题，除非任务明确要求调整顺序。
- 一次至少完成一道题，并同步更新进度。
- 新增内容优先保持可运行、可复习、可继续扩展。
- Notebook 应尽量自包含，读者打开后不依赖额外上下文也能理解题意、思路和代码。

## 最近一次推进

- 已完成：`p138 Copy List with Random Pointer`
- 产出文件：
  - [p138_copy_list_with_random_pointer.ipynb](/D:/PROJECT/Project_HU/freeedoooooo/algs/solutions-python/java2python/p138_copy_list_with_random_pointer.ipynb)

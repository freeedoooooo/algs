# algs

## 说明

这个仓库里的 Python 题解整理分成两条独立任务线，不混用清单，也不共用输出目录：

1. `top100`
2. `java2python`

两条线都使用同一份题解结构模板，但题目来源、推进依据、输出位置和进度统计彼此分开。

## 统一模板

所有 Python notebook 统一参考：

- [leetcode_explanation_template.md](solutions-python/leetcode_explanation_template.md)

整理时，notebook 至少包含这些部分：

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

## Top100 任务线

`top100` 是独立题单，按 Top100 清单顺序逐题整理。

- 清单文件：[top100.md](solutions-python/top100.md)
- 输出目录：[solutions-python/top100](solutions-python/top100/)

执行规则：

1. 只参考 `top100.md` 里的题目顺序推进。
2. 生成的 notebook 只放到 `solutions-python/top100/`。
3. 完成一道题后，只更新 `top100.md` 的 `进度` 列。
4. `top100` 的进度不因为 `java2python` 完成同题而自动勾选。

当前已产出：

- [p031_next_permutation.ipynb](solutions-python/top100/p031_next_permutation.ipynb)

## Java2Python 任务线

`java2python` 也是独立题单，它的目标不是直接按 Top100 走，而是参考已有 Java 历史题解，把对应题目迁移整理成 Python notebook。

- 清单文件：[java2python.md](solutions-python/java2python.md)
- 输出目录：[solutions-python/java2python](solutions-python/java2python/)
- Java 参考目录：[solutions-java](solutions-java/)

执行规则：

1. 只参考 `java2python.md` 的任务顺序推进。
2. 先阅读 `solutions-java` 中对应题目的历史实现和思路。
3. `java2python` 的整理必须明确参考原来的 Java 方案，不能脱离原实现另写一套思路。
4. 每个 `java2python` notebook 都要包含原始 Java 代码、Java 方案解析，以及对应的 Python 转写与讲解。
5. 再把题解迁移整理成 Python notebook。
6. 生成的 notebook 只放到 `solutions-python/java2python/`。
7. 完成一道题后，只更新 `java2python.md` 的 `进度` 列。

当前已产出：

- [p002_add_two_numbers.ipynb](solutions-python/java2python/p002_add_two_numbers.ipynb)
- [p021_merge_two_sorted_lists.ipynb](solutions-python/java2python/p021_merge_two_sorted_lists.ipynb)
- [p086_partition_list.ipynb](solutions-python/java2python/p086_partition_list.ipynb)
- [p094_binary_tree_inorder_traversal.ipynb](solutions-python/java2python/p094_binary_tree_inorder_traversal.ipynb)
- [p138_copy_list_with_random_pointer.ipynb](solutions-python/java2python/p138_copy_list_with_random_pointer.ipynb)
- [p142_linked_list_cycle_ii.ipynb](solutions-python/java2python/p142_linked_list_cycle_ii.ipynb)
- [p144_binary_tree_preorder_traversal.ipynb](solutions-python/java2python/p144_binary_tree_preorder_traversal.ipynb)

## 进度更新约定

- `top100` 只维护 `top100.md`
- `java2python` 只维护 `java2python.md`
- 两条线即使题号重合，进度也分别统计

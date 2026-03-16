from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "leetcode-python"


def md(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "id": uuid4().hex[:8],
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": uuid4().hex[:8],
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(name: str, cells: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    path.write_text(
        json.dumps(notebook(cells), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )


index_cells = [
    md(
        dedent(
            """
            # LeetCode Python Notebook 索引

            这个目录把 `src/leetcode` 下的 Java 题解，按题型整理成了 Python 版 Jupyter Notebook。

            ## 目录说明

            - `01_linked_list.ipynb`：链表专题
            - `02_binary_tree_traversal.ipynb`：二叉树遍历专题
            - `03_stack_queue_design.ipynb`：栈、队列与循环队列设计专题
            - `04_binary_search_and_sort.ipynb`：二分、归并统计与排序专题
            - `05_trie.ipynb`：前缀树专题

            ## 整理原则

            - 保留原始 Java 解法的核心思路
            - 改写为更贴近 LeetCode Python 提交风格的实现
            - 把原代码里关键注释重新整理为可读中文
            - 补充必要的边界情况说明、复杂度说明和简单示例
            """
        ).strip()
        + "\n"
    )
]


linked_list_cells = [
    md(
        dedent(
            """
            # 链表专题

            覆盖题目：

            | 题号 | 题目 |
            | --- | --- |
            | 2 | Add Two Numbers |
            | 21 | Merge Two Sorted Lists |
            | 86 | Partition List |
            | 138 | Copy List with Random Pointer |
            | 142 | Linked List Cycle II |
            | 148 | Sort List |
            | 160 | Intersection of Two Linked Lists |
            | 206 | Reverse Linked List |
            | 234 | Palindrome Linked List |

            这一册主要整理了原仓库里链表相关题解。原 Java 注释已经有比较明确的解题意图，我这里把它们重写成更适合 Python notebook 阅读的版本，并补充了边界情况与复杂度说明。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            from __future__ import annotations
            from dataclasses import dataclass
            from typing import Optional


            @dataclass
            class ListNode:
                val: int = 0
                next: Optional["ListNode"] = None


            class RandomNode:
                def __init__(self, x: int, next: Optional["RandomNode"] = None, random: Optional["RandomNode"] = None):
                    self.val = x
                    self.next = next
                    self.random = random


            def build_linked_list(values: list[int]) -> Optional[ListNode]:
                dummy = ListNode()
                cur = dummy
                for value in values:
                    cur.next = ListNode(value)
                    cur = cur.next
                return dummy.next


            def linked_list_to_list(head: Optional[ListNode]) -> list[int]:
                ans = []
                while head:
                    ans.append(head.val)
                    head = head.next
                return ans
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P002 两数相加

            原 Java 解法的核心点有三个：

            - 用虚拟头结点统一处理头节点创建逻辑
            - 每一位计算时都把空链表位置当成 `0`
            - 遍历结束后，别忘了处理最后一位进位

            时间复杂度 `O(max(m, n))`，空间复杂度 `O(max(m, n))`（结果链表不计入额外空间时，可视为 `O(1)` 辅助空间）。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP002:
                def addTwoNumbers(self, l1: Optional[ListNode], l2: Optional[ListNode]) -> Optional[ListNode]:
                    dummy = ListNode()
                    cur = dummy
                    carry = 0

                    while l1 or l2 or carry:
                        value1 = l1.val if l1 else 0
                        value2 = l2.val if l2 else 0
                        total = value1 + value2 + carry
                        carry, digit = divmod(total, 10)

                        cur.next = ListNode(digit)
                        cur = cur.next

                        if l1:
                            l1 = l1.next
                        if l2:
                            l2 = l2.next

                    return dummy.next


            l1 = build_linked_list([2, 4, 3])
            l2 = build_linked_list([5, 6, 4])
            linked_list_to_list(SolutionP002().addTwoNumbers(l1, l2))
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P021 合并两个有序链表

            原文件给了递归和迭代两种写法。这里都保留下来：

            - 递归写法短，但会占用调用栈
            - 迭代写法更接近工程里常用的链表合并方式
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP021:
                def mergeTwoListsRecursive(
                    self,
                    list1: Optional[ListNode],
                    list2: Optional[ListNode],
                ) -> Optional[ListNode]:
                    if not list1:
                        return list2
                    if not list2:
                        return list1
                    if list1.val < list2.val:
                        list1.next = self.mergeTwoListsRecursive(list1.next, list2)
                        return list1
                    list2.next = self.mergeTwoListsRecursive(list1, list2.next)
                    return list2

                def mergeTwoListsIterative(
                    self,
                    list1: Optional[ListNode],
                    list2: Optional[ListNode],
                ) -> Optional[ListNode]:
                    dummy = ListNode()
                    tail = dummy

                    while list1 and list2:
                        if list1.val <= list2.val:
                            tail.next = list1
                            list1 = list1.next
                        else:
                            tail.next = list2
                            list2 = list2.next
                        tail = tail.next

                    tail.next = list1 or list2
                    return dummy.next


            a = build_linked_list([1, 2, 4])
            b = build_linked_list([1, 3, 4])
            linked_list_to_list(SolutionP021().mergeTwoListsIterative(a, b))
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P086 分隔链表

            原 Java 代码强调了一个很容易遗漏的点：

            - 每次把节点摘出来以后，立刻执行 `head.next = None`

            这样可以避免原链表残留指针导致拼接后出现环，或者把不该带上的后续节点一并挂过去。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP086:
                def partition(self, head: Optional[ListNode], x: int) -> Optional[ListNode]:
                    small_dummy = ListNode()
                    large_dummy = ListNode()
                    small_tail = small_dummy
                    large_tail = large_dummy

                    while head:
                        nxt = head.next
                        head.next = None
                        if head.val < x:
                            small_tail.next = head
                            small_tail = small_tail.next
                        else:
                            large_tail.next = head
                            large_tail = large_tail.next
                        head = nxt

                    small_tail.next = large_dummy.next
                    return small_dummy.next


            linked_list_to_list(SolutionP086().partition(build_linked_list([1, 4, 3, 2, 5, 2]), 3))
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P138 复制带随机指针的链表

            原 Java 解法用了三次遍历，且没有额外哈希表：

            1. 在每个原节点后面插入它的复制节点
            2. 根据 `原节点.random.next` 设置复制节点的 `random`
            3. 再把新旧链表拆开

            这是这题最经典的 `O(1)` 额外空间做法。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP138:
                def copyRandomList(self, head: Optional[RandomNode]) -> Optional[RandomNode]:
                    if not head:
                        return None

                    cur = head
                    while cur:
                        nxt = cur.next
                        cur.next = RandomNode(cur.val, nxt)
                        cur = nxt

                    cur = head
                    while cur:
                        copy = cur.next
                        copy.random = cur.random.next if cur.random else None
                        cur = copy.next

                    cur = head
                    new_head = head.next
                    while cur:
                        copy = cur.next
                        nxt = copy.next
                        cur.next = nxt
                        copy.next = nxt.next if nxt else None
                        cur = nxt

                    return new_head
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P142 环形链表 II

            原注释里写的是 Floyd 快慢指针证明。结论可以记成一句话：

            - 快慢指针第一次相遇后，让其中一个回到头节点
            - 两个指针都改成一步一步走
            - 再次相遇的位置，就是入环点
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP142:
                def detectCycle(self, head: Optional[ListNode]) -> Optional[ListNode]:
                    if not head or not head.next:
                        return None

                    slow = head
                    fast = head

                    while fast and fast.next:
                        slow = slow.next
                        fast = fast.next.next
                        if slow is fast:
                            break
                    else:
                        return None

                    fast = head
                    while slow is not fast:
                        slow = slow.next
                        fast = fast.next

                    return slow
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P148 排序链表

            原 Java 文件重点强调的是：

            - 题目要求 `O(n log n)` 时间复杂度
            - 如果想把额外空间压到 `O(1)`，就不要用递归版归并排序
            - 更合适的是自底向上的迭代归并排序

            下面保留这个思路，写成 Python 版的 bottom-up merge sort。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP148:
                def sortList(self, head: Optional[ListNode]) -> Optional[ListNode]:
                    if not head or not head.next:
                        return head

                    length = 0
                    cur = head
                    while cur:
                        length += 1
                        cur = cur.next

                    dummy = ListNode(0, head)
                    step = 1

                    while step < length:
                        prev = dummy
                        cur = dummy.next

                        while cur:
                            left = cur
                            right = self._split(left, step)
                            cur = self._split(right, step)
                            merged_head, merged_tail = self._merge(left, right)
                            prev.next = merged_head
                            prev = merged_tail

                        step <<= 1

                    return dummy.next

                def _split(self, head: Optional[ListNode], size: int) -> Optional[ListNode]:
                    if not head:
                        return None
                    for _ in range(size - 1):
                        if not head.next:
                            break
                        head = head.next
                    second = head.next
                    head.next = None
                    return second

                def _merge(
                    self,
                    left: Optional[ListNode],
                    right: Optional[ListNode],
                ) -> tuple[Optional[ListNode], Optional[ListNode]]:
                    dummy = ListNode()
                    tail = dummy

                    while left and right:
                        if left.val <= right.val:
                            tail.next = left
                            left = left.next
                        else:
                            tail.next = right
                            right = right.next
                        tail = tail.next

                    tail.next = left or right
                    while tail.next:
                        tail = tail.next

                    return dummy.next, tail


            linked_list_to_list(SolutionP148().sortList(build_linked_list([4, 2, 1, 3])))
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P160 相交链表

            原 Java 方案是“长度差对齐”版本：

            - 先分别走到两个链表尾部，同时算出长度差
            - 如果尾节点不是同一个对象，说明一定不相交
            - 让长链表先走 `diff` 步，再同步向前
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP160:
                def getIntersectionNode(
                    self,
                    headA: Optional[ListNode],
                    headB: Optional[ListNode],
                ) -> Optional[ListNode]:
                    if not headA or not headB:
                        return None

                    len_a = 0
                    len_b = 0
                    cur_a = headA
                    cur_b = headB
                    tail_a = None
                    tail_b = None

                    while cur_a:
                        len_a += 1
                        tail_a = cur_a
                        cur_a = cur_a.next

                    while cur_b:
                        len_b += 1
                        tail_b = cur_b
                        cur_b = cur_b.next

                    if tail_a is not tail_b:
                        return None

                    long_head = headA if len_a >= len_b else headB
                    short_head = headB if len_a >= len_b else headA

                    for _ in range(abs(len_a - len_b)):
                        long_head = long_head.next

                    while long_head is not short_head:
                        long_head = long_head.next
                        short_head = short_head.next

                    return long_head
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P206 反转链表

            原 Java 文件同时给了迭代和递归写法。迭代版最值得记忆的就是这三步：

            - 先保存 `next`
            - 再反转指针 `head.next = pre`
            - 最后整体往前推进
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP206:
                def reverseList(self, head: Optional[ListNode]) -> Optional[ListNode]:
                    prev = None
                    cur = head
                    while cur:
                        nxt = cur.next
                        cur.next = prev
                        prev = cur
                        cur = nxt
                    return prev

                def reverseListRecursive(self, head: Optional[ListNode]) -> Optional[ListNode]:
                    if not head or not head.next:
                        return head
                    new_head = self.reverseListRecursive(head.next)
                    head.next.next = head
                    head.next = None
                    return new_head


            linked_list_to_list(SolutionP206().reverseList(build_linked_list([1, 2, 3, 4, 5])))
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P234 回文链表

            原 Java 代码有一个很好的工程意识：

            - 先找到中点
            - 原地反转后半部分
            - 比较两边是否相等
            - 最后再把链表恢复成原样

            这样既满足空间复杂度要求，也不会破坏输入结构。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP234:
                def isPalindrome(self, head: Optional[ListNode]) -> bool:
                    if not head or not head.next:
                        return True

                    slow = head
                    fast = head
                    while fast.next and fast.next.next:
                        slow = slow.next
                        fast = fast.next.next

                    second = self._reverse(slow.next)
                    slow.next = None

                    p1 = head
                    p2 = second
                    result = True
                    while p1 and p2:
                        if p1.val != p2.val:
                            result = False
                            break
                        p1 = p1.next
                        p2 = p2.next

                    slow.next = self._reverse(second)
                    return result

                def _reverse(self, head: Optional[ListNode]) -> Optional[ListNode]:
                    prev = None
                    cur = head
                    while cur:
                        nxt = cur.next
                        cur.next = prev
                        prev = cur
                        cur = nxt
                    return prev


            SolutionP234().isPalindrome(build_linked_list([1, 2, 2, 1]))
            """
        ).strip()
        + "\n"
    ),
]
binary_tree_cells = [
    md(
        dedent(
            """
            # 二叉树遍历专题

            覆盖题目：

            | 题号 | 题目 |
            | --- | --- |
            | 94 | Binary Tree Inorder Traversal |
            | 144 | Binary Tree Preorder Traversal |
            | 145 | Binary Tree Postorder Traversal |

            这三题原 Java 解法都采用了非递归写法，重点是用栈模拟递归过程。这样更适合统一记忆遍历模板。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            from __future__ import annotations
            from dataclasses import dataclass
            from typing import Optional


            @dataclass
            class TreeNode:
                val: int
                left: Optional["TreeNode"] = None
                right: Optional["TreeNode"] = None
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P094 二叉树的中序遍历

            原 Java 注释说明得很完整：

            - 一路把左边界压栈
            - 左边走到底后弹栈访问当前节点
            - 再转向右子树

            这就是标准的中序非递归模板。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP094:
                def inorderTraversal(self, root: Optional[TreeNode]) -> list[int]:
                    ans = []
                    stack = []
                    cur = root

                    while stack or cur:
                        while cur:
                            stack.append(cur)
                            cur = cur.left
                        cur = stack.pop()
                        ans.append(cur.val)
                        cur = cur.right

                    return ans
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P144 二叉树的前序遍历

            原 Java 代码特别提醒了一点：

            - 先压右孩子，再压左孩子

            因为栈是后进先出，所以左孩子会先弹出来，从而得到 `根 -> 左 -> 右` 的顺序。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP144:
                def preorderTraversal(self, root: Optional[TreeNode]) -> list[int]:
                    if not root:
                        return []

                    ans = []
                    stack = [root]
                    while stack:
                        node = stack.pop()
                        ans.append(node.val)
                        if node.right:
                            stack.append(node.right)
                        if node.left:
                            stack.append(node.left)
                    return ans
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P145 二叉树的后序遍历

            原 Java 解法使用两个栈：

            - 第一个栈按“根、右、左”的顺序收集节点
            - 第二个栈再把顺序倒过来，变成“左、右、根”

            这是最容易理解的非递归后序遍历写法。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP145:
                def postorderTraversal(self, root: Optional[TreeNode]) -> list[int]:
                    if not root:
                        return []

                    stack = [root]
                    collect = []

                    while stack:
                        node = stack.pop()
                        collect.append(node)
                        if node.left:
                            stack.append(node.left)
                        if node.right:
                            stack.append(node.right)

                    return [node.val for node in reversed(collect)]


            root = TreeNode(1, None, TreeNode(2, TreeNode(3)))
            SolutionP145().postorderTraversal(root)
            """
        ).strip()
        + "\n"
    ),
]
stack_queue_cells = [
    md(
        dedent(
            """
            # 栈与队列设计专题

            覆盖题目：

            | 题号 | 题目 |
            | --- | --- |
            | 155 | Min Stack |
            | 225 | Implement Stack using Queues |
            | 232 | Implement Queue using Stacks |
            | 622 | Design Circular Queue |
            | 641 | Design Circular Deque |

            这一册主要是“数据结构设计题”。代码本身不长，但要把操作语义、状态变量和边界处理讲清楚。
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P155 最小栈

            原 Java 实现用了两个同步栈：

            - `data_stack` 存真实数据
            - `min_stack` 每个位置都存“当前阶段最小值”

            这样 `getMin()` 就可以做到 `O(1)`。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class MinStack:
                def __init__(self) -> None:
                    self.data_stack = []
                    self.min_stack = []

                def push(self, val: int) -> None:
                    self.data_stack.append(val)
                    if not self.min_stack:
                        self.min_stack.append(val)
                    else:
                        self.min_stack.append(min(val, self.min_stack[-1]))

                def pop(self) -> None:
                    self.data_stack.pop()
                    self.min_stack.pop()

                def top(self) -> int:
                    return self.data_stack[-1]

                def getMin(self) -> int:
                    return self.min_stack[-1]
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P225 用队列实现栈

            原 Java 思路是：

            - 新元素先入队
            - 再把前面已有元素依次搬到队尾

            这样队头始终就是“栈顶”。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            from collections import deque


            class MyStack:
                def __init__(self) -> None:
                    self.queue = deque()

                def push(self, x: int) -> None:
                    self.queue.append(x)
                    for _ in range(len(self.queue) - 1):
                        self.queue.append(self.queue.popleft())

                def pop(self) -> int:
                    return self.queue.popleft()

                def top(self) -> int:
                    return self.queue[0]

                def empty(self) -> bool:
                    return not self.queue
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P232 用栈实现队列

            原 Java 版本每次 `pop/peek` 都会把元素从一个栈倒到另一个栈，再倒回来。
            这种写法和原题思路一致，但不是最优。

            这里我保留更常见的双栈优化版本：

            - `in_stack` 专门负责入队
            - `out_stack` 专门负责出队
            - 只有 `out_stack` 为空时，才把 `in_stack` 全部倒过去

            均摊时间复杂度更好。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class MyQueue:
                def __init__(self) -> None:
                    self.in_stack = []
                    self.out_stack = []

                def _move(self) -> None:
                    if not self.out_stack:
                        while self.in_stack:
                            self.out_stack.append(self.in_stack.pop())

                def push(self, x: int) -> None:
                    self.in_stack.append(x)

                def pop(self) -> int:
                    self._move()
                    return self.out_stack.pop()

                def peek(self) -> int:
                    self._move()
                    return self.out_stack[-1]

                def empty(self) -> bool:
                    return not self.in_stack and not self.out_stack
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P622 设计循环队列

            原 Java 实现维护了四个状态：

            - `queue`：底层数组
            - `head`：队头位置
            - `tail`：下一个可写位置
            - `size`：当前元素数量

            有了 `size`，就能避免“头尾相等时到底是空还是满”的歧义。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class MyCircularQueue:
                def __init__(self, k: int):
                    self.queue = [0] * k
                    self.head = 0
                    self.tail = 0
                    self.size = 0
                    self.limit = k

                def enQueue(self, value: int) -> bool:
                    if self.isFull():
                        return False
                    self.queue[self.tail] = value
                    self.tail = (self.tail + 1) % self.limit
                    self.size += 1
                    return True

                def deQueue(self) -> bool:
                    if self.isEmpty():
                        return False
                    self.head = (self.head + 1) % self.limit
                    self.size -= 1
                    return True

                def Front(self) -> int:
                    return -1 if self.isEmpty() else self.queue[self.head]

                def Rear(self) -> int:
                    if self.isEmpty():
                        return -1
                    return self.queue[(self.tail - 1) % self.limit]

                def isEmpty(self) -> bool:
                    return self.size == 0

                def isFull(self) -> bool:
                    return self.size == self.limit
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P641 设计循环双端队列

            原 Java 代码里一个容易忽略的细节是：

            - 当队列为空时，无论是头插还是尾插，都要重新把 `head` 和 `tail` 调整到同一个有效位置

            否则第一次插入后的指针状态会不正确。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class MyCircularDeque:
                def __init__(self, k: int):
                    self.data = [0] * k
                    self.head = 0
                    self.tail = 0
                    self.size = 0
                    self.limit = k

                def insertFront(self, value: int) -> bool:
                    if self.isFull():
                        return False
                    if self.isEmpty():
                        self.data[0] = value
                        self.head = self.tail = 0
                    else:
                        self.head = (self.head - 1) % self.limit
                        self.data[self.head] = value
                    self.size += 1
                    return True

                def insertLast(self, value: int) -> bool:
                    if self.isFull():
                        return False
                    if self.isEmpty():
                        self.data[0] = value
                        self.head = self.tail = 0
                    else:
                        self.tail = (self.tail + 1) % self.limit
                        self.data[self.tail] = value
                    self.size += 1
                    return True

                def deleteFront(self) -> bool:
                    if self.isEmpty():
                        return False
                    self.head = (self.head + 1) % self.limit
                    self.size -= 1
                    return True

                def deleteLast(self) -> bool:
                    if self.isEmpty():
                        return False
                    self.tail = (self.tail - 1) % self.limit
                    self.size -= 1
                    return True

                def getFront(self) -> int:
                    return -1 if self.isEmpty() else self.data[self.head]

                def getRear(self) -> int:
                    return -1 if self.isEmpty() else self.data[self.tail]

                def isEmpty(self) -> bool:
                    return self.size == 0

                def isFull(self) -> bool:
                    return self.size == self.limit
            """
        ).strip()
        + "\n"
    ),
]
binary_search_sort_cells = [
    md(
        dedent(
            """
            # 二分与排序专题

            覆盖题目：

            | 题号 | 题目 |
            | --- | --- |
            | 162 | Find Peak Element |
            | 493 | Reverse Pairs |
            | 912 | Sort an Array |

            这一册把“二分答案位置”和“归并排序衍生统计”放在一起，方便把查找与分治的套路串起来。
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P162 寻找峰值

            原 Java 文件除了峰值题本身，还顺手整理了基础二分模板。我这里保留了这层脉络：

            - 精确查找
            - 找“最左满足条件的位置”
            - 找“最右满足条件的位置”
            - 峰值题的二分判定

            对峰值题来说，关键不是死记模板，而是能判断“中点应该往哪边收缩区间”。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            def binary_search(arr: list[int], target: int) -> int:
                left, right = 0, len(arr) - 1
                while left <= right:
                    mid = left + (right - left) // 2
                    if arr[mid] == target:
                        return mid
                    if arr[mid] < target:
                        left = mid + 1
                    else:
                        right = mid - 1
                return -1


            def find_left(arr: list[int], target: int) -> int:
                left, right = 0, len(arr) - 1
                ans = -1
                while left <= right:
                    mid = left + (right - left) // 2
                    if arr[mid] >= target:
                        ans = mid
                        right = mid - 1
                    else:
                        left = mid + 1
                return ans


            def find_right(arr: list[int], target: int) -> int:
                left, right = 0, len(arr) - 1
                ans = -1
                while left <= right:
                    mid = left + (right - left) // 2
                    if arr[mid] <= target:
                        ans = mid
                        left = mid + 1
                    else:
                        right = mid - 1
                return ans


            class SolutionP162:
                def findPeakElement(self, nums: list[int]) -> int:
                    n = len(nums)
                    if n == 1:
                        return 0
                    if nums[0] > nums[1]:
                        return 0
                    if nums[-1] > nums[-2]:
                        return n - 1

                    left, right = 1, n - 2
                    while left <= right:
                        mid = left + (right - left) // 2
                        if nums[mid] > nums[mid - 1] and nums[mid] > nums[mid + 1]:
                            return mid
                        if nums[mid] < nums[mid + 1]:
                            left = mid + 1
                        else:
                            right = mid - 1

                    return -1
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P493 翻转对

            原 Java 代码使用的是“归并排序 + 跨区间统计”。

            为什么能这么做？

            - 递归到某一层时，左右两半都已经有序
            - 统计 `nums[i] > 2 * nums[j]` 时，可以让右指针单调移动
            - 统计完成后再执行正常的 merge

            这类题和“小和问题”“逆序对问题”是同一套分治骨架。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP493:
                def reversePairs(self, nums: list[int]) -> int:
                    if len(nums) < 2:
                        return 0
                    temp = [0] * len(nums)
                    return self._sort_and_count(nums, 0, len(nums) - 1, temp)

                def _sort_and_count(self, nums: list[int], left: int, right: int, temp: list[int]) -> int:
                    if left >= right:
                        return 0

                    mid = left + (right - left) // 2
                    count = self._sort_and_count(nums, left, mid, temp)
                    count += self._sort_and_count(nums, mid + 1, right, temp)

                    j = mid + 1
                    for i in range(left, mid + 1):
                        while j <= right and nums[i] > 2 * nums[j]:
                            j += 1
                        count += j - (mid + 1)

                    i, j, k = left, mid + 1, left
                    while i <= mid and j <= right:
                        if nums[i] <= nums[j]:
                            temp[k] = nums[i]
                            i += 1
                        else:
                            temp[k] = nums[j]
                            j += 1
                        k += 1

                    while i <= mid:
                        temp[k] = nums[i]
                        i += 1
                        k += 1

                    while j <= right:
                        temp[k] = nums[j]
                        j += 1
                        k += 1

                    for k in range(left, right + 1):
                        nums[k] = temp[k]

                    return count


            SolutionP493().reversePairs([1, 3, 2, 3, 1])
            """
        ).strip()
        + "\n"
    ),
    md(
        dedent(
            """
            ## P912 排序数组

            原 Java 文件里通过外部 `MergeSort`、`QuickSort` 对同一组随机数组做了结果比对。
            这里为了更贴近 LeetCode Python 提交场景，直接给出一个稳定的归并排序版本。

            如果后面你希望，我也可以继续补一版“随机快排 notebook”。
            """
        ).strip()
        + "\n"
    ),
    code(
        dedent(
            """
            class SolutionP912:
                def sortArray(self, nums: list[int]) -> list[int]:
                    if len(nums) < 2:
                        return nums
                    temp = [0] * len(nums)
                    self._merge_sort(nums, 0, len(nums) - 1, temp)
                    return nums

                def _merge_sort(self, nums: list[int], left: int, right: int, temp: list[int]) -> None:
                    if left >= right:
                        return
                    mid = left + (right - left) // 2
                    self._merge_sort(nums, left, mid, temp)
                    self._merge_sort(nums, mid + 1, right, temp)
                    self._merge(nums, left, mid, right, temp)

                def _merge(self, nums: list[int], left: int, mid: int, right: int, temp: list[int]) -> None:
                    i, j, k = left, mid + 1, left
                    while i <= mid and j <= right:
                        if nums[i] <= nums[j]:
                            temp[k] = nums[i]
                            i += 1
                        else:
                            temp[k] = nums[j]
                            j += 1
                        k += 1

                    while i <= mid:
                        temp[k] = nums[i]
                        i += 1
                        k += 1

                    while j <= right:
                        temp[k] = nums[j]
                        j += 1
                        k += 1

                    for idx in range(left, right + 1):
                        nums[idx] = temp[idx]


            SolutionP912().sortArray([5, 2, 3, 1])
            """
        ).strip()
        + "\n"
    ),
]
trie_cells = []


def main() -> None:
    write_notebook("00_index.ipynb", index_cells)
    write_notebook("01_linked_list.ipynb", linked_list_cells)
    write_notebook("02_binary_tree_traversal.ipynb", binary_tree_cells)
    write_notebook("03_stack_queue_design.ipynb", stack_queue_cells)
    write_notebook("04_binary_search_and_sort.ipynb", binary_search_sort_cells)
    write_notebook("05_trie.ipynb", trie_cells)


if __name__ == "__main__":
    main()

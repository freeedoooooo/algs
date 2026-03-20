# 中国大陆算法面试高频 LeetCode Top 100

说明：

- 这份表格只保留 LeetCode 平台题目
- 题目筛选以中国大陆互联网算法面试的常见刷题顺序为目标
- `重复` 列表示该题是否已经出现在你当前的 [TASK_LIST.md](D:/PROJECT/Project_HU/freeedoooooo/algs/leetcode-python/TASK_LIST.md) 中
- 优先级用于刷题顺序建议：`🔴 高 / 🟡 中 / ⚪ 低`

来源参考：

- 力扣官方热题100：https://leetcode.cn/studyplan/top-100-liked/
- 力扣官方面试经典150：https://leetcode.cn/studyplan/top-interview-150/
- CodeTop 开源仓库：https://github.com/afatcoder/LeetcodeTop
- 力扣讨论整理：https://leetcode.cn/discuss/comment/YUmrqP/793lKv/

| 序号 | 优先级 | 状态 | 重复 | 题号 | 题目英文名 | 题目中文名 | 题型 | 题目内容简单描述 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 🔴 高 |  |  | p001 | Two Sum | 两数之和 | 哈希表 | 在数组中找出和为目标值的两个数下标 |
| 2 | 🔴 高 |  | 是 | p002 | Add Two Numbers | 两数相加 | 链表 | 两个逆序链表表示整数，返回它们相加后的结果链表 |
| 3 | 🔴 高 |  |  | p003 | Longest Substring Without Repeating Characters | 无重复字符的最长子串 | 滑动窗口 | 求不含重复字符的最长子串长度 |
| 4 | 🟡 中 |  |  | p004 | Median of Two Sorted Arrays | 寻找两个正序数组的中位数 | 二分查找 | 在两个有序数组中以对数复杂度求中位数 |
| 5 | 🟡 中 |  |  | p005 | Longest Palindromic Substring | 最长回文子串 | 动态规划 / 字符串 | 找到字符串中的最长回文子串 |
| 6 | 🟡 中 |  |  | p008 | String to Integer (atoi) | 字符串转换整数 | 字符串 | 按题目规则把字符串转换成 32 位整数 |
| 7 | 🟡 中 |  |  | p014 | Longest Common Prefix | 最长公共前缀 | 字符串 | 找出字符串数组的最长公共前缀 |
| 8 | 🔴 高 |  |  | p015 | 3Sum | 三数之和 | 哈希 / 双指针 | 找出所有和为 0 且不重复的三元组 |
| 9 | 🔴 高 |  |  | p019 | Remove Nth Node From End of List | 删除链表的倒数第 N 个结点 | 链表 / 双指针 | 删除单链表中倒数第 N 个节点 |
| 10 | 🔴 高 |  |  | p020 | Valid Parentheses | 有效的括号 | 栈 | 判断括号字符串是否合法匹配 |
| 11 | 🔴 高 |  | 是 | p021 | Merge Two Sorted Lists | 合并两个有序链表 | 链表 | 将两个递增链表合并为一个新的递增链表 |
| 12 | 🟡 中 |  |  | p022 | Generate Parentheses | 括号生成 | 回溯 | 生成所有合法括号组合 |
| 13 | 🔴 高 |  |  | p023 | Merge k Sorted Lists | 合并 K 个升序链表 | 链表 / 分治 / 堆 | 合并多条有序链表 |
| 14 | 🟡 中 |  |  | p024 | Swap Nodes in Pairs | 两两交换链表中的节点 | 链表 | 每两个节点为一组交换位置 |
| 15 | 🔴 高 |  |  | p025 | Reverse Nodes in k-Group | K 个一组翻转链表 | 链表 | 每 k 个节点为一组进行翻转 |
| 16 | 🔴 高 |  |  | p031 | Next Permutation | 下一个排列 | 双指针 / 贪心 | 原地求字典序下一个更大的排列 |
| 17 | 🟡 中 |  |  | p032 | Longest Valid Parentheses | 最长有效括号 | 动态规划 / 栈 | 求最长合法括号子串长度 |
| 18 | 🔴 高 |  |  | p033 | Search in Rotated Sorted Array | 搜索旋转排序数组 | 二分查找 | 在旋转有序数组中查找目标值 |
| 19 | 🟡 中 |  |  | p034 | Find First and Last Position of Element in Sorted Array | 在排序数组中查找元素的第一个和最后一个位置 | 二分查找 | 找出目标值的左右边界 |
| 20 | 🟡 中 |  |  | p039 | Combination Sum | 组合总和 | 回溯 | 找出所有和为目标值的组合 |
| 21 | 🟡 中 |  |  | p041 | First Missing Positive | 缺失的第一个正数 | 哈希 / 原地置换 | 在线性时间内找出缺失的最小正整数 |
| 22 | 🔴 高 |  |  | p042 | Trapping Rain Water | 接雨水 | 栈 / 双指针 | 计算柱状图能接多少雨水 |
| 23 | ⚪ 低 |  |  | p043 | Multiply Strings | 字符串相乘 | 字符串 / 模拟 | 实现大整数字符串相乘 |
| 24 | 🔴 高 |  |  | p046 | Permutations | 全排列 | 回溯 | 生成数组的所有排列 |
| 25 | 🟡 中 |  |  | p048 | Rotate Image | 旋转图像 | 矩阵 | 原地旋转二维矩阵 |
| 26 | 🔴 高 |  |  | p053 | Maximum Subarray | 最大子数组和 | 动态规划 | 求连续子数组最大和 |
| 27 | 🟡 中 |  |  | p054 | Spiral Matrix | 螺旋矩阵 | 矩阵 | 按螺旋顺序输出矩阵元素 |
| 28 | 🔴 高 |  |  | p056 | Merge Intervals | 合并区间 | 排序 | 合并所有重叠区间 |
| 29 | 🟡 中 |  |  | p062 | Unique Paths | 不同路径 | 动态规划 | 统计从左上到右下的路径数量 |
| 30 | 🟡 中 |  |  | p064 | Minimum Path Sum | 最小路径和 | 动态规划 | 求网格中从左上到右下的最小路径和 |
| 31 | 🟡 中 |  |  | p069 | Sqrt(x) | x 的平方根 | 二分查找 | 计算整数平方根 |
| 32 | 🔴 高 |  |  | p070 | Climbing Stairs | 爬楼梯 | 动态规划 | 求爬到楼顶的不同方法数 |
| 33 | 🔴 高 |  |  | p072 | Edit Distance | 编辑距离 | 动态规划 | 求两个字符串的最小编辑次数 |
| 34 | 🔴 高 |  |  | p076 | Minimum Window Substring | 最小覆盖子串 | 滑动窗口 | 找到包含目标串所有字符的最短子串 |
| 35 | 🟡 中 |  |  | p078 | Subsets | 子集 | 回溯 | 生成一个集合的所有子集 |
| 36 | 🟡 中 |  |  | p079 | Word Search | 单词搜索 | 回溯 / DFS | 在二维网格中判断单词是否存在 |
| 37 | 🟡 中 |  |  | p082 | Remove Duplicates from Sorted List II | 删除排序链表中的重复元素 II | 链表 | 删除所有重复值节点，仅保留不重复节点 |
| 38 | 🟡 中 |  |  | p088 | Merge Sorted Array | 合并两个有序数组 | 数组 / 双指针 | 原地合并两个有序数组 |
| 39 | 🟡 中 |  |  | p092 | Reverse Linked List II | 反转链表 II | 链表 | 反转链表指定区间 |
| 40 | 🟡 中 |  |  | p093 | Restore IP Addresses | 复原 IP 地址 | 回溯 | 从字符串中恢复所有合法 IP 地址 |
| 41 | 🔴 高 |  | 是 | p094 | Binary Tree Inorder Traversal | 二叉树的中序遍历 | 二叉树遍历 | 按左根右顺序遍历二叉树 |
| 42 | 🔴 高 |  |  | p098 | Validate Binary Search Tree | 验证二叉搜索树 | 二叉树 / BST | 判断一棵树是否为合法 BST |
| 43 | 🟡 中 |  |  | p101 | Symmetric Tree | 对称二叉树 | 二叉树 | 判断二叉树是否轴对称 |
| 44 | 🔴 高 |  |  | p102 | Binary Tree Level Order Traversal | 二叉树的层序遍历 | BFS | 按层遍历二叉树 |
| 45 | 🔴 高 |  |  | p103 | Binary Tree Zigzag Level Order Traversal | 二叉树的锯齿形层序遍历 | BFS | 按之字形顺序层序遍历 |
| 46 | 🔴 高 |  |  | p104 | Maximum Depth of Binary Tree | 二叉树的最大深度 | 二叉树 | 求二叉树最大深度 |
| 47 | 🔴 高 |  |  | p105 | Construct Binary Tree from Preorder and Inorder Traversal | 从前序与中序遍历序列构造二叉树 | 二叉树 / 递归 | 根据前序和中序序列重建二叉树 |
| 48 | 🟡 中 |  |  | p110 | Balanced Binary Tree | 平衡二叉树 | 二叉树 | 判断二叉树是否平衡 |
| 49 | 🟡 中 |  |  | p112 | Path Sum | 路径总和 | 二叉树 | 判断是否存在根到叶路径和等于目标值 |
| 50 | 🟡 中 |  |  | p113 | Path Sum II | 路径总和 II | 二叉树 / 回溯 | 返回所有满足目标和的根到叶路径 |
| 51 | 🔴 高 |  |  | p121 | Best Time to Buy and Sell Stock | 买卖股票的最佳时机 | 动态规划 | 只能交易一次时求最大利润 |
| 52 | 🟡 中 |  |  | p122 | Best Time to Buy and Sell Stock II | 买卖股票的最佳时机 II | 动态规划 / 贪心 | 可多次交易时求最大利润 |
| 53 | 🔴 高 |  |  | p124 | Binary Tree Maximum Path Sum | 二叉树中的最大路径和 | 二叉树 / DFS | 求二叉树中的最大路径和 |
| 54 | 🟡 中 |  |  | p128 | Longest Consecutive Sequence | 最长连续序列 | 哈希表 | 求数组中最长连续序列长度 |
| 55 | ⚪ 低 |  |  | p129 | Sum Root to Leaf Numbers | 求根到叶节点数字之和 | 二叉树 / DFS | 计算所有根到叶路径表示数字之和 |
| 56 | 🟡 中 |  |  | p136 | Single Number | 只出现一次的数字 | 位运算 | 找到只出现一次的元素 |
| 57 | 🟡 中 |  | 是 | p138 | Copy List with Random Pointer | 复制带随机指针的链表 | 链表 | 深拷贝带随机指针的复杂链表 |
| 58 | 🔴 高 |  |  | p141 | Linked List Cycle | 环形链表 | 链表 / 快慢指针 | 判断链表是否有环 |
| 59 | 🔴 高 |  | 是 | p142 | Linked List Cycle II | 环形链表 II | 链表 / 快慢指针 | 返回链表入环的第一个节点 |
| 60 | 🟡 中 |  |  | p143 | Reorder List | 重排链表 | 链表 | 按指定规则重排链表 |
| 61 | 🟡 中 |  | 是 | p144 | Binary Tree Preorder Traversal | 二叉树的前序遍历 | 二叉树遍历 | 按根左右顺序遍历二叉树 |
| 62 | 🔴 高 |  |  | p146 | LRU Cache | LRU 缓存 | 设计 / 哈希 / 双向链表 | 设计最近最少使用缓存 |
| 63 | 🟡 中 |  | 是 | p148 | Sort List | 排序链表 | 链表 / 归并排序 | 在 `O(n log n)` 时间内排序链表 |
| 64 | 🟡 中 |  |  | p151 | Reverse Words in a String | 翻转字符串里的单词 | 字符串 | 翻转句子中的单词顺序 |
| 65 | 🟡 中 |  |  | p153 | Find Minimum in Rotated Sorted Array | 寻找旋转排序数组中的最小值 | 二分查找 | 在旋转有序数组中找最小值 |
| 66 | 🔴 高 |  | 是 | p155 | Min Stack | 最小栈 | 栈 | 支持常数时间获取最小值的栈 |
| 67 | 🔴 高 |  | 是 | p160 | Intersection of Two Linked Lists | 相交链表 | 链表 | 找到两个链表开始相交的节点 |
| 68 | 🟡 中 |  | 是 | p162 | Find Peak Element | 寻找峰值 | 二分查找 | 用对数时间找到任意一个峰值位置 |
| 69 | ⚪ 低 |  |  | p169 | Majority Element | 多数元素 | 哈希 / 摩尔投票 | 找出数组中出现次数超过一半的元素 |
| 70 | ⚪ 低 |  |  | p179 | Largest Number | 最大数 | 排序 / 贪心 | 重新排列数组使其组成最大的数字 |
| 71 | 🔴 高 |  |  | p198 | House Robber | 打家劫舍 | 动态规划 | 不能偷相邻房屋时求最大收益 |
| 72 | 🟡 中 |  |  | p199 | Binary Tree Right Side View | 二叉树的右视图 | 二叉树 / BFS | 返回从右侧观察二叉树时能看到的节点值 |
| 73 | 🔴 高 |  |  | p200 | Number of Islands | 岛屿数量 | DFS / BFS | 统计网格中的岛屿数量 |
| 74 | 🔴 高 |  | 是 | p206 | Reverse Linked List | 反转链表 | 链表 | 原地反转单链表 |
| 75 | 🔴 高 |  |  | p215 | Kth Largest Element in an Array | 数组中的第 K 个最大元素 | 堆 / 快速选择 | 找到数组中第 K 大元素 |
| 76 | 🟡 中 |  |  | p221 | Maximal Square | 最大正方形 | 动态规划 | 找到只包含 `1` 的最大正方形面积 |
| 77 | 🟡 中 |  |  | p227 | Basic Calculator II | 基本计算器 II | 栈 / 字符串 | 计算只含加减乘除的表达式 |
| 78 | 🟡 中 |  | 是 | p232 | Implement Queue using Stacks | 用栈实现队列 | 栈与队列设计 | 用两个栈实现队列 |
| 79 | 🟡 中 |  | 是 | p234 | Palindrome Linked List | 回文链表 | 链表 / 快慢指针 | 判断链表是否为回文结构 |
| 80 | 🔴 高 |  |  | p236 | Lowest Common Ancestor of a Binary Tree | 二叉树的最近公共祖先 | 二叉树 | 找到两个节点的最近公共祖先 |
| 81 | 🔴 高 |  |  | p239 | Sliding Window Maximum | 滑动窗口最大值 | 单调队列 | 求每个滑动窗口中的最大值 |
| 82 | 🟡 中 |  |  | p240 | Search a 2D Matrix II | 搜索二维矩阵 II | 矩阵 / 搜索 | 在行列都递增的矩阵中查找目标值 |
| 83 | 🟡 中 |  |  | p297 | Serialize and Deserialize Binary Tree | 二叉树的序列化与反序列化 | 二叉树 / 设计 | 设计二叉树的序列化与反序列化方案 |
| 84 | 🔴 高 |  |  | p300 | Longest Increasing Subsequence | 最长递增子序列 | 动态规划 / 二分 | 求数组的最长递增子序列长度 |
| 85 | 🔴 高 |  |  | p322 | Coin Change | 零钱兑换 | 动态规划 | 求凑成目标金额所需的最少硬币数 |
| 86 | 🔴 高 |  |  | p347 | Top K Frequent Elements | 前 K 个高频元素 | 堆 / 桶排序 / 哈希 | 返回数组中出现频率最高的前 K 个元素 |
| 87 | 🟡 中 |  |  | p394 | Decode String | 字符串解码 | 栈 / 字符串 | 解码形如 `3[a2[c]]` 的字符串 |
| 88 | 🟡 中 |  |  | p415 | Add Strings | 字符串相加 | 字符串 | 计算两个非负整数字符串之和 |
| 89 | ⚪ 低 |  |  | p426 | Convert Binary Search Tree to Sorted Doubly Linked List | 将二叉搜索树转化为排序的双向链表 | BST | 将 BST 原地转换为有序循环双向链表 |
| 90 | ⚪ 低 |  |  | p468 | Validate IP Address | 验证 IP 地址 | 字符串 | 判断输入是 IPv4、IPv6 还是非法地址 |
| 91 | ⚪ 低 |  |  | p470 | Implement Rand10() Using Rand7() | 用 Rand7() 实现 Rand10() | 数学 / 概率 | 用已有随机函数实现新的随机分布 |
| 92 | 🟡 中 |  |  | p543 | Diameter of Binary Tree | 二叉树的直径 | 二叉树 | 求二叉树任意两点路径的最大长度 |
| 93 | 🔴 高 |  |  | p560 | Subarray Sum Equals K | 和为 K 的子数组 | 前缀和 / 哈希 | 统计和等于 K 的连续子数组个数 |
| 94 | 🟡 中 |  |  | p695 | Max Area of Island | 岛屿的最大面积 | DFS / BFS | 求网格中最大岛屿面积 |
| 95 | ⚪ 低 |  |  | p704 | Binary Search | 二分查找 | 二分查找 | 在有序数组中查找目标值 |
| 96 | ⚪ 低 |  |  | p718 | Maximum Length of Repeated Subarray | 最长重复子数组 | 动态规划 | 求两个数组的最长公共连续子数组长度 |
| 97 | 🟡 中 |  |  | p739 | Daily Temperatures | 每日温度 | 单调栈 | 求每一天距离下一个更高温度的天数 |
| 98 | 🟡 中 |  | 是 | p912 | Sort an Array | 排序数组 | 排序 | 对整数数组进行排序 |
| 99 | 🟡 中 |  |  | p958 | Check Completeness of a Binary Tree | 二叉树的完全性检验 | 二叉树 / BFS | 判断一棵树是否为完全二叉树 |
| 100 | 🟡 中 |  |  | p1143 | Longest Common Subsequence | 最长公共子序列 | 动态规划 | 求两个字符串的最长公共子序列长度 |

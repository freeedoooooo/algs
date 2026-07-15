# 字符串专项路线图

说明：

- 这份路线图用于补充 `TOP100` 之外但很有学习价值的字符串算法题
- 重点不是把字符串题“刷完”，而是建立一套能迁移的字符串算法知识结构
- 当前路线按中国大陆常见算法面试的准备节奏来设计：先主线高频，再专项补强，再进阶算法

---

## 一、推荐学习顺序

### 阶段 1：字符串基础处理

目标：

- 熟悉双指针、模拟、基础匹配
- 先把最常见的字符串题写顺

建议顺序：

1. `p028` `Find the Index of the First Occurrence in a String`
2. `p415` `Add Strings`
3. `p151` `Reverse Words in a String`
4. `p008` `String to Integer (atoi)`

### 阶段 2：滑动窗口与子串问题

目标：

- 建立“窗口扩张 / 收缩 / 计数器”的统一思维

建议顺序：

1. `p003` `Longest Substring Without Repeating Characters`
2. `p076` `Minimum Window Substring`
3. `p438` `Find All Anagrams in a String`
4. `p567` `Permutation in String`

### 阶段 3：回文专题

目标：

- 掌握中心扩展
- 理解回文类题目的常见状态设计

建议顺序：

1. `p005` `Longest Palindromic Substring`
2. `p125` `Valid Palindrome`
3. `p647` `Palindromic Substrings`
4. `p214` `Shortest Palindrome`

### 阶段 4：KMP 与前后缀体系

目标：

- 真正理解 `next` 数组 / 失配回退 / 最长相等前后缀

建议顺序：

1. `p028` `Find the Index of the First Occurrence in a String`
2. `p459` `Repeated Substring Pattern`
3. `p1392` `Longest Happy Prefix`
4. `p214` `Shortest Palindrome`

### 阶段 5：Trie 与前缀树专题

目标：

- 理解前缀共享结构
- 熟悉插入、查询、计数、删除

建议顺序：

1. `p208` `Implement Trie (Prefix Tree)`
2. `p211` `Design Add and Search Words Data Structure`
3. `p1804` `Implement Trie II (Prefix Tree)`
4. `p212` `Word Search II`

### 阶段 6：字符串哈希 / Rabin-Karp / 模式匹配扩展

目标：

- 知道除了 KMP 以外，还有什么匹配思路
- 会做“快速比较子串”和“重复模式”类问题

建议顺序：

1. `p686` `Repeated String Match`
2. `p187` `Repeated DNA Sequences`
3. `p1044` `Longest Duplicate Substring`

### 阶段 7：高级字符串算法了解向

目标：

- 了解但不一定要求面试现场手写
- 建立完整知识地图

建议专题：

1. `Manacher`
2. `AC 自动机`
3. `Suffix Array / Suffix Automaton`

---

## 二、专项题表

| 序号 | 模块 | 题号 | 题目英文名 | 题目中文名 | 推荐算法 | 为什么值得补 | 实际场景举例 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 基础匹配 | p028 | Find the Index of the First Occurrence in a String | 找出字符串中第一个匹配项的下标 | KMP / 双指针 | 这是最经典的字符串匹配入口题，也是学习 KMP 最自然的起点 | 对应日志关键字匹配、敏感词扫描、编辑器查找功能 |
| 2 | 基础模拟 | p415 | Add Strings | 字符串相加 | 模拟 | 字符串逐位处理是基础能力，适合练细节和边界 | 对应金额字段累加、长数字串计算 |
| 3 | 基础清洗 | p151 | Reverse Words in a String | 翻转字符串里的单词 | 双指针 / 字符串 | 很适合训练空格处理、切分和重组 | 对应搜索词规范化、文本预处理 |
| 4 | 基础解析 | p008 | String to Integer (atoi) | 字符串转换整数 | 模拟 / 字符串 | 面试里经常拿来考边界处理能力 | 对应命令行参数解析、配置输入清洗 |
| 5 | 滑动窗口 | p003 | Longest Substring Without Repeating Characters | 无重复字符的最长子串 | 滑动窗口 | 这是滑动窗口最标准的入门题，必须熟练 | 对应连续会话去重、流式唯一窗口分析 |
| 6 | 滑动窗口 | p076 | Minimum Window Substring | 最小覆盖子串 | 滑动窗口 | 滑动窗口进阶核心题，能训练计数器维护能力 | 对应最短命中日志片段、最小覆盖搜索片段 |
| 7 | 滑动窗口 | p438 | Find All Anagrams in a String | 找到字符串中所有字母异位词 | 滑动窗口 / 计数数组 | 适合巩固固定窗口与字符计数差分 | 对应模板命中检测、乱序词匹配 |
| 8 | 滑动窗口 | p567 | Permutation in String | 字符串的排列 | 滑动窗口 | 和 p438 很接近，能形成窗口题组 | 对应权限串匹配、模式出现判断 |
| 9 | 回文 | p005 | Longest Palindromic Substring | 最长回文子串 | 中心扩展 / DP | 回文问题第一题，覆盖面很广 | 对应文本对称片段提取、序列模式分析 |
| 10 | 回文 | p125 | Valid Palindrome | 验证回文串 | 双指针 | 回文基础校验题，适合练字符串双指针 | 对应输入清洗后对称性验证 |
| 11 | 回文 | p647 | Palindromic Substrings | 回文子串 | 中心扩展 / DP | 能帮助把“找最长”升级为“统计全部” | 对应文本模式统计、对称片段计数 |
| 12 | 回文 / KMP | p214 | Shortest Palindrome | 最短回文串 | KMP / 回文前缀 | 这题能把 KMP 和回文前缀联系起来，非常适合进阶 | 对应最短对称补全、特殊编码拼接 |
| 13 | KMP | p028 | Find the Index of the First Occurrence in a String | 找出字符串中第一个匹配项的下标 | KMP | KMP 最标准模板题，必须掌握 | 对应大文本中快速查找模式串 |
| 14 | KMP | p459 | Repeated Substring Pattern | 重复的子字符串 | KMP / 前后缀 | 很适合理解前后缀相等与周期性判断 | 对应周期串识别、重复模式检测 |
| 15 | KMP | p1392 | Longest Happy Prefix | 最长快乐前缀 | KMP / 前后缀 | 直接考最长相等前后缀，是理解 `next` 的好题 | 对应公共边界串提取、签名前缀匹配 |
| 16 | Trie | p208 | Implement Trie (Prefix Tree) | 实现 Trie（前缀树） | Trie | Trie 的入门模板题，必须先会它 | 对应搜索建议、词典前缀匹配 |
| 17 | Trie | p211 | Design Add and Search Words Data Structure | 添加与搜索单词 - 数据结构设计 | Trie / DFS | 在 Trie 基础上加入通配符搜索，是很好的进阶题 | 对应模糊搜索、通配词匹配 |
| 18 | Trie | p1804 | Implement Trie II (Prefix Tree) | 实现 Trie II（前缀树） | Trie / 计数 | 比普通 Trie 更贴近真实工程，加入计数与删除 | 对应搜索提示词计数、热词前缀统计 |
| 19 | Trie + 回溯 | p212 | Word Search II | 单词搜索 II | Trie / DFS / 回溯 | 这是 Trie 与网格搜索的代表题，综合性强 | 对应字典匹配、网格文本识别 |
| 20 | 字符串哈希 | p686 | Repeated String Match | 重复叠加字符串匹配 | 字符串匹配 / KMP / 哈希 | 适合比较不同匹配算法的优劣 | 对应重复模板拼接后的模式检查 |
| 21 | 字符串哈希 | p187 | Repeated DNA Sequences | 重复的 DNA 序列 | 哈希 / 位编码 | 很适合入门滚动哈希和定长窗口编码 | 对应生物序列重复片段识别 |
| 22 | 字符串哈希 | p1044 | Longest Duplicate Substring | 最长重复子串 | 二分 + 哈希 | 这是字符串哈希的代表性进阶题 | 对应重复片段压缩、文本重复检测 |
| 23 | 多模式匹配 | p1408 | String Matching in an Array | 数组中的字符串匹配 | 暴力 / KMP | 虽不一定必须 KMP，但很适合练字符串包含判断 | 对应关键字集合中的冗余规则清理 |

---

## 三、为什么 KMP 不在主 Top100 里

主要原因不是它不重要，而是：

- 在中国大陆常规算法面试里，直接要求手写完整 KMP 的频率不如链表、树、DFS/BFS、二分、DP、滑动窗口高
- 很多面试官更常考“字符串匹配问题”，但未必强制要求用 KMP
- 如果基础主线还没刷完，优先继续补主线高频题，收益通常更高

但如果你准备的是：

- 更偏基础算法的笔试
- 对字符串算法更敏感的团队
- 或者你想把算法知识体系补完整

那 KMP、Trie、字符串哈希都是非常值得单独补掉的一块。

---

## 四、进阶算法了解向

这些内容建议在主线和专项题做完后再补，不建议放在前面：

### 1. Manacher

- 用途：在线性时间内求最长回文子串
- 适用：当你已经理解中心扩展，但想进一步补齐回文算法体系
- 现实类比：大文本中快速找对称模式片段

### 2. AC 自动机

- 用途：多模式串同时匹配
- 适用：当你已经掌握 Trie，并想解决“一次扫描匹配多个关键词”
- 现实类比：敏感词过滤、规则词库扫描、日志多关键词告警

### 3. Suffix Array / Suffix Automaton

- 用途：处理后缀、重复子串、子串排名等复杂问题
- 适用：更偏竞赛或高级算法岗位准备
- 现实类比：大规模文本索引、重复片段统计、搜索底层结构理解

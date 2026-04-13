# 克隆Random链表

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：06 链表相关面试题
- 原始条目：☒ 克隆Random链表

## 一句话结论
Random 链表比普通链表多了一条 `random` 指针，所以克隆时不能只复制 `next`，还要完整复制节点之间的随机指向关系。
最直观的做法是用哈希表保存“原节点 -> 新节点”的映射，进一步优化则是把拷贝节点直接穿插进原链表中，用结构本身替代哈希表，把额外空间降到 `O(1)`。

## 核心知识点
- 这题难点不在复制节点值，而在复制 `random` 指针指向的拓扑关系。
- 哈希表版的核心是先建立映射，再统一补 `next` 和 `random`。
- 原地穿插版的核心是让“原节点的复制节点”始终紧挨在原节点后面，从而等效得到映射关系。
- 面试高频要求通常是：时间复杂度 `O(N)`，额外空间复杂度 `O(1)`。

## 图片转写 / 题意还原
原图内容可以整理为：

- 常见面试题
- 有一种特殊的单链表节点：

```java
class Node {
    int value;
    Node next;
    Node rand;
}
```

- `rand` 指针是单链表节点结构中新增的指针，可能指向链表中的任意一个节点，也可能指向 `null`
- 现在给定这类无环链表的头节点 `head`
- 要实现一个函数，完成整条链表的复制，并返回复制后新链表的头节点
- 要求：
  - 时间复杂度 `O(N)`
  - 额外空间复杂度 `O(1)`

这说明哈希表版是容易想到的入门写法，而面试真正想听到的是原地优化版。

## 图解
以链表：

```text
A -> B -> C
```

且：

```text
A.random -> C
B.random -> A
C.random -> null
```

为例，原地穿插版可以画成：

### 第 1 步：每个原节点后面插入复制节点

```text
A -> A' -> B -> B' -> C -> C'
```

这时天然有：

```text
A 的复制 = A'
B 的复制 = B'
C 的复制 = C'
```

### 第 2 步：补复制节点的 random

```text
A.random  = C    => A'.random = C'
B.random  = A    => B'.random = A'
C.random  = null => C'.random = null
```

### 第 3 步：拆分成两条链表

```text
原链表：A  -> B  -> C
新链表：A' -> B' -> C'
```

理解重点：

```text
原节点的复制节点永远就在它 next 的位置
```

## 解题思路
### 1. 版本 1：哈希表版
最容易想到的方式是：

1. 第一遍：为每个原节点创建一个新节点，并存入映射表  
   `map.put(oldNode, newNode)`
2. 第二遍：根据原节点的 `next` / `random`，到映射表里找到对应的新节点并连接
3. 返回 `map.get(head)`

优点：

- 思路直接
- 代码容易写对

缺点：

- 需要 `O(N)` 额外空间

### 2. 版本 2：原地穿插版
为了去掉哈希表，可以让映射关系“长在链表结构里”。

第一遍遍历时，把每个复制节点插到原节点后面：

```text
1 -> 2 -> 3
```

变成：

```text
1 -> 1' -> 2 -> 2' -> 3 -> 3'
```

于是天然就有了映射关系：

```text
原节点 cur 的复制节点 = cur.next
```

### 3. 利用穿插结构设置 random
如果原节点 `cur.random = R`，那么：

- 原节点 `cur` 的复制节点是 `cur.next`
- 原节点 `R` 的复制节点是 `R.next`

所以可以直接写成：

```java
cur.next.random = cur.random != null ? cur.random.next : null;
```

这就是原地版最巧的地方。

### 4. 最后拆分出新旧链表
第三遍遍历时，把交错在一起的链表拆开：

- 原链表重新串回去
- 新链表单独串出来

拆完之后：

- 原链表恢复原状
- 新链表就是完整复制结果

## 典型例子
假设有链表：

```text
A -> B -> C
```

并且：

- `A.random = C`
- `B.random = A`
- `C.random = null`

### 第一步：穿插复制节点

```text
A -> A' -> B -> B' -> C -> C'
```

### 第二步：设置复制节点的 random

- `A'.random = C'`
- `B'.random = A'`
- `C'.random = null`

### 第三步：拆分
原链表恢复为：

```text
A -> B -> C
```

新链表为：

```text
A' -> B' -> C'
```

并且 `random` 指向关系完全对应。

## 复杂度
- 时间复杂度：
  - 哈希表版：`O(N)`
  - 原地穿插版：`O(N)`
- 空间复杂度：
  - 哈希表版：`O(N)`
  - 原地穿插版：`O(1)`

## 易错点
- 复制的不是值，而是整套指针关系；`random` 不能直接指回原链表节点。
- 原地版第二轮设置 `random` 时，要注意 `cur.random` 可能为 `null`。
- 最后一轮拆分新旧链表时，`next` 指针非常容易接错。
- 如果忘了把原链表恢复，最后得到的结构往往是“新旧节点交错混在一起”。

## 代码 / 伪代码
仓库中的对应实现：

- [CopyListWithRandomPointer.java](../../../solutions-java/leetcode/p138_copy_list_with_random_pointer/CopyListWithRandomPointer.java)

这份代码实现的是原地穿插版，并且分成了 3 次遍历：

### 第一次遍历：插入复制节点

```java
while (cur != null) {
    next = cur.next;
    cur.next = new Node(cur.val);
    cur.next.next = next;
    cur = next;
}
```

### 第二次遍历：设置复制节点的 random

```java
copy = cur.next;
copy.random = cur.random != null ? cur.random.next : null;
```

### 第三次遍历：拆分新旧链表

```java
cur.next = next;
copy.next = next != null ? next.next : null;
```

如果是哈希表版，伪代码可以写成：

```java
Map<Node, Node> map = new HashMap<>();
for (Node cur = head; cur != null; cur = cur.next) {
    map.put(cur, new Node(cur.val));
}
for (Node cur = head; cur != null; cur = cur.next) {
    map.get(cur).next = map.get(cur.next);
    map.get(cur).random = map.get(cur.random);
}
return map.get(head);
```

## 记忆点
- 哈希表版最好想，原地穿插版最好考。
- 原地版最关键的等式：`复制节点 = 原节点.next`。
- 设置 `random` 时，原节点的 `random.next` 就是目标复制节点。
- 整题固定三步：穿插、补 `random`、拆分。

# 给定一颗二叉树的头节点head，返回这颗二叉树中最大的二叉搜索子树的头节点

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：08 二叉树的递归套路
- 原始条目：☒ 给定一颗二叉树的头节点head，返回这颗二叉树中最大的二叉搜索子树的头节点

## 一句话结论
这题的关键，不是暴力判断每棵子树是不是 BST，而是让每棵子树返回一份足够判断“自己能不能整体成为 BST”的信息。
只要同时拿到左右子树的最大值、最小值、最大 BST 大小和最大 BST 头节点，就能在 `O(N)` 时间内得到答案。

## 核心知识点
- 当前节点所在子树的最大 BST 只有 3 种来源：
  - 左树里的最大 BST
  - 右树里的最大 BST
  - 以当前节点为头的整棵树本身就是 BST
- 要判断“当前整棵树是不是 BST”，必须知道：
  - 左树是不是整棵 BST
  - 右树是不是整棵 BST
  - 左树最大值是否小于当前值
  - 右树最小值是否大于当前值
- 所以 `Info` 里通常至少需要：
  - `min`
  - `max`
  - `maxBSTSize`
  - `maxBSTHead`
  - 当前整棵树大小 `allSize` 或者当前整棵树是否整树为 BST 的判断依据

## 图片转写 / 题意还原
原始笔记虽然只有题目名称，但题意是非常典型的综合树题：给定一棵二叉树头节点 `head`，要求返回这棵树中“最大的二叉搜索子树”的头节点。

题目要求：

- 给定一棵普通二叉树
- 在它内部找到“最大的那棵二叉搜索子树”
- 返回这棵最大 BST 的头节点

这里注意：

```text
不是判断整棵树是不是 BST
而是在整棵树里找最大的一棵 BST 子树
```

## 图解
假设树如下：

```text
        6
      /   \
     1     12
          /  \
         10   13
        / \
       4  14
```

这棵树整体不是 BST，因为：

```text
14 在 12 的左子树里
却大于 12
```

但其中以 `10` 为头的这棵子树：

```text
      10
     /  \
    4   14
```

是 BST。

如果它恰好是整棵树里最大的 BST 子树，那么答案就返回节点 `10`。

## 解题思路
### 1. 当前节点答案的可能性
以当前节点 `x` 为头时，最大的 BST 子树只可能来自：

1. 左子树内部
2. 右子树内部
3. 当前整棵树自己就是 BST

这就是这题最核心的分类讨论。

### 2. 判断“当前整棵树是不是 BST”需要什么
如果想让以 `x` 为头的整棵树成为 BST，必须满足：

- 左子树本身是一整棵 BST
- 右子树本身是一整棵 BST
- 左子树最大值 `< x.value`
- 右子树最小值 `> x.value`

所以左右子树至少要返回：

- 最大值
- 最小值
- 它们内部最大的 BST 大小
- 它们内部最大的 BST 头节点
- 它们整棵树大小，方便判断“最大 BST 是否就是整棵左树 / 右树”

### 3. `Info` 设计
一种常见设计是：

```text
min
max
allSize
maxBSTSize
maxBSTHead
```

解释：

- `min/max`：帮助父节点判断 BST 条件
- `allSize`：当前整棵树一共多少节点
- `maxBSTSize`：当前子树内部最大 BST 的大小
- `maxBSTHead`：当前子树内部最大 BST 的头节点

### 4. 递归合并逻辑
对于当前节点 `x`：

1. 先递归拿左右 `Info`
2. 先假设答案来自左或右中更大的那棵 BST
3. 再判断“当前整棵树能否成为 BST”
4. 如果能，当前答案更新为 `x`

伪代码骨架：

```java
Info process(Node x) {
    if (x == null) {
        return null;
    }
    Info leftInfo = process(x.left);
    Info rightInfo = process(x.right);

    int min = x.value;
    int max = x.value;
    int allSize = 1;

    // 更新 min / max / allSize
    // 默认先从左右内部最大BST里选一个
    // 再判断当前整棵树是不是BST

    return new Info(...);
}
```

## 典型例子
看这棵树：

```text
        6
      /   \
     1     12
          /  \
         10   13
        / \
       4  14
```

在节点 `10` 这棵子树上：

- 左最大值 `4 < 10`
- 右最小值 `14 > 10`
- 左右子树本身也都是 BST

所以以 `10` 为头的整棵树是 BST，大小为 3。

在节点 `12` 这棵子树上：

- 左子树里有 `14`
- `14 > 12`
- 破坏了 BST 条件

所以以 `12` 为头的整棵树不是 BST。

此时最大 BST 子树就可能留在左边的 `10` 那棵树里。

## 复杂度
- 时间复杂度：`O(N)`
- 空间复杂度：`O(H)`

其中：

- `N` 是节点数
- `H` 是树高

## 易错点
- 题目要返回的是“最大 BST 子树的头节点”，不是大小本身。
- 判断当前整棵树是不是 BST 时，不能只看左右最大 BST，要看左右整棵树是否本身就是 BST。
- 所以常常需要 `allSize` 来判断：`left.maxBSTSize == left.allSize`。
- `null` 子树在判断 BST 条件时要当成天然合法。
- `min/max` 的更新别漏掉当前节点自身。

## 代码 / 伪代码
仓库里目前没有这一题对应的现成实现文件，这里保留标准伪代码骨架。

```java
class Info {
    int min;
    int max;
    int allSize;
    int maxBSTSize;
    Node maxBSTHead;
}

Info process(Node x) {
    if (x == null) {
        return null;
    }
    Info leftInfo = process(x.left);
    Info rightInfo = process(x.right);

    int min = x.value;
    int max = x.value;
    int allSize = 1;

    if (leftInfo != null) {
        min = Math.min(min, leftInfo.min);
        max = Math.max(max, leftInfo.max);
        allSize += leftInfo.allSize;
    }
    if (rightInfo != null) {
        min = Math.min(min, rightInfo.min);
        max = Math.max(max, rightInfo.max);
        allSize += rightInfo.allSize;
    }

    int p1 = leftInfo == null ? 0 : leftInfo.maxBSTSize;
    int p2 = rightInfo == null ? 0 : rightInfo.maxBSTSize;
    Node head = p1 >= p2 ? (leftInfo == null ? null : leftInfo.maxBSTHead)
                         : (rightInfo == null ? null : rightInfo.maxBSTHead);
    int maxBSTSize = Math.max(p1, p2);

    boolean leftBST = leftInfo == null || leftInfo.maxBSTSize == leftInfo.allSize;
    boolean rightBST = rightInfo == null || rightInfo.maxBSTSize == rightInfo.allSize;
    boolean leftLessX = leftInfo == null || leftInfo.max < x.value;
    boolean rightMoreX = rightInfo == null || rightInfo.min > x.value;

    if (leftBST && rightBST && leftLessX && rightMoreX) {
        head = x;
        maxBSTSize = (leftInfo == null ? 0 : leftInfo.allSize)
                   + (rightInfo == null ? 0 : rightInfo.allSize)
                   + 1;
    }

    return new Info(min, max, allSize, maxBSTSize, head);
}
```

## 记忆点
- 当前答案只看 3 种来源：左、右、整棵自己。
- `Info` 重点字段：`min/max`、`allSize`、`maxBSTSize`、`maxBSTHead`。
- 判断“当前整棵树是 BST”时，要确认左右整棵树本身就是 BST。
- 这是树形 DP 里信息量比较大但非常典型的一题。

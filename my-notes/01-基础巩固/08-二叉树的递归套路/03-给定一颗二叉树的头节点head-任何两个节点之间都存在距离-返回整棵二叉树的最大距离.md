# 给定一颗二叉树的头节点head，任何两个节点之间都存在距离，返回整棵二叉树的最大距离

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：08 二叉树的递归套路
- 原始条目：☒ 给定一颗二叉树的头节点head，任何两个节点之间都存在距离，返回整棵二叉树的最大距离

## 一句话结论
二叉树最大距离题的关键，不是枚举任意两点，而是发现答案只会出现在 3 种情况里：左树内部、右树内部、经过当前节点。
所以每棵子树只需要返回“高度”和“最大距离”两份信息，就能在线性时间内解决。

## 核心知识点
- 树上两点之间的距离，等于路径上经过的节点数或边数，课程里通常按节点数来记。
- 以当前节点 `x` 为头时，最大距离只有 3 种来源：
  - 左子树内部
  - 右子树内部
  - 从左树最深节点经过 `x` 到右树最深节点
- 所以 `Info` 只需要：
  - `height`
  - `maxDistance`
- 这是“先列当前节点答案可能性，再反推 `Info`”的典型题。

## 图片转写 / 题意还原
原始笔记虽然只有题目名称，但题意其实是树形 DP 经典题：给定一棵二叉树头节点 `head`，任意两个节点之间都存在距离，要求返回整棵树的最大距离。

题目要求：

- 给定一棵二叉树
- 任意两个节点之间都存在距离
- 返回整棵树中最大的那个距离

这里通常还默认一个口径问题：

- 距离既可以按“路径上的边数”定义
- 也可以按“路径上的节点数”定义

课程版本一般按“节点数”来记，所以回答这题时最好先把统计口径说清楚。

重点不在“怎么定义距离”，而在于：

```text
最大距离不需要枚举所有节点对
可以在递归返回时顺便求出来
```

## 图解
假设二叉树如下：

```text
        1
      /   \
     2     3
    / \     \
   4   5     6
```

整棵树的最大距离路径是：

```text
4 -> 2 -> 1 -> 3 -> 6
```

如果按节点数记距离，就是：

```text
5
```

对当前节点 `1` 来说，答案可能来自：

### 情况 1：完全在左树里

```text
4 <-> 5
```

### 情况 2：完全在右树里

```text
3 <-> 6
```

### 情况 3：经过当前节点

```text
左树最深点 -> 1 -> 右树最深点
```

这第三种情况的长度就是：

```text
left.height + right.height + 1
```

## 解题思路
### 1. 当前节点的答案有哪些可能
以当前节点 `x` 为头时，最大距离只可能是：

1. 左子树自己的最大距离
2. 右子树自己的最大距离
3. 经过 `x` 的那条路径

这一步一旦看清，题就已经做出来大半。

### 2. 为了算“经过当前节点”的答案，需要什么信息
如果想计算：

```text
左最深点 -> x -> 右最深点
```

那我就必须知道：

- 左子树高度
- 右子树高度

同时，为了和“完全在左边”“完全在右边”的情况比较，我还需要：

- 左子树最大距离
- 右子树最大距离

所以 `Info` 自然就是：

```text
height
maxDistance
```

### 3. 递归函数怎么写
定义：

```java
Info process(Node x)
```

返回：

- 以 `x` 为头的树高度
- 以 `x` 为头的树最大距离

伪代码：

```java
Info process(Node x) {
    if (x == null) {
        return new Info(0, 0);
    }
    Info leftInfo = process(x.left);
    Info rightInfo = process(x.right);

    int height = Math.max(leftInfo.height, rightInfo.height) + 1;
    int p1 = leftInfo.maxDistance;
    int p2 = rightInfo.maxDistance;
    int p3 = leftInfo.height + rightInfo.height + 1;
    int maxDistance = Math.max(Math.max(p1, p2), p3);

    return new Info(height, maxDistance);
}
```

## 典型例子
看这棵树：

```text
    1
   / \
  2   3
 /
4
```

从下往上返回：

- `4`：高度 1，最大距离 1
- `2`：左高 1，右高 0，高度 2，最大距离 max(1, 0, 2) = 2
- `3`：高度 1，最大距离 1
- `1`：左高 2，右高 1，高度 3，最大距离 max(2, 1, 4) = 4

最大路径是：

```text
4 -> 2 -> 1 -> 3
```

按节点数记距离就是 4。

## 复杂度
- 时间复杂度：`O(N)`
- 空间复杂度：`O(H)`

其中：

- `N` 是节点数
- `H` 是树高

## 易错点
- 先明确课程里距离按“节点数”还是“边数”统计，别混。
- 经过当前节点的情况不是 `left.maxDistance + right.maxDistance`，而是 `left.height + right.height + 1`。
- `null` 节点的高度和最大距离通常都返回 0。
- 最大距离不一定经过根节点，但在每个子树里都要考虑“经过当前节点”的情况。

## 代码 / 伪代码
仓库里目前没有这一题对应的现成实现文件，这里保留标准伪代码。

```java
class Info {
    int height;
    int maxDistance;

    Info(int height, int maxDistance) {
        this.height = height;
        this.maxDistance = maxDistance;
    }
}

Info process(Node x) {
    if (x == null) {
        return new Info(0, 0);
    }
    Info leftInfo = process(x.left);
    Info rightInfo = process(x.right);
    int height = Math.max(leftInfo.height, rightInfo.height) + 1;
    int p1 = leftInfo.maxDistance;
    int p2 = rightInfo.maxDistance;
    int p3 = leftInfo.height + rightInfo.height + 1;
    int maxDistance = Math.max(Math.max(p1, p2), p3);
    return new Info(height, maxDistance);
}
```

## 记忆点
- 最大距离只看 3 种情况：左、右、过根。
- `Info` 只要高度和最大距离。
- 过根路径长度 = 左高 + 右高 + 1。
- 这是树形 DP 第二个非常经典的题。

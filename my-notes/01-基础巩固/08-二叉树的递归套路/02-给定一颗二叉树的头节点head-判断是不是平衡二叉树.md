# 给定一颗二叉树的头节点head，判断是不是平衡二叉树

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：08 二叉树的递归套路
- 原始条目：☒ 给定一颗二叉树的头节点head，判断是不是平衡二叉树

## 一句话结论
判断一棵树是不是平衡二叉树，核心不是对每个节点反复求高度，而是让每棵子树一次性返回“自己是否平衡”和“自己高度”。
这样每个节点只处理一次，时间复杂度就能做到 `O(N)`。

## 核心知识点
- 平衡二叉树要求：每个节点的左右子树高度差不超过 1。
- 当前节点是否平衡，只依赖：
  - 左子树是否平衡
  - 右子树是否平衡
  - 左右高度差是否不超过 1
- 所以每棵子树只需要返回两个信息：
  - `isBalanced`
  - `height`
- 这是最标准的树形 DP / `Info` 模型题。

## 图片转写 / 题意还原
原始笔记虽然只有题目名称，但题意很典型：给定一棵二叉树头节点 `head`，判断整棵树是否为平衡二叉树。

题目本质是：

- 给你一棵二叉树
- 判断是否每个节点都满足平衡条件

平衡条件是：

```text
任意节点
左树高度和右树高度差 <= 1
```

## 图解
### 1. 平衡树示例

```text
      1
     / \
    2   3
   /
  4
```

各节点高度差都不超过 1，所以它是平衡树。

### 2. 非平衡树示例

```text
    1
   /
  2
 /
3
```

在节点 `1` 处：

```text
左高 = 2
右高 = 0
高度差 = 2
```

所以不是平衡树。

## 解题思路
### 1. 暴力写法为什么慢
最直观的想法是：

1. 对每个节点分别算左树高度
2. 再算右树高度
3. 判断高度差
4. 再递归去左右子树做同样事情

问题在于：

- 高度会被重复计算很多次
- 最坏情况下会退化到 `O(N^2)`

### 2. 递归套路怎么想
以当前节点 `x` 为头，如果我已经拿到了：

- 左子树的 `Info`
- 右子树的 `Info`

那么我能不能判断 `x` 这棵树是否平衡？

当然可以，因为只需要：

```text
left.isBalanced
right.isBalanced
abs(left.height - right.height) <= 1
```

同时，当前树的高度也能算出来：

```text
height = max(left.height, right.height) + 1
```

于是 `Info` 就自然确定了：

```text
isBalanced
height
```

### 3. 递归函数设计
定义：

```java
Info process(Node x)
```

返回：

- 以 `x` 为头的树是否平衡
- 以 `x` 为头的树高度是多少

伪代码：

```java
Info process(Node x) {
    if (x == null) {
        return new Info(true, 0);
    }
    Info leftInfo = process(x.left);
    Info rightInfo = process(x.right);

    int height = Math.max(leftInfo.height, rightInfo.height) + 1;
    boolean isBalanced = leftInfo.isBalanced
            && rightInfo.isBalanced
            && Math.abs(leftInfo.height - rightInfo.height) <= 1;

    return new Info(isBalanced, height);
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

从下往上返回信息：

- `4`：平衡，高度 1
- `2`：左高 1，右高 0，平衡，高度 2
- `3`：平衡，高度 1
- `1`：左高 2，右高 1，平衡，高度 3

所以整棵树平衡。

再看：

```text
    1
   /
  2
 /
3
```

返回信息：

- `3`：平衡，高度 1
- `2`：平衡，高度 2
- `1`：左高 2，右高 0，高度差 2，不平衡

## 复杂度
- 时间复杂度：`O(N)`
- 空间复杂度：`O(H)`

其中：

- `N` 是节点数
- `H` 是树高

## 易错点
- 平衡条件是“每个节点都满足”，不是只有根节点满足。
- 不要每次都单独去重新算高度，那会重复计算。
- `null` 节点要返回“平衡，高度 0”。
- 当前节点的高度是 `max(left, right) + 1`，别漏掉自己这一层。

## 代码 / 伪代码
仓库里目前没有这一题对应的现成实现文件，这里保留标准伪代码。

```java
class Info {
    boolean isBalanced;
    int height;

    Info(boolean isBalanced, int height) {
        this.isBalanced = isBalanced;
        this.height = height;
    }
}

Info process(Node x) {
    if (x == null) {
        return new Info(true, 0);
    }
    Info leftInfo = process(x.left);
    Info rightInfo = process(x.right);
    int height = Math.max(leftInfo.height, rightInfo.height) + 1;
    boolean isBalanced = leftInfo.isBalanced
            && rightInfo.isBalanced
            && Math.abs(leftInfo.height - rightInfo.height) <= 1;
    return new Info(isBalanced, height);
}
```

## 记忆点
- 平衡树题的 `Info` 只有两个字段：是否平衡、高度。
- 当前节点答案 = 左信息 + 右信息 + 自己做一次判断。
- `null` 返回平衡且高度为 0。
- 这是树形 DP 最标准的入门题。

# 快速排序 2.0（partition返回一个区间）

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：03 归并排序、随机快排
- 原始条目：☒ 快速排序 2.0（partition返回一个区间）

## 一句话结论
快速排序 2.0 的关键升级，是 partition 不再只返回一个 `pivot` 位置，而是直接返回“等于区间”。
这样所有等于 `pivot` 的元素一次性归位，后续递归只处理小于区和大于区，效率比 1.0 更稳。

## 核心知识点
- 快排 2.0 建立在荷兰国旗问题之上。
- partition 后数组被分成三段：小于、等于、大于。
- 返回的是等于区间 `[start, end]`。
- 递归时直接跳过等于区，不再重复处理相同元素。

## 相比 1.0 提升了什么
快排 1.0 的 partition 只返回一个点：

```text
<= pivot | pivot | > pivot
```

如果数组里有很多元素都等于 `pivot`，
它们仍然可能被递归到下一层。

快排 2.0 直接把它们收拢成：

```text
< pivot | = pivot | > pivot
```

然后只递归：

- `< pivot`
- `> pivot`

中间 `= pivot` 这整段都不用再管了。

## 解题思路
### 1. 先选一个 pivot
和快排 1.0 一样，先在区间 `[l...r]` 内选一个划分值。

### 2. 用荷兰国旗问题做 partition
维护三个区域：

```text
小于区 | 等于区 | 未处理区 | 大于区
```

遍历完之后，会直接得到：

```text
[l ... low-1]      < pivot
[low ... high]     = pivot
[high+1 ... r]     > pivot
```

### 3. 只递归两边
因为等于区已经全部到位，
所以后续递归只需处理：

```java
quickSort2(arr, l, pivots[0] - 1);
quickSort2(arr, pivots[1] + 1, r);
```

这里 `pivots[0]` 和 `pivots[1]` 就是等于区间的左右边界。

## 典型例子
数组：

```text
[5, 3, 3, 7, 2, 3, 8]
```

假设：

```text
pivot = 3
```

partition 后会形成：

```text
[2 | 3, 3, 3 | 5, 7, 8]
```

这里最重要的变化是：

- 所有 `3` 都已经集中在一起
- 后续递归完全不用再碰它们

所以接下来只需递归：

- 左边 `[2]`
- 右边 `[5, 7, 8]`

## 为什么这版更推荐
因为在大量重复值场景下：

- 1.0 会反复递归等于 pivot 的元素
- 2.0 直接一次性跳过整段等于区

这会显著减少不必要的递归。

也是因为这个原因，仓库里 `QuickSort.java` 明确标了：

```text
【推荐】荷兰国旗问题
```

## 复杂度
- 平均时间复杂度：`O(N log N)`
- 最坏时间复杂度：`O(N^2)`
- 额外空间复杂度：递归栈平均 `O(log N)`，最坏 `O(N)`

和 1.0 一样，最坏情况仍然可能退化，
只是对重复元素场景更友好。

## 易错点
- partition 返回的是区间，不是单点。
- 递归边界要跳过整个等于区，不能只跳过一个位置。
- `> pivot` 的分支交换后当前位还没检查，指针不能乱动。

## 代码 / 伪代码
仓库里的对应实现：

- [QuickSort.java](../../../solutions-java/practice/algs01_sort/QuickSort.java)

核心框架：

```java
void quickSort2(int[] arr, int l, int r) {
    if (l >= r) {
        return;
    }
    int x = arr[l + (int)(Math.random() * (r - l + 1))];
    int[] pivots = partition2(arr, l, r, x);
    quickSort2(arr, l, pivots[0] - 1);
    quickSort2(arr, pivots[1] + 1, r);
}
```

## 和记忆点
- 2.0：partition 返回一个区间。
- 这个区间就是所有等于 `pivot` 的元素。
- 后续递归只排两边，不排中间。

# 图的拓扑排序算法

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：11 暴力递归
- 原始条目：☒ 图的拓扑排序算法

## 一句话结论
拓扑排序是给有向无环图里的节点安排一个合法顺序，使得每条有向边都满足“起点在前，终点在后”。
最经典写法是基于入度表和队列，不断弹出当前入度为 `0` 的点。

## 核心知识点
- 只适用于有向无环图，简称 DAG。
- 入度为 `0` 的点一定可以排在当前最前面。
- 删除一个点后，要把它邻居的入度减一。
- 如果最终没排完所有点，说明图里有环。

## 图片转写 / 题意还原
原始笔记里明确写了：

- 注意：要求是有向图，且不能有环

这就是拓扑排序最关键的使用前提。

## 图解
图：

```text
课程基础 -> 数据结构
数据结构 -> 图论
算法基础 -> 图论
图论 -> 最短路
```

一个合法拓扑序可以是：

```text
课程基础, 算法基础, 数据结构, 图论, 最短路
```

## 解题思路
### 1. 统计每个点的入度
先做一份 `inMap`。

### 2. 把所有入度为 0 的点进队
这些点当前没有任何前置依赖。

### 3. 反复弹出并删除影响
每弹出一个点：

- 加入答案序列
- 扫它的邻居
- 邻居入度减一
- 哪个邻居减到 `0`，哪个邻居进队

## 复杂度
- 时间复杂度：`O(V + E)`
- 空间复杂度：`O(V)`

## 典型例子
任务依赖：

```text
A -> C
B -> C
C -> D
```

合法顺序可以是：

```text
A, B, C, D
```

或：

```text
B, A, C, D
```

说明拓扑序通常不唯一。

## 易错点
- 拓扑排序不能用于有环图。
- “有向图”还不够，必须是“有向无环图”。
- 拓扑序可能不唯一，题目通常只要返回任意一个合法序即可。

## 代码 / 伪代码
课程标准伪代码：

```java
List<Node> sortedTopology(Graph graph) {
    Map<Node, Integer> inMap = new HashMap<>();
    Queue<Node> zeroInQueue = new LinkedList<>();
    for (Node node : graph.nodes.values()) {
        inMap.put(node, node.in);
        if (node.in == 0) {
            zeroInQueue.add(node);
        }
    }
    List<Node> ans = new ArrayList<>();
    while (!zeroInQueue.isEmpty()) {
        Node cur = zeroInQueue.poll();
        ans.add(cur);
        for (Node next : cur.nexts) {
            inMap.put(next, inMap.get(next) - 1);
            if (inMap.get(next) == 0) {
                zeroInQueue.add(next);
            }
        }
    }
    return ans;
}
```

## 记忆点
- 拓扑排序只用于 DAG。
- 入度为 0 的点先出。
- 删点就删掉它对后续点的入度影响。
- 排不完说明有环。

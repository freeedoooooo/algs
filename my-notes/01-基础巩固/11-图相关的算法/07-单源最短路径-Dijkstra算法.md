# 单源最短路径算法之迪杰斯特拉算法-Dijkstra

[返回章节](../12-暴力递归到动态规划1-递归尝试/README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：12 动态规划
- 原始条目：☒ 单源最短路径算法之迪杰斯特拉算法-Dijkstra

## 一句话结论
Dijkstra 用来求“从一个源点出发，到图中其他所有点的最短距离”，前提是图中边权不能为负。
它的本质是贪心：每次锁定当前距离最小的未处理节点，这个节点的最短路一旦确定就不会再变。

## 核心知识点
- 这是单源最短路，不是多源。
- 边权必须非负。
- 维护一张距离表 `distanceMap`。
- 每次选当前未锁定、距离最小的点。
- 用这个点的出边尝试更新其他点。

## 图片转写 / 题意还原
原始笔记中只保留了题目名称，这里把标准题意补完整：

- 给定一张带权有向图或无向图，以及一个指定源点 `source`
- 边权表示从一个点走到另一个点的代价、距离或时间
- 要求计算：从 `source` 出发，到图中每个可达节点的最短路径长度
- 若某个节点从 `source` 无法到达，它的距离通常记为无穷大或“不存在”

这题默认有一个关键前提：

- 所有边权都必须是非负数

因此，Dijkstra 解决的不是“任意图最短路”，而是：

```text
单源最短路
+ 非负边权
+ 输出源点到所有点的最短距离
```

把流程翻译成做题语言，就是：

1. 先把源点距离设为 `0`
2. 其余点距离设为未知或无穷大
3. 每次从“当前还没确定答案的点”里，选一个距离最小的点
4. 用这个点去更新它能到达的邻居距离
5. 一旦这个点被选出来，它的最短距离就正式确定
6. 最后得到一张“源点到各点最短距离表”

## 图解
图：

```text
A -> B (3)
A -> C (1)
C -> B (1)
B -> D (2)
C -> D (5)
```

从 `A` 出发：

- 初始：`A=0`
- 先锁 `A`，更新 `B=3, C=1`
- 再锁 `C`，更新 `B=min(3, 1+1)=2, D=6`
- 再锁 `B`，更新 `D=min(6, 2+2)=4`
- 再锁 `D`

最终：

```text
A=0, C=1, B=2, D=4
```

## 解题思路
### 1. 为什么“当前最小未锁定点”可以直接定死
因为所有边权都非负。

所以：

- 如果当前它已经是未锁定里最小的
- 后面再绕路回来只会更长，不可能更短

### 2. 松弛操作
对当前点 `cur` 的每条出边 `cur -> to`：

```text
distance[to] = min(distance[to], distance[cur] + weight)
```

## 复杂度
- 普通实现时间复杂度：`O(V^2 + E)`
- 空间复杂度：`O(V)`

## 典型例子
地图导航里：

- 起点固定
- 每条边有通行代价
- 需要求从起点到其他位置的最短距离

这是 Dijkstra 最直接的业务抽象。

## 易错点
- 负权边不能用 Dijkstra。
- “最短路已确定”的条件，是它已经成为当前最小未锁定点。
- Dijkstra 求的是距离，不一定直接保存整条路径；若要路径，还得额外记录前驱。

## 代码 / 伪代码
课程标准伪代码：

```java
Map<Node, Integer> dijkstra(Node from) {
    Map<Node, Integer> distanceMap = new HashMap<>();
    distanceMap.put(from, 0);
    Set<Node> selected = new HashSet<>();
    Node minNode = getMinDistanceAndUnselectedNode(distanceMap, selected);
    while (minNode != null) {
        int distance = distanceMap.get(minNode);
        for (Edge edge : minNode.edges) {
            Node to = edge.to;
            if (!distanceMap.containsKey(to)) {
                distanceMap.put(to, distance + edge.weight);
            } else {
                distanceMap.put(to, Math.min(distanceMap.get(to), distance + edge.weight));
            }
        }
        selected.add(minNode);
        minNode = getMinDistanceAndUnselectedNode(distanceMap, selected);
    }
    return distanceMap;
}
```

## 记忆点
- Dijkstra = 单源最短路 + 非负权。
- 每次锁定当前最小未处理点。
- 锁定后就不会再变。
- 核心操作叫“松弛”。

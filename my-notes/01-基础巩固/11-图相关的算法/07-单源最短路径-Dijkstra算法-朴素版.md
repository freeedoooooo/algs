# 单源最短路径-Dijkstra算法

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：11 图相关的算法
- 原始条目：☒ 单源最短路径算法之迪杰斯特拉算法-Dijkstra

## 一句话结论
`Dijkstra` 用来解决：

```text
从一个固定起点出发
到图中其他各点的最短路径长度
```

它有一个非常重要的前提：

```text
边权不能为负
```

它的核心贪心思想可以直接记成：

```text
每次都从“当前还没确定答案的点”里
选出距离起点最近的那个点
把它正式锁定
再用它去更新别的点
```

## 题意说明
这篇不是某一道具体题，而是在讲图上的单源最短路径模板。

它主要解决的是：

```text
给定一个起点 source
如何求出 source 到每个可达节点的最短距离
```

这里有几个关键词要先分清：

- 单源：只有一个起点
- 最短路径：总权值最小，不是经过边数最少
- 非负边权：所有边权都不能小于 `0`

所以 `Dijkstra` 解决的不是“任意图最短路”，而是：

```text
单源最短路
+ 非负边权
+ 输出起点到各点的最短距离
```

## 先抓住 Dijkstra 的手感
第一次学 `Dijkstra`，最容易绕晕的地方通常不是代码，而是：

```text
为什么“当前最小的未锁定点”可以直接定死
```

先别急着证明，先把它想成这样：

```text
起点到各点的距离在不断被更新
谁当前最小，谁就最有可能已经拿到最终答案
```

而因为边权都非负，所以：

```text
后面再绕别的路回来
只会更长，不会更短
```

这就是 `Dijkstra` 整个算法能成立的关键。

## 图解：一步一步跑 Dijkstra
下面用一张简单的有向带权图来跑一遍。

先别急着盯公式，先统一盯住每一轮的 3 件事：

- 现在未锁定的点里，谁的距离最小
- 为什么这一次轮到它被锁定
- 它出发后，能把哪些点的距离继续变小

把这个节奏抓住，`Dijkstra` 就会一下子顺很多。

### 原图

```mermaid
graph LR
    A((A)) -->|3| B((B))
    A -->|1| C((C))
    C -->|1| B
    B -->|2| D((D))
    C -->|5| D
```

我们要求的是：

```text
从 A 出发
到 A、B、C、D 的最短距离
```

为了让过程更清楚，后面统一用这两个词：

- 锁定：这个点的最短距离已经最终确定，后面不会再改
- 更新：尝试用当前锁定点去缩短别的点的距离

### 初始状态

- `distance[A] = 0`
- 其他点都还不知道，视为无穷大
- 已锁定点集合：空

```text
A = 0
B = inf
C = inf
D = inf
```

现在只有一件事最确定：

```text
起点 A 到自己的距离一定是 0
所以第一轮一定先从 A 开始
```

### 第 1 步：先锁定 `A`

因为起点到自己的距离一定是 `0`，所以它肯定最先被锁定。

然后用 `A` 的出边去更新邻居：

- `A -> B (3)`，所以 `B = 3`
- `A -> C (1)`，所以 `C = 1`

```mermaid
graph LR
    A((A)) -->|3| B((B))
    A -->|1| C((C))
    C -->|1| B
    B -->|2| D((D))
    C -->|5| D

    style A fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    linkStyle 0 stroke:#f59e0b,stroke-width:4px
    linkStyle 1 stroke:#f59e0b,stroke-width:4px
```

当前距离表：

```text
A = 0   (已锁定)
B = 3
C = 1
D = inf
```

这一步结束后，虽然 `B` 已经有了一个距离 `3`，但别急着把它当最终答案。  
因为我们已经看到 `C = 1`，它比 `B = 3` 更近，下一轮很可能先轮到 `C`，而 `C` 也许还能帮我们把 `B` 变得更短。

### 第 2 步：锁定当前最小未锁定点 `C`

现在还没锁定的点里：

- `B = 3`
- `C = 1`
- `D = inf`

最小的是 `C`，所以锁定 `C`。

为什么 `C` 现在就能锁定？  
因为未锁定点里它已经最小了，而边权都非负，所以就算你想“绕一圈再回到 `C`”，总距离也只会更大，不可能再比 `1` 更小。

然后用 `C` 去更新邻居：

- `C -> B (1)`，所以 `B = min(3, 1 + 1) = 2`
- `C -> D (5)`，所以 `D = min(inf, 1 + 5) = 6`

```mermaid
graph LR
    A((A)) -->|3| B((B))
    A -->|1| C((C))
    C -->|1| B
    B -->|2| D((D))
    C -->|5| D

    style A fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style C fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    linkStyle 1 stroke:#16a34a,stroke-width:4px
    linkStyle 2 stroke:#f59e0b,stroke-width:4px
    linkStyle 4 stroke:#f59e0b,stroke-width:4px
```

当前距离表：

```text
A = 0   (已锁定)
C = 1   (已锁定)
B = 2
D = 6
```

这里是整段图解里最关键的一次更新：

- 原来我们记录的 `B = 3`，路径是 `A -> B`
- 现在经过 `C`，得到新路径 `A -> C -> B`，长度变成 `2`

这就说明：  
`distance[x]` 不是一开始写上去就不动，而是在不断比较、不断变短，直到某个点被锁定为止。

### 第 3 步：锁定当前最小未锁定点 `B`

现在未锁定点里：

- `B = 2`
- `D = 6`

最小的是 `B`，所以锁定 `B`。

然后用 `B` 去更新邻居：

- `B -> D (2)`，所以 `D = min(6, 2 + 2) = 4`

```mermaid
graph LR
    A((A)) -->|3| B((B))
    A -->|1| C((C))
    C -->|1| B
    B -->|2| D((D))
    C -->|5| D

    style A fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style B fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style C fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    linkStyle 1 stroke:#16a34a,stroke-width:4px
    linkStyle 2 stroke:#16a34a,stroke-width:4px
    linkStyle 3 stroke:#f59e0b,stroke-width:4px
```

当前距离表：

```text
A = 0   (已锁定)
C = 1   (已锁定)
B = 2   (已锁定)
D = 4
```

这一轮再看一次“更新”到底在干什么：

- 原来 `D = 6`，对应路径 `A -> C -> D`
- 现在经过 `B`，得到 `A -> C -> B -> D`，长度是 `4`

于是 `D` 又被缩短了。  
这也是为什么 `Dijkstra` 不是“从起点直接看一圈就结束”，而是要一轮一轮地拿当前最近的点继续往外扩。

### 第 4 步：锁定 `D`

这时只剩下 `D`，直接锁定即可。

```mermaid
graph LR
    A((A)) -->|3| B((B))
    A -->|1| C((C))
    C -->|1| B
    B -->|2| D((D))
    C -->|5| D

    style A fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style B fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style C fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style D fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    linkStyle 1 stroke:#16a34a,stroke-width:4px
    linkStyle 2 stroke:#16a34a,stroke-width:4px
    linkStyle 3 stroke:#16a34a,stroke-width:4px
```

最终最短距离就是：

```text
A = 0
C = 1
B = 2
D = 4
```

如果把整段过程压缩成一张表，就是：

| 轮次 | 锁定点 | 关键更新 | 距离表 |
|---|---|---|---|
| 1 | `A` | `B: inf -> 3`，`C: inf -> 1` | `A=0, B=3, C=1, D=inf` |
| 2 | `C` | `B: 3 -> 2`，`D: inf -> 6` | `A=0, B=2, C=1, D=6` |
| 3 | `B` | `D: 6 -> 4` | `A=0, B=2, C=1, D=4` |
| 4 | `D` | 无 | `A=0, B=2, C=1, D=4` |

所以这个例子的锁定顺序是：

```text
A -> C -> B -> D
```

最终最短距离和对应路径分别是：

- `A -> A = 0`
- `A -> C = 1`
- `A -> C -> B = 2`
- `A -> C -> B -> D = 4`

如果你读到这里脑子里能稳定复述出下面这句话，图解部分就算真正吃透了：

```text
每一轮都先挑“当前最近的未锁定点”
把它定死
再拿它去尝试缩短别人的距离
```

## 这里最关键的动作：松弛
`Dijkstra` 每一步都在做一个核心动作，叫“松弛”。

如果当前锁定点是 `cur`，它到起点的最短距离已经确定为 `distance[cur]`，  
那么对于每条边 `cur -> to`，我们都尝试：

```text
distance[to] = min(distance[to], distance[cur] + weight)
```

这句话的意思其实很朴素：

```text
看看“先到 cur，再走这条边”
会不会比原来记录的到 to 的距离更短
```

如果更短，就更新。

## 为什么“当前最小未锁定点”可以直接锁定
这是 `Dijkstra` 的核心逻辑。

假设当前未锁定点里，`X` 的距离最小。

如果你想通过别的未锁定点绕一圈再回到 `X`，因为：

- 那个别的点当前距离不会比 `X` 更小
- 后续边权又都非负

所以绕路回来只会让总距离更大，不可能更小。

也就是说：

```text
一旦某个点成为“当前最小未锁定点”
它的最短距离就已经最终确定
```

这就是“锁定”这一步的数学依据。

## 终止条件
`Dijkstra` 的终止条件也可以分成两种情况：

- 主动结束：所有可达点都已经被锁定
- 被动结束：再也找不到新的未锁定可达点

第二种情况通常对应：

```text
图里还有别的点
但它们从 source 根本到不了
```

这时算法也会自然停止，因为距离表里不会再出现新的有限值。

## Dijkstra 到底适合什么题
只要题目满足下面这些味道，就要优先想到 `Dijkstra`：

- 起点固定
- 边有权值
- 问的是最小总代价，不是最少边数
- 边权非负

比如：

- 地图导航最短路
- 网络传输最小时延
- 从一个仓库到各配送点的最低成本

## 和 BFS 的区别
这两个算法都能“从一个起点往外扩”，但解决的问题并不一样。

| 维度 | BFS | Dijkstra |
|---|---|---|
| 适用图 | 无权图 / 等权图 | 非负带权图 |
| 扩展依据 | 按层数扩展 | 按当前最小距离扩展 |
| 解决的问题 | 最少边数 / 最少步数 | 最小总代价 |
| 常用结构 | 队列 | 距离表 + 选最小点 / 小根堆 |

可以这样记：

```text
无权最短路先想 BFS
非负带权最短路先想 Dijkstra
```

## 复杂度
普通写法的复杂度通常记成：

- 时间复杂度：`O(V^2 + E)`
- 空间复杂度：`O(V)`

如果再用小根堆优化，常见可以写成：

- 时间复杂度：`O((V + E) log V)`

所以面试里通常会区分两版：

- 朴素版：靠遍历找当前最小未锁定点
- 堆优化版：靠小根堆更快取最小距离点

## 代码模板
### 1. 朴素版

```java
Map<Node, Integer> dijkstra(Node from) {
    // distanceMap 记录:
    // 从起点 from 出发，到每个节点当前已知的最短距离
    Map<Node, Integer> distanceMap = new HashMap<>();

    // 起点到自己的距离一定是 0
    distanceMap.put(from, 0);

    // selected 表示已经“锁定答案”的节点
    // 进入这个集合的节点，最短距离就不会再改
    Set<Node> selected = new HashSet<>();

    // 先从当前距离最小的未锁定节点开始
    Node minNode = getMinDistanceAndUnselectedNode(distanceMap, selected);

    // 只要还能找到这样的节点，就继续做
    while (minNode != null) {
        // minNode 到起点的最短距离已经确定
        int distance = distanceMap.get(minNode);

        // 用 minNode 的所有出边去做“松弛”
        for (Edge edge : minNode.edges) {
            Node to = edge.to;

            // 如果 to 之前从来没被记录过
            // 说明这是第一次找到从 from 到 to 的路径
            if (!distanceMap.containsKey(to)) {
                distanceMap.put(to, distance + edge.weight);
            } else {
                // 如果 to 之前有记录
                // 就比较“旧距离”和“经过 minNode 的新距离”谁更短
                distanceMap.put(to, Math.min(distanceMap.get(to), distance + edge.weight));
            }
        }

        // minNode 已经完成使命，正式锁定
        selected.add(minNode);

        // 继续找下一个“当前距离最小的未锁定节点”
        minNode = getMinDistanceAndUnselectedNode(distanceMap, selected);
    }

    // 返回 from 到所有可达节点的最短距离表
    return distanceMap;
}
```

最核心的部分就是两件事：

- 找当前最小未锁定点
- 用它的出边做松弛

### 2. `getMinDistanceAndUnselectedNode` 在干什么

它其实就是在做这件事：

```text
把 distanceMap 里所有还没锁定的点扫一遍
找出当前距离最小的那个
```

对应代码可以直接写成：

```java
Node getMinDistanceAndUnselectedNode(Map<Node, Integer> distanceMap, Set<Node> selected) {
    Node minNode = null;
    int minDistance = Integer.MAX_VALUE;

    // 遍历所有已经出现在 distanceMap 里的节点
    for (Map.Entry<Node, Integer> entry : distanceMap.entrySet()) {
        Node node = entry.getKey();
        int distance = entry.getValue();

        // 只在“未锁定节点”里挑最小值
        if (!selected.contains(node) && distance < minDistance) {
            minNode = node;
            minDistance = distance;
        }
    }

    return minNode;
}
```

这段方法可以这样理解：

- `distanceMap` 里装的是“目前已经摸到的节点”和它们的当前最短距离
- `selected` 里装的是“已经锁定、以后不再改”的节点
- 这个方法每次都从 `distanceMap` 里挑出一个“距离最小且还没锁定”的节点返回

如果最后返回的是 `null`，表示两种可能：

- 所有可达节点都已经锁定完了
- 剩下的节点根本不可达，`distanceMap` 里已经没有新的候选点了

也就是说，朴素版慢就慢在这里。  
因为它每一轮都要线性扫描一遍 `distanceMap`，去手动找当前最小未锁定点。

## 易错点
- 边权只要出现负数，就不能直接用 `Dijkstra`。
- `Dijkstra` 求的是最短距离，不会自动还原整条路径；如果要路径，需要额外记录前驱节点。
- “当前最小未锁定点”一旦锁定，就不要再改它。
- 不可达节点不会出现在最终有效距离里，或者会保留为无穷大。
- 不要把“最少边数”问题误写成 `Dijkstra`，无权图更适合直接用 `BFS`。

## 记忆点
- `Dijkstra` = 单源最短路 + 非负边权。
- 每次锁定当前最小未处理点。
- 锁定后距离就不会再变。
- 核心动作是松弛。
- 无权最短路先想 `BFS`，带权最短路再想 `Dijkstra`。

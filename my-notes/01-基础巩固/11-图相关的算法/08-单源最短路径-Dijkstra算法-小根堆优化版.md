# 迪杰斯特拉算法改进，更新小根堆

[返回章节](../12-暴力递归到动态规划1-递归尝试/README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：12 动态规划
- 原始条目：☒ 迪杰斯特拉算法改进，更新小根堆

## 一句话结论
普通 Dijkstra 慢在“每轮都要线性扫描找最小未处理点”，改进版的核心就是用支持更新的小根堆来维护候选节点。
这样每次取最小点的代价下降，整体效率更高，特别适合边比较多的图。

## 核心知识点
- 本质仍然是 Dijkstra，前提仍是无负权边。
- 优化点是“找最小未锁定点”这一步。
- 普通堆不够，需要支持“某节点距离变小”的更新。
- 常见实现是自己维护 `indexMap + distanceMap + heap`。

## 图片转写 / 题意还原
原图内容可以整理为：

- Dijkstra 算法必须指定一个源点
- 生成源点到各点最小距离表
- 每次从未处理记录里拿出最小记录
- 通过这个点的出边更新距离表
- 当所有点都被处理过，过程停止

原始笔记还额外提醒：

- 要求边的权值不为负
- 这是一种贪心思路

## 图解
普通版和堆优化版的区别：

```text
普通版：
每轮从 distanceMap 里手动找最小未锁定点

堆优化版：
每轮从小根堆直接弹出最小距离点
```

其余松弛逻辑完全一致。

## 解题思路
### 1. 为什么普通优先队列不够
因为同一个节点可能被多次更新出更小距离。

你需要支持：

- 节点没进过堆 -> 加入
- 节点已在堆中 -> 更新为更小值
- 节点已经弹出锁定 -> 忽略

### 2. 自定义堆的职责
通常需要三个结构：

- `nodes[]`：真正的堆数组
- `heapIndexMap`：节点当前在堆中的位置，没进堆或已弹出也能区分
- `distanceMap`：节点当前最好距离

### 3. 典型接口
经典接口通常叫：

```text
addOrUpdateOrIgnore(node, distance)
pop()
```

## 复杂度
- 时间复杂度：`O((V + E) log V)`
- 空间复杂度：`O(V)`

## 典型例子
在稠密图里，普通版每轮线性扫表会比较慢；堆优化版能更快找到当前最近的待处理节点，因此更适合工程化实现。

## 易错点
- 这不是“换个容器”这么简单，关键是堆要支持更新。
- 节点已经弹出锁定后，后续再收到更新要忽略。
- 边权为负时，堆优化版一样不能用。

## 代码 / 伪代码
课程标准伪代码骨架：

```java
void addOrUpdateOrIgnore(Node node, int distance) {
    if (inHeap(node)) {
        distanceMap.put(node, Math.min(distanceMap.get(node), distance));
        heapInsert(heapIndexMap.get(node));
    }
    if (!isEntered(node)) {
        nodes[size] = node;
        heapIndexMap.put(node, size);
        distanceMap.put(node, distance);
        heapInsert(size++);
    }
}

Map<Node, Integer> dijkstra2(Node head, int size) {
    NodeHeap nodeHeap = new NodeHeap(size);
    nodeHeap.addOrUpdateOrIgnore(head, 0);
    Map<Node, Integer> result = new HashMap<>();
    while (!nodeHeap.isEmpty()) {
        Record record = nodeHeap.pop();
        Node cur = record.node;
        int distance = record.distance;
        for (Edge edge : cur.edges) {
            nodeHeap.addOrUpdateOrIgnore(edge.to, distance + edge.weight);
        }
        result.put(cur, distance);
    }
    return result;
}
```

## 记忆点
- 优化的是“找最小未锁定点”。
- 需要支持更新的小根堆。
- 常见接口：`addOrUpdateOrIgnore`。
- 仍然只适用于非负权图。

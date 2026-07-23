# 框架可视化-预警报告页分析数据 技术设计
> 编号：`0015` | 模块：`rule` | 服务：`dib-agent-service-rule` | 创建时间：`2026-05-14`
> 关联需求：`requirements.md`

---

## 概述

在现有“框架可视化配置”和“预警报告业务规则查询”能力之上，补充预警报告页的数据分析接口。

本次新增 3 个接口：

1. 查询预警报告头部信息
2. 查询统计层级上一级风险分布
3. 查询统计层级下一级风险节点列表

这 3 个接口统一放到 `ComFrameVisualizationWarningController` 中，但与现有“节点及下级节点业务规则查询”能力分开实现。

---

## 架构设计

### 整体调用链

```text
ComFrameVisualizationWarningController
    -> ComFrameVisualizationWarningPageAggregate
        -> IComFrameInfoService
        -> IComFrameVisualizationService
        -> IComFrameVisualizationLevelService
        -> IComFrameVisualizationModuleService
        -> IComFrameNodeService
        -> ComFrameValueFieldAggregate
        -> ComFrameVisualizationWarningPageMapper
            -> com_frame_value
            -> com_frame_node
            -> com_frame_visualization
            -> com_frame_visualization_level
```

### 设计原则

- 控制器仍归属 `ComFrameVisualizationWarningController`
- 页面分析查询与“节点业务规则查询”聚合逻辑解耦
- 数据统计优先在数据库层完成
- 风险等级映射逻辑统一收口在 Aggregate 层

---

## 涉及文件

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/aggregate/ComFrameVisualizationWarningPageAggregate.java` | 预警报告页分析聚合层 |
| 修改 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/controller/ComFrameVisualizationWarningController.java` | 新增 3 个页面分析接口 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/mapper/frame/ComFrameVisualizationWarningPageMapper.java` | 页面分析查询 Mapper |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/resources/mapper/frame/ComFrameVisualizationWarningPageMapper.xml` | 页面分析 SQL |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/req/FrameVisualizationWarningAnalysisQueryReq.java` | 通用查询请求 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningHeaderResp.java` | 页头响应 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningParentStatResp.java` | 上一级分布响应 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningChildNodeResp.java` | 下一级节点响应 |

---

## 数据模型

### 输入

#### FrameVisualizationWarningAnalysisQueryReq

| 参数/字段 | 类型 | 来源 | 说明 |
|----------|------|------|------|
| frameId | Long | 请求体 | 当前框架 ID |
| dimFilterList | List<DimFilterBO> | 请求体 | 企业、报告期等维度过滤条件 |

### 输出

#### 1. 页头响应：FrameVisualizationWarningHeaderResp

| 字段名 | 类型 | 说明 |
|--------|------|------|
| rootNodeId | Long | 根节点 ID |
| rootNodeCode | String | 根节点编码 |
| rootNodeName | String | 根节点名称 |
| riskLevelId | Long | 风险等级 ID |
| riskLevelName | String | 风险等级名称 |
| riskLevelColor | String | 风险等级颜色 |

#### 2. 上一级分布响应：FrameVisualizationWarningParentStatResp

| 字段名 | 类型 | 说明 |
|--------|------|------|
| nodeId | Long | 节点 ID |
| nodeCode | String | 节点编码 |
| nodeName | String | 节点名称 |
| riskCount | Long | 风险数 |
| ratio | String / BigDecimal | 占比 |

#### 3. 下一级节点响应：FrameVisualizationWarningChildNodeResp

| 字段名 | 类型 | 说明 |
|--------|------|------|
| nodeId | Long | 节点 ID |
| nodeCode | String | 节点编码 |
| nodeName | String | 节点名称 |
| nodeLevel | Integer | 节点层级 |
| riskCount | Long | 风险数 |
| riskLevelId | Long | 风险等级 ID |
| riskLevelName | String | 风险等级名称 |
| riskLevelColor | String | 风险等级颜色 |

---

## 涉及数据库表

| 表名 | 操作 | 说明 |
|------|------|------|
| `com_frame_info` | 查询 | 校验框架存在 |
| `com_frame_visualization` | 查询 | 获取当前框架可视化配置 |
| `com_frame_visualization_level` | 查询 | 获取风险等级区间配置 |
| `com_frame_visualization_module` | 查询 | 校验预警报告模块启用 |
| `com_frame_node` | 查询 | 获取根节点、统计层级节点及上下级节点 |
| `com_frame_value` | 查询 | 统计风险数与节点结果 |

---

## 接口设计

### API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/comFrameVisualizationWarning/getWarningHeader` | 查询预警报告头部信息 |
| POST | `/comFrameVisualizationWarning/listParentRiskStat` | 查询统计层级上一级风险分布 |
| POST | `/comFrameVisualizationWarning/listChildRiskNode` | 查询统计层级下一级风险节点列表 |

### 请求示例

```json
{
  "frameId": 1001,
  "dimFilterList": [
    {
      "dimId": 1,
      "dimValueList": ["000004"]
    },
    {
      "dimId": 2,
      "dimValueList": ["2025-12-31"]
    }
  ]
}
```

---

## 核心逻辑设计

### 主流程

```text
1. 校验 frameId 对应框架存在
2. 查询框架可视化主配置
3. 校验“预警报告”模块已启用
4. 读取 statLevel
5. 查询根节点
6. 查询 statLevel 对应节点、上一级节点、下一级节点
7. 校验 dimFilterList 合法，并映射到 com_frame_value 字段
8. 调用 Mapper 分别查询：
   - 根节点结果
   - 上一级节点风险统计
   - 下一级节点风险统计
9. 基于可视化等级区间统一映射风险等级
10. 返回 3 个独立接口结果
```

### 1. 根节点风险等级

```text
1. 获取框架根节点
2. 在 com_frame_value 中按根节点 + 维度过滤查询结果
3. 取该结果的风险分值
4. 根据可视化等级区间映射到等级名称、颜色
5. 返回页头信息
```

说明：

- 这里固定取框架根节点
- 不受上一级/下一级统计口径影响

### 2. 上一级风险分布

```text
1. 计算 parentLevel = statLevel - 1
2. 若 parentLevel 不存在，则返回空列表
3. 查询该层级节点在当前筛选条件下的风险数
4. 过滤 riskCount = 0 的节点
5. 基于有效节点总风险数计算占比
6. 返回分布结果
```

说明：

- 只返回风险数 > 0 的节点
- 返回结果用于圆环图和图例

### 3. 下一级节点列表

```text
1. 计算 childLevel = statLevel + 1
2. 若 childLevel 不存在，则返回空列表
3. 查询该层级节点在当前筛选条件下的风险数与风险分值
4. 过滤 riskCount = 0 的节点
5. 对每个节点风险分值映射风险等级
6. 返回节点列表
```

说明：

- 只返回风险数 > 0 的节点
- 用于页面右侧风险节点展示

### 风险等级映射

统一复用可视化等级区间配置：

```text
score -> levelRange -> levelId / levelName / levelColor
```

若未命中任何等级区间：

- 页头：等级字段可为空
- 下一级节点列表：等级字段可为空

---

## SQL 设计建议

### 1. 根节点查询

- 在 SQL 中根据 `frame_id + node_id + dimFilterList` 直接定位根节点结果记录

### 2. 上一级分布查询

- 在 SQL 中按上一级节点分组统计风险数
- 通过 `HAVING risk_count > 0` 过滤 0 风险节点

### 3. 下一级节点列表查询

- 在 SQL 中按下一级节点分组统计风险数
- 通过 `HAVING risk_count > 0` 过滤 0 风险节点
- 可同时带出用于等级映射的代表性风险分值

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| 框架不存在 | 直接拒绝 | `框架不存在` |
| 未配置可视化 | 直接拒绝 | `当前框架未配置可视化` |
| 预警报告模块未启用 | 直接拒绝 | `预警报告模块未启用` |
| 维度条件非法 | 直接拒绝 | `维度条件不属于当前框架` |
| 统计层级无上一级/下一级 | 正常返回空列表 | `success` |

---

## 影响范围

### 新增文件

- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/aggregate/ComFrameVisualizationWarningPageAggregate.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/mapper/frame/ComFrameVisualizationWarningPageMapper.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/resources/mapper/frame/ComFrameVisualizationWarningPageMapper.xml`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/req/FrameVisualizationWarningAnalysisQueryReq.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningHeaderResp.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningParentStatResp.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningChildNodeResp.java`

### 修改文件

- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/controller/ComFrameVisualizationWarningController.java`

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| `statLevel` 在部分框架中可能已接近根或叶子层 | 上一级或下一级查询为空 | 将其定义为正常场景，返回空列表 |
| 风险数口径若定义不清 | 前后端理解不一致 | 在开发前固定“风险数”统计 SQL 口径 |
| 同一节点可能存在多条结果记录 | 等级映射口径不一致 | 在 SQL 中明确采用哪一个分值字段或聚合方式 |

---

**状态**：草稿

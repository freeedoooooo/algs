# 框架可视化-综合分析 技术设计

> 编号：`0013` | 模块：`rule` | 服务：`dib-agent-service-rule` | 创建时间：`2026-05-09`
> 关联需求：`requirements.md`

---

## 概述

在现有“框架结果查询”和“框架可视化配置”能力之上，新增综合分析查询能力，向前端提供 3 个拆分接口：风险等级统计、前 10 大风险、各等级企业名单分页。

本方案仅消费已有框架结果表和可视化配置，不改动框架计算逻辑，也不新增结果类持久化表。

---

## 架构设计

### 整体架构

```text
ComFrameVisualizationSummaryController
    -> ComFrameVisualizationSummaryAggregate
        -> IComFrameVisualizationService
        -> IComFrameVisualizationLevelService
        -> IComFrameVisualizationModuleService
        -> IComFrameInfoService
        -> ComFrameValueFieldAggregate
        -> ComFrameVisualizationSummaryMapper
            -> com_frame_value
```

### 设计原则

- 查询维度解析复用现有 `ComFrameValueFieldAggregate`
- 可视化配置读取复用现有可视化主表/等级表/模块表
- 综合分析统计单独下沉 Mapper，避免在 Aggregate 中拼大段 SQL
- 风险等级映射逻辑在 Aggregate 层统一收口，确保 3 个接口口径一致

### 涉及文件

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/controller/ComFrameVisualizationSummaryController.java` | 综合分析接口控制器 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/aggregate/ComFrameVisualizationSummaryAggregate.java` | 综合分析聚合层 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/mapper/frame/ComFrameVisualizationSummaryMapper.java` | 综合分析自定义查询 Mapper |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/resources/mapper/ComFrameVisualizationSummaryMapper.xml` | 综合分析自定义 SQL |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/req/FrameVisualizationSummaryQueryReq.java` | 风险等级统计/前 10 大风险查询请求 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/req/FrameVisualizationSummaryCompanyPageReq.java` | 企业名单分页请求 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationRiskLevelStatResp.java` | 风险等级统计响应 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationTopRiskResp.java` | 前 10 大风险响应 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationCompanyResp.java` | 企业名单响应 |

---

## 数据模型

### 输入

#### FrameVisualizationSummaryQueryReq

| 参数/字段 | 类型 | 来源 | 说明 |
|----------|------|------|------|
| frameId | Long | 请求体 | 当前框架 ID |
| dimFilterList | List<DimFilterBO> | 请求体 | 维度筛选条件 |
| topN | Integer | 请求体 | 前 10 大风险接口可选参数，默认 10 |

#### FrameVisualizationSummaryCompanyPageReq

| 参数/字段 | 类型 | 来源 | 说明 |
|----------|------|------|------|
| frameId | Long | 请求体 | 当前框架 ID |
| dimFilterList | List<DimFilterBO> | 请求体 | 维度筛选条件 |
| levelId | Long | 请求体 | 风险等级配置 ID |
| pageNum | Integer | 请求体 | 页码 |
| pageSize | Integer | 请求体 | 每页条数 |

### 输出

#### 风险等级统计

| 字段名 | 类型 | 说明 |
|--------|------|------|
| levelId | Long | 风险等级配置 ID |
| levelName | String | 风险等级名称 |
| levelColor | String | 风险等级颜色 |
| companyCount | Long | 企业数量 |
| ratio | String / BigDecimal | 占比 |

#### 前 10 大风险

| 字段名 | 类型 | 说明 |
|--------|------|------|
| nodeId | Long | 节点 ID |
| nodeCode | String | 节点编码 |
| nodeName | String | 节点名称 |
| riskCompanyCount | Long | 风险企业数 |

#### 企业名单分页

| 字段名 | 类型 | 说明 |
|--------|------|------|
| companyCode | String | 企业编码 |
| companyName | String | 企业名称 |
| industryCode | String | 行业编码 |
| industryName | String | 行业名称 |
| reportDate | String | 报告期 |
| score | Double | 风险分值 |
| levelId | Long | 风险等级 ID |
| levelName | String | 风险等级名称 |

### 常量约定

| 常量名 | 值 | 说明 |
|------|------|------|
| `DEFAULT_COMPANY_DIM_FIELD` | `dim_sec_code` | 企业编码/名称默认维度字段 |
| `DEFAULT_INDUSTRY_DIM_FIELD` | `dim_industry_code` | 所属行业默认维度字段 |

### 涉及数据库表

| 表名 | 操作 | 说明 |
|------|------|------|
| `com_frame_visualization` | 查询 | 获取当前框架可视化主配置 |
| `com_frame_visualization_level` | 查询 | 获取风险等级区间配置 |
| `com_frame_visualization_module` | 查询 | 校验“综合分析”模块是否启用 |
| `com_frame_value` | 查询 | 综合分析底层结果来源 |
| `com_frame_info` | 查询 | 框架基础信息和维度配置 |

---

## 接口设计

### API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/comFrameVisualizationSummary/riskLevelStat` | 查询风险等级统计 |
| POST | `/comFrameVisualizationSummary/topRisk` | 查询前 10 大风险 |
| POST | `/comFrameVisualizationSummary/pageCompanyByRiskLevel` | 分页查询指定风险等级企业名单 |

### 请求/响应示例

```json
// 风险等级统计请求
{
  "frameId": 1001,
  "dimFilterList": [
    {
      "dimId": 1,
      "dimValueList": ["2025-12-31"]
    }
  ]
}
```

```json
// 风险等级统计响应
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "levelId": 1,
      "levelName": "高",
      "levelColor": "#D92D20",
      "companyCount": 120,
      "ratio": "12.56%"
    }
  ]
}
```

```json
// 前10大风险请求
{
  "frameId": 1001,
  "dimFilterList": [
    {
      "dimId": 1,
      "dimValueList": ["2025-12-31"]
    }
  ],
  "topN": 10
}
```

```json
// 企业名单分页请求
{
  "frameId": 1001,
  "levelId": 1,
  "pageNum": 1,
  "pageSize": 20,
  "dimFilterList": [
    {
      "dimId": 1,
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
3. 校验“综合分析”模块存在、未删除、已启用
4. 读取 statLevel
5. 查询风险等级配置并构造成有序区间列表
6. 校验 dimFilterList 中的 dimId 是否属于当前框架维度
7. 将 dimId 转为 com_frame_value 的字段名
8. 执行底层结果查询
9. 按接口类型分别组装返回
```

### 风险等级统计

处理流程：

```text
1. 查询 node_level = statLevel 的结果记录
2. 应用维度过滤条件
3. 逐条按 node_score 命中风险等级区间
4. 按 levelId 分组累计 companyCount
5. 计算各等级占比
6. 返回完整风险等级统计列表
```

说明：

- 若某等级数量为 0，也建议返回该等级，便于前端稳定渲染
- 占比基于命中任一风险等级区间的全部企业数计算

### 前 10 大风险

处理流程：

```text
1. 查询 node_level >= statLevel 的结果记录
2. 应用维度过滤条件
3. 按 nodeId / nodeCode / nodeName 分组
4. 统计每个节点命中的企业数量
5. 按 riskCompanyCount 倒序排序
6. 截取前 topN 条返回
```

说明：

- 该接口不按风险等级分组，而是按风险节点分组
- 统计值定义为企业数，不直接返回分值平均值或最大值

### 企业名单分页

处理流程：

```text
1. 校验 levelId 属于当前框架可视化等级配置
2. 查询 node_level = statLevel 的结果记录
3. 应用维度过滤条件
4. 根据 node_score 命中目标等级区间
5. 提取企业维度、行业维度、报告期、score 等展示字段
6. 按约定排序后分页
7. 返回 PageResp
```

说明：

- 企业名称、行业名称通过现有维度名称补充逻辑映射
- 企业字段默认取常量 `DEFAULT_COMPANY_DIM_FIELD=dim_sec_code`
- 行业字段默认取常量 `DEFAULT_INDUSTRY_DIM_FIELD=dim_industry_code`
- 默认排序固定为 `score desc, companyCode asc`

### 关键技术点

1. 维度过滤复用
- 复用 `ComFrameValueFieldAggregate#getDimIdToFieldNameMap`
- 复用 `DimFilterBO`
- 保持与现有框架结果分页接口一致的维度过滤方式

2. 风险等级命中
- 复用现有可视化等级配置中的 `scoreRange`
- 统一调用区间解析工具
- 避免不同接口出现不一致的分值命中逻辑

3. 聚合查询策略
- “前 10 大风险”适合在 SQL 层按节点聚合
- “企业名单分页”适合 SQL 层过滤 + Java 层补充等级信息
- “风险等级统计”可根据实现复杂度选择 SQL 粗查 + Java 分组，或先全量命中后分组

---

## 数据库变更（如有）

```sql
-- 本需求不新增数据库表
-- 本需求仅消费已有 com_frame_visualization / com_frame_visualization_level /
-- com_frame_visualization_module / com_frame_value
```

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| 框架不存在 | 直接拒绝 | `框架不存在` |
| 未配置框架可视化 | 直接拒绝 | `当前框架未配置可视化` |
| 综合分析模块未启用 | 直接拒绝 | `综合分析模块未启用` |
| 维度条件非法 | 直接拒绝 | `维度条件不属于当前框架` |
| 风险等级不存在 | 直接拒绝 | `风险等级不存在或不属于当前框架` |
| 查询结果为空 | 正常返回空列表/空分页 | `success` |

---

## 影响范围

### 新增文件

- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/controller/ComFrameVisualizationSummaryController.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/aggregate/ComFrameVisualizationSummaryAggregate.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/mapper/frame/ComFrameVisualizationSummaryMapper.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/resources/mapper/ComFrameVisualizationSummaryMapper.xml`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/req/FrameVisualizationSummaryQueryReq.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/req/FrameVisualizationSummaryCompanyPageReq.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationRiskLevelStatResp.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationTopRiskResp.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationCompanyResp.java`

### 修改文件

- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/config/enums/frame/FrameVisualizationModuleEnum.java`
  - 如需补充“综合分析”模块判断辅助方法，可在该文件增强

### 无需修改

- 框架计算逻辑
- 框架结果表结构
- 已有框架结果分页/导出接口

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 结果表数据量较大，Java 全量分组内存压力大 | 接口慢、内存抖动 | 优先将过滤、排序、聚合下推到 SQL |
| 企业名称、行业名称维度在不同框架下不完全一致 | 页面字段可能为空 | 在需求中明确默认映射规则，并允许为空 |
| 风险等级区间未覆盖全部分值 | 部分记录无法命中等级 | 需求层明确未命中记录不纳入统计 |
| statLevel 口径理解偏差 | 前后端展示不一致 | 在文档中明确区分“node_level = statLevel”和“node_level >= statLevel”的使用场景 |

---

**状态**：草稿

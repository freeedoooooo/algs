# 框架可视化预警报告-节点业务规则查询 技术设计

> 编号：`0014` | 模块：`rule` | 服务：`dib-agent-service-rule` | 创建时间：`2026-05-14`
> 关联范围：`ComFrameVisualizationWarningController` 新增“查询某个框架节点及其下级节点的所有业务规则”接口

---

## 概述

在现有“框架可视化”能力下，为“预警报告”模块新增一个节点业务规则查询接口。

该接口用于：
- 输入某个框架节点
- 查询该节点自身及其所有下级节点
- 返回目标节点基础信息
- 返回这些节点下绑定的全部业务规则信息
- 返回每条业务规则关联的 DataEase 看板关系信息

本次仅新增查询能力，不改动框架节点、节点规则绑定、业务规则主数据、规则看板关系的存储结构。

---

## 架构设计

### 整体调用链

```text
ComFrameVisualizationWarningController
    -> ComFrameVisualizationWarningAggregate
        -> IComFrameInfoService
        -> IComFrameVisualizationService
        -> IComFrameVisualizationModuleService
        -> IComFrameNodeService
        -> IComFrameNodeRuleService
        -> IComRuleInfoService
        -> IComRuleDataeaseBoardRelationService
```

### 设计原则

- 复用现有框架节点树结构，不新增节点树查询表
- 复用 `com_frame_node_rule` 作为节点与业务规则绑定关系来源
- 复用 `com_rule_info` 作为业务规则主数据来源
- 复用 `com_rule_dashboard_relation` 作为规则看板关系来源
- 查询结果按“节点 -> 规则列表”分组返回，方便前端直接展示预警报告
- 每条规则下补充 `dashboardList`
- 不新增自定义 XML，优先使用现有 Service/LambdaQuery 完成查询与组装

### 涉及文件

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/aggregate/ComFrameVisualizationWarningAggregate.java` | 预警报告聚合层 |
| 修改 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/controller/ComFrameVisualizationWarningController.java` | 新增查询接口 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/req/FrameVisualizationWarningNodeRuleQueryReq.java` | 请求对象 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningNodeRuleResp.java` | 顶层响应对象 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningNodeRuleItemResp.java` | 节点分组响应对象 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningBizRuleResp.java` | 规则明细响应对象 |
| 新增 | `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningRuleDashboardResp.java` | 规则看板明细响应对象 |

---

## 数据模型

### 输入

#### FrameVisualizationWarningNodeRuleQueryReq

| 参数/字段 | 类型 | 来源 | 说明 |
|----------|------|------|------|
| frameId | Long | 请求体 | 框架 ID |
| nodeId | Long | 请求体 | 目标框架节点 ID |

说明：
- 本期默认查询“当前节点 + 所有下级节点”
- 本期不额外开放 `containSelf` 参数，固定包含当前节点自身

### 输出

#### 顶层响应：FrameVisualizationWarningNodeRuleResp

| 字段名 | 类型 | 说明 |
|--------|------|------|
| frameId | Long | 框架 ID |
| nodeId | Long | 目标节点 ID |
| nodeCode | String | 目标节点编码 |
| nodeName | String | 目标节点名称 |
| nodeLevel | Integer | 目标节点层级 |
| nodeIdPath | String | 目标节点路径 |
| ruleCount | Integer | 命中的业务规则绑定总数 |
| nodeRuleList | List<FrameVisualizationWarningNodeRuleItemResp> | 节点维度分组后的规则列表 |

#### 节点分组响应：FrameVisualizationWarningNodeRuleItemResp

| 字段名 | 类型 | 说明 |
|--------|------|------|
| frameNodeId | Long | 节点 ID |
| frameNodeCode | String | 节点编码 |
| frameNodeName | String | 节点名称 |
| frameNodeLevel | Integer | 节点层级 |
| frameNodeIdPath | String | 节点路径 |
| ruleCount | Integer | 当前节点下绑定规则数量 |
| ruleList | List<FrameVisualizationWarningBizRuleResp> | 当前节点下的规则列表 |

#### 规则明细响应：FrameVisualizationWarningBizRuleResp

| 字段名 | 类型 | 说明 |
|--------|------|------|
| ruleId | Long | 业务规则 ID |
| ruleCode | String | 业务规则编码 |
| ruleName | String | 业务规则名称 |
| ruleDesc | String | 业务规则描述 |
| ruleType | String/Enum | 业务规则类型 |
| enableFlag | Boolean | 业务规则是否启用 |
| ruleWeight | Double | 节点下该规则权重 |
| ruleTestWeight | Double | 节点下该规则试算权重 |
| dashboardList | List<FrameVisualizationWarningRuleDashboardResp> | 该规则关联的看板列表 |

#### 规则看板明细：FrameVisualizationWarningRuleDashboardResp

| 字段名 | 类型 | 说明 |
|--------|------|------|
| dashboardId | String | 看板 ID |
| dashboardName | String | 看板名称 |
| dashboardDesc | String | 看板描述 |
| orderNum | Integer | 排序号 |
| enableFlag | Boolean | 看板关系是否启用 |

### 涉及数据库表

| 表名 | 操作 | 说明 |
|------|------|------|
| `com_frame_info` | 查询 | 校验框架是否存在 |
| `com_frame_visualization` | 查询 | 校验当前框架已配置可视化 |
| `com_frame_visualization_module` | 查询 | 校验“预警报告”模块已启用 |
| `com_frame_node` | 查询 | 查询目标节点及其下级节点 |
| `com_frame_node_rule` | 查询 | 查询节点与业务规则绑定关系 |
| `com_rule_info` | 查询 | 查询业务规则主数据 |
| `com_rule_dashboard_relation` | 查询 | 查询规则与看板关系 |

---

## 接口设计

### API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/comFrameVisualizationWarning/listNodeBizRule` | 查询目标节点及其下级节点的业务规则列表 |

### 请求示例

```json
{
  "frameId": 1001,
  "nodeId": 20001
}
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "frameId": 1001,
    "nodeId": 20001,
    "nodeCode": "A01",
    "nodeName": "流动性风险",
    "nodeLevel": 1,
    "nodeIdPath": "100/20001",
    "ruleCount": 3,
    "nodeRuleList": [
      {
        "frameNodeId": 20001,
        "frameNodeCode": "A01",
        "frameNodeName": "流动性风险",
        "frameNodeLevel": 1,
        "frameNodeIdPath": "100/20001",
        "ruleCount": 1,
        "ruleList": [
          {
            "ruleId": 3001,
            "ruleCode": "BIZ_RULE_001",
            "ruleName": "现金覆盖率校验",
            "ruleDesc": "校验企业现金覆盖率是否异常",
            "ruleType": "BIZ",
            "enableFlag": true,
            "ruleWeight": 0.4,
            "ruleTestWeight": 0.4,
            "dashboardList": [
              {
                "dashboardId": "DE_1001",
                "dashboardName": "现金覆盖率监控看板",
                "dashboardDesc": "展示现金覆盖率相关预警指标",
                "orderNum": 1,
                "enableFlag": true
              }
            ]
          }
        ]
      }
    ]
  }
}
```

---

## 核心逻辑设计

### 主流程

```text
1. 校验 frameId 对应框架存在且未删除
2. 校验当前框架存在可视化配置且预警报告模块已启用
3. 校验 nodeId 属于当前 frameId
4. 查询目标节点自身信息
5. 查询目标节点自身及所有下级节点
6. 查询这些节点下绑定的全部业务规则关系
7. 批量查询业务规则主表信息
8. 批量查询规则看板关系信息
9. 按节点分组组装规则列表
10. 返回“目标节点信息 + 节点规则分组列表”
```

### 节点范围查询规则

目标节点及其下级节点的查询口径建议如下：

```text
node.id_path = targetNode.idPath
OR node.id_path LIKE CONCAT(targetNode.idPath, '/%')
```

说明：
- 不建议使用 `LIKE CONCAT(targetNode.idPath, '%')`
- 因为路径前缀可能出现误匹配，例如 `1/2/3` 和 `1/2/30`
- 使用 `=` + `LIKE ... '/%'` 的组合更稳

### 节点规则组装策略

查询与组装分为 4 批：

1. 查询节点列表
- 来源：`com_frame_node`
- 输出：`childNodeList`

2. 查询节点规则绑定关系列表
- 来源：`com_frame_node_rule`
- 条件：`frame_id = frameId`、`frame_node_id in childNodeIds`、`del_flag = false`
- 输出：`nodeRuleEntityList`

3. 查询业务规则主数据
- 来源：`com_rule_info`
- 条件：`id in ruleIds`、`del_flag = false`
- 输出：`ruleInfoMap`

4. 查询规则看板关系
- 来源：`com_rule_dashboard_relation`
- 条件：`rule_id in ruleIds`、`del_flag = false`
- 输出：`ruleDashboardRelationList`

最终在 Aggregate 中做：

```text
childNodeId -> List<ComFrameNodeRuleEntity>
ruleId -> ComRuleInfoEntity
ruleId -> List<ComRuleDashboardRelationEntity>
```

然后将每个节点下的规则明细组装成 `nodeRuleList`，并在每条规则下补充 `dashboardList`。

### 返回分组口径

本接口返回结构按“节点分组”，而不是简单返回平铺规则列表。

原因：
- 更符合“某个节点及下级节点的规则报告”语义
- 前端展示时无需再自行做二次分组
- 后续若要补充节点维度统计信息，也更容易扩展

### 排序建议

节点排序：
1. `node_level ASC`
2. `id_path ASC`
3. `order_num ASC`
4. `id ASC`

规则排序：
1. `ruleInfo.order_num ASC`
2. `ruleInfo.rule_name ASC`
3. `ruleInfo.id ASC`

看板排序：
1. `dashboardRelation.order_num ASC`
2. `dashboardRelation.add_time DESC`
3. `dashboardRelation.id ASC`

---

## 关键技术点

### 1. 可视化模块启用校验

虽然接口归属 `ComFrameVisualizationWarningController`，但仍需要校验：
- 当前框架已配置可视化
- 预警报告模块存在
- 预警报告模块已启用

否则接口应拒绝访问。

### 2. 目标节点与下级节点范围判定

必须基于 `id_path` 判定子树范围，不建议用递归逐层查子节点。

原因：
- 现有节点模型已经有层级路径字段
- 单次批量查询更稳定
- 与现有框架节点树存储设计一致

### 3. 规则绑定信息、规则主信息、规则看板信息分离

节点下规则需要同时返回：
- 关系表字段：`ruleWeight`、`ruleTestWeight`
- 主表字段：`ruleCode`、`ruleName`、`ruleDesc`、`ruleType`、`enableFlag`
- 看板关系字段：`dashboardId`、`dashboardName`、`dashboardDesc`、`orderNum`、`enableFlag`

因此必须分批查询后再组装，不建议单表或循环逐条查库。

---

## 数据库变更

本需求不新增数据库表、不修改表结构。

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| 框架不存在 | 直接拒绝 | `框架不存在` |
| 框架未配置可视化 | 直接拒绝 | `当前框架未配置可视化` |
| 预警报告模块未启用 | 直接拒绝 | `预警报告模块未启用` |
| 节点不存在 | 直接拒绝 | `框架节点不存在` |
| 节点不属于当前框架 | 直接拒绝 | `框架节点不属于当前框架` |
| 节点及下级节点无任何规则绑定 | 正常返回空列表 | `success` |

---

## 影响范围

### 新增文件

- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/aggregate/ComFrameVisualizationWarningAggregate.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/req/FrameVisualizationWarningNodeRuleQueryReq.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningNodeRuleResp.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningNodeRuleItemResp.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningBizRuleResp.java`
- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/model/frame/resp/FrameVisualizationWarningRuleDashboardResp.java`

### 修改文件

- `dib-agent-service-rule/dib-agent-service-rule-web/src/main/java/com/dib/agent/rule/web/controller/ComFrameVisualizationWarningController.java`

### 无需修改

- `com_frame_node`
- `com_frame_node_rule`
- `com_rule_info`
- `com_rule_dashboard_relation`
- 现有框架计算逻辑

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 某个中间节点下子树较大，节点与规则数据量偏多 | 接口返回耗时增加 | 先按节点批量查询，避免循环查库；后续如数据量继续增大，再评估自定义 Mapper 联表查询 |
| 规则主表存在逻辑删除或缺失记录 | 某些节点规则明细缺失 | 组装时过滤无效规则，并记录 warn 日志 |
| 规则看板关系存在脏数据 | 某些规则的 `dashboardList` 不完整 | 过滤无效看板关系记录，并记录 warn 日志 |
| `id_path` 前缀匹配写法不严谨 | 误查到非当前子树节点 | 固定使用 `id_path = ? OR id_path LIKE ?` 口径 |

---

**状态**：草稿

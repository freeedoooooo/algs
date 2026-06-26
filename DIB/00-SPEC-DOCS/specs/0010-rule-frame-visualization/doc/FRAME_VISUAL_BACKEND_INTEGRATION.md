# 框架可视化前后端对接说明

本文基于 `apps/app-data/src/views/FrameworkConfig/FrameVisual/FrameVisual.vue` 的现有交互逻辑整理，目标是把“框架可视化树 / 综合分析 / 预警分析”从前端 mock 和本地状态切换为后端真实数据驱动。

## 一、当前前端已经做了什么

### 1. 框架可视化树

前端在页面初始化时先拉取框架列表，再按当前选中框架加载详情、维度、节点树和规则绑定：

- 框架列表：`listSelectableFrameInfo()`
- 框架详情：`getFrameInfo(frameId)`
- 框架节点树：`listFrameNodeTree(frameId)`
- 节点-业务规则绑定：`listFrameNodeRuleBindings(frameId, treeNodes)`
- 维度元数据：`resolveFrameDimensions(frameInfo)`

当前左侧“框架可视化树”的新增、编辑、删除、保存、发布都还停留在前端内存态，`handleDialogSubmit`、`handleSave`、`handlePublish` 只改本地数据，没有真正落库。

### 2. 综合分析

`SummaryAnalysisView` 直接消费本地组装的数据：

- 风险等级分布 `riskDistribution`
- 十大风险 `topRisks`
- 风险等级明细表 `riskLevelTables`

也就是说，当前综合分析的图表数据还没有后端真实接口支撑。

### 3. 预警分析

`WarningReportView` 的数据链路更复杂：

- 先根据框架节点树和规则绑定生成 `reportSections`
- 再根据规则 ID 拉取 BI 可视化实例
- 再从 `localStorage` 读取/写入“预警分析-可视化绑定”
- 最终把 `searchValues + searchBinding` 传给 BI iframe

也就是说，当前预警分析里“可视化选择绑定”是本地持久化，跨设备、跨账号、跨浏览器都不会共享。

## 二、现有可复用接口

这些接口前端已经在用，后端联动时建议继续保留：

| 接口 | 作用 |
| --- | --- |
| `POST /api/rule/comFrameInfo/listFrameInfo` | 框架列表 |
| `GET /api/rule/comFrameInfo/getFrameInfo/{frameId}` | 框架详情，当前前端依赖 `dimIds`、`frameResultConfig`、`frameDesc`、`frameStatus` |
| `GET /api/rule/comFrameNode/getFrameNodeTree/{frameId}` | 框架节点树 |
| `GET /api/rule/comFrameNode/listAllFrameNodeByFrameId/{frameId}` | 节点明细 |
| `GET /api/rule/comFrameNode/listBizRuleByFrameNodeId/{nodeId}` | 单节点关联规则 |
| `POST /api/rule/comRuleInfo/listOfEnable` | 启用业务规则列表 |
| `POST /api/data/comDataDimInfo/listOfEnable` | 启用维度列表 |
| `POST /api/data/comDataDynamicQuery/dimTree/{dimId}` | 维度树数据 |
| `GET /api/rule/comBizRuleDashboard/listByRuleId/{ruleId}` | 规则对应 BI 可视化实例 |
| `POST /api/mdm/dict/list` | 框架属性字典 |

## 三、建议新增的后端接口

下面按“框架可视化树 / 综合分析 / 预警分析”拆分。

### 3.1 框架可视化树 CRUD

> 推荐把它理解成“框架可视化配置”的 CRUD，而不是单独新建一棵业务树表。左侧树只是这个配置的视图层。

#### 3.1.1 列表

| 项 | 内容 |
| --- | --- |
| 方法 | `GET` |
| 路径 | `/api/rule/comFrameVisual/list` |
| 作用 | 返回左侧树所需的框架可视化配置列表 |
| 说明 | 可按 `frameName`、`frameCode`、`frameStatus`、`frameAttribute` 过滤 |

#### 3.1.2 详情

| 项 | 内容 |
| --- | --- |
| 方法 | `GET` |
| 路径 | `/api/rule/comFrameVisual/get/{id}` |
| 作用 | 返回单个框架可视化配置详情 |
| 必要字段 | `id`、`frameId`、`frameCode`、`frameName`、`frameAttribute`、`dimIds`、`frameResultConfig`、`modules`、`statisticLevel`、`note`、`frameStatus`、`updateTime` |

#### 3.1.3 新增

| 项 | 内容 |
| --- | --- |
| 方法 | `POST` |
| 路径 | `/api/rule/comFrameVisual/add` |
| 作用 | 新增框架可视化配置 |

建议请求体：

```json
{
  "frameId": "10001",
  "frameCode": "FV-001",
  "frameName": "上市公司质量评估",
  "frameAttribute": "LISTED_COMPANY",
  "dimIds": ["dim1", "dim2"],
  "frameResultConfig": [
    { "levelNum": 1, "levelName": "高", "scoreRange": "[90,+∞)" }
  ],
  "modules": ["summaryAnalysis", "warningReport"],
  "statisticLevel": 1,
  "note": "..."
}
```

#### 3.1.4 编辑

| 项 | 内容 |
| --- | --- |
| 方法 | `POST` |
| 路径 | `/api/rule/comFrameVisual/edit` |
| 作用 | 修改框架可视化配置 |

#### 3.1.5 删除

| 项 | 内容 |
| --- | --- |
| 方法 | `DELETE` |
| 路径 | `/api/rule/comFrameVisual/delete/{id}` |
| 作用 | 删除框架可视化配置 |

#### 3.1.6 发布

| 项 | 内容 |
| --- | --- |
| 方法 | `POST` |
| 路径 | `/api/rule/comFrameVisual/publish/{id}` |
| 作用 | 将草稿配置发布为正式可用配置 |

> 如果后端已有框架主数据 CRUD，也可以直接复用 `comFrameInfo`，但需要补齐“模块开关、风险等级配置、发布状态”这些字段。

### 3.2 综合分析接口

综合分析页当前没有真实数据源，建议后端提供一个聚合查询接口，一次返回图表和表格所需的数据。

#### 3.2.1 综合分析查询

| 项 | 内容 |
| --- | --- |
| 方法 | `POST` |
| 路径 | `/api/rule/comFrameVisual/summary/query` |
| 作用 | 按当前框架、维度筛选、统计层级返回综合分析数据 |

建议请求体：

```json
{
  "frameId": "10001",
  "dimFilters": {
    "dimA": ["a1", "a2"],
    "dimB": ["b1"]
  },
  "reportPeriod": "2024-12-31",
  "subjectName": "某上市公司",
  "statisticLevel": 1
}
```

建议返回体：

```json
{
  "riskDistribution": [
    { "levelNum": 1, "levelName": "高", "value": 12, "color": "#F53F3F" }
  ],
  "topRisks": [
    { "name": "信息披露不规范", "value": 120 }
  ],
  "riskLevelTables": [
    {
      "level": { "levelNum": 1, "levelName": "高", "scoreRange": "[90,+∞)" },
      "rows": [
        {
          "subjectName": "ST某公司",
          "industry": "制造业",
          "category": "高",
          "riskValue": "92"
        }
      ]
    }
  ]
}
```

### 3.3 预警分析接口

预警分析建议拆成“树、规则绑定、可视化绑定”三类能力。

#### 3.3.1 预警分析树与规则绑定汇总

| 项 | 内容 |
| --- | --- |
| 方法 | `GET` |
| 路径 | `/api/rule/comFrameVisual/warning/tree/{frameId}` |
| 作用 | 一次返回框架节点树、节点绑定规则、节点统计数 |

建议返回体包含：

- `frameNodeTree`
- `ruleBindings`
- `reportSections`
- `riskTree`

这样前端就不需要再对每个节点单独调用 `listBizRuleByFrameNodeId`，可以直接解决当前的 N+1 问题。

#### 3.3.2 规则可视化实例批量查询

| 项 | 内容 |
| --- | --- |
| 方法 | `POST` |
| 路径 | `/api/rule/comBizRuleDashboard/listByRuleIds` |
| 作用 | 一次返回多个规则对应的 BI 可视化实例 |

返回对象建议补充：

- `searchBinding`
- `isDefaultForWarningReport`
- `bindingStatus`

> 当前前端需要从 `searchBinding` 推导 BI 参数映射；如果后端不返回该字段，前端只能继续依赖推断逻辑，稳定性会比较差。

#### 3.3.3 预警可视化绑定查询

| 项 | 内容 |
| --- | --- |
| 方法 | `GET` |
| 路径 | `/api/rule/comFrameVisual/warning/visual-binding/{frameId}` |
| 作用 | 查询当前框架下每个预警章节对应的可视化实例选择 |

返回体建议：

```json
{
  "frameId": "10001",
  "bindings": [
    {
      "sectionId": "node1:rule1",
      "ruleId": "rule1",
      "visualTabId": "tab1"
    }
  ]
}
```

#### 3.3.4 预警可视化绑定保存

| 项 | 内容 |
| --- | --- |
| 方法 | `POST` |
| 路径 | `/api/rule/comFrameVisual/warning/visual-binding/save` |
| 作用 | 保存“章节 -> BI 可视化实例”的绑定关系 |

建议请求体：

```json
{
  "frameId": "10001",
  "sectionId": "node1:rule1",
  "ruleId": "rule1",
  "visualTabId": "tab1"
}
```

#### 3.3.5 预警分析查询

| 项 | 内容 |
| --- | --- |
| 方法 | `POST` |
| 路径 | `/api/rule/comFrameVisual/warning/query` |
| 作用 | 按当前框架、节点、维度筛选返回预警分析所需的章节和筛选上下文 |

这个接口是否必须，取决于后端是否希望把预警章节、过滤条件、展示范围也由服务端统一控制。若只是 BI iframe 自己负责取数，则该接口可以简化为“读绑定 + 读规则实例”。

## 四、建议统一的数据规范

### 4.1 框架可视化配置字段

建议后端至少统一以下字段：

- `id`
- `frameId`
- `frameCode`
- `frameName`
- `frameAttribute`
- `frameStatus`
- `dimIds`
- `frameResultConfig`
- `modules`
- `statisticLevel`
- `note`
- `updateTime`

### 4.2 预警分析章节字段

建议统一以下字段：

- `sectionId`
- `frameNodeId`
- `ruleId`
- `ruleCode`
- `ruleName`
- `ruleDescription`
- `visualTabId`
- `searchBinding`
- `isDefaultForWarningReport`
- `enableFlag`

### 4.3 维度筛选字段

前端 toolbar 侧当前已经按 `dimId -> values[]` 组装筛选条件，后端接收时建议保持这个结构：

```json
{
  "dimFilters": {
    "dimId1": ["v1", "v2"],
    "dimId2": ["v3"]
  }
}
```

## 五、接口落地优先级

建议按下面顺序联调：

1. 先补齐框架可视化树 CRUD，让左侧树和详情从后端读写。
2. 再补综合分析 `summary/query`，替换当前 mock 图表数据。
3. 再补预警分析的树/规则绑定汇总接口，替换节点级 N+1 请求。
4. 最后把预警可视化绑定从 `localStorage` 迁到后端保存。

## 六、对接结论

如果只说“完成当前页面的真实联动”，后端最少需要新增/补齐的能力是：

1. 框架可视化配置 CRUD
2. 综合分析聚合查询
3. 预警分析树和规则绑定汇总
4. 预警分析可视化绑定持久化
5. 规则 BI 可视化实例批量查询，并补 `searchBinding`

现有的 `comFrameInfo`、`comFrameNode`、`comDataDimInfo`、`comDataDynamicQuery`、`comBizRuleDashboard` 可以继续复用，但要么补字段，要么补批量接口，否则前端仍然会停留在 mock / 推断 / localStorage 的工作方式。

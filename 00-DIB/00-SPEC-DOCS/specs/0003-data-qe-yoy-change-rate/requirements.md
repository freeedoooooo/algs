# 003 同比变动率算子 需求文档

## 背景

在质量评价体系中，需要衡量指标值相对于上一自然年同期的变化幅度。为此需要开发一个同比变动率算子（`Alg_QE_YoY_Change_Rate`），支持通过公式表达式动态计算本期值与上期值，并输出同比变动率。

## 目标用户

- 质量评价数据分析人员
- 数据产品团队

## 功能描述

开发一个 Groovy 脚本算子 `Alg_QE_YoY_Change_Rate`，实现以下计算流程：

1. **计算本期值**：根据传入的公式表达式，从业务表中计算当前报告期的本期值
2. **计算上期值**：使用相同公式，查询上一自然年同期（report_date 年份 -1）的上期值
3. **计算同比变动率**：根据本期值和上期值，按以下规则计算

## 核心算法规则

### 同比变动率公式

```
同比变动率 = IFNULL(本期 - 上期, 0) / ABS(上期)
```

### 特殊情况处理

| 条件 | 结果 |
|------|------|
| 上期为 0，本期 > 0 | 同比变动率 = 1 |
| 上期为 0，本期 < 0 | 同比变动率 = -1 |
| 上期为 0，本期 = 0 | 同比变动率 = 0 |
| 上期为 null | 不参与计算，返回空集并打印 WARN 日志 |
| 本期为 null | IFNULL 处理为 0，即 `(0 - 上期) / ABS(上期)` |

### 上期定义

上期 = 上一自然年同期，即 report_date 年份减 1，月日不变。

例：本期 `2024-12-31` → 上期 `2023-12-31`

## 输入参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `formula` | String | 本期值计算公式，直接使用业务表字段名（如 `A / B` 或 `A - B`） |
| `companyDimField` | String | 公司维度字段名（如 `dim_sec_code`） |

报告期 `report_date` 从 `DataIndexCalcReq` 对象中获取，表名通过 `IndexSqlUtil.generateSqlBuilder` 动态获取。

## 输出结果

算子返回 `List<Map<String, Object>>`，每条记录包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `report_date` | String | 报告期 |
| `dim_report_date` | String | 报告期（维度字段） |
| `${companyDimField}` | String | 公司维度字段（动态字段名） |
| `index_value` | Double | 同比变动率 |

## 用户故事

- 作为质量评价分析人员，我希望能够计算任意公式指标的同比变动率，以便衡量公司指标的年度变化趋势
- 作为数据产品团队，我希望算子能够正确处理上期为 0 或 null 的边界情况，以便输出稳健的变动率结果

## 验收标准

- [ ] 标准1：算子能够根据公式表达式正确计算本期值
- [ ] 标准2：算子能够正确获取上一自然年同期数据
- [ ] 标准3：上期数据不存在时，返回空集并打印 WARN 日志
- [ ] 标准4：上期为 0、本期 > 0 时，同比变动率 = 1
- [ ] 标准5：上期为 0、本期 < 0 时，同比变动率 = -1
- [ ] 标准6：上期为 0、本期 = 0 时，同比变动率 = 0
- [ ] 标准7：本期为 null 时，IFNULL 处理为 0 参与计算
- [ ] 标准8：输出字段包含 report_date、dim_report_date、companyDimField、index_value

## 边界条件

- 上期数据不存在（无对应年份数据）：返回空集，打印 WARN 日志
- 上期值为 null：不参与计算，返回空集，打印 WARN 日志
- 上期值为 0：按特殊规则处理（见上表）
- 本期值为 null：IFNULL 处理为 0

## 所属模块

- 项目：dib-agent-service-data
- 模块：dib-agent-service-data-web
- 目录：`src/main/resources/indexFunc/qualityEvaluation/`
- 脚本文件：`Alg6_QE_YoY_Change_Rate.groovy`

## 非功能需求

- 日志前缀统一使用 `【同比算子】`
- 代码风格与 `indexFunc/qualityEvaluation/` 下现有脚本保持一致
- 使用相同工具类：`DataQueryInfrastructure`、`IndexSqlUtil`、`DibSqlBuilder`

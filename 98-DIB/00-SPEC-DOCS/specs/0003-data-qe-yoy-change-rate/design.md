# 003 同比变动率算子 技术设计

## 概述

开发 Groovy 脚本算子 `Alg6_QE_YoY_Change_Rate`，通过单一 CTE 链式 SQL 查询，完成本期值计算、上期值获取、同比变动率计算的全流程。算子结构与 `Alg1_QE_Industry_Deviation_Rate.groovy` 保持一致。

---

## 架构设计

### 整体架构

```
DataIndexCalcReq（输入，含 report_date）
       ↓
Alg6_QE_YoY_Change_Rate.groovy
       ↓
┌──────────────────────────────────────────┐
│  前置检查：查询上期数据是否存在           │
│  - 上期 report_date = 年份-1 同月日      │
│  - 不存在 → 返回空集 + WARN 日志         │
└──────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│  CTE Step 1: current_data               │
│  - 查询本期数据，按公式计算本期值        │
└──────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│  CTE Step 2: prior_data                 │
│  - 查询上期数据，按相同公式计算上期值    │
└──────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│  CTE Step 3: yoy_result                 │
│  - JOIN 本期与上期（按公司维度字段）     │
│  - 计算同比变动率（含防0/null逻辑）      │
└──────────────────────────────────────────┘
       ↓
List<Map<String, Object>>（输出结果）
```

### 文件位置

```
dib-agent-service-data-web/
└── src/main/resources/indexFunc/
    └── qualityEvaluation/
        └── Alg6_QE_YoY_Change_Rate.groovy   ← 新增
```

---

## 数据模型

### 动态参数

| 参数名 | 来源 | 说明 |
|--------|------|------|
| `formula` | 函数参数 | 本期值计算公式，直接使用业务表字段名（如 `A / B`） |
| `companyDimField` | 函数参数 | 公司维度字段名（如 `dim_sec_code`） |
| `tableName` | `IndexSqlUtil.generateSqlBuilder(calcReq).getTableName()` | 数据表名，动态获取 |
| `reportDate` | `calcReq.getDimReportDate()` | 本期报告期 |
| `priorReportDate` | reportDate 年份 -1 | 上期报告期（自动推算） |

### 上期日期推算

```groovy
// 本期：2024-12-31 → 上期：2023-12-31
String priorReportDate = (reportDate[0..3].toInteger() - 1).toString() + reportDate[4..]
```

### 输出字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `report_date` | String | 本期报告期 |
| `dim_report_date` | String | 报告期（维度字段） |
| `${companyDimField}` | String | 公司维度字段（动态） |
| `index_value` | Double | 同比变动率 |

---

## SQL 设计

### 前置检查 SQL

```sql
SELECT COUNT(1) FROM ${tableName}
WHERE report_date = '${priorReportDate}'
```

若结果为 0，直接返回空集并打印 WARN 日志。

### 完整 CTE SQL

> `${tableName}`、`${formula}`、`${companyDimField}`、`${reportDate}`、`${priorReportDate}` 均为 Groovy 字符串插值。

```sql
WITH
-- Step 1: 本期数据
current_data AS (
    SELECT
        report_date,
        ${companyDimField},
        (${formula}) AS current_value
    FROM ${tableName}
    WHERE report_date = '${reportDate}'
),

-- Step 2: 上期数据（上一自然年同期）
prior_data AS (
    SELECT
        ${companyDimField},
        (${formula}) AS prior_value
    FROM ${tableName}
    WHERE report_date = '${priorReportDate}'
),

-- Step 3: 计算同比变动率
yoy_result AS (
    SELECT
        c.report_date,
        c.${companyDimField},
        c.current_value,
        p.prior_value,
        CASE
            WHEN p.prior_value = 0 AND IFNULL(c.current_value, 0) > 0 THEN 1
            WHEN p.prior_value = 0 AND IFNULL(c.current_value, 0) < 0 THEN -1
            WHEN p.prior_value = 0                                     THEN 0
            ELSE IFNULL(c.current_value - p.prior_value, 0) / ABS(p.prior_value)
        END AS yoy_rate
    FROM current_data c
    JOIN prior_data p ON c.${companyDimField} = p.${companyDimField}
)

SELECT
    report_date,
    report_date  AS dim_report_date,
    ${companyDimField},
    yoy_rate     AS index_value
FROM yoy_result
ORDER BY ${companyDimField}
```

### 关键技术点

| 场景 | 处理方式 |
|------|----------|
| 上期不存在 | 前置 COUNT 检查，返回空集 + WARN |
| 上期为 0，本期 > 0 | CASE WHEN → 1 |
| 上期为 0，本期 < 0 | CASE WHEN → -1 |
| 上期为 0，本期 = 0 | CASE WHEN → 0 |
| 本期为 null | IFNULL(current_value - prior_value, 0) 处理 |
| 公式动态化 | Groovy 字符串插值 `(${formula})` |

---

## 代码结构设计

### 函数签名

```groovy
/**
 * 计算同比变动率
 * @param formula        本期值计算公式（直接使用业务表字段名，如 "A / B"）
 * @param companyDimField 公司维度字段名（如 "dim_sec_code"）
 * @return 计算结果列表
 */
List<Map<String, Object>> calc(String formula, String companyDimField)
```

### 代码框架

```groovy
List<Map<String, Object>> calc(String formula, String companyDimField) {
    // 1. 获取 calcReq、dataSourceCode、tableName、reportDate
    // 2. 推算 priorReportDate = (year - 1) + month-day
    // 3. 前置检查：查询上期数据是否存在，不存在则 WARN + 返回空集
    // 4. 构建并执行 CTE SQL
    // 5. 返回结果
}

private static String buildYoYSql(
    String tableName, String formula,
    String companyDimField, String reportDate, String priorReportDate
) { ... }

private static String buildCheckSql(String tableName, String priorReportDate) { ... }
```

---

## 影响范围

### 新增文件

| 文件 | 说明 |
|------|------|
| `indexFunc/qualityEvaluation/Alg6_QE_YoY_Change_Rate.groovy` | 算子脚本（新增） |

### 无需修改的文件

- 不涉及任何 Java 代码修改
- 不涉及数据库 DDL 变更

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 上期数据不存在 | 返回空集，记录 WARN 日志 |
| formula 为空 | 抛出 IllegalArgumentException |
| companyDimField 为空 | 抛出 IllegalArgumentException |
| 数据源连接失败 | 抛出异常，记录 ERROR 日志 |

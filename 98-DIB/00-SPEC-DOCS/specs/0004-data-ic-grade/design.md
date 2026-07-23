# 004 内控评级-评级分数算子 技术设计

## 概述

开发 Groovy 脚本算子 `Alg_IC_Grade`，使用单一 CTE 链式 SQL 查询，完成从原始指标值 G 到内控评级分数的全流程计算。

前半段（Step 1~5，G → G2）与 `Alg_IC_Adjust_Factor` 完全相同；后半段引入外部调整系数 `saleAdj` 加权，再经行业分组标准差和线性变换，输出 0~1000 区间的评级分数。

---

## 架构设计

### 整体数据流

```
DataIndexCalcReq（输入，含 report_date）
       ↓
Alg_IC_Grade.groovy
       ↓
┌──────────────────────────────────────┐
│  CTE Step 1: sample_data             │
│  - 从动态表名取样本                   │
│  - 过滤 report_date，排除 null 值    │
│  - 按 measureField ASC 排序          │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 2: percentile_value        │
│  - 取 P1（1%分位）和 P99（99%分位）  │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 3: g0（双截尾）            │
│  - 低于 P1 → 替换为 P1              │
│  - 高于 P99 → 替换为 P99            │
│  - 其余保持原值                      │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 4: industry_median（G1）   │
│  - 按 dim_industry_code_sw 分组      │
│  - 计算 G0 中位数                    │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 5: g2                      │
│  - G2 = G0 - G1                     │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 6: sale_adj                │
│  - 从 com_data_index_value 关联      │
│  - 条件：dim_sec_code + dim_report_date + index_code │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 7: g3                      │
│  - G3 = G2 × saleAdj                │
│  - INNER JOIN，无 saleAdj 的公司排除 │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 8: g4                      │
│  - G4 = STDDEV_SAMP(G3)             │
│  - 按 dim_industry_code_sw 分组      │
│  - NULL/0 时取 0                     │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 9: g5                      │
│  - G5 = G4 × 500 + 500              │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  最终 SELECT：截断                   │
│  - > 1000 → 1000                    │
│  - < 0    → 0                       │
│  - 其余保持 G5                       │
└──────────────────────────────────────┘
       ↓
List<Map<String, Object>>（输出结果）
```

### 文件位置

```
dib-agent-service-data-web/
└── src/main/resources/indexFunc/
    └── internalControl/
        └── Alg_IC_Grade.groovy   ← 新增
```

---

## 数据模型

### 动态参数

| 参数名 | 来源 | 说明 |
|--------|------|------|
| `measureField` | 函数参数传入 | 原始指标值 G 所在字段（如 `B1000001BT`） |
| `adjustFactorIndexCode` | 函数参数传入 | saleAdj 的指标编码，用于关联指标结果表 |
| `tableName` | `IndexSqlUtil.generateSqlBuilder(calcReq).getTableName()` | 数据表名，动态获取 |
| `reportDate` | `calcReq.getDimReportDate()` | 报告期，从请求对象获取 |

### 固定字段

| 字段名 | 说明 |
|--------|------|
| `sec_code` | 公司代码 |
| `report_date` | 报告期 |
| `dim_industry_code_sw` | 申万行业代码 |

### 输入表

**主数据表**（动态表名）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `sec_code` | VARCHAR | 公司代码 |
| `report_date` | DATE | 报告期 |
| `dim_industry_code_sw` | VARCHAR | 申万行业代码 |
| `${measureField}` | DECIMAL | 原始指标值 G |

**调整系数表**（固定：`com_data_index_value`）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `dim_sec_code` | VARCHAR | 公司代码（维度字段） |
| `dim_report_date` | VARCHAR | 报告期（维度字段） |
| `index_code` | VARCHAR | 指标编码 |
| `index_value` | DECIMAL | 指标值（即 saleAdj） |

### 输出字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `sec_code` | String | 公司代码 |
| `report_date` | String | 报告期 |
| `dim_report_date` | String | 报告期（维度字段） |
| `dim_industry_code_sw` | String | 申万行业代码 |
| `index_value` | Double | 最终评级分数（0~1000） |

---

## SQL 设计

### 完整 CTE SQL

```sql
WITH
-- Step 1: 获取样本数据，排除 null 值，按指标值升序排序
sample_data AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY ${measureField} ASC) AS row_num,
        COUNT(*) OVER ()                                  AS total_rows,
        sec_code,
        report_date,
        dim_industry_code_sw,
        ${measureField} AS origin_value
    FROM ${tableName}
    WHERE report_date = '${reportDate}'
      AND ${measureField} IS NOT NULL
),

-- Step 2: 计算 P1（1%分位）和 P99（99%分位）的值
percentile_value AS (
    SELECT
        (SELECT origin_value FROM sample_data
         WHERE row_num = FLOOR(1 + (total_rows - 1) * 0.01)
         LIMIT 1) AS p1_value,
        (SELECT origin_value FROM sample_data
         WHERE row_num = FLOOR(1 + (total_rows - 1) * 0.99)
         LIMIT 1) AS p99_value
    FROM sample_data
    LIMIT 1
),

-- Step 3: 双截尾，得到 G0
g0 AS (
    SELECT
        s.sec_code,
        s.report_date,
        s.dim_industry_code_sw,
        CASE
            WHEN s.row_num <= FLOOR(1 + (s.total_rows - 1) * 0.01) THEN p.p1_value
            WHEN s.row_num >= FLOOR(1 + (s.total_rows - 1) * 0.99) THEN p.p99_value
            ELSE s.origin_value
        END AS g0
    FROM sample_data s, percentile_value p
),

-- Step 4: 按行业计算 G0 中位数，得到 G1
industry_rank AS (
    SELECT
        sec_code,
        dim_industry_code_sw,
        g0,
        ROW_NUMBER() OVER (PARTITION BY dim_industry_code_sw ORDER BY g0) AS rn,
        COUNT(*)     OVER (PARTITION BY dim_industry_code_sw)              AS cnt
    FROM g0
),
industry_median AS (
    SELECT
        dim_industry_code_sw,
        AVG(g0) AS g1
    FROM industry_rank
    WHERE rn IN (FLOOR((cnt + 1) / 2.0), CEIL((cnt + 1) / 2.0))
    GROUP BY dim_industry_code_sw
),

-- Step 5: 去除行业影响，G2 = G0 - G1
g2 AS (
    SELECT
        a.sec_code,
        a.report_date,
        a.dim_industry_code_sw,
        (a.g0 - b.g1) AS g2
    FROM g0 a
    JOIN industry_median b ON a.dim_industry_code_sw = b.dim_industry_code_sw
),

-- Step 6: 从指标结果表关联 saleAdj
sale_adj AS (
    SELECT
        dim_sec_code    AS sec_code,
        dim_report_date AS report_date,
        index_value     AS sale_adj
    FROM com_data_index_value
    WHERE index_code      = '${adjustFactorIndexCode}'
      AND dim_report_date = '${reportDate}'
),

-- Step 7: 加权，G3 = G2 × saleAdj（INNER JOIN，无 saleAdj 的公司排除）
g3 AS (
    SELECT
        a.sec_code,
        a.report_date,
        a.dim_industry_code_sw,
        (a.g2 * b.sale_adj) AS g3
    FROM g2 a
    INNER JOIN sale_adj b
        ON a.sec_code   = b.sec_code
       AND a.report_date = b.report_date
),

-- Step 8: 按行业计算 G3 样本标准差，得到 G4
-- 同一行业内所有公司 G4 值相同；行业只有一家公司时 STDDEV_SAMP 返回 NULL，取 0
g4 AS (
    SELECT
        sec_code,
        report_date,
        dim_industry_code_sw,
        g3,
        COALESCE(
            STDDEV_SAMP(g3) OVER (PARTITION BY dim_industry_code_sw),
            0
        ) AS g4
    FROM g3
),

-- Step 9: 线性变换，G5 = G4 × 500 + 500
g5 AS (
    SELECT
        sec_code,
        report_date,
        dim_industry_code_sw,
        (g4 * 500 + 500) AS g5
    FROM g4
)

-- 最终输出：截断到 [0, 1000]
SELECT
    sec_code,
    report_date,
    report_date AS dim_report_date,
    dim_industry_code_sw,
    CASE
        WHEN g5 > 1000 THEN 1000
        WHEN g5 < 0    THEN 0
        ELSE g5
    END AS index_value
FROM g5
ORDER BY dim_industry_code_sw, sec_code
```

### 关键技术点

| 步骤 | 技术 | 说明 |
|------|------|------|
| 双截尾 | ROW_NUMBER + FLOOR | 与 AdjustFactor 完全相同 |
| 中位数 | ROW_NUMBER + FLOOR/CEIL | 奇偶数均适用 |
| saleAdj 关联 | INNER JOIN | 无调整系数的公司自动排除 |
| 行业标准差 | STDDEV_SAMP() OVER (PARTITION BY) | 窗口函数，每行保留公司粒度 |
| NULL 保护 | COALESCE(..., 0) | 行业只有一家公司时 STDDEV_SAMP 返回 NULL |
| 线性变换 | G4 × 500 + 500 | 映射到 0~1000 区间 |
| 截断 | CASE WHEN | 超出 [0,1000] 边界时截断 |

---

## 代码结构设计

### 函数签名

```groovy
/**
 * 计算内控评级分数
 * @param measureField          度量字段名，即原始指标值 G 所在字段（如 B1000001BT）
 * @param adjustFactorIndexCode saleAdj 对应的指标编码，用于从指标结果表关联调整系数
 * @return 计算结果列表
 */
List<Map<String, Object>> calc(String measureField, String adjustFactorIndexCode)
```

### 完整代码框架

```groovy
package indexFunc.internalControl

import com.dib.agent.data.source.DataQueryInfrastructure
import com.dib.agent.data.web.config.constant.DibIndexConst
import com.dib.agent.data.web.model.index.req.DataIndexCalcReq
import com.dib.agent.data.web.util.DibSqlBuilder
import com.dib.agent.data.web.util.IndexSqlUtil
import com.dib.agent.data.web.util.SpringContextUtil
import org.slf4j.Logger
import org.slf4j.LoggerFactory

/**
 * 内控评级-评级分数算子
 *
 * 计算流程：
 * G → G0（双截尾）→ G1（行业中位数）→ G2（去行业影响）
 * → G3（G2 × saleAdj 加权）→ G4（行业 STDDEV_SAMP）
 * → G5（G4 × 500 + 500）→ 截断到 [0, 1000]
 *
 * 动态参数：measureField、adjustFactorIndexCode、tableName（通过 IndexSqlUtil 获取）
 * 固定字段：sec_code, report_date, dim_industry_code_sw
 *
 * @author AI Assistant
 * @since 2026-03-17
 */
List<Map<String, Object>> calc(String measureField, String adjustFactorIndexCode) {
    Logger log = LoggerFactory.getLogger(this.class)
    DataIndexCalcReq calcReq = getBinding().getVariable(DibIndexConst.INDEX_SCRIPT_PARAM_NAME) as DataIndexCalcReq

    log.info("【内控算子】开始计算评级分数，指标 = {}", calcReq.getIndexCode())
    log.debug("【内控算子】度量字段 = {}，调整系数指标编码 = {}", measureField, adjustFactorIndexCode)

    try {
        if (!measureField) throw new IllegalArgumentException("度量字段不能为空")
        if (!adjustFactorIndexCode) throw new IllegalArgumentException("调整系数指标编码不能为空")

        String dataSourceCode = IndexSqlUtil.getDataSourceCode(calcReq)
        String tableName      = IndexSqlUtil.generateSqlBuilder(calcReq).getTableName()
        String reportDate     = calcReq.getDimReportDate()

        log.debug("【内控算子】表名 = {}，报告期 = {}", tableName, reportDate)

        String sql = buildGradeSql(tableName, measureField, adjustFactorIndexCode, reportDate)
        log.debug("【内控算子】SQL =\n{}", sql)

        List<Map<String, Object>> result = SpringContextUtil
            .getBean(DataQueryInfrastructure.class)
            .queryMaps(dataSourceCode, sql)

        if (result.isEmpty()) {
            log.warn("【内控算子】未查询到数据，请检查报告期 {} 的数据是否存在", reportDate)
        }

        log.info("【内控算子】计算完成，返回 {} 条记录", result.size())
        return result

    } catch (Exception e) {
        log.error("【内控算子】计算失败：{}", e.getMessage(), e)
        throw e
    }
}

/**
 * 构建评级分数计算 SQL（CTE 链式查询）
 *
 * @param tableName             数据表名（动态）
 * @param measureField          度量字段名（动态）
 * @param adjustFactorIndexCode saleAdj 指标编码（动态）
 * @param reportDate            报告期，格式 yyyy-MM-dd
 * @return 完整 CTE SQL
 */
private static String buildGradeSql(
        String tableName, String measureField,
        String adjustFactorIndexCode, String reportDate) {
    return """
WITH
-- Step 1~9 完整 CTE 链（见 SQL 设计章节）
...
SELECT sec_code, report_date, report_date AS dim_report_date,
       dim_industry_code_sw, index_value
FROM g5
ORDER BY dim_industry_code_sw, sec_code
"""
}
```

---

## 影响范围

### 新增文件

| 文件 | 说明 |
|------|------|
| `indexFunc/internalControl/Alg_IC_Grade.groovy` | 算子脚本（新增） |

### 无需修改的文件

- 不涉及任何 Java 代码修改
- 不涉及数据库 DDL 变更
- 不涉及配置文件修改

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| `measureField` 为空 | 抛出 `IllegalArgumentException`，记录 ERROR 日志 |
| `adjustFactorIndexCode` 为空 | 抛出 `IllegalArgumentException`，记录 ERROR 日志 |
| 原始指标值全为 null | 返回空列表，记录 WARN 日志 |
| 某公司无对应 saleAdj | INNER JOIN 自动排除，不影响其他公司计算 |
| 行业只有一家公司 | STDDEV_SAMP 返回 NULL，COALESCE 取 0，G4 = 0 |
| 行业内所有 G3 相同 | STDDEV_SAMP = 0，G4 = 0，G5 = 500，正常输出 |
| 数据源连接失败 | 抛出异常，记录 ERROR 日志 |
| 报告期无数据 | 返回空列表，记录 WARN 日志 |

---

## 风险点

| 风险 | 影响 | 应对 |
|------|------|------|
| saleAdj 数据缺失导致样本减少 | 中 | INNER JOIN 设计符合需求，记录 WARN 提示 |
| STDDEV_SAMP 返回 NULL（单公司行业） | 中 | COALESCE(..., 0) 保护 |
| G5 超出 [0,1000] 范围 | 低 | CASE WHEN 截断保护 |
| 数据量大导致性能问题 | 中 | 单一 SQL 减少往返，依赖数据库优化器 |

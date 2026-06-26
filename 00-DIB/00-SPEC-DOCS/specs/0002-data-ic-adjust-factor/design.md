# 002 内控评级-规模调整系数算子 技术设计

## 概述

开发 Groovy 脚本算子 `Alg_IC_Adjust_Factor`，使用单一 CTE 链式 SQL 查询，完成从原始指标值 G 到规模调整系数 sizeAdj 的全流程计算。算子结构与 `Alg_Industry_Deviation.groovy` 保持一致。

---

## 架构设计

### 整体架构

```
DataIndexCalcReq（输入，含 report_date）
       ↓
Alg_IC_Adjust_Factor.groovy
       ↓
┌──────────────────────────────────────┐
│  CTE Step 1: sample_data             │
│  - 从 com_data_index_value 取样本    │
│  - 过滤 report_date，排除 null 值    │
│  - 按 index_value ASC 排序           │
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
│  CTE Step 6: g3（Z-Score 标准化）    │
│  - avg_g = AVG(G2)                  │
│  - stddev_g = STDDEV_SAMP(G2)       │
│  - G3 = (G2 - avg_g) / stddev_g    │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 7: g4（行业 G3 最小值）    │
│  - G4 = MIN(G3) per industry        │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  CTE Step 8: size_adj（最终结果）    │
│  - sizeAdj = G3 - G4               │
└──────────────────────────────────────┘
       ↓
List<Map<String, Object>>（输出结果）
```

### 文件位置

```
dib-agent-service-data-web/
└── src/main/resources/indexFunc/
    └── internalControl/
        └── Alg_IC_Adjust_Factor.groovy   ← 新增
```

---

## 数据模型

### 动态参数

| 参数名 | 来源 | 说明 |
|--------|------|------|
| `tableName` | `IndexSqlUtil.generateSqlBuilder(calcReq).getTableName()` | 数据表名，动态获取 |
| `measureField` | 函数参数传入 | 度量字段名，即原始指标值 G 所在字段（如 `B1000001BT`） |
| `reportDate` | `calcReq.getReportDate()` | 报告期，从请求对象获取 |

### 固定字段

| 字段名 | 说明 |
|--------|------|
| `sec_code` | 公司代码 |
| `report_date` | 报告期 |
| `dim_industry_code_sw` | 申万行业代码（固定字段名） |

### 输入表结构

**动态表名**（通过 `tableName` 参数传入）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `sec_code` | VARCHAR | 公司代码 |
| `report_date` | DATE | 报告期 |
| `dim_industry_code_sw` | VARCHAR | 申万行业代码（固定字段名） |
| `${measureField}` | DECIMAL | 原始指标值 G（字段名动态传入） |

### 输出字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `sec_code` | String | 公司代码 |
| `report_date` | String | 报告期 |
| `dim_report_date` | String | 报告期（维度字段） |
| `dim_industry_code_sw` | String | 申万行业代码 |
| `index_value` | Double | 规模调整系数（sizeAdj） |

---

## SQL 设计

### 完整 CTE SQL

> 其中 `${tableName}`、`${measureField}`、`${reportDate}` 为 Groovy 字符串插值，运行时动态替换。

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
        ${measureField} AS index_value
    FROM ${tableName}
    WHERE report_date = '${reportDate}'
      AND ${measureField} IS NOT NULL
),

-- Step 2: 计算 P1（1%分位）和 P99（99%分位）的值
percentile_value AS (
    SELECT
        (SELECT index_value FROM sample_data
         WHERE row_num = FLOOR(1 + (total_rows - 1) * 0.01)
         LIMIT 1) AS p1_value,
        (SELECT index_value FROM sample_data
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
            ELSE s.index_value
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

-- Step 6: Z-Score 标准化，G3 = (G2 - avg_g) / stddev_g
global_stats AS (
    SELECT
        AVG(g2)          AS avg_g,
        STDDEV_SAMP(g2)  AS stddev_g
    FROM g2
),
g3 AS (
    SELECT
        a.sec_code,
        a.report_date,
        a.dim_industry_code_sw,
        CASE
            WHEN b.stddev_g = 0 OR b.stddev_g IS NULL THEN 0
            ELSE (a.g2 - b.avg_g) / b.stddev_g
        END AS g3
    FROM g2 a, global_stats b
),

-- Step 7: 按行业取 G3 最小值，得到 G4
g4 AS (
    SELECT
        dim_industry_code_sw,
        MIN(g3) AS g4
    FROM g3
    GROUP BY dim_industry_code_sw
),

-- Step 8: 规模调整系数 sizeAdj = G3 - G4
size_adj AS (
    SELECT
        a.sec_code,
        a.report_date,
        a.report_date                AS dim_report_date,
        a.dim_industry_code_sw,
        (a.g3 - b.g4)               AS size_adj
    FROM g3 a
    LEFT JOIN g4 b ON a.dim_industry_code_sw = b.dim_industry_code_sw
)

SELECT
    sec_code,
    report_date,
    dim_report_date,
    dim_industry_code_sw,
    size_adj AS index_value
FROM size_adj
ORDER BY dim_industry_code_sw, sec_code
```

### 关键技术点

| 步骤 | 技术 | 说明 |
|------|------|------|
| 分位数计算 | 子查询 + ROW_NUMBER | 按排序位置取 P1/P99 |
| 中位数计算 | ROW_NUMBER + FLOOR/CEIL | 奇偶数均适用 |
| 标准化 | AVG + STDDEV_SAMP | 样本标准差（n-1） |
| 除零保护 | CASE WHEN stddev_g = 0 | G3 = 0 |
| 行业最小值 | MIN() GROUP BY | 确保 sizeAdj ≥ 0 |

---

## 代码结构设计

### 函数签名

```groovy
/**
 * 计算内控评级规模调整系数
 * @param measureField 度量字段名，即原始指标值 G 所在的字段（如 B1000001BT）
 * @return 计算结果列表
 */
List<Map<String, Object>> calc(String measureField)
```

> 表名通过 `IndexSqlUtil.generateSqlBuilder(calcReq).getTableName()` 动态获取，与 `Alg_Industry_Deviation` 保持一致。

### 代码框架

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
 * 内控评级-规模调整系数算子
 *
 * 计算流程：
 * G → G0（双截尾）→ G1（行业中位数）→ G2（去行业影响）
 * → G3（Z-Score标准化）→ G4（行业最小值）→ sizeAdj（规模调整系数）
 *
 * 动态参数：measureField（度量字段）、tableName（通过 IndexSqlUtil 获取）
 * 固定字段：sec_code, report_date, dim_industry_code_sw
 *
 * @author [Author]
 * @since 2026-03-16
 */
List<Map<String, Object>> calc(String measureField) {
    Logger log = LoggerFactory.getLogger(this.class)
    DataIndexCalcReq calcReq = getBinding().getVariable(DibIndexConst.INDEX_SCRIPT_PARAM_NAME) as DataIndexCalcReq

    log.info("【内控算子】开始计算规模调整系数，指标 = {}", calcReq.getIndexCode())
    log.debug("【内控算子】度量字段 = {}", measureField)

    try {
        if (!measureField) {
            throw new IllegalArgumentException("度量字段不能为空")
        }

        String dataSourceCode = IndexSqlUtil.getDataSourceCode(calcReq)
        DibSqlBuilder dibSqlBuilder = IndexSqlUtil.generateSqlBuilder(calcReq)
        String tableName = dibSqlBuilder.getTableName()
        String reportDate = calcReq.getReportDate()

        log.debug("【内控算子】表名 = {}, 报告期 = {}", tableName, reportDate)

        String sql = buildSizeAdjSql(tableName, measureField, reportDate)
        log.debug("【内控算子】SQL =\n{}", sql)

        List<Map<String, Object>> result = SpringContextUtil
            .getBean(DataQueryInfrastructure.class)
            .queryRows(dataSourceCode, sql)

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
 * 构建规模调整系数计算 SQL
 * @param tableName    数据表名（动态）
 * @param measureField 度量字段名（动态）
 * @param reportDate   报告期，格式 yyyy-MM-dd
 * @return 完整 CTE SQL
 */
private String buildSizeAdjSql(String tableName, String measureField, String reportDate) {
    return """
        WITH
        -- Step 1 ~ Step 8 CTE 链（见 SQL 设计章节）
        ...
        SELECT sec_code, report_date, dim_report_date,
               dim_industry_code_sw, size_adj AS index_value
        FROM size_adj
        ORDER BY dim_industry_code_sw, sec_code
    """
}
```

---

## 影响范围

### 新增文件

| 文件 | 说明 |
|------|------|
| `indexFunc/internalControl/Alg_IC_Adjust_Factor.groovy` | 算子脚本（新增） |

### 无需修改的文件

- 不涉及任何 Java 代码修改
- 不涉及数据库 DDL 变更
- 不涉及配置文件修改

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| `index_value` 全为 null | 返回空列表，记录 WARN 日志 |
| `stddev_g = 0`（所有 G2 相同） | G3 = 0，通过 CASE WHEN 保护 |
| 行业只有一家公司 | 中位数 = 该公司值，G2 = 0，正常计算 |
| 数据源连接失败 | 抛出异常，记录 ERROR 日志 |
| 报告期无数据 | 返回空列表，记录 WARN 日志 |

---

## 风险点

| 风险 | 影响 | 应对 |
|------|------|------|
| 分位数行号计算精度 | 中 | 使用 FLOOR 确保整数行号，与参考 SQL 保持一致 |
| stddev_g 为 0 导致除零 | 高 | CASE WHEN 保护，G3 = 0 |
| 数据量大导致性能问题 | 中 | 单一 SQL 减少往返，依赖数据库优化器 |

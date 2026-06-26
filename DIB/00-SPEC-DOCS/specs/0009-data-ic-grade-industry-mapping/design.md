# 技术设计文档：0009 - 内控评级算子补充申万行业归并逻辑

## 1. 设计概述

在两个内控评级算子的 SQL CTE 链中，在 `sample_data` 之后插入一个新的 `industry_mapped` CTE，完成申万行业编码的归并处理。后续所有行业分组计算改用 `mapped_industry_code` 字段，最终结果同时输出原始编码和归并编码。

---

## 2. 影响文件

| 文件 | 改动类型 |
|------|---------|
| `indexFunc/internalControl/Alg1_IC_Adjust_Factor.groovy` | 修改 SQL 构建逻辑 |
| `indexFunc/internalControl/Alg2_IC_Final_Score.groovy` | 修改 SQL 构建逻辑 |

Java/Groovy 的 `calc()` 函数签名、参数校验、日志、查询执行逻辑**均不变**。

---

## 3. 新增 CTE：`industry_mapped`

### 3.1 逻辑说明

```
sample_data（已有）
    ↓
industry_count          -- 统计每个二级行业编码的公司数
    ↓
industry_mapped         -- 公司数 < 5 → mapped_industry_code = '510100'
                        -- 公司数 >= 5 → mapped_industry_code = 原始编码
    ↓
（后续 CTE 全部改用 mapped_industry_code 分组）
```

### 3.2 SQL 片段

```sql
-- 统计每个二级行业编码的公司数
industry_count AS (
    SELECT
        dim_industry_code_sw,
        COUNT(DISTINCT sec_code) AS company_count
    FROM sample_data
    GROUP BY dim_industry_code_sw
),
```

---

## 3.5 `sample_data` 二级行业过滤

申万行业编码规则：**末尾 2 位为 `00`** 即为二级行业编码（如 `410200`、`510100`）。

`sample_data` CTE 的 WHERE 条件需新增过滤，只保留二级行业编码的数据：

```sql
WHERE report_date = '${reportDate}'
  AND ${measureField} IS NOT NULL
  AND RIGHT(${industryDimField}, 2) = '00'    -- 只取二级行业编码
```

此过滤加在两个算子的 `cteSampleData(...)` 方法中，确保进入计算链的数据已是纯二级行业。

```sql
-- 统计每个二级行业编码的公司数（sample_data 已过滤为二级行业，此处直接统计）
industry_count AS (
    SELECT
        dim_industry_code_sw,
        COUNT(DISTINCT sec_code) AS company_count
    FROM sample_data
    GROUP BY dim_industry_code_sw
),

-- 行业归并：不足5家 → 510100
industry_mapped AS (
    SELECT
        s.sec_code,
        s.report_date,
        s.dim_industry_code_sw                                    AS original_industry_code,
        CASE
            WHEN c.company_count < 5 THEN '510100'
            ELSE s.dim_industry_code_sw
        END                                                       AS mapped_industry_code,
        s.measure_value
    FROM sample_data s
    JOIN industry_count c ON s.dim_industry_code_sw = c.dim_industry_code_sw
)
```

---

## 4. Alg1 改动详情（规模调整系数）

### 4.1 当前 CTE 链

```
sample_data → percentile_value → g0 → industry_rank → industry_median
→ g2 → global_stats → g3 → g4 → size_adj → SELECT
```

### 4.2 改动后 CTE 链

```
sample_data → industry_count → industry_mapped
→ percentile_value → g0 → industry_rank → industry_median
→ g2 → global_stats → g3 → g4 → size_adj → SELECT
```

### 4.3 各 CTE 字段变更

| CTE | 变更说明 |
|-----|---------|
| `sample_data` | 不变，保留 `dim_industry_code_sw` 字段 |
| `industry_count` | **新增**，统计各行业公司数 |
| `industry_mapped` | **新增**，输出 `original_industry_code` + `mapped_industry_code` + `measure_value` + `sec_code` |
| `percentile_value` | 数据来源改为 `industry_mapped`（取 `measure_value`） |
| `g0` | JOIN 来源改为 `industry_mapped`，`dim_industry_code_sw` 改为 `mapped_industry_code` |
| `industry_rank` | `PARTITION BY` 改为 `mapped_industry_code` |
| `industry_median` | `GROUP BY` 改为 `mapped_industry_code` |
| `g2` | JOIN 条件改为 `mapped_industry_code` |
| `g3`、`g4`、`size_adj` | `dim_industry_code_sw` 字段改为 `mapped_industry_code` |
| `SELECT` | 新增输出 `original_industry_code`、`mapped_industry_code` |

### 4.4 最终 SELECT 新增字段

```sql
original_industry_code,
mapped_industry_code,
```

---

## 5. Alg2 改动详情（评级分数）

### 5.1 当前 CTE 链

```
sample_data → percentile_value → g0 → industry_rank → industry_median
→ g2 → sale_adj → g3 → g4 → g5 → SELECT
```

### 5.2 改动后 CTE 链

```
sample_data → industry_count → industry_mapped
→ percentile_value → g0 → industry_rank → industry_median
→ g2 → sale_adj → g3 → g4 → g5 → SELECT
```

### 5.3 各 CTE 字段变更

Alg2 与 Alg1 的变更模式完全一致，差异仅在于：
- `g0` 中字段名为 `winsorized_value`（而非 `g0`）
- `g3` 是加权步骤（`g2 × sale_adj`），不是 Z-Score
- `g4` 是按行业计算样本标准差
- `g5` 是线性变换

所有行业分组字段 `dim_industry_code_sw` 统一改为 `mapped_industry_code`，逻辑不变。

### 5.4 最终 SELECT 新增字段

```sql
original_industry_code,
mapped_industry_code,
```

---

## 6. 代码结构规范（遵循宪法）

按宪法要求，每个 CTE 对应一个独立的 `private static String` 方法：

### Alg1 新增方法

```groovy
/**
 * industry_count：统计每个申万二级行业编码下的公司数量，用于判断是否需要归并
 */
private static String cteIndustryCount() { ... }

/**
 * industry_mapped：申万行业归并处理
 * 公司数 < 5 的行业 → mapped_industry_code 替换为 510100（综合-综合）
 * 公司数 >= 5 的行业 → mapped_industry_code 保持原始编码不变
 */
private static String cteIndustryMapped() { ... }
```

### Alg2 新增方法（同上，方法名相同）

```groovy
private static String cteIndustryCount() { ... }
private static String cteIndustryMapped() { ... }
```

### `buildXxxSql` 方法串联顺序

```groovy
// Alg1
"WITH " +
    cteSampleData(...) + ", " +
    cteIndustryCount() + ", " +       // 新增
    cteIndustryMapped() + ", " +      // 新增
    ctePercentileValue() + ", " +
    cteG0() + ", " +
    ...

// Alg2
"WITH " +
    cteSampleData(...) + ", " +
    cteIndustryCount() + ", " +       // 新增
    cteIndustryMapped() + ", " +      // 新增
    ctePercentileValue() + ", " +
    cteG0() + ", " +
    ...
```

---

## 7. 注意事项

1. `sample_data` WHERE 条件新增 `RIGHT(${industryDimField}, 2) = '00'`，只保留申万二级行业编码数据，过滤掉一级和三级编码行。
2. `industry_mapped` 中 `510100` 本身的公司（如果原本就有）和被归并进来的公司，合并后一起参与后续计算，无需特殊处理，SQL 自然合并。
3. `percentile_value` 的双截尾基于全样本（不分行业），数据来源从 `sample_data` 改为 `industry_mapped` 的 `measure_value`，结果不变，只是保持 CTE 链的一致性。
4. 禁止在 SQL 字符串内写 `--` 注释（遵循宪法），注释统一写在方法 JavaDoc 上。
5. `original_industry_code` 在整个 CTE 链中需要透传，确保最终 SELECT 能取到。

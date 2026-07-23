# 002 内控评级-规模调整系数算子 需求文档

## 背景

内控评级体系中，不同规模的公司在同一行业内存在天然的差异。为了消除规模因素对评级的影响，需要开发一个规模调整系数算子（`Alg_IC_Adjust_Factor`），对原始指标值进行双截尾处理、行业中位数去除、标准化，最终输出每家公司的规模调整系数（`sizeAdj`），用于后续内控评级计算。

## 目标用户

- 内控评级数据分析人员
- 数据产品团队
- 内控评级模型开发人员

## 功能描述

开发一个 Groovy 脚本算子 `Alg_IC_Adjust_Factor`，实现以下计算流程：

1. **G → G0（双截尾）**：对原始指标值进行上下 1% 分位数截尾，消除极端值影响
2. **G0 → G1（行业中位数）**：按行业分组计算中位数
3. **G0 → G2（去除行业影响）**：`G2 = G0 - G1`，消除行业差异
4. **G2 → G3（标准化）**：对 G2 进行 Z-Score 标准化，`G3 = (G2 - avg(G2)) / stddev(G2)`
5. **G3 → G4（行业最小值）**：按行业分组取 G3 的最小值
6. **G3/G4 → sizeAdj（规模调整系数）**：`sizeAdj = G3 - G4`，确保每个行业最小值为 0

## 所属模块

- 项目：dib-agent-service-data（独立项目）
- 模块：dib-agent-service-data-web
- 目录：`src/main/resources/indexFunc/internalControl/`
- 脚本文件：`Alg_IC_Adjust_Factor.groovy`

## 核心算法规则

### 步骤 1：获取样本范围并排序（G → G0 准备）

从固定样本范围表中获取当期公司列表，关联指标值表获取原始指标值 G，并按 G 升序排序：

```sql
-- 样本范围表（固定）
com_data_index_value

-- 关键字段
sec_code          -- 公司代码
report_date       -- 报告期
dim_industry_code_sw  -- 申万行业代码（固定字段名）
index_value       -- 指标值（固定字段名，即原始值 G）
```

### 步骤 2：双截尾（G → G0）

取上下 1% 分位数的值，对超出范围的值进行替换：

- 下截尾：`row_num <= FLOOR(1 + (total_rows - 1) * 0.01)` → 替换为 P1 值
- 上截尾：`row_num >= FLOOR(1 + (total_rows - 1) * 0.99)` → 替换为 P99 值
- 其余：保持原值

**公式**：
```
P1  = 第 FLOOR(1 + (N-1) * 0.01) 个排序值
P99 = 第 FLOOR(1 + (N-1) * 0.99) 个排序值
G0  = CASE WHEN rank <= P1位置 THEN P1
           WHEN rank >= P99位置 THEN P99
           ELSE G
      END
```

### 步骤 3：计算行业中位数（G1）

按 `dim_industry_code_sw` 分组，计算 G0 的中位数：

```
G1 = median(G0) per industry
```

中位数计算方式：
```sql
WHERE rn IN (FLOOR((cnt + 1) / 2.0), CEIL((cnt + 1) / 2.0))
```

### 步骤 4：去除行业影响（G2）

```
G2 = G0 - G1
```

### 步骤 5：Z-Score 标准化（G3）

对全量 G2 计算均值和样本标准差：

```
avg_g   = AVG(G2)
stddev_g = STDDEV_SAMP(G2)
G3 = (G2 - avg_g) / stddev_g
```

### 步骤 6：行业 G3 最小值（G4）

按行业分组取 G3 的最小值：

```
G4 = MIN(G3) per industry
```

### 步骤 7：计算规模调整系数（sizeAdj）

```
sizeAdj = G3 - G4
```

**说明**：此操作确保每个行业内的最小值为 0，所有值非负。

## 输入参数

算子接收 `DataIndexCalcReq` 对象，报告期 `report_date` 从该对象中获取。**表名和度量字段通过参数动态传入**，行业字段固定。

**动态参数（通过函数参数传入）**：

| 参数名 | 说明 |
|--------|------|
| `measureField` | 度量字段名，即原始指标值 G 所在的字段（如 `B1000001BT`） |
| `tableName` | 数据表名（通过 `IndexSqlUtil` / `DibSqlBuilder` 从 `calcReq` 中获取） |

**固定字段（不通过参数传入）**：

| 字段名 | 说明 |
|--------|------|
| `sec_code` | 公司代码 |
| `report_date` | 报告期 |
| `dim_industry_code_sw` | 申万行业代码（固定字段名）

## 输出结果

算子返回 `List<Map<String, Object>>`，每条记录包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `sec_code` | String | 公司代码 |
| `report_date` | String | 报告期 |
| `dim_report_date` | String | 报告期（维度字段，与 report_date 相同） |
| `dim_industry_code_sw` | String | 申万行业代码 |
| `index_value` | Double | 最终计算值（sizeAdj，规模调整系数） |

**说明**：
- 只输出最终结果字段，中间步骤（G0~G4）仅在 CTE SQL 中体现
- `index_value` 为最终输出值，即 `sizeAdj`
- 与现有脚本保持一致，输出 `dim_report_date` 维度字段

## 用户故事

- 作为内控评级分析人员，我希望能够计算每家公司的规模调整系数，以便在评级模型中消除规模因素的影响
- 作为数据产品团队，我希望算子能够自动处理极端值（双截尾），以便提供更稳健的调整系数
- 作为模型开发人员，我希望算子输出的 sizeAdj 值非负且行业内最小值为 0，以便直接用于后续评级计算

## 验收标准

- [ ] 标准1：算子能够正确执行双截尾（上下 1% 分位数替换）
- [ ] 标准2：算子能够正确计算行业中位数 G1
- [ ] 标准3：算子能够正确计算 G2 = G0 - G1
- [ ] 标准4：算子能够正确进行 Z-Score 标准化得到 G3
- [ ] 标准5：算子能够正确计算行业 G3 最小值 G4
- [ ] 标准6：算子能够正确计算 sizeAdj = G3 - G4，且每个行业最小值为 0
- [ ] 标准7：输出字段包含 sec_code、report_date、dim_report_date、dim_industry_code_sw、index_value
- [ ] 标准8：算子能够正确处理边界情况（指标值为空、行业只有一家公司等）

## 边界条件

- 当 `index_value` 为空（null）时，该公司不参与计算
- 当行业只有一家公司时，中位数即为该公司的值，G2 = 0
- 当 `stddev_g = 0`（所有 G2 相同）时，G3 = 0（避免除零错误）
- 当 `G4 = 0` 时，`sizeAdj = G3`

## 非功能需求

### 性能
- 处理 1000 家公司数据，执行时间 < 30 秒
- 支持并发执行多个指标计算任务

### 可维护性
- 代码结构清晰，遵循现有 Groovy 脚本规范（参考 `indexFunc/industry/` 下的脚本）
- 关键步骤添加日志输出，便于调试
- 日志前缀统一使用 `【内控算子】`

### 兼容性
- 与现有 `indexFunc/` 目录下的脚本保持一致的代码风格
- 使用相同的工具类（`DataQueryInfrastructure`、`IndexSqlUtil`、`DibSqlBuilder` 等）
- 输出格式与现有脚本一致（包含 `dim_report_date` 字段）

## 参考资料

### 参考 SQL

```sql
with sample_data as (
    SELECT sec_code, report_date 
    FROM com_data_index_value 
    WHERE report_date = '2024-12-31'
),
total_capital as (
    SELECT 
        ROW_NUMBER() OVER (ORDER BY B.index_value ASC) AS row_num,
        count(*) over () as total_rows,
        A.sec_code,
        A.report_date,
        B.dim_industry_code_sw,
        B.index_value
    FROM sample_data A
    INNER JOIN com_data_index_value B
        ON A.sec_code = B.sec_code AND A.report_date = B.report_date
),
percentile_positions_value AS (
    SELECT 
        (SELECT index_value FROM total_capital 
         WHERE row_num = FLOOR(1 + (total_rows - 1) * 0.01)) AS p1_value,
        (SELECT index_value FROM total_capital 
         WHERE row_num = FLOOR(1 + (total_rows - 1) * 0.99)) AS p99_value
),
total_capital_replace as (
    SELECT 
        A.sec_code, A.report_date, A.dim_industry_code_sw,
        CASE 
            WHEN A.row_num <= FLOOR(1 + (A.total_rows - 1) * 0.01) THEN B.p1_value
            WHEN A.row_num >= FLOOR(1 + (A.total_rows - 1) * 0.99) THEN B.p99_value
            ELSE A.index_value 
        END AS g0
    FROM total_capital A, percentile_positions_value B
),
industry_rank as (
    SELECT sec_code, dim_industry_code_sw, g0,
        ROW_NUMBER() OVER (PARTITION BY dim_industry_code_sw ORDER BY g0) AS rn,
        COUNT(*) OVER (PARTITION BY dim_industry_code_sw) AS cnt
    FROM total_capital_replace
),
industry_median as (
    SELECT dim_industry_code_sw, AVG(g0) AS g1
    FROM industry_rank
    WHERE rn IN (FLOOR((cnt + 1) / 2.0), CEIL((cnt + 1) / 2.0))
    GROUP BY dim_industry_code_sw
),
g2 as (
    SELECT a.sec_code, a.report_date, a.dim_industry_code_sw, (a.g0 - b.g1) as g2
    FROM total_capital_replace a, industry_median b
    WHERE a.dim_industry_code_sw = b.dim_industry_code_sw
),
gg as (
    SELECT avg(g2) as avg_g, STDDEV_SAMP(g2) as stddev_g FROM g2
),
g3 as (
    SELECT a.sec_code, a.report_date, a.dim_industry_code_sw, a.g2,
        (a.g2 - b.avg_g) / b.stddev_g as g3
    FROM g2 a, gg b
),
g4 as (
    SELECT dim_industry_code_sw, min(g3) as g4 FROM g3 GROUP BY dim_industry_code_sw
),
sizeAdj as (
    SELECT a.sec_code, a.report_date, a.dim_industry_code_sw, a.g3 - b.g4 as sizeAdj
    FROM g3 a LEFT JOIN g4 b ON a.dim_industry_code_sw = b.dim_industry_code_sw
)
SELECT 
    sec_code,
    report_date,
    report_date as dim_report_date,
    dim_industry_code_sw,
    sizeAdj as index_value
FROM sizeAdj
```

### 参考脚本
- `indexFunc/industry/Alg_Industry_Deviation.groovy` - 行业偏离度算子（结构参考）
- `indexFunc/toubao/Alg6_TB_Median_Dimless.groovy` - 中位数计算
- `indexFunc/toubao/Alg7_TB_Average_Dimless.groovy` - 均值计算

## 待确认问题

- [x] 算子命名：`Alg_IC_Adjust_Factor` - 已确认
- [x] 行业字段名：`dim_industry_code_sw`（固定）- 已确认
- [x] 指标值字段名：`index_value`（固定）- 已确认
- [x] 样本范围表：`com_data_index_value`（固定）- 已确认
- [x] 输出字段：只输出最终结果，中间步骤在 CTE 中体现 - 已确认
- [x] 脚本目录：`indexFunc/internalControl/` - 已确认

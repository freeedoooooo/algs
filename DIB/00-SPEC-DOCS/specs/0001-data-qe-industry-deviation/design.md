# 999 行业算子开发 技术设计

## 概述

开发一个基于 Groovy 的行业偏离度计算算子，使用 SQL CTE（公用表表达式）和窗口函数实现复杂的统计分析逻辑。算子采用多步骤 SQL 查询链式处理，确保高性能和可维护性。

## 架构设计

### 整体架构

```
定时任务/接口调用
       ↓
DataIndexCalcReq（输入参数）
       ↓
Alg_Industry_Deviation.groovy
       ↓
┌─────────────────────────────────┐
│  Step 1: 行业动态级别调整        │
│  - 统计三级行业公司数量          │
│  - 不足5家上升到二级             │
│  - 二级不足5家上升到一级         │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│  Step 2: 计算行业中位数和中位差  │
│  - 按行业分组排序                │
│  - 计算中位数 m                  │
│  - 计算中位差 x1 = |x0 - m|     │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│  Step 3: 计算全局中位差中位数    │
│  - 收集所有行业的中位差          │
│  - 计算 m1 = median(x1)         │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│  Step 4: 计算有效值范围          │
│  - 对每个行业计算范围            │
│  - [m - 3*m1, m + 3*m1]        │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│  Step 5: 剔除异常值计算行业均值  │
│  - 筛选有效值范围内的数据        │
│  - 计算行业均值                  │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│  Step 6: 计算行业偏离度          │
│  - 偏离度 = (值-均值)/|均值|    │
│  - 处理均值为0的特殊情况         │
└─────────────────────────────────┘
       ↓
List<Map<String, Object>>（输出结果）
```

### 技术选型

| 技术 | 选择 | 原因 |
|------|------|------|
| 脚本语言 | Groovy | 与现有脚本保持一致，支持动态执行 |
| SQL 技术 | CTE + 窗口函数 | 高性能，逻辑清晰，易于维护 |
| 日志框架 | SLF4J + Logback | 与现有项目一致 |
| 工具类 | IndexSqlUtil、DibSqlBuilder | 复用现有基础设施 |
| 数据查询 | DataQueryInfrastructure | 统一数据访问接口 |

## 数据模型

### 输入数据结构

**DataIndexCalcReq 对象**：
```groovy
class DataIndexCalcReq {
    String indexCode           // 指标代码
    String indexFormula        // 指标公式（用于生成 SQL）
    String dataSourceCode      // 数据源编码
    // ... 其他字段由 IndexSqlUtil 处理
}
```

**脚本方法参数**：
```groovy
/**
 * @param measureField 度量字段名（指标值字段，如 "revenue"）
 * @param companyDimField 公司维度字段名（如 "company_code"）
 * @param industryL1Field 一级行业维度字段名（如 "industry_l1_code"）
 * @param industryL2Field 二级行业维度字段名（如 "industry_l2_code"）
 * @param industryL3Field 三级行业维度字段名（如 "industry_l3_code"）
 */
List<Map<String, Object>> calc(
    String measureField,
    String companyDimField,
    String industryL1Field,
    String industryL2Field,
    String industryL3Field
)
```

**数据表结构**（单表，由调用方提供）：

```sql
data_table (
    report_date DATE,              -- 报告期（固定字段）
    company_code VARCHAR,          -- 公司代码（维度字段，字段名动态）
    company_name VARCHAR,          -- 公司名称（可选）
    industry_l1_code VARCHAR,      -- 一级行业代码（维度字段，字段名动态）
    industry_l1_name VARCHAR,      -- 一级行业名称（可选）
    industry_l2_code VARCHAR,      -- 二级行业代码（维度字段，字段名动态）
    industry_l2_name VARCHAR,      -- 二级行业名称（可选）
    industry_l3_code VARCHAR,      -- 三级行业代码（维度字段，字段名动态）
    industry_l3_name VARCHAR,      -- 三级行业名称（可选）
    revenue DECIMAL,               -- 指标值（度量字段，字段名动态）
    ...                            -- 其他维度和度量字段
)
```

**说明**：
- 所有数据在一张表中，包含公司信息、行业信息和指标值
- 字段名通过参数动态传入，不硬编码
- 参考 Alg1、Alg6、Alg7 的参数传递模式

### 输出数据结构

```groovy
List<Map<String, Object>> result = [
    [
        report_date: "2024-12-31",
        dim_report_date: "2024-12-31",
        company_code: "000001",           // 使用传入的 companyDimField
        company_name: "平安银行",
        industry_level: 3,
        industry_code: "480201",          // 最终确定的行业代码
        industry_name: "银行",
        origin_value: 15.5,               // 原始指标值
        median_value: 12.3,               // 行业中位数
        median_diff: 3.2,                 // 中位差
        valid_range_min: 8.5,             // 有效值范围下限
        valid_range_max: 16.1,            // 有效值范围上限
        industry_avg: 12.8,               // 行业均值
        industry_deviation: 0.211,        // 行业偏离度
        index_value: 0.211                // 最终计算值
    ],
    // ... 更多记录
]
```

**说明**：
- `report_date` 和 `dim_report_date` 是固定字段（参考 Alg1、Alg6）
- 维度字段使用传入的字段名
- 输出格式与现有脚本保持一致

## 核心算法设计

### 算法实现方案

采用 **单一 SQL 查询** 方案，使用 CTE 链式处理，一次性完成所有计算步骤。

**优点**：
- 性能最优，减少数据库往返
- 逻辑集中，易于理解和维护
- 充分利用数据库优化器

**参考**：Alg3_TB_Partition_Rank_Dimless.groovy 的复杂 CTE 链式查询模式

### SQL 设计（伪代码）

**说明**：
- 使用 `IndexSqlUtil.generateSqlBuilder(calcReq)` 获取基础查询
- 所有数据在一张表中，通过维度字段区分公司和行业
- 字段名通过参数动态传入

```sql
WITH 
-- Step 1: 获取基础数据（使用 IndexSqlUtil 生成的查询）
base_data AS (
    SELECT 
        report_date,
        ${companyDimField} as company_code,
        ${industryL1Field} as industry_l1_code,
        ${industryL2Field} as industry_l2_code,
        ${industryL3Field} as industry_l3_code,
        ${measureField} as origin_value
    FROM ${tableName}
    WHERE ${measureField} IS NOT NULL
      AND report_date = ?
),

-- Step 2: 统计三级行业公司数量
industry_l3_count AS (
    SELECT 
        industry_l3_code,
        COUNT(DISTINCT company_code) as company_count
    FROM base_data
    GROUP BY industry_l3_code
),

-- Step 3: 统计二级行业公司数量
industry_l2_count AS (
    SELECT 
        industry_l2_code,
        COUNT(DISTINCT company_code) as company_count
    FROM base_data
    GROUP BY industry_l2_code
),

-- Step 4: 统计一级行业公司数量
industry_l1_count AS (
    SELECT 
        industry_l1_code,
        COUNT(DISTINCT company_code) as company_count
    FROM base_data
    GROUP BY industry_l1_code
),

-- Step 5: 确定每个公司的最终行业级别
company_final_industry AS (
    SELECT 
        b.report_date,
        b.company_code,
        b.origin_value,
        CASE 
            WHEN l3.company_count >= 5 THEN 3
            WHEN l2.company_count >= 5 THEN 2
            ELSE 1
        END as industry_level,
        CASE 
            WHEN l3.company_count >= 5 THEN b.industry_l3_code
            WHEN l2.company_count >= 5 THEN b.industry_l2_code
            ELSE b.industry_l1_code
        END as industry_code
    FROM base_data b
    LEFT JOIN industry_l3_count l3 ON b.industry_l3_code = l3.industry_l3_code
    LEFT JOIN industry_l2_count l2 ON b.industry_l2_code = l2.industry_l2_code
    LEFT JOIN industry_l1_count l1 ON b.industry_l1_code = l1.industry_l1_code
),

-- Step 6: 计算每个行业的中位数（参考 Alg6）
industry_median AS (
    SELECT
        industry_code,
        AVG(origin_value) as median_value
    FROM (
        SELECT
            industry_code,
            origin_value,
            ROW_NUMBER() OVER (PARTITION BY industry_code ORDER BY origin_value) as rn,
            COUNT(*) OVER (PARTITION BY industry_code) as cnt
        FROM company_final_industry
    ) ranked
    WHERE 
        CASE WHEN cnt % 2 = 1 THEN rn = FLOOR(cnt / 2) + 1
             ELSE rn IN (cnt DIV 2, cnt DIV 2 + 1)
        END
    GROUP BY industry_code
),

-- Step 7: 计算每个公司的中位差
company_median_diff AS (
    SELECT
        c.*,
        m.median_value,
        ABS(c.origin_value - m.median_value) as median_diff
    FROM company_final_industry c
    JOIN industry_median m ON c.industry_code = m.industry_code
),

-- Step 8: 计算全局中位差的中位数 m1
global_median_diff AS (
    SELECT
        AVG(median_diff) as m1
    FROM (
        SELECT
            median_diff,
            ROW_NUMBER() OVER (ORDER BY median_diff) as rn,
            COUNT(*) OVER () as cnt
        FROM company_median_diff
    ) ranked
    WHERE 
        CASE WHEN cnt % 2 = 1 THEN rn = FLOOR(cnt / 2) + 1
             ELSE rn IN (cnt DIV 2, cnt DIV 2 + 1)
        END
),

-- Step 9: 计算每个行业的有效值范围
industry_valid_range AS (
    SELECT
        m.industry_code,
        m.median_value,
        g.m1,
        m.median_value - 3 * g.m1 as valid_range_min,
        m.median_value + 3 * g.m1 as valid_range_max
    FROM industry_median m
    CROSS JOIN global_median_diff g
),

-- Step 10: 剔除异常值，计算行业均值
industry_avg AS (
    SELECT
        c.industry_code,
        AVG(c.origin_value) as industry_avg
    FROM company_median_diff c
    JOIN industry_valid_range r ON c.industry_code = r.industry_code
    WHERE c.origin_value BETWEEN r.valid_range_min AND r.valid_range_max
    GROUP BY c.industry_code
),

-- Step 11: 计算最终结果
final_result AS (
    SELECT
        c.report_date,
        c.report_date as dim_report_date,
        c.company_code,
        c.company_code as dim_company_code,
        c.industry_level,
        c.industry_code,
        c.origin_value,
        c.median_value,
        c.median_diff,
        r.valid_range_min,
        r.valid_range_max,
        a.industry_avg,
        CASE 
            WHEN a.industry_avg != 0 THEN 
                (c.origin_value - a.industry_avg) / ABS(a.industry_avg)
            ELSE 
                c.origin_value - a.industry_avg
        END as industry_deviation
    FROM company_median_diff c
    JOIN industry_valid_range r ON c.industry_code = r.industry_code
    JOIN industry_avg a ON c.industry_code = a.industry_code
)

SELECT 
    *,
    industry_deviation as index_value
FROM final_result
ORDER BY industry_code, company_code;
```

**关键点**：
- 使用 `${companyDimField}`、`${measureField}` 等变量替换字段名
- 参考 Alg1 的 `selectSql.replace(calcReq.getIndexFormula(), measureField)` 模式
- 使用 `DibSqlBuilder` 获取表名和基础查询条件

### 关键技术点

1. **中位数计算**：
   - 使用 ROW_NUMBER() 窗口函数排序
   - 根据奇偶数量选择中间值
   - 参考 Alg6_TB_Median_Dimless.groovy

2. **动态行业级别**：
   - 使用 CASE WHEN 根据公司数量选择行业级别
   - 三级→二级→一级的逐级判断

3. **异常值剔除**：
   - 使用 BETWEEN 条件筛选有效值范围
   - 参考 Alg1 的异常值处理逻辑

4. **性能优化**：
   - 使用 CTE 避免重复计算
   - 充分利用窗口函数减少子查询
   - 添加必要的索引建议

## 代码结构设计

### 文件结构

```
dib-agent-service-data-web/
└── src/main/resources/indexFunc/
    └── industry/
        └── Alg_Industry_Deviation.groovy
```

### 代码框架

```groovy
package indexFunc.industry

import com.dib.agent.data.source.DataQueryInfrastructure
import com.dib.agent.data.web.config.constant.DibIndexConst
import com.dib.agent.data.web.model.index.req.DataIndexCalcReq
import com.dib.agent.data.web.util.DibSqlBuilder
import com.dib.agent.data.web.util.IndexSqlUtil
import com.dib.agent.data.web.util.SpringContextUtil
import org.slf4j.Logger
import org.slf4j.LoggerFactory

/**
 * 行业偏离度算子
 * 
 * 算法步骤：
 * 1. 行业动态级别调整（三级→二级→一级）
 * 2. 计算行业中位数和中位差
 * 3. 计算全局中位差中位数 m1
 * 4. 计算有效值范围 [m - 3*m1, m + 3*m1]
 * 5. 剔除异常值，计算行业均值
 * 6. 计算行业偏离度
 *
 * @author [Your Name]
 * @since 2026-03-05
 */
List<Map<String, Object>> calc(
    String measureField,
    String companyDimField,
    String industryL1Field,
    String industryL2Field,
    String industryL3Field
) {
    Logger log = LoggerFactory.getLogger(this.class)
    DataIndexCalcReq calcReq = getBinding().getVariable(DibIndexConst.INDEX_SCRIPT_PARAM_NAME) as DataIndexCalcReq
    
    log.info("【行业算子】开始计算指标 {} 的行业偏离度", calcReq.getIndexCode())
    log.debug("【行业算子】度量字段 = {}", measureField)
    log.debug("【行业算子】公司维度字段 = {}", companyDimField)
    log.debug("【行业算子】行业维度字段 = {}, {}, {}", industryL1Field, industryL2Field, industryL3Field)
    
    // 获取数据源编码
    String dataSourceCode = IndexSqlUtil.getDataSourceCode(calcReq)
    
    // 获取表名和基础查询（参考 Alg1、Alg6）
    DibSqlBuilder dibSqlBuilder = IndexSqlUtil.generateSqlBuilder(calcReq)
    String tableName = dibSqlBuilder.getTableName()
    
    // 构建 SQL
    String sql = buildIndustryDeviationSql(
        tableName, 
        measureField, 
        companyDimField,
        industryL1Field,
        industryL2Field,
        industryL3Field
    )
    
    log.debug("【行业算子】SQL =\n {}", sql)
    
    // 执行查询
    List<Map<String, Object>> resultList = SpringContextUtil.getBean(DataQueryInfrastructure.class)
        .queryRows(dataSourceCode, sql)
    
    log.info("【行业算子】计算完成，返回 {} 条记录", resultList.size())
    
    return resultList
}

/**
 * 构建行业偏离度计算 SQL
 */
private String buildIndustryDeviationSql(
    String tableName,
    String measureField,
    String companyDimField,
    String industryL1Field,
    String industryL2Field,
    String industryL3Field
) {
    // 构建完整 SQL（使用 CTE）
    String sql = """
        WITH 
        -- Step 1: 获取基础数据
        base_data AS (
            SELECT 
                report_date,
                ${companyDimField} as company_code,
                ${industryL1Field} as industry_l1_code,
                ${industryL2Field} as industry_l2_code,
                ${industryL3Field} as industry_l3_code,
                ${measureField} as origin_value
            FROM ${tableName}
            WHERE ${measureField} IS NOT NULL
        ),
        
        -- Step 2-5: 行业级别调整
        -- ... 其他 CTE
        
        -- Step 11: 最终结果
        final_result AS (
            SELECT
                report_date,
                report_date as dim_report_date,
                company_code,
                company_code as dim_company_code,
                -- ... 其他字段
                industry_deviation as index_value
            FROM ...
        )
        
        SELECT * FROM final_result
        ORDER BY industry_code, company_code
    """
    
    return sql
}
```

**关键点**：
- 参数模式参考 Alg3：`calc(String measureField, String secDimField, ...)`
- 使用 `DibSqlBuilder` 获取表名，参考 Alg6、Alg7
- 字段名动态替换，参考 Alg1 的 `replace()` 模式
- 输出字段包含 `dim_report_date`、`dim_company_code`，与现有脚本一致

### 函数签名

```groovy
/**
 * 计算行业偏离度
 *
 * @param measureField 度量字段名（指标值字段，如 "revenue"）
 * @param companyDimField 公司维度字段名（如 "company_code"）
 * @param industryL1Field 一级行业维度字段名（如 "industry_l1_code"）
 * @param industryL2Field 二级行业维度字段名（如 "industry_l2_code"）
 * @param industryL3Field 三级行业维度字段名（如 "industry_l3_code"）
 * @return 计算结果列表
 */
List<Map<String, Object>> calc(
    String measureField,
    String companyDimField,
    String industryL1Field,
    String industryL2Field,
    String industryL3Field
)
```

**参数说明**：
- 所有字段名都是动态传入，不硬编码
- 参考 Alg3 的多参数模式：`calc(String measureField, String secDimField, ...)`
- 参考 Alg1 的字段替换模式：`selectSql.replace(calcReq.getIndexFormula(), measureField)`

## 日志设计

### 日志级别

| 级别 | 使用场景 |
|------|----------|
| INFO | 算子开始、完成、记录数量 |
| DEBUG | SQL 语句、中间结果 |
| WARN | 异常情况（如行业公司数不足） |
| ERROR | 执行错误 |

### 日志示例

```groovy
log.info("【行业算子】开始计算指标 {} 的行业偏离度", calcReq.getIndexCode())
log.debug("【行业算子】度量字段 = {}", measureField)
log.debug("【行业算子】报告期 = {}", reportDate)
log.debug("【行业算子】SQL =\n {}", sql)
log.info("【行业算子】计算完成，返回 {} 条记录", resultList.size())
```

## 性能优化

### 数据库优化

1. **索引建议**：
   ```sql
   -- 数据表（单表）
   CREATE INDEX idx_data_report ON data_table(report_date);
   CREATE INDEX idx_data_company ON data_table(company_code);
   CREATE INDEX idx_data_industry_l3 ON data_table(industry_l3_code);
   CREATE INDEX idx_data_industry_l2 ON data_table(industry_l2_code);
   CREATE INDEX idx_data_industry_l1 ON data_table(industry_l1_code);
   CREATE INDEX idx_data_measure ON data_table(measure_field);
   
   -- 复合索引（提升性能）
   CREATE INDEX idx_data_composite ON data_table(report_date, industry_l3_code, measure_field);
   ```

   **说明**：
   - 字段名仅为示例，实际字段名由参数传入
   - 索引应根据实际表结构和字段名创建

2. **查询优化**：
   - 使用 CTE 避免重复计算
   - 窗口函数替代子查询
   - 合理使用 JOIN 类型
   - 参考 Alg6 的 CTE 优化模式

### 代码优化

1. **参数化查询**：避免 SQL 注入
2. **结果集大小控制**：必要时分页处理
3. **内存管理**：及时释放大对象

## 错误处理

### 异常场景

| 场景 | 处理方式 |
|------|----------|
| 表名参数缺失 | 抛出 IllegalArgumentException |
| 数据源连接失败 | 抛出 DataAccessException |
| SQL 执行错误 | 记录错误日志，抛出异常 |
| 结果集为空 | 返回空列表，记录 WARN 日志 |
| 指标值全部为空 | 返回空列表，记录 WARN 日志 |

### 错误处理代码

```groovy
try {
    // 参数校验
    if (!measureField) {
        throw new IllegalArgumentException("度量字段不能为空")
    }
    
    // 执行查询
    List<Map<String, Object>> resultList = queryData(sql)
    
    // 结果校验
    if (resultList.isEmpty()) {
        log.warn("【行业算子】未查询到数据，请检查输入参数")
    }
    
    return resultList
    
} catch (Exception e) {
    log.error("【行业算子】计算失败：{}", e.getMessage(), e)
    throw e
}
```

## 测试策略

### 单元测试

1. **中位数计算测试**：
   - 奇数个数据
   - 偶数个数据
   - 单个数据

2. **行业级别调整测试**：
   - 三级行业 >= 5 家
   - 三级行业 < 5 家，二级 >= 5 家
   - 二级行业 < 5 家，一级 >= 5 家
   - 一级行业 < 5 家

3. **异常值剔除测试**：
   - 正常值范围内
   - 超出有效范围
   - 边界值

4. **偏离度计算测试**：
   - 均值 != 0
   - 均值 = 0
   - 正偏离
   - 负偏离

### 集成测试

1. **完整流程测试**：使用真实数据验证整个计算流程
2. **性能测试**：1000 家公司数据，执行时间 < 30 秒
3. **并发测试**：多个指标同时计算

### 测试数据

```groovy
// 测试数据示例
def testData = [
    // 三级行业 >= 5 家
    [company_code: "000001", industry_l3: "480201", value: 15.5],
    [company_code: "000002", industry_l3: "480201", value: 12.3],
    [company_code: "000003", industry_l3: "480201", value: 18.7],
    [company_code: "000004", industry_l3: "480201", value: 11.2],
    [company_code: "000005", industry_l3: "480201", value: 14.8],
    
    // 三级行业 < 5 家，需要上升到二级
    [company_code: "000006", industry_l3: "480202", value: 20.1],
    [company_code: "000007", industry_l3: "480202", value: 19.5],
]
```

## 部署说明

### 部署步骤

1. 将 `Alg_Industry_Deviation.groovy` 放入 `src/main/resources/indexFunc/industry/` 目录
2. 重启 dib-agent-service-data 服务
3. 配置定时任务或接口调用
4. 验证算子执行结果

### 配置要求

- JDK 8+
- Groovy 2.5+
- 数据库支持窗口函数（PostgreSQL 9.3+、MySQL 8.0+）

### 监控指标

- 执行时间
- 处理记录数
- 错误率
- 内存使用

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 数据量过大导致性能问题 | 高 | 添加分页处理，优化 SQL，增加索引 |
| 行业分类数据不完整 | 中 | 添加数据校验，记录异常日志 |
| 中位数计算精度问题 | 低 | 使用数据库内置函数，确保精度 |
| 并发执行资源竞争 | 中 | 使用连接池，限制并发数 |

## 扩展性设计

### 支持其他行业分类标准

```groovy
// 预留参数
List<Map<String, Object>> calc(
    String measureField,
    String industryStandard = "SHENWAN"  // 默认申万，可扩展为 "CSI"（中证）
)
```

### 支持自定义异常值阈值

```groovy
// 预留参数
List<Map<String, Object>> calc(
    String measureField,
    double outlierThreshold = 3.0  // 默认 3 倍 m1，可配置
)
```

### 支持多报告期批量计算

```groovy
// 预留参数
List<Map<String, Object>> calc(
    String measureField,
    List<String> reportDates  // 支持多个报告期
)
```

## 参考实现

### 参考脚本对照表

| 算法步骤 | 参考脚本 | 借鉴点 |
|---------|---------|--------|
| 中位数计算 | Alg6_TB_Median_Dimless.groovy | CTE + 窗口函数实现中位数 |
| 均值计算 | Alg7_TB_Average_Dimless.groovy | 分组统计和 AVG() 使用 |
| 异常值处理 | Alg1_TB_Regular_Dimless.groovy | errNums 排除逻辑 |
| 复杂 CTE 链 | Alg3_TB_Partition_Rank_Dimless.groovy | 多步骤 CTE 组织方式 |
| 日志输出 | 所有脚本 | Logger 使用模式 |
| 工具类使用 | 所有脚本 | IndexSqlUtil、SpringContextUtil |

## 附录

### SQL 方言兼容性

| 数据库 | 窗口函数 | CTE | 中位数函数 | 兼容性 |
|--------|---------|-----|-----------|--------|
| PostgreSQL | ✅ | ✅ | PERCENTILE_CONT | ✅ 完全兼容 |
| MySQL 8.0+ | ✅ | ✅ | 需手动实现 | ✅ 兼容 |
| Oracle | ✅ | ✅ | MEDIAN | ✅ 兼容 |
| SQL Server | ✅ | ✅ | PERCENTILE_CONT | ✅ 兼容 |

### 性能基准

| 数据规模 | 预期执行时间 | 内存占用 |
|---------|-------------|---------|
| 100 家公司 | < 5 秒 | < 50 MB |
| 500 家公司 | < 15 秒 | < 100 MB |
| 1000 家公司 | < 30 秒 | < 200 MB |
| 5000 家公司 | < 2 分钟 | < 500 MB |

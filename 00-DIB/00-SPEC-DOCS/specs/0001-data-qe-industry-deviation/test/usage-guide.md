# 行业偏离度算子 - 使用说明文档

## 算子概述

**算子名称**：行业偏离度算子（Industry Deviation Operator）

**需求编号**：001

**脚本文件**：`Alg_Industry_Deviation.groovy`

**功能描述**：根据申万行业分类，计算公司指标值相对于行业均值的偏离度，用于识别行业内的异常公司。

**适用场景**：
- 财务指标行业对比分析
- 异常公司识别
- 行业研究报告
- 投资决策支持

---

## 算法原理

### 核心步骤

1. **行业动态级别调整**
   - 优先使用三级行业分类
   - 若三级行业公司数<5，上升到二级
   - 若二级行业公司数<5，上升到一级

2. **计算行业中位数**
   - 按最终行业分组
   - 计算每组指标值的中位数 m

3. **计算中位差**
   - 每个公司的中位差 = |指标值 - 行业中位数|

4. **计算全局中位差中位数 m1**
   - 对所有公司的中位差再次计算中位数

5. **确定有效值范围**
   - 有效范围 = [m - 3*m1, m + 3*m1]

6. **剔除异常值，计算行业均值**
   - 只使用有效范围内的值
   - 行业均值 = sum(有效值) / count(有效值)

7. **计算行业偏离度**
   - 若行业均值 ≠ 0：偏离度 = (指标值 - 行业均值) / |行业均值|
   - 若行业均值 = 0：偏离度 = 指标值 - 行业均值

---

## 参数说明

### 输入参数

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|-------|------|------|------|------|
| measureField | String | 是 | 度量字段名（指标值字段） | `roe_value` |
| companyDimField | String | 是 | 公司维度字段名 | `company_code` |
| industryL1Field | String | 是 | 一级行业维度字段名 | `sw_industry_l1` |
| industryL2Field | String | 是 | 二级行业维度字段名 | `sw_industry_l2` |
| industryL3Field | String | 是 | 三级行业维度字段名 | `sw_industry_l3` |

### 输出字段

| 字段名 | 类型 | 说明 |
|-------|------|------|
| report_date | Date | 报告期 |
| dim_report_date | Date | 报告期（维度字段） |
| company_code | String | 公司代码 |
| dim_company_code | String | 公司代码（维度字段） |
| industry_level | Integer | 最终使用的行业级别（1/2/3） |
| industry_code | String | 最终使用的行业代码 |
| origin_value | Decimal | 原始指标值 |
| median_value | Decimal | 行业中位数 |
| median_diff | Decimal | 中位差 |
| valid_range_min | Decimal | 有效值范围下限 |
| valid_range_max | Decimal | 有效值范围上限 |
| industry_avg | Decimal | 行业均值（剔除异常值后） |
| industry_deviation | Decimal | 行业偏离度 |
| index_value | Decimal | 指标值（等于 industry_deviation） |

---

## 调用示例

### 示例1：计算 ROE 行业偏离度

**场景**：计算所有公司2024年12月31日的净资产收益率（ROE）行业偏离度

**请求参数**：
```json
{
  "indexCode": "ROE_INDUSTRY_DEVIATION",
  "reportDate": "2024-12-31",
  "dataSourceCode": "FINANCIAL_DATA",
  "tableName": "fact_financial_indicators",
  "params": {
    "measureField": "roe_value",
    "companyDimField": "company_code",
    "industryL1Field": "sw_industry_l1",
    "industryL2Field": "sw_industry_l2",
    "industryL3Field": "sw_industry_l3"
  }
}
```

**调用方式**：
```bash
curl -X POST http://server:8080/api/index/calc \
  -H "Content-Type: application/json" \
  -d @request.json
```

**返回结果示例**：
```json
[
  {
    "report_date": "2024-12-31",
    "dim_report_date": "2024-12-31",
    "company_code": "000001",
    "dim_company_code": "000001",
    "industry_level": 3,
    "industry_code": "801010",
    "origin_value": 15.5,
    "median_value": 12.3,
    "median_diff": 3.2,
    "valid_range_min": 8.5,
    "valid_range_max": 16.1,
    "industry_avg": 12.8,
    "industry_deviation": 0.2109,
    "index_value": 0.2109
  }
]
```

---

### 示例2：计算营业收入增长率行业偏离度

**请求参数**：
```json
{
  "indexCode": "REVENUE_GROWTH_DEVIATION",
  "reportDate": "2024-12-31",
  "dataSourceCode": "FINANCIAL_DATA",
  "tableName": "fact_financial_indicators",
  "params": {
    "measureField": "revenue_growth_rate",
    "companyDimField": "company_code",
    "industryL1Field": "sw_industry_l1",
    "industryL2Field": "sw_industry_l2",
    "industryL3Field": "sw_industry_l3"
  }
}
```

---

## 数据要求

### 输入数据表结构

```sql
CREATE TABLE fact_financial_indicators (
    report_date DATE NOT NULL,
    company_code VARCHAR(20) NOT NULL,
    sw_industry_l1 VARCHAR(10),
    sw_industry_l2 VARCHAR(10),
    sw_industry_l3 VARCHAR(10),
    roe_value DECIMAL(18, 4),
    revenue_growth_rate DECIMAL(18, 4),
    -- 其他指标字段...
    PRIMARY KEY (report_date, company_code)
);
```

### 数据质量要求

1. **必填字段**：
   - report_date（报告期）
   - company_code（公司代码）
   - 度量字段（指标值）

2. **行业分类字段**：
   - 至少需要一级行业分类
   - 建议提供完整的三级分类

3. **数据完整性**：
   - 指标值为 NULL 的记录将被排除
   - 行业分类缺失的记录将被排除

---

## 索引建议

为提升性能，建议在数据表上创建以下索引：

```sql
-- 复合索引1：报告期 + 公司代码
CREATE INDEX idx_report_company ON fact_financial_indicators(report_date, company_code);

-- 复合索引2：报告期 + 三级行业
CREATE INDEX idx_report_industry_l3 ON fact_financial_indicators(report_date, sw_industry_l3);

-- 复合索引3：报告期 + 二级行业
CREATE INDEX idx_report_industry_l2 ON fact_financial_indicators(report_date, sw_industry_l2);

-- 复合索引4：报告期 + 一级行业
CREATE INDEX idx_report_industry_l1 ON fact_financial_indicators(report_date, sw_industry_l1);
```

---

## 结果解读

### 偏离度含义

| 偏离度范围 | 含义 | 说明 |
|-----------|------|------|
| > 0.5 | 显著高于行业均值 | 公司表现远超行业平均水平 |
| 0.1 ~ 0.5 | 高于行业均值 | 公司表现优于行业平均水平 |
| -0.1 ~ 0.1 | 接近行业均值 | 公司表现与行业平均水平相当 |
| -0.5 ~ -0.1 | 低于行业均值 | 公司表现弱于行业平均水平 |
| < -0.5 | 显著低于行业均值 | 公司表现远低于行业平均水平 |

### 应用场景示例

**场景1：识别高成长公司**
```sql
-- 查找营业收入增长率显著高于行业的公司
SELECT 
    company_code,
    origin_value as revenue_growth_rate,
    industry_avg,
    industry_deviation
FROM result
WHERE industry_deviation > 0.5
ORDER BY industry_deviation DESC
LIMIT 20;
```

**场景2：行业对比分析**
```sql
-- 对比不同行业的平均偏离度
SELECT 
    industry_code,
    COUNT(*) as company_count,
    AVG(industry_deviation) as avg_deviation,
    STDDEV(industry_deviation) as stddev_deviation
FROM result
GROUP BY industry_code
ORDER BY avg_deviation DESC;
```

---

## 注意事项

1. **行业分类标准**
   - 必须使用申万行业分类标准
   - 确保行业代码的一致性

2. **数据时效性**
   - 建议使用最新报告期数据
   - 定期更新计算结果

3. **异常值处理**
   - 算子会自动剔除异常值
   - 剔除标准：超出 [m - 3*m1, m + 3*m1] 范围

4. **性能考虑**
   - 大数据量（>5000家公司）建议分批计算
   - 合理使用索引提升查询性能

5. **结果验证**
   - 首次使用建议人工抽样验证
   - 关注行业均值为0的特殊情况

---

## 常见问题

### Q1：为什么某些公司没有计算结果？

**A**：可能原因：
- 指标值为 NULL
- 行业分类缺失
- 所在行业公司数不足（一级行业<5家）

### Q2：偏离度为什么会很大（>10）？

**A**：可能原因：
- 行业均值接近0
- 公司指标值异常（未被剔除）
- 建议检查原始数据质量

### Q3：如何处理行业均值为0的情况？

**A**：算子已自动处理：
- 当行业均值=0时，偏离度 = 指标值 - 行业均值
- 此时偏离度表示绝对差异，而非相对差异

### Q4：计算速度慢怎么办？

**A**：优化建议：
- 检查索引是否创建
- 减少数据量（按报告期分批）
- 优化数据库配置

---

## 运维监控

### 监控指标

1. **执行时间**
   - 正常：< 30秒（1000家公司）
   - 告警：> 60秒

2. **错误率**
   - 正常：< 1%
   - 告警：> 5%

3. **数据量**
   - 监控每次计算的公司数量
   - 监控结果记录数

### 日志检索

```bash
# 查看算子执行日志
grep "【行业算子】" application.log

# 查看错误日志
grep "【行业算子】.*ERROR" application.log

# 查看性能日志
grep "【行业算子】.*计算完成" application.log
```

---

## 版本历史

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| 1.0 | 2026-03-05 | 初始版本 | AI Assistant |

---

## 联系方式

如有问题或建议，请联系：
- 项目组：dib-agent-service-data 团队
- 文档位置：`AI-DOCS/specs/999-industry-operator/`

---

## 相关文档

- 需求文档：`requirements.md`
- 设计文档：`design.md`
- 单元测试指南：`unit-test-guide.md`
- 集成测试指南：`integration-test-guide.md`

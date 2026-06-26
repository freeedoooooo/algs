# 行业偏离度算子 - 集成测试指南

## 测试目标

验证 `Alg_Industry_Deviation.groovy` 在真实环境中的完整功能，包括：
- 完整计算流程验证
- 性能测试
- 并发测试
- 结果准确性验证

## 测试环境准备

### 环境要求

- 测试环境：dib-agent-service-data 测试服务器
- 数据库：测试数据库（包含真实业务数据）
- JDK版本：1.8+
- Groovy版本：2.5+

### 数据准备

使用真实业务数据进行测试，数据规模：
- 公司数量：1000家
- 行业分类：申万三级行业分类（完整）
- 报告期：2024-12-31
- 指标：净资产收益率（ROE）

---

## 测试用例

### 用例1：完整流程测试

**测试目标**：验证从接口调用到结果返回的完整流程

**测试步骤**：

1. 构造请求参数
```json
{
  "indexCode": "ROE_INDUSTRY_DEVIATION",
  "reportDate": "2024-12-31",
  "dataSourceCode": "FINANCIAL_DATA",
  "params": {
    "measureField": "roe_value",
    "companyDimField": "company_code",
    "industryL1Field": "sw_industry_l1",
    "industryL2Field": "sw_industry_l2",
    "industryL3Field": "sw_industry_l3"
  }
}
```

2. 调用算子接口
```bash
curl -X POST http://test-server:8080/api/index/calc \
  -H "Content-Type: application/json" \
  -d @request.json
```

3. 验证响应结果
- HTTP状态码：200
- 返回记录数：1000条
- 响应时间：< 30秒

**预期结果**：
- ✅ 接口调用成功
- ✅ 返回数据完整
- ✅ 所有公司都有偏离度计算结果

---

### 用例2：性能测试

**测试目标**：验证算子在大数据量下的性能表现

**测试场景**：

| 数据规模 | 公司数量 | 预期执行时间 |
|---------|---------|------------|
| 小规模   | 100家   | < 5秒      |
| 中规模   | 500家   | < 15秒     |
| 大规模   | 1000家  | < 30秒     |
| 超大规模 | 5000家  | < 120秒    |

**测试步骤**：

1. 准备不同规模的测试数据
2. 分别执行算子计算
3. 记录执行时间
4. 分析性能瓶颈

**性能监控指标**：
- SQL执行时间
- 数据库连接时间
- 内存使用情况
- CPU使用率

**预期结果**：
- ✅ 1000家公司数据执行时间 < 30秒
- ✅ 内存使用 < 2GB
- ✅ CPU使用率 < 80%

---

### 用例3：并发测试

**测试目标**：验证多个指标同时计算时的稳定性

**测试场景**：
- 并发数：5个指标同时计算
- 每个指标：1000家公司数据
- 测试时长：10分钟

**测试步骤**：

1. 准备5个不同指标的请求
```bash
# 指标1：ROE
# 指标2：ROA
# 指标3：营业收入增长率
# 指标4：净利润增长率
# 指标5：资产负债率
```

2. 使用JMeter或类似工具模拟并发请求
3. 监控系统资源使用情况
4. 检查是否有错误或超时

**预期结果**：
- ✅ 所有请求成功完成
- ✅ 无数据库连接池耗尽
- ✅ 无内存溢出
- ✅ 响应时间稳定

---

### 用例4：结果准确性验证

**测试目标**：验证计算结果的准确性

**验证方法**：

1. 选择10家样本公司
2. 手工计算行业偏离度
3. 对比算子计算结果

**手工计算步骤**：

```python
# 示例：手工计算公司A的行业偏离度

# 1. 确定行业级别
industry_companies = get_companies_in_industry('A0101')
if len(industry_companies) >= 5:
    industry_level = 3
    industry_code = 'A0101'

# 2. 计算行业中位数
values = [100, 105, 108, 110, 115, 120]
median = calculate_median(values)  # 109

# 3. 计算中位差
median_diffs = [abs(v - median) for v in values]  # [9, 4, 1, 1, 6, 11]

# 4. 计算全局中位差中位数 m1
m1 = calculate_median(all_median_diffs)  # 假设 = 5

# 5. 计算有效值范围
valid_range = [median - 3*m1, median + 3*m1]  # [94, 124]

# 6. 剔除异常值，计算行业均值
valid_values = [v for v in values if valid_range[0] <= v <= valid_range[1]]
industry_avg = sum(valid_values) / len(valid_values)  # 109.67

# 7. 计算偏离度
company_value = 120
deviation = (company_value - industry_avg) / abs(industry_avg)  # 0.0942
```

**对比验证**：
```sql
SELECT 
    company_code,
    origin_value,
    industry_avg,
    industry_deviation,
    -- 手工计算值
    0.0942 as manual_deviation,
    -- 误差
    ABS(industry_deviation - 0.0942) as error
FROM result
WHERE company_code = 'A';
```

**预期结果**：
- ✅ 误差 < 0.0001（0.01%）
- ✅ 所有样本公司验证通过

---

### 用例5：日志完整性测试

**测试目标**：验证日志输出是否完整清晰

**验证内容**：

1. 日志级别正确
```
INFO - 【行业算子】开始计算指标 ROE 的行业偏离度
DEBUG - 【行业算子】度量字段 = roe_value
DEBUG - 【行业算子】公司维度字段 = company_code
INFO - 【行业算子】计算完成，返回 1000 条记录
```

2. 异常日志完整
```
ERROR - 【行业算子】计算失败：度量字段不能为空
```

3. 性能日志
```
DEBUG - 【行业算子】SQL 执行时间 = 25.3秒
```

**预期结果**：
- ✅ 日志格式统一
- ✅ 日志信息完整
- ✅ 便于问题排查

---

## 测试执行计划

### 第1天：环境准备
- 部署算子到测试环境
- 准备测试数据
- 配置监控工具

### 第2天：功能测试
- 执行用例1：完整流程测试
- 执行用例4：结果准确性验证
- 执行用例5：日志完整性测试

### 第3天：性能测试
- 执行用例2：性能测试
- 执行用例3：并发测试
- 性能调优（如需要）

### 第4天：回归测试
- 重新执行所有测试用例
- 编写测试报告

---

## 测试通过标准

- ✅ 完整流程测试通过
- ✅ 性能测试达标（1000家公司 < 30秒）
- ✅ 并发测试无错误
- ✅ 结果准确性验证通过（误差 < 0.01%）
- ✅ 日志输出完整清晰

---

## 问题记录模板

| 问题ID | 问题描述 | 严重程度 | 复现步骤 | 解决方案 | 状态 |
|-------|---------|---------|---------|---------|------|
| IT-001 | 性能测试超时 | 高 | 1000家公司数据执行超过30秒 | 优化SQL索引 | 已解决 |

---

## 相关文档

- 单元测试指南：`unit-test-guide.md`
- 需求文档：`requirements.md`
- 设计文档：`design.md`

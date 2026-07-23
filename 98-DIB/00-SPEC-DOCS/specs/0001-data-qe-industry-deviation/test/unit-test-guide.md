# 行业偏离度算子 - 单元测试指南

## 测试目标

验证 `Alg_Industry_Deviation.groovy` 脚本的核心算法逻辑正确性，包括：
- 中位数计算
- 行业级别动态调整
- 异常值剔除
- 偏离度计算

## 测试数据准备

### 测试表结构

```sql
CREATE TABLE test_industry_data (
    report_date DATE,
    dim_company_code VARCHAR(20),
    dim_industry_l1 VARCHAR(10),
    dim_industry_l2 VARCHAR(10),
    dim_industry_l3 VARCHAR(10),
    measure_value DECIMAL(18, 4)
);
```

### 测试数据集

```sql
-- 场景1：三级行业公司数>=5（正常情况）
INSERT INTO test_industry_data VALUES
('2024-12-31', 'C001', 'A', 'A01', 'A0101', 100.0),
('2024-12-31', 'C002', 'A', 'A01', 'A0101', 110.0),
('2024-12-31', 'C003', 'A', 'A01', 'A0101', 105.0),
('2024-12-31', 'C004', 'A', 'A01', 'A0101', 115.0),
('2024-12-31', 'C005', 'A', 'A01', 'A0101', 120.0),
('2024-12-31', 'C006', 'A', 'A01', 'A0101', 95.0),
('2024-12-31', 'C007', 'A', 'A01', 'A0101', 108.0);

-- 场景2：三级行业公司数<5，二级行业>=5（上升到二级）
INSERT INTO test_industry_data VALUES
('2024-12-31', 'C011', 'B', 'B01', 'B0101', 200.0),
('2024-12-31', 'C012', 'B', 'B01', 'B0101', 210.0),
('2024-12-31', 'C013', 'B', 'B01', 'B0102', 220.0),
('2024-12-31', 'C014', 'B', 'B01', 'B0102', 230.0),
('2024-12-31', 'C015', 'B', 'B01', 'B0103', 240.0),
('2024-12-31', 'C016', 'B', 'B01', 'B0103', 250.0);

-- 场景3：二级行业公司数<5，一级行业>=5（上升到一级）
INSERT INTO test_industry_data VALUES
('2024-12-31', 'C021', 'C', 'C01', 'C0101', 300.0),
('2024-12-31', 'C022', 'C', 'C01', 'C0101', 310.0),
('2024-12-31', 'C023', 'C', 'C02', 'C0201', 320.0),
('2024-12-31', 'C024', 'C', 'C02', 'C0201', 330.0),
('2024-12-31', 'C025', 'C', 'C03', 'C0301', 340.0),
('2024-12-31', 'C026', 'C', 'C03', 'C0301', 350.0);

-- 场景4：包含异常值（用于测试异常值剔除）
INSERT INTO test_industry_data VALUES
('2024-12-31', 'C031', 'D', 'D01', 'D0101', 400.0),
('2024-12-31', 'C032', 'D', 'D01', 'D0101', 410.0),
('2024-12-31', 'C033', 'D', 'D01', 'D0101', 405.0),
('2024-12-31', 'C034', 'D', 'D01', 'D0101', 415.0),
('2024-12-31', 'C035', 'D', 'D01', 'D0101', 408.0),
('2024-12-31', 'C036', 'D', 'D01', 'D0101', 9999.0);  -- 异常值

-- 场景5：均值为0的情况
INSERT INTO test_industry_data VALUES
('2024-12-31', 'C041', 'E', 'E01', 'E0101', -10.0),
('2024-12-31', 'C042', 'E', 'E01', 'E0101', -5.0),
('2024-12-31', 'C043', 'E', 'E01', 'E0101', 0.0),
('2024-12-31', 'C044', 'E', 'E01', 'E0101', 5.0),
('2024-12-31', 'C045', 'E', 'E01', 'E0101', 10.0);
```

## 测试用例

### 用例1：中位数计算测试

**测试目标**：验证中位数计算的准确性

**测试数据**：
- 奇数个数据：[100, 105, 110, 115, 120] → 中位数 = 110
- 偶数个数据：[100, 105, 110, 115] → 中位数 = (105 + 110) / 2 = 107.5
- 单个数据：[100] → 中位数 = 100

**验证方法**：
```sql
-- 查询场景1的中位数
SELECT 
    industry_code,
    median_value
FROM (
    -- 执行算子脚本
) result
WHERE industry_code = 'A0101';
```

**预期结果**：
- 场景1（7个数据）：中位数 = 108.0

---

### 用例2：行业级别调整测试

**测试目标**：验证行业级别动态调整逻辑

**测试场景**：
1. 三级行业公司数>=5 → 使用三级行业分组
2. 三级行业公司数<5，二级>=5 → 使用二级行业分组
3. 二级行业公司数<5，一级>=5 → 使用一级行业分组

**验证方法**：
```sql
SELECT 
    company_code,
    industry_level,
    industry_code
FROM (
    -- 执行算子脚本
) result
WHERE company_code IN ('C001', 'C011', 'C021');
```

**预期结果**：
- C001: industry_level = 3, industry_code = 'A0101'
- C011: industry_level = 2, industry_code = 'B01'
- C021: industry_level = 1, industry_code = 'C'

---

### 用例3：异常值剔除测试

**测试目标**：验证 3*m1 阈值异常值剔除逻辑

**测试数据**：场景4（包含异常值 9999.0）

**验证方法**：
```sql
SELECT 
    industry_code,
    industry_avg,
    COUNT(*) as valid_count
FROM (
    -- 执行算子脚本
) result
WHERE industry_code = 'D0101'
GROUP BY industry_code, industry_avg;
```

**预期结果**：
- 异常值 9999.0 应被剔除
- 行业均值应基于正常值计算：(400 + 410 + 405 + 415 + 408) / 5 = 407.6
- valid_count = 5（不包含异常值）

---

### 用例4：偏离度计算测试（均值!=0）

**测试目标**：验证偏离度计算公式

**测试数据**：场景1

**验证方法**：
```sql
SELECT 
    company_code,
    origin_value,
    industry_avg,
    industry_deviation,
    ROUND((origin_value - industry_avg) / ABS(industry_avg), 4) as expected_deviation
FROM (
    -- 执行算子脚本
) result
WHERE industry_code = 'A0101';
```

**预期结果**：
- 偏离度 = (指标值 - 行业均值) / |行业均值|
- 正偏离：指标值 > 行业均值 → 偏离度 > 0
- 负偏离：指标值 < 行业均值 → 偏离度 < 0

---

### 用例5：偏离度计算测试（均值=0）

**测试目标**：验证均值为0时的特殊处理

**测试数据**：场景5

**验证方法**：
```sql
SELECT 
    company_code,
    origin_value,
    industry_avg,
    industry_deviation
FROM (
    -- 执行算子脚本
) result
WHERE industry_code = 'E0101';
```

**预期结果**：
- 当 industry_avg = 0 时
- 偏离度 = 指标值 - 行业均值 = 指标值

---

### 用例6：边界条件测试

**测试目标**：验证边界条件处理

**测试场景**：
1. 指标值为 NULL → 不参与计算
2. 行业分类缺失 → 不参与计算
3. 一级行业公司数<5 → 单独分组

**测试数据**：
```sql
-- 指标值为 NULL
INSERT INTO test_industry_data VALUES
('2024-12-31', 'C051', 'F', 'F01', 'F0101', NULL);

-- 行业分类缺失
INSERT INTO test_industry_data VALUES
('2024-12-31', 'C052', NULL, NULL, NULL, 500.0);
```

**验证方法**：
```sql
SELECT COUNT(*) as total_count
FROM (
    -- 执行算子脚本
) result
WHERE company_code IN ('C051', 'C052');
```

**预期结果**：
- total_count = 0（这些记录不应出现在结果中）

---

### 用例7：输出字段完整性测试

**测试目标**：验证输出字段是否完整

**验证方法**：
```sql
SELECT 
    CASE WHEN dim_report_date IS NOT NULL THEN 1 ELSE 0 END as has_dim_report_date,
    CASE WHEN dim_company_code IS NOT NULL THEN 1 ELSE 0 END as has_dim_company_code,
    CASE WHEN industry_level IS NOT NULL THEN 1 ELSE 0 END as has_industry_level,
    CASE WHEN industry_code IS NOT NULL THEN 1 ELSE 0 END as has_industry_code,
    CASE WHEN origin_value IS NOT NULL THEN 1 ELSE 0 END as has_origin_value,
    CASE WHEN median_value IS NOT NULL THEN 1 ELSE 0 END as has_median_value,
    CASE WHEN industry_avg IS NOT NULL THEN 1 ELSE 0 END as has_industry_avg,
    CASE WHEN industry_deviation IS NOT NULL THEN 1 ELSE 0 END as has_industry_deviation,
    CASE WHEN index_value IS NOT NULL THEN 1 ELSE 0 END as has_index_value
FROM (
    -- 执行算子脚本
) result
LIMIT 1;
```

**预期结果**：
- 所有字段值均为 1（所有必需字段都存在）

---

## 测试执行步骤

1. **准备测试环境**
   ```bash
   # 连接到测试数据库
   mysql -h test-db-host -u username -p
   ```

2. **创建测试表并插入数据**
   ```sql
   -- 执行上述测试表结构和测试数据SQL
   ```

3. **执行算子脚本**
   - 通过 dib-agent-service-data 的接口调用算子
   - 传入参数：
     - measureField: 'measure_value'
     - companyDimField: 'dim_company_code'
     - industryL1Field: 'dim_industry_l1'
     - industryL2Field: 'dim_industry_l2'
     - industryL3Field: 'dim_industry_l3'

4. **验证测试结果**
   - 执行各测试用例的验证SQL
   - 对比实际结果与预期结果

5. **清理测试数据**
   ```sql
   DROP TABLE test_industry_data;
   ```

---

## 测试通过标准

- ✅ 所有7个测试用例全部通过
- ✅ 中位数计算准确（误差 < 0.01）
- ✅ 行业级别调整符合规则
- ✅ 异常值正确剔除
- ✅ 偏离度计算准确（误差 < 0.0001）
- ✅ 边界条件处理正确
- ✅ 输出字段完整

---

## 注意事项

1. **数据库兼容性**：测试SQL需根据实际数据库（MySQL/PostgreSQL/Oracle）调整语法
2. **精度问题**：浮点数比较时使用 ROUND() 函数避免精度误差
3. **日志检查**：测试过程中检查日志输出是否完整清晰
4. **性能监控**：记录每个测试用例的执行时间

---

## 相关文档

- 需求文档：`requirements.md`
- 设计文档：`design.md`
- 脚本文件：`Alg_Industry_Deviation.groovy`

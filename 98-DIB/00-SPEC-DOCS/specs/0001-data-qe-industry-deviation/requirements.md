# 001 行业算子开发 需求文档

## 背景

为了支持 BI 展示和客户数据包需求，需要开发一个行业算子，用于根据业务表计算特定指标的行业偏离度。该算子基于申万行业分类标准，通过统计分析方法剔除异常值，计算行业均值和偏离度，为数据分析提供标准化的行业对比指标。

## 目标用户

- BI 数据分析人员
- 数据产品团队
- 客户（通过数据包获取计算结果）

## 功能描述

开发一个 Groovy 脚本算子，实现基于申万行业分类的指标行业偏离度计算。算子通过定时任务接口调用触发，对输入的指标数据进行行业分组、异常值剔除、均值计算和偏离度计算，输出标准化的行业对比结果。

## 所属模块

- 项目：dib-agent-service-data（独立项目，非 ARS 项目）
- 模块：dib-agent-service-data-web
- 目录：`src/main/resources/indexFunc/`
- 脚本文件：`Alg_Industry_Deviation.groovy`

## 核心算法规则

### 步骤 1：行业处理（动态行业级别调整）

按申万行业三级分类标准统计各行业公司数量，根据公司数量动态调整行业级别：

1. 优先使用三级行业分类
2. 如果三级行业公司数量 < 5 家，上升到二级行业
3. 如果二级行业公司数量 < 5 家，上升到一级行业
4. 如果一级行业公司数量 < 5 家，单独分组（不剔除）

**规则说明**：
- 每个公司最终归属到一个行业分组
- 行业级别可能不一致（部分公司在三级，部分在二级或一级）
- 目的是确保每个行业分组有足够的样本量进行统计分析

### 步骤 2：计算行业中位差

对每个行业分组：

1. 将该行业内所有公司的指标值 x0 从小到大排序
2. 计算该行业的指标值中位数 m
3. 计算每个公司的中位差：x1 = |x0 - m|

**公式**：
```
m = median(x0_1, x0_2, ..., x0_n)
x1_i = |x0_i - m|
```

### 步骤 3：计算指标有效值范围

1. 收集所有行业的中位差 x1
2. 计算所有中位差的中位数 m1：`m1 = median(x1_1, x1_2, ..., x1_k)`
3. 对每个行业，计算有效值范围：`[m - 3*m1, m + 3*m1]`

**说明**：
- m 是该行业的指标值中位数
- m1 是全局中位差的中位数
- 3 倍 m1 作为异常值判断的阈值

### 步骤 4：剔除异常值，计算行业均值

对每个行业：

1. 遍历该行业内所有公司的指标值 x0
2. 筛选出在有效值范围内的指标值
3. 计算行业均值（算术平均）：

```
行业均值 = sum(有效值范围内的 x0) / 有效值范围内的 x0 个数
```

### 步骤 5：计算行业偏离度

对每个公司，根据其指标值和所属行业的均值计算偏离度：

**公式**：
```
if 行业均值 != 0:
    行业偏离度 = (指标值 - 行业均值) / abs(行业均值)
else:
    行业偏离度 = (指标值 - 行业均值)
```

**说明**：
- 偏离度为正：指标值高于行业均值
- 偏离度为负：指标值低于行业均值
- 偏离度的绝对值越大，偏离程度越高

## 输入参数

算子接收 `DataIndexCalcReq` 对象作为输入参数，包含以下字段：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| indexCode | String | 是 | 指标代码，用于标识计算的指标 |
| measureField | String | 是 | 度量字段名，指标值所在的字段名 |
| reportDate | String | 是 | 报告期，格式如 "2024-12-31"（单个日期） |
| companyTableName | String | 是 | 公司数据表名（动态传入） |
| industryTableName | String | 是 | 行业分类表名（动态传入） |
| companyIndustryMapTable | String | 是 | 公司行业映射表名（动态传入） |
| dataSourceCode | String | 是 | 数据源编码 |

**说明**：
- 表名通过参数动态传入，不在脚本中硬编码
- 具体的表结构和字段由调用方保证
- 脚本只负责算法逻辑实现

## 输出结果

算子返回 `List<Map<String, Object>>`，每条记录包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| company_code | String | 公司代码 |
| company_name | String | 公司名称 |
| report_date | String | 报告期 |
| industry_level | Integer | 最终确定的行业级别（1/2/3） |
| industry_code | String | 行业代码 |
| industry_name | String | 行业名称 |
| origin_value | Double | 原始指标值 |
| median_value | Double | 行业中位数 |
| median_diff | Double | 中位差 x1 |
| valid_range_min | Double | 有效值范围下限 |
| valid_range_max | Double | 有效值范围上限 |
| industry_avg | Double | 行业均值（剔除异常值后） |
| industry_deviation | Double | 行业偏离度 |
| index_value | Double | 最终计算值（行业偏离度） |

**说明**：
- `index_value` 字段为最终输出值，与 `industry_deviation` 相同
- 保留中间计算结果字段，便于调试和验证

## 用户故事

- 作为 BI 数据分析人员，我希望能够计算公司指标的行业偏离度，以便在数据可视化中展示公司在行业中的相对位置
- 作为数据产品团队，我希望算子能够自动剔除异常值，以便提供更准确的行业对比数据
- 作为客户，我希望获得标准化的行业对比指标，以便评估公司在行业中的表现

## 验收标准

- [ ] 标准1：算子能够正确实现行业动态级别调整（三级→二级→一级）
- [ ] 标准2：算子能够正确计算行业中位数和中位差
- [ ] 标准3：算子能够正确计算有效值范围并剔除异常值
- [ ] 标准4：算子能够正确计算行业均值（仅使用有效值）
- [ ] 标准5：算子能够正确计算行业偏离度（处理均值为0的情况）
- [ ] 标准6：算子能够通过定时任务接口调用触发执行
- [ ] 标准7：算子执行性能满足要求（处理千级公司数据在合理时间内完成）
- [ ] 标准8：算子能够正确处理边界情况（指标值为空、行业分类缺失等）

## 边界条件

- 当指标值为空（null）时，该公司不参与计算，不影响行业统计
- 当公司没有行业分类信息时，该公司被排除，不参与计算
- 当三级行业公司数量 < 5 家时，自动上升到二级行业
- 当二级行业公司数量 < 5 家时，自动上升到一级行业
- 当一级行业公司数量 < 5 家时，单独分组（不剔除）
- 当行业均值 = 0 时，偏离度计算公式为：`偏离度 = 指标值 - 行业均值`
- 当行业均值 ≠ 0 时，偏离度计算公式为：`偏离度 = (指标值 - 行业均值) / abs(行业均值)`

## 非功能需求

### 性能
- 处理 1000 家公司数据，执行时间 < 30 秒
- 支持并发执行多个指标计算任务

### 可维护性
- 代码结构清晰，遵循现有 Groovy 脚本规范
- 关键步骤添加日志输出，便于调试
- 算法参数（如异常值阈值 3 倍 m1）可配置化

### 可扩展性
- 支持未来扩展其他行业分类标准（如中证行业分类）
- 支持未来扩展其他异常值剔除算法

### 兼容性
- 与现有 indexFunc 目录下的脚本保持一致的代码风格
- 使用相同的工具类和基础设施（DataQueryInfrastructure、IndexSqlUtil 等）

## 参考资料

### 参考脚本（按场景分类）

**基础查询和工具类**：
- `indexFunc/common/Query.groovy` - 数据查询基础函数
- `indexFunc/common/Rank_Fraction.groovy` - 排名分数计算
- `indexFunc/common/Rank_Percent.groovy` - 排名百分比计算

**统计算法参考**：
- `indexFunc/toubao/Alg6_TB_Median_Dimless.groovy` - 中位数计算（使用 CTE 和窗口函数）
- `indexFunc/toubao/Alg7_TB_Average_Dimless.groovy` - 均值计算（分组统计）
- `indexFunc/toubao/Alg1_TB_Regular_Dimless.groovy` - 常规无量纲化（异常值处理）

**分组和排序参考**：
- `indexFunc/toubao/Alg3_TB_Partition_Rank_Dimless.groovy` - 分档排名（复杂 CTE 链式查询）
- `indexFunc/toubao/Alg8_TB_Rank_Dimless.groovy` - 排名无量纲化

**其他算法**：
- `indexFunc/toubao/Alg2_TB_Regular_Dimless_Piecewise.groovy` - 分段无量纲化
- `indexFunc/toubao/Alg4_TB_Quest_Count_Dimless.groovy` - 问卷计数
- `indexFunc/toubao/Alg9_TB_Partition_Measure_Dimless.groovy` - 分档度量

### 技术要点参考

1. **CTE（公用表表达式）使用**：参考 Alg6、Alg3，使用 WITH 子句构建多步骤查询
2. **窗口函数**：参考 Alg6 的 ROW_NUMBER()、COUNT() OVER()
3. **中位数计算**：参考 Alg6 的中位数算法实现
4. **分组统计**：参考 Alg7 的 GROUP BY 和 AVG() 使用
5. **异常值处理**：参考 Alg1 的 errNums 排除逻辑
6. **动态 SQL 构建**：参考所有脚本使用 DibSqlBuilder 和 IndexSqlUtil
7. **日志输出**：参考所有脚本的 Logger 使用模式
8. **脚本缓存优化**：参考 Alg1 的 formulaScriptClassCache

### 行业分类标准

- 申万行业分类标准：三级分类体系（一级→二级→三级）

## 待确认问题

- [x] 表名通过参数传入，不硬编码 - 已确认
- [x] 指标值为空时不参与计算 - 已确认
- [x] 行业分类缺失时排除该公司 - 已确认
- [x] 一级行业不足5家时单独分组 - 已确认
- [x] 功能命名：999-industry-operator - 已确认
- [x] 脚本文件名：Alg_Industry_Deviation.groovy - 已确认

# 002 内控评级-规模调整系数算子 任务清单

## 任务列表

- [ ] 1. 创建算子脚本文件
  - [ ] 1.1 在 `dib-agent-service-data-web/src/main/resources/indexFunc/internalControl/` 目录下创建 `Alg_IC_Adjust_Factor.groovy`
  - [ ] 1.2 添加 package 声明和 import 语句（参考 `Alg_Industry_Deviation.groovy`）
  - [ ] 1.3 编写类头注释（算法步骤、动态参数说明、固定字段说明）

- [ ] 2. 实现 `calc(String measureField)` 主函数
  - [ ] 2.1 从 binding 获取 `DataIndexCalcReq`，提取 `reportDate`
  - [ ] 2.2 通过 `IndexSqlUtil.getDataSourceCode(calcReq)` 获取数据源编码
  - [ ] 2.3 通过 `IndexSqlUtil.generateSqlBuilder(calcReq).getTableName()` 获取动态表名
  - [ ] 2.4 添加参数校验（measureField 非空）
  - [ ] 2.5 调用 `buildSizeAdjSql` 构建 SQL，调用 `DataQueryInfrastructure.queryRows` 执行查询
  - [ ] 2.6 添加日志（INFO 级别记录开始/完成，DEBUG 级别记录表名/SQL，WARN 级别记录空结果）

- [ ] 3. 实现 `buildSizeAdjSql(String tableName, String measureField, String reportDate)` 方法
  - [ ] 3.1 实现 Step 1（sample_data CTE）：从动态表名查询，过滤 reportDate 和 null 值，ROW_NUMBER 排序
  - [ ] 3.2 实现 Step 2（percentile_value CTE）：子查询取 P1/P99 分位值
  - [ ] 3.3 实现 Step 3（g0 CTE）：双截尾逻辑，CASE WHEN 替换极端值
  - [ ] 3.4 实现 Step 4（industry_rank + industry_median CTE）：按 dim_industry_code_sw 分组计算中位数
  - [ ] 3.5 实现 Step 5（g2 CTE）：G2 = G0 - G1
  - [ ] 3.6 实现 Step 6（global_stats + g3 CTE）：Z-Score 标准化，含 stddev_g = 0 的除零保护
  - [ ] 3.7 实现 Step 7（g4 CTE）：按行业取 G3 最小值
  - [ ] 3.8 实现 Step 8（size_adj CTE）：sizeAdj = G3 - G4
  - [ ] 3.9 编写最终 SELECT，输出 sec_code、report_date、dim_report_date、dim_industry_code_sw、index_value

- [ ] 4. 验证与测试
  - [ ] 4.1 使用参考 SQL（需求文档中的 SQL）在数据库中手动验证计算结果
  - [ ] 4.2 验证边界条件：行业只有一家公司时 G2 = 0
  - [ ] 4.3 验证边界条件：stddev_g = 0 时 G3 = 0（不报错）
  - [ ] 4.4 验证输出字段完整性（5 个字段均存在）
  - [ ] 4.5 验证每个行业内 sizeAdj 最小值为 0

## 验收标准对照

| 验收标准 | 对应任务 |
|----------|----------|
| 正确执行双截尾（上下 1% 分位数替换） | 3.2, 3.3 |
| 正确计算行业中位数 G1 | 3.4 |
| 正确计算 G2 = G0 - G1 | 3.5 |
| 正确进行 Z-Score 标准化得到 G3 | 3.6 |
| 正确计算行业 G3 最小值 G4 | 3.7 |
| 正确计算 sizeAdj = G3 - G4，行业最小值为 0 | 3.8, 4.5 |
| 输出字段包含 5 个指定字段 | 3.9, 4.4 |
| 正确处理边界情况 | 4.2, 4.3 |

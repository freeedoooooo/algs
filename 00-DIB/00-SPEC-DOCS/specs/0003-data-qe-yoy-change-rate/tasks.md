# 003 同比变动率算子 任务清单

## 任务列表

- [ ] 1. 创建算子脚本文件
  - [ ] 1.1 在 `indexFunc/qualityEvaluation/` 下创建 `Alg6_QE_YoY_Change_Rate.groovy`
  - [ ] 1.2 添加 package 声明和 import 语句（参考 `Alg1_QE_Industry_Deviation_Rate.groovy`）

- [ ] 2. 实现 `calc(String formula, String companyDimField)` 主函数
  - [ ] 2.1 从 binding 获取 `DataIndexCalcReq`，提取 `reportDate`（使用 `getDimReportDate()`）
  - [ ] 2.2 推算上期日期：`priorReportDate = (year - 1) + month-day`
  - [ ] 2.3 通过 `IndexSqlUtil` 获取 `dataSourceCode` 和 `tableName`
  - [ ] 2.4 添加参数校验（formula、companyDimField 非空）
  - [ ] 2.5 执行前置检查 SQL，若上期数据不存在则打印 WARN 并返回空集
  - [ ] 2.6 构建并执行主 CTE SQL，返回结果

- [ ] 3. 实现 `buildCheckSql` 方法
  - [ ] 3.1 生成检查上期数据是否存在的 COUNT SQL

- [ ] 4. 实现 `buildYoYSql` 方法
  - [ ] 4.1 实现 current_data CTE：按 formula 计算本期值
  - [ ] 4.2 实现 prior_data CTE：按相同 formula 计算上期值
  - [ ] 4.3 实现 yoy_result CTE：JOIN 本期与上期，CASE WHEN 处理防0/null逻辑
  - [ ] 4.4 编写最终 SELECT，输出 report_date、dim_report_date、companyDimField、index_value

- [ ] 5. 验证
  - [ ] 5.1 验证上期不存在时返回空集并有 WARN 日志
  - [ ] 5.2 验证上期为 0、本期 > 0 时结果为 1
  - [ ] 5.3 验证上期为 0、本期 < 0 时结果为 -1
  - [ ] 5.4 验证本期为 null 时 IFNULL 正确处理

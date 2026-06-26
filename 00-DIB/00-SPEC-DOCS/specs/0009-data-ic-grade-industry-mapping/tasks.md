# 任务清单：0009 - 内控评级算子补充申万行业归并逻辑

## 任务列表

- [x] 1. 修改 Alg1_IC_Adjust_Factor.groovy
  - [x] 1.1 `cteSampleData` 新增二级行业过滤条件 `RIGHT(..., 2) = '00'`
  - [x] 1.2 新增 `cteIndustryCount()` 方法
  - [x] 1.3 新增 `cteIndustryMapped()` 方法
  - [x] 1.4 修改 `cteG0()`：数据来源改为 `industry_mapped`，行业字段改为 `mapped_industry_code`，透传 `original_industry_code`
  - [x] 1.5 修改 `cteIndustryRank()`：`PARTITION BY` 改为 `mapped_industry_code`
  - [x] 1.6 修改 `cteIndustryMedian()`：`GROUP BY` 改为 `mapped_industry_code`
  - [x] 1.7 修改 `cteG2()`：JOIN 条件改为 `mapped_industry_code`，透传 `original_industry_code`
  - [x] 1.8 修改 `cteG3()`、`cteG4()`、`cteSizeAdj()`：行业字段改为 `mapped_industry_code`，透传 `original_industry_code`
  - [x] 1.9 修改 `buildSizeAdjSql()`：串联顺序加入 `cteIndustryCount` 和 `cteIndustryMapped`
  - [x] 1.10 修改 `selectFinal()`：新增输出 `original_industry_code`、`mapped_industry_code`

- [x] 2. 修改 Alg2_IC_Final_Score.groovy
  - [x] 2.1 `cteSampleData` 新增二级行业过滤条件 `RIGHT(..., 2) = '00'`
  - [x] 2.2 新增 `cteIndustryCount()` 方法
  - [x] 2.3 新增 `cteIndustryMapped()` 方法
  - [x] 2.4 修改 `cteG0()`：数据来源改为 `industry_mapped`，行业字段改为 `mapped_industry_code`，透传 `original_industry_code`
  - [x] 2.5 修改 `cteIndustryRank()`：`PARTITION BY` 改为 `mapped_industry_code`
  - [x] 2.6 修改 `cteIndustryMedian()`：`GROUP BY` 改为 `mapped_industry_code`
  - [x] 2.7 修改 `cteG2()`：JOIN 条件改为 `mapped_industry_code`，透传 `original_industry_code`
  - [x] 2.8 修改 `cteG3()`、`cteG4()`、`cteG5()`：行业字段改为 `mapped_industry_code`，透传 `original_industry_code`
  - [x] 2.9 修改 `buildGradeSql()`：串联顺序加入 `cteIndustryCount` 和 `cteIndustryMapped`
  - [x] 2.10 修改 `selectFinal()`：新增输出 `original_industry_code`、`mapped_industry_code`

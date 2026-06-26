# 004 内控评级-评级分数算子 任务清单

> 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-03-17
> 关联文档：`requirements.md` | `design.md`

---

## 任务列表

- [x] 1. 编写算子脚本 `Alg_IC_Grade.groovy`
  - [x] 1.1 创建脚本文件，声明包名和导入语句
  - [x] 1.2 实现 `calc(String measureField, String adjustFactorIndexCode)` 主函数框架（参数校验、获取运行时参数、日志）
  - [x] 1.3 实现 `buildGradeSql(...)` 私有方法，编写完整 CTE SQL
    - [x] 1.3.1 Step 1~5：sample_data / percentile_value / g0 / industry_rank / industry_median / g2（复用 AdjustFactor 逻辑）
    - [x] 1.3.2 Step 6：sale_adj CTE（从 com_data_index_value 关联 saleAdj）
    - [x] 1.3.3 Step 7：g3 CTE（G3 = G2 × saleAdj，INNER JOIN）
    - [x] 1.3.4 Step 8：g4 CTE（STDDEV_SAMP 窗口函数，COALESCE 处理 NULL）
    - [x] 1.3.5 Step 9：g5 CTE（G5 = G4 × 500 + 500）
    - [x] 1.3.6 最终 SELECT（CASE WHEN 截断到 [0, 1000]，输出标准字段）

- [x] 2. 验证
  - [x] 2.1 对照 requirements.md 验收标准逐项检查
  - [x] 2.2 边界条件验证（无 saleAdj 公司排除、单公司行业 G4=0、G5 截断）
  - [x] 2.3 宪法自检（脚本模式、包名、日志规范、SQL 规范）

---

## 任务状态说明

| 标记 | 含义 |
|------|------|
| `- [ ]` | 未开始 |
| `- [-]` | 进行中 |
| `- [x]` | 已完成 |

---

## 验收标准对照

| 验收标准 | 对应任务 |
|---------|---------|
| 标准1：双截尾正确 | 1.3.1 |
| 标准2：行业中位数 G1 正确 | 1.3.1 |
| 标准3：G2 = G0 - G1 正确 | 1.3.1 |
| 标准4：G3 = G2 × saleAdj 正确 | 1.3.2 / 1.3.3 |
| 标准5：G4 行业标准差正确 | 1.3.4 |
| 标准6：G5 = G4 × 500 + 500 正确 | 1.3.5 |
| 标准7：最终值截断正确 | 1.3.6 |
| 标准8：输出字段完整 | 1.3.6 |
| 标准9：无 saleAdj 公司排除 | 1.3.3 |
| 标准10：单公司行业 G4 = 0 | 1.3.4 |

---

## 进度记录

| 时间 | 完成任务 | 备注 |
|------|---------|------|
| | | |

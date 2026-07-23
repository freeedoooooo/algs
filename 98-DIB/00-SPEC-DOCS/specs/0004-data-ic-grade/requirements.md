# 004 内控评级-评级分数算子 需求文档

## 背景

内控评级体系中，在完成规模调整系数（`sizeAdj`）计算后，需要进一步结合销售调整系数（`saleAdj`）对原始指标值进行加权处理，并通过标准化和线性变换，将结果映射到 0~1000 的评分区间，最终输出每家公司的内控评级分数。

本算子（`Alg_IC_Grade`）的前半段逻辑（双截尾、行业中位数、去行业影响）与 `Alg_IC_Adjust_Factor` 完全相同，后半段引入外部调整系数 `saleAdj` 进行加权，再经行业分组标准化和线性变换得到最终评级分数。

## 目标用户

- 内控评级数据分析人员
- 数据产品团队
- 内控评级模型开发人员

## 功能描述

开发一个 Groovy 脚本算子 `Alg_IC_Grade`，实现以下计算流程：

1. **G → G0（双截尾）**：对原始指标值进行上下 1% 分位数截尾，消除极端值影响（与 AdjustFactor 相同）
2. **G0 → G1（行业中位数）**：按行业分组计算 G0 的中位数（与 AdjustFactor 相同）
3. **G0 → G2（去除行业影响）**：`G2 = G0 - G1`（与 AdjustFactor 相同）
4. **G2 → G3（加权）**：`G3 = G2 × saleAdj`，其中 `saleAdj` 来自指标结果表，按公司+报告期关联
5. **G3 → G4（行业标准差）**：按行业分组计算 G3 的样本标准差，`G4 = STDDEV_SAMP(G3) per industry`
6. **G4 → G5（线性变换）**：`G5 = G4 × 500 + 500`
7. **G5 → 最终值（截断）**：`index_value = CASE WHEN G5 > 1000 THEN 1000 WHEN G5 < 0 THEN 0 ELSE G5 END`

## 所属模块

- 项目：dib-agent-service-data（独立项目）
- 模块：dib-agent-service-data-web
- 目录：`src/main/resources/indexFunc/internalControl/`
- 脚本文件：`Alg_IC_Grade.groovy`

## 核心算法规则

### 步骤 1~3：与 AdjustFactor 相同

参见 `0002-ic-adjust-factor/requirements.md`，步骤 1~3（G → G0 → G1 → G2）逻辑完全复用。

关键字段：

```
sec_code              -- 公司代码
report_date           -- 报告期
dim_industry_code_sw  -- 申万行业代码（固定字段名）
${measureField}       -- 原始指标值 G（动态字段名）
```

### 步骤 4：加权（G3 = G2 × saleAdj）

从指标结果表 `com_data_index_value` 中，按 `dim_sec_code + dim_report_date + index_code` 关联，获取每家公司的 `saleAdj` 值：

```sql
-- 关联条件
com_data_index_value.dim_sec_code    = g2.sec_code
com_data_index_value.dim_report_date = g2.report_date
com_data_index_value.index_code      = '${adjustFactorIndexCode}'

-- 计算
G3 = G2 × saleAdj（即 com_data_index_value.index_value）
```

**说明**：若某公司无对应 `saleAdj`，该公司不参与后续计算（使用 INNER JOIN）。

### 步骤 5：行业标准差（G4）

按 `dim_industry_code_sw` 分组，计算 G3 的样本标准差：

```
G4 = STDDEV_SAMP(G3) PARTITION BY dim_industry_code_sw
```

每家公司的 G4 值 = 其所在行业所有公司 G3 的样本标准差（同一行业内所有公司 G4 值相同）。

**边界处理**：当行业内只有一家公司或 `STDDEV_SAMP = 0` 时，G4 = 0。

### 步骤 6：线性变换（G5）

```
G5 = G4 × 500 + 500
```

### 步骤 7：截断（最终值）

```
index_value = CASE
    WHEN G5 > 1000 THEN 1000
    WHEN G5 < 0    THEN 0
    ELSE G5
END
```

## 输入参数

算子接收 `DataIndexCalcReq` 对象，报告期从该对象中获取。

**动态参数（通过函数参数传入）**：

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `measureField` | String | 度量字段名，即原始指标值 G 所在的字段（如 `B1000001BT`） |
| `adjustFactorIndexCode` | String | saleAdj 对应的指标编码，用于从指标结果表关联调整系数 |

**固定字段（不通过参数传入）**：

| 字段名 | 说明 |
|--------|------|
| `sec_code` | 公司代码 |
| `report_date` | 报告期 |
| `dim_industry_code_sw` | 申万行业代码（固定字段名） |

**saleAdj 来源表**：

| 表名 | 字段 | 关联条件 |
|------|------|----------|
| `com_data_index_value` | `index_value`（即 saleAdj） | `dim_sec_code = sec_code AND dim_report_date = report_date AND index_code = adjustFactorIndexCode` |

## 输出结果

算子返回 `List<Map<String, Object>>`，每条记录包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `sec_code` | String | 公司代码 |
| `report_date` | String | 报告期 |
| `dim_report_date` | String | 报告期（维度字段，与 report_date 相同） |
| `dim_industry_code_sw` | String | 申万行业代码 |
| `index_value` | Double | 最终评级分数（0~1000，截断后） |

## 用户故事

- 作为内控评级分析人员，我希望能够计算每家公司的内控评级分数，以便在评级模型中综合反映规模和销售调整因素
- 作为数据产品团队，我希望算子能够自动处理极端值（双截尾）并关联外部调整系数，以便提供更准确的评级分数
- 作为模型开发人员，我希望算子输出的评级分数在 0~1000 区间内，以便直接用于评级展示和比较

## 验收标准

- [ ] 标准1：算子能够正确执行双截尾（上下 1% 分位数替换）
- [ ] 标准2：算子能够正确计算行业中位数 G1
- [ ] 标准3：算子能够正确计算 G2 = G0 - G1
- [ ] 标准4：算子能够正确从指标结果表关联 saleAdj，计算 G3 = G2 × saleAdj
- [ ] 标准5：算子能够正确按行业分组计算 G3 的样本标准差 G4
- [ ] 标准6：算子能够正确计算 G5 = G4 × 500 + 500
- [ ] 标准7：最终值正确截断（>1000 取 1000，<0 取 0）
- [ ] 标准8：输出字段包含 sec_code、report_date、dim_report_date、dim_industry_code_sw、index_value
- [ ] 标准9：无 saleAdj 的公司不参与计算（INNER JOIN）
- [ ] 标准10：行业只有一家公司或标准差为 0 时，G4 = 0，正常输出

## 边界条件

- 当 `measureField` 对应值为 null 时，该公司不参与计算
- 当某公司在指标结果表中无对应 `saleAdj` 时，该公司不参与计算（INNER JOIN）
- 当行业内只有一家公司时，`STDDEV_SAMP = NULL`，G4 = 0
- 当行业内所有公司 G3 相同时，`STDDEV_SAMP = 0`，G4 = 0
- G5 超出 [0, 1000] 范围时，截断到边界值

## 非功能需求

### 性能
- 处理 1000 家公司数据，执行时间 < 30 秒
- 支持并发执行多个指标计算任务

### 可维护性
- 代码结构清晰，遵循现有 Groovy 脚本规范
- 关键步骤添加日志输出，便于调试
- 日志前缀统一使用 `【内控算子】`

### 兼容性
- 与现有 `indexFunc/` 目录下的脚本保持一致的代码风格
- 使用相同的工具类（`DataQueryInfrastructure`、`IndexSqlUtil`、`DibSqlBuilder` 等）
- 输出格式与现有脚本一致（包含 `dim_report_date` 字段）

## 参考资料

- `0002-ic-adjust-factor/requirements.md` - 规模调整系数算子（前半段逻辑复用）
- `indexFunc/internalControl/Alg_IC_Adjust_Factor.groovy` - 参考脚本

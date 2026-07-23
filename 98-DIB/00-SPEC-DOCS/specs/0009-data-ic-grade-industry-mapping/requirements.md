# 需求文档：0009 - 内控评级算子补充申万行业归并逻辑

## 1. 背景

内控评级模块包含两个 Groovy 算子：
- `Alg1_IC_Adjust_Factor.groovy`（规模调整系数）
- `Alg2_IC_Final_Score.groovy`（评级分数）

两个算子在按行业分组计算时，直接使用原始行业编码字段（`industryDimField`）进行分组，**未处理"行业公司数不足"的归并场景**。

当某个申万二级行业下的公司数不足 5 家时，该行业样本量过小，统计结果不可靠，需要将这些公司归并到"综合-综合"行业（编码 `510100`）参与计算。

## 2. 本次范围

- **只处理申万行业编码场景**（6位纯数字编码，如 `410200`）
- 国标行业编码场景（字母开头）另行开发，本次不涉及
- 修改文件：`Alg1_IC_Adjust_Factor.groovy` 和 `Alg2_IC_Final_Score.groovy`

## 3. 申万行业编码规则

- 编码格式：6位纯数字
- 本算子**只使用二级行业编码**（后两位为 `00`，如 `410200`、`510100`）
- 数据源中已过滤为二级行业编码，不存在三级编码数据

## 4. 行业归并规则

### 触发条件
某个申万二级行业编码下，公司数量 **< 5 家**。

### 归并目标
将不足 5 家的行业下的所有公司，临时行业编码替换为 `510100`（综合-综合）。

### 归并说明
- 归并仅影响**计算过程中的行业分组**，不修改原始行业编码
- 原始行业编码（`original_industry_code`）和归并后的临时行业编码（`mapped_industry_code`）**都需要输出到最终结果**
- 归并后，`510100` 本身的公司 + 被归并进来的公司，合并为一组参与后续计算

## 5. 计算流程变更

### 变更位置
在现有 `sample_data` CTE 之后、行业分组计算（`industry_rank` / `industry_median`）之前，**新增一个 `industry_mapped` CTE**，完成行业归并。

### 新增 CTE 逻辑（`industry_mapped`）

```
Step 1: 统计每个二级行业编码的公司数量
Step 2: 公司数 >= 5 → 保留原编码；公司数 < 5 → 替换为 510100
Step 3: 后续所有行业分组计算使用 mapped_industry_code 替代原始 industry_code
```

### 输出字段变更

最终 SELECT 需新增输出：
- `original_industry_code`：原始行业编码（来自 `industryDimField`）
- `mapped_industry_code`：归并后的临时行业编码（用于计算的实际分组编码）

## 6. 函数签名

**不变**，两个算子的参数列表保持原样：

- `Alg1`：`calc(String measureField, String companyDimField, String industryDimField)`
- `Alg2`：`calc(String measureField, String companyDimField, String industryDimField, String adjustFactorIndexCode)`

## 7. 验收标准

1. 两个算子均新增 `industry_mapped` CTE，实现申万行业归并逻辑
2. 行业公司数 >= 5 的，`mapped_industry_code` = 原始编码
3. 行业公司数 < 5 的，`mapped_industry_code` = `510100`
4. 后续所有行业分组（中位数、标准差等）均使用 `mapped_industry_code`
5. 最终结果同时输出 `original_industry_code` 和 `mapped_industry_code`
6. 原有计算逻辑（双截尾、Z-Score、线性变换等）不变
7. 函数签名不变，不新增参数

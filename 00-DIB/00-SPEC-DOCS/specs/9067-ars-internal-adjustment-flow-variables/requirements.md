# 9067 指标内部调整单审批流程网关变量 需求文档

## 背景
当前指标内部调整单在提交审批时，审批流程的网关变量不完整，缺少以下关键信息：
1. 支出事项编码（mattersCodes）
2. 调增合计金额（increaseAmount）
3. 调减合计金额（decreaseAmount）

这些变量在审批流程中用于网关条件判断，类似于采购项目中 `handleApprovalFlow` 方法的实现方式。

## 目标用户
预算管理人员、审批人员

## 功能描述
在指标内部调整单提交审批时，向审批流程传递以下网关变量：
1. **支出事项编码列表**（mattersCodes）：从调整明细中获取所有支出预算事项编码
2. **调增合计金额**（increaseAmount）：所有调增明细的金额汇总
3. **调减合计金额**（decreaseAmount）：所有调减明细的金额汇总

## 所属模块
- 前端：无需修改
- 后端：budget-ms（端口 18612）

## 用户故事
- 作为审批流程配置人员，我希望在指标内部调整单审批流程中能够使用支出事项编码、调增金额、调减金额作为网关条件，以便实现更灵活的审批路由

## 验收标准
- [ ] 标准1：提交审批时，流程变量中包含 `increaseMattersCodes`（调增支出事项编码列表）
- [ ] 标准2：提交审批时，流程变量中包含 `decreaseMattersCodes`（调减支出事项编码列表）
- [ ] 标准3：提交审批时，流程变量中包含 `increaseAmount`（调增合计金额）
- [ ] 标准4：提交审批时，流程变量中包含 `decreaseAmount`（调减合计金额）
- [ ] 标准5：支出事项编码从 `t_scope_expenditure.c_matters_code` 字段获取
- [ ] 标准6：调增合计金额为所有 `adjustType='1'` 的明细金额之和
- [ ] 标准7：调减合计金额为所有 `adjustType='2'` 的明细金额之和

## 边界条件
- 当调整明细为空时，mattersCodes 应为空列表，金额应为 0
- 当支出事项编码为空时，应过滤掉空值
- 金额计算应保留 2 位小数

## 非功能需求
- 无特殊性能要求
- 无特殊安全要求

## 技术分析

### 涉及文件
**后端**：
- `ars-budget/budget-ms/src/main/java/com/dibcn/ars/budget/service/budgetAdjustments/impl/BudgetIndicatorAdjustmentHeaderServiceImpl.java` - Service 实现
- `ars-budget/budget-ms/src/main/resources/mapper/budgetAdjustments/BudgetIndicatorAdjustmentDetailMapper.xml` - Mapper XML（需要修改查询以获取 mattersCode）

### 数据结构
- 调整明细表：`t_budget_indicator_adjustment_detail`
  - `c_scope_id` - 开支范围ID
  - `c_adjust_type` - 调整类型（"1"=调增，"2"=调减）
  - `n_adjust_amount` - 调整金额
- 开支范围表：`t_scope_expenditure`
  - `c_matters_code` - 支出预算事项编码

### 参考实现
采购项目中的 `handleApprovalFlow` 方法：
```java
variables.put("mattersCodes", req.getDetailList().stream()
    .map(PurchaseDetailReqVO::getMattersCode).toList());
```

## 待确认问题
- [x] 已确认：只需要修改后端，前端无需改动
- [x] 已确认：变量名称使用 mattersCodes、increaseAmount、decreaseAmount

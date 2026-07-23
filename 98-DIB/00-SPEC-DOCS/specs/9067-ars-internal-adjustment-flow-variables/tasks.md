# 9067 指标内部调整单审批流程网关变量 任务清单

## 任务概览
- 总任务数：3
- 前端任务：0
- 后端任务：3
- 预估工时：0.5 小时

## 后端任务

### 1. 新增 Mapper XML 查询方法
- **描述**：在 `BudgetIndicatorAdjustmentDetailMapper.xml` 中新增查询方法，关联 `t_scope_expenditure` 表获取 `mattersCode`
- **所属微服务**：budget-ms (18613)
- **涉及文件**：`ars-budget/budget-ms/src/main/resources/mapper/budgetAdjustments/BudgetIndicatorAdjustmentDetailMapper.xml`
- **依赖**：无
- **验收标准**：
  - 新增 `selectDetailWithMattersCodeByHeaderId` 查询方法
  - 返回 adjustType、adjustAmount、mattersCode 三个字段
- [x] 完成 (2026-01-15)

### 2. 新增 Mapper 接口方法
- **描述**：在 `BudgetIndicatorAdjustmentDetailMapper.java` 中新增接口方法
- **所属微服务**：budget-ms (18613)
- **涉及文件**：`ars-budget/budget-ms/src/main/java/com/dibcn/ars/budget/mapper/budgetAdjustments/BudgetIndicatorAdjustmentDetailMapper.java`
- **依赖**：任务 1
- **验收标准**：
  - 新增 `selectDetailWithMattersCodeByHeaderId` 方法
- [x] 完成 (2026-01-15)

### 3. 修改 Service 层 - 重写 buildFlowGatewayVariables 方法
- **描述**：修改 `buildFlowGatewayVariables` 方法，使用新的查询方法获取 mattersCode
- **所属微服务**：budget-ms (18613)
- **涉及文件**：`ars-budget/budget-ms/src/main/java/com/dibcn/ars/budget/service/budgetAdjustments/impl/BudgetIndicatorAdjustmentHeaderServiceImpl.java`
- **依赖**：任务 2
- **验收标准**：
  - 调用新的查询方法获取明细数据
  - 正确计算 increaseMattersCodes、decreaseMattersCodes、increaseAmount、decreaseAmount
- [x] 完成 (2026-01-15)

## 执行顺序
1 → 2 → 3

## 清理任务（可选）

### 清理不再需要的代码
以下代码是之前方案遗留的，可以清理：
- 实体类 `BudgetIndicatorAdjustmentDetail` 中的 `mattersCode` 字段（如果不需要）
- DTO `BudgetAdjustmentDTO.DetailDTO` 中的 `mattersCode` 字段（如果不需要）
- Service 层 `getBudgetIndicatorAdjustmentDetail` 方法中的 `detail.setMattersCode(...)` 调用（如果不需要）

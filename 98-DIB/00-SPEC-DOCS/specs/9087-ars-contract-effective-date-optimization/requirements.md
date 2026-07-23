# 9087 合同生效时间优化 需求文档

## 背景

当前合同管理模块中，生效时间字段存在以下限制：
1. 后台保存接口对生效时间有严格校验
2. 履约阶段的计划付款日期必须在生效时间范围内
3. 合同备案登记界面的生效时间从合同自动带出且不可编辑

这些限制在实际业务场景中过于严格，需要进行优化调整。

## 目标用户

- 合同管理员
- 合同起草人员
- 合同备案登记人员

## 功能描述

本需求涉及三个主要变更：

1. **移除后台生效时间校验**：去除后台保存接口中对生效时间的强制校验
2. **移除履约阶段时间限制**：去除"履约阶段计划付款日期必须在生效时间内"的限制
3. **优化备案登记界面**：调整生效时间字段的位置和编辑权限

## 所属模块

- **前端**：`a-front` 应用
- **后端**：`contract-ms` (18610) 微服务

## 用户故事

### US1：移除生效时间校验
作为合同管理员，我希望在保存合同时不受生效时间的强制校验限制，以便更灵活地处理特殊业务场景。

### US2：移除履约阶段时间限制
作为合同起草人员，我希望履约阶段的计划付款日期不受生效时间范围的限制，以便处理跨期合同或特殊付款安排。

### US3：优化备案登记界面
作为合同备案登记人员，我希望能够编辑生效时间字段，并且界面布局更加合理，以便更高效地完成备案工作。

## 验收标准

### 需求1：移除后台生效时间校验

- [ ] 1.1 WHEN 保存合同时生效日期早于签订日期 THEN 系统 SHALL 允许保存而不报错
- [ ] 1.2 WHEN 保存合同时计划结束日期早于生效日期 THEN 系统 SHALL 允许保存而不报错
- [ ] 1.3 WHEN 历史合同录入时生效日期为空 THEN 系统 SHALL 允许保存而不报错

### 需求2：移除履约阶段时间限制

- [ ] 2.1 WHEN 设置计划付款日期早于合同生效日期 THEN 系统 SHALL 允许保存而不报错
- [ ] 2.2 WHEN 设置计划付款日期晚于合同计划结束日期 THEN 系统 SHALL 允许保存而不报错
- [ ] 2.3 WHEN 前端表单校验计划付款日期 THEN 系统 SHALL 不再校验是否在生效时间范围内

### 需求3：优化备案登记界面

- [ ] 3.1 WHEN 打开合同备案登记界面 THEN 生效时间字段 SHALL 显示在归属地字段的前面（同一行）
- [ ] 3.2 WHEN 显示生效时间和归属地字段 THEN 两个字段 SHALL 各占 50% 宽度
- [ ] 3.3 WHEN 合同已有生效时间 THEN 系统 SHALL 自动从合同信息中带出该值（保持原有逻辑）
- [ ] 3.4 WHEN 生效时间已从合同带出 THEN 用户 SHALL 可以编辑修改该值（不再是只读）
- [ ] 3.5 WHEN 生效时间字段配置为自定义 THEN 系统 SHALL 支持表单起草界面的自定义配置

## 边界条件

- 当生效时间为空时，系统应正常保存合同
- 当用户清空已有的生效时间时，系统应允许保存
- 当合同信息中有生效时间时，备案登记界面自动带出（保持原有逻辑）
- 当用户修改已带出的生效时间后，以用户修改的值为准

## 非功能需求

- **性能**：无特殊要求
- **安全**：无特殊要求
- **权限**：沿用现有合同管理权限体系

## 涉及文件分析

### 后端文件

| 文件路径 | 变更内容 |
|---------|---------|
| `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/validator/HistoryRecordValidator.java` | 移除 `validateDateLogic` 方法中的生效时间校验 |
| `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/service/impl/ContractHistoryRecordServiceImpl.java` | 移除履约阶段日期范围校验 |

### 前端文件

| 文件路径 | 变更内容 |
|---------|---------|
| `ars-front-2/apps/a-front/src/fromConfig/ContractCommonFormCfg.ts` | 移除 `planPayDate` 字段的 `validateDateInRange` 校验 |
| `ars-front-2/apps/a-front/src/views/Contract/drafting/common/configData/ContractDraftingInfoFormCfg.ts` | 移除 `planPayDate` 字段的 `validateDateInRange` 校验 |
| `ars-front-2/apps/a-front/src/views/Contract/record/register/configData/formCfg.ts` | 添加生效时间字段，调整归属地布局 |
| `ars-front-2/apps/a-front/src/views/Contract/record/register/RegisterForm.vue` | 处理生效时间字段的数据绑定和编辑逻辑 |

## 待确认问题

- [x] 确认后端校验移除范围：仅移除生效时间相关校验，保留其他必填校验
- [x] 确认前端校验移除范围：仅移除计划付款日期的时间范围校验
- [x] 确认备案登记界面的生效时间字段格式：日期范围选择器（起止日期）

# 9087 合同生效时间优化 任务清单

## 任务概览

- 总任务数：9
- 后端任务：5
- 前端任务：3
- 数据库任务：1

## 后端任务

### 1. 数据库变更 - 新增生效时间字段

- **描述**：在合同备案表中新增生效时间字段
- **所属微服务**：contract-ms (18610)
- **涉及文件**：SQL 脚本
- **依赖**：无
- **验收标准**：字段成功添加到数据库表
- **SQL 脚本**：
  ```sql
  ALTER TABLE t_contract_record 
  ADD COLUMN dt_effective_date DATE COMMENT '生效日期',
  ADD COLUMN dt_plan_end_date DATE COMMENT '计划结束日期';
  ```
- _Requirements: 3.3, 3.4_
- [x] 完成

### 2. 后端实体变更 - ContractRecordEntity

- **描述**：在合同备案实体类中新增生效时间字段
- **所属微服务**：contract-ms
- **涉及文件**：
  - `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/model/entity/ContractRecordEntity.java`
- **依赖**：任务 1
- **验收标准**：实体类包含 effectiveDate 和 planEndDate 字段
- _Requirements: 3.3, 3.4_
- [x] 完成

### 3. 后端 VO 变更 - 请求和响应对象

- **描述**：在备案登记的请求和响应 VO 中新增生效时间字段
- **所属微服务**：contract-ms
- **涉及文件**：
  - `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/model/vo/record/register/RecordRegisterReqVO.java`
  - `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/model/vo/record/register/RecordRegisterRespVO.java`
- **依赖**：任务 2
- **验收标准**：VO 类包含生效时间字段，支持前端传参和返回
- _Requirements: 3.3, 3.4_
- [x] 完成

### 4. 移除后台生效时间校验

- **描述**：移除历史合同录入验证器中的日期逻辑校验和必填校验
- **所属微服务**：contract-ms
- **涉及文件**：
  - `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/validator/HistoryRecordValidator.java`
  - `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/model/vo/record/history/ContractInfoHistoryVO.java`
  - `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/model/vo/info/BasicInformationVO.java`
  - `ars-contract/contract-sdk/src/main/java/com/dibcn/ars/contract/vo/BasicInformationVO.java`
- **依赖**：无
- **验收标准**：
  - 生效日期不再是必填字段
  - 生效日期可以早于签订日期
  - 计划结束日期可以早于生效日期
  - 保存接口不再报日期校验错误
- _Requirements: 1.1, 1.2, 1.3_
- [x] 完成

### 5. 移除履约阶段日期范围校验

- **描述**：移除历史合同导入时履约阶段的日期范围校验
- **所属微服务**：contract-ms
- **涉及文件**：
  - `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/service/impl/ContractHistoryRecordServiceImpl.java`
- **依赖**：无
- **验收标准**：计划收付款日期不再受生效时间范围限制
- _Requirements: 2.1, 2.2_
- [x] 完成

## 前端任务

### 6. 移除前端履约阶段日期校验

- **描述**：移除合同起草表单中计划付款日期的日期范围校验
- **所属应用**：a-front
- **涉及文件**：
  - `ars-front-2/apps/a-front/src/fromConfig/ContractCommonFormCfg.ts`
  - `ars-front-2/apps/a-front/src/views/Contract/drafting/common/configData/ContractDraftingInfoFormCfg.ts`
- **依赖**：无
- **验收标准**：
  - 计划付款日期字段不再显示"计划付款日期需在合同生效期间内"错误
  - 可以设置任意日期
- _Requirements: 2.3_
- [x] 完成

### 7. 备案登记表单配置 - 添加生效时间字段

- **描述**：在备案登记表单中添加生效时间字段，调整归属地布局
- **所属应用**：a-front
- **涉及文件**：
  - `ars-front-2/apps/a-front/src/views/Contract/record/register/configData/formCfg.ts`
- **依赖**：任务 3（后端 VO 完成）
- **验收标准**：
  - 生效时间字段显示在归属地前面
  - 两个字段各占 50% 宽度，同一行显示
  - 生效时间可编辑
- _Requirements: 3.1, 3.2, 3.4_
- [x] 完成

### 8. 备案登记页面 - 数据绑定和初始化

- **描述**：处理生效时间字段的数据绑定、初始化和保存逻辑
- **所属应用**：a-front
- **涉及文件**：
  - `ars-front-2/apps/a-front/src/views/Contract/record/register/RegisterForm.vue`
- **依赖**：任务 7
- **验收标准**：
  - 新建时从合同详情自动带出生效时间
  - 编辑时优先显示备案记录中的生效时间
  - 保存时正确提交生效时间字段
- _Requirements: 3.3, 3.4_
- [x] 完成

## 验收任务

### 9. 功能验收测试

- **描述**：验证所有功能点是否正常工作
- **依赖**：任务 1-8 全部完成
- **验收标准**：
  - [ ] 后台保存合同时不再校验生效时间逻辑
  - [ ] 履约阶段计划付款日期可以超出生效时间范围
  - [ ] 备案登记界面生效时间和归属地同行显示，各占 50%
  - [ ] 生效时间从合同详情自动带出
  - [ ] 生效时间可编辑并正确保存到备案表
- [ ] 完成

## 执行顺序

```
1 (数据库) → 2 (实体) → 3 (VO) → 7 (前端配置) → 8 (前端页面)
                                    ↑
4 (后端校验移除) ─────────────────────┘
5 (后端校验移除) ─────────────────────┘
6 (前端校验移除) ─────────────────────┘
                                    ↓
                              9 (验收测试)
```

## 注意事项

1. 数据库变更需要先在开发环境执行，确认无误后再同步到其他环境
2. 后端任务 4、5 和前端任务 6 可以并行执行，互不依赖
3. 前端任务 7、8 依赖后端任务 3 完成（需要 VO 支持新字段）
4. 所有任务完成后进行集成测试

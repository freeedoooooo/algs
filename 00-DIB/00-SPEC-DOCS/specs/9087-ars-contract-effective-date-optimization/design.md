# 9087 合同生效时间优化 技术设计

## 概述

本需求涉及移除合同管理模块中生效时间相关的校验限制，并优化合同备案登记界面的生效时间字段布局和编辑权限。

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (a-front)                          │
├─────────────────────────────────────────────────────────────┤
│  合同起草界面                    合同备案登记界面              │
│  ├─ ContractCommonFormCfg.ts    ├─ RegisterForm.vue          │
│  └─ ContractDraftingInfoFormCfg └─ formCfg.ts                │
│       ↓ 移除日期范围校验              ↓ 添加生效时间字段        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 (contract-ms:18610)                   │
├─────────────────────────────────────────────────────────────┤
│  HistoryRecordValidator.java                                 │
│  └─ validateDateLogic() → 移除生效时间校验                    │
│  ContractHistoryRecordServiceImpl.java                       │
│  └─ validateStageInfo() → 移除履约阶段日期范围校验            │
└─────────────────────────────────────────────────────────────┘
```

### 前端架构

- **所属应用**：`a-front`
- **涉及页面**：
  - 合同起草界面：`/views/Contract/drafting/`
  - 合同备案登记界面：`/views/Contract/record/register/`
- **涉及配置**：
  - `ContractCommonFormCfg.ts` - 通用表单配置
  - `ContractDraftingInfoFormCfg.ts` - 起草表单配置
  - `formCfg.ts` - 备案登记表单配置

### 后端架构

- **所属微服务**：`contract-ms` (端口 18610)
- **涉及模块**：
  - `validator/` - 数据校验
  - `service/impl/` - 业务逻辑实现

## 数据模型

### 前端类型定义

无新增类型，复用现有 `basicInformationVO` 中的字段：

```typescript
interface IBasicInformationVO {
  effectiveDate: string    // 生效日期
  planEndDate: string      // 计划结束日期
  daterange: [string, string]  // 日期范围（前端展示用）
  // ... 其他字段
}
```

### 后端实体类

无新增实体，复用现有字段。

### 数据库变更

**表名**：`t_contract_record`

**新增字段**：

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `dt_effective_date` | `DATE` | 生效日期 |
| `dt_plan_end_date` | `DATE` | 计划结束日期 |

**SQL 脚本**：
```sql
ALTER TABLE t_contract_record 
ADD COLUMN dt_effective_date DATE COMMENT '生效日期',
ADD COLUMN dt_plan_end_date DATE COMMENT '计划结束日期';
```

## 技术方案

### 需求1：移除后台生效时间校验

#### 1.1 修改 HistoryRecordValidator.java

**文件路径**：`ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/validator/HistoryRecordValidator.java`

**变更内容**：移除 `validateDateLogic` 方法中的日期逻辑校验

```java
// 修改前
private void validateDateLogic(ContractInfoHistoryVO contractInfo, List<String> errors) {
    // ... 校验生效日期不能早于签订日期
    // ... 校验计划结束日期不能早于生效日期
}

// 修改后
private void validateDateLogic(ContractInfoHistoryVO contractInfo, List<String> errors) {
    // 移除生效时间相关校验，允许灵活设置日期
    // 保留方法签名以保持代码结构，方法体置空或仅保留空值检查
}
```

#### 1.2 修改 ContractHistoryRecordServiceImpl.java

**文件路径**：`ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/service/impl/ContractHistoryRecordServiceImpl.java`

**变更内容**：移除 `validateStageInfo` 方法中的日期范围校验（约第1009行）

```java
// 修改前
if (payDate.isBefore(excelBaseInfo.getEffectiveDate()) || payDate.isAfter(excelBaseInfo.getPlanEndDate())) {
    errorMessage.append("计划收付款日期应在生效时间[").append(excelBaseInfo.getEffectiveDateRange()).append("]范围内; ");
    isValid = false;
}

// 修改后
// 移除此校验逻辑，允许计划收付款日期不受生效时间范围限制
```

### 需求2：移除履约阶段时间限制

#### 2.1 修改 ContractCommonFormCfg.ts

**文件路径**：`ars-front-2/apps/a-front/src/fromConfig/ContractCommonFormCfg.ts`

**变更内容**：移除 `planPayDate` 字段的 `validateDateInRange` 校验规则（约第1130行）

```typescript
// 修改前
{
  label: '计划付款日期',
  field: 'planPayDate',
  widget: 'date',
  required: true,
  display: extendConfig.display,
  props: {
    disabled: props.readonly
  },
  rules: [
    {
      validator: (rule: any, value: any, callback: any) => {
        const start = formData.basicInformationVO.effectiveDate
        const end = formData.basicInformationVO.planEndDate
        if (value && !validateDateInRange(value, start, end)) {
          callback(new Error('计划付款日期需在合同生效期间内'))
        }
        callback()
      },
      trigger: 'blur'
    }
  ]
}

// 修改后
{
  label: '计划付款日期',
  field: 'planPayDate',
  widget: 'date',
  required: true,
  display: extendConfig.display,
  props: {
    disabled: props.readonly
  }
  // 移除 rules，不再校验日期范围
}
```

#### 2.2 修改 ContractDraftingInfoFormCfg.ts

**文件路径**：`ars-front-2/apps/a-front/src/views/Contract/drafting/common/configData/ContractDraftingInfoFormCfg.ts`

**变更内容**：同样移除 `planPayDate` 字段的 `validateDateInRange` 校验规则（约第751行）

### 需求3：优化备案登记界面

#### 3.1 后端：修改 ContractRecordEntity.java

**文件路径**：`ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/model/entity/ContractRecordEntity.java`

**变更内容**：新增生效时间字段

```java
/**
 * 生效日期
 */
@TableField("dt_effective_date")
private LocalDate effectiveDate;

/**
 * 计划结束日期
 */
@TableField("dt_plan_end_date")
private LocalDate planEndDate;
```

#### 3.2 后端：修改相关 VO 类

**文件路径**：`ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/model/vo/record/register/`

需要在 `RecordRegisterReqVO` 和 `RecordRegisterRespVO` 中添加对应字段。

#### 3.3 后端：修改 ContractRecordService

确保保存和查询时正确处理新增的生效时间字段。

#### 3.4 前端：修改 formCfg.ts

**文件路径**：`ars-front-2/apps/a-front/src/views/Contract/record/register/configData/formCfg.ts`

**变更内容**：添加生效时间字段，调整归属地布局

```typescript
// 修改前
{
  label: '归属地',
  widget: 'RegionTreeSelect',
  required: true,
  prop: 'regionId',
  style: 'width:100%',
  props: {
    placeholder: '请选择归属地'
  }
}

// 修改后
{
  label: '生效时间',
  widget: 'daterange',
  required: true,
  prop: 'effectiveDateRange',
  style: 'width:50%',
  props: {
    type: 'daterange',
    startPlaceholder: '开始日期',
    endPlaceholder: '结束日期',
    format: 'YYYY-MM-DD',
    valueFormat: 'YYYY-MM-DD'
  },
  hooks: {
    changeObj: ({ context, obj }) => {
      if (obj && obj.length === 2) {
        context.model.effectiveDate = obj[0]
        context.model.planEndDate = obj[1]
      }
    }
  }
},
{
  label: '归属地',
  widget: 'RegionTreeSelect',
  required: true,
  prop: 'regionId',
  style: 'width:50%',  // 从100%改为50%
  props: {
    placeholder: '请选择归属地'
  }
}
```

#### 3.5 前端：修改 RegisterForm.vue

**文件路径**：`ars-front-2/apps/a-front/src/views/Contract/record/register/RegisterForm.vue`

**变更内容**：
1. 在 `form` 对象中添加 `effectiveDate`、`planEndDate`、`effectiveDateRange` 字段
2. 在 `getRecordInfo` 方法中从合同详情初始化生效时间
3. 确保保存时提交生效时间字段

```typescript
// form 对象添加字段
const form = reactive({
  // ... 现有字段
  effectiveDate: '',      // 新增：生效日期
  planEndDate: '',        // 新增：计划结束日期
  effectiveDateRange: [] as string[],  // 新增：生效时间范围（前端展示用）
})

// getRecordInfo 方法中初始化（从合同详情带出）
if (contractDetail && contractDetail.basicInformationVO) {
  const basicInfo = contractDetail.basicInformationVO
  // 从合同详情带出生效时间作为初始值
  form.effectiveDate = basicInfo.effectiveDate || ''
  form.planEndDate = basicInfo.planEndDate || ''
  form.effectiveDateRange = [basicInfo.effectiveDate, basicInfo.planEndDate]
}

// 如果是编辑模式，从备案记录中读取（优先使用备案记录的值）
if (data.effectiveDate) {
  form.effectiveDate = data.effectiveDate
  form.planEndDate = data.planEndDate
  form.effectiveDateRange = [data.effectiveDate, data.planEndDate]
}
```

## 影响范围

### 前端

| 文件 | 变更类型 | 说明 |
|-----|---------|------|
| `ContractCommonFormCfg.ts` | 修改 | 移除 planPayDate 的日期范围校验 |
| `ContractDraftingInfoFormCfg.ts` | 修改 | 移除 planPayDate 的日期范围校验 |
| `formCfg.ts` | 修改 | 添加生效时间字段，调整归属地宽度 |
| `RegisterForm.vue` | 修改 | 添加生效时间字段和数据初始化逻辑 |

### 后端

| 文件 | 变更类型 | 说明 |
|-----|---------|------|
| `HistoryRecordValidator.java` | 修改 | 移除 validateDateLogic 中的日期校验 |
| `ContractHistoryRecordServiceImpl.java` | 修改 | 移除履约阶段日期范围校验 |
| `ContractRecordEntity.java` | 修改 | 新增 effectiveDate、planEndDate 字段 |
| `RecordRegisterReqVO.java` | 修改 | 新增 effectiveDate、planEndDate 字段 |
| `RecordRegisterRespVO.java` | 修改 | 新增 effectiveDate、planEndDate 字段 |
| `ContractRecordServiceImpl.java` | 修改 | 处理生效时间字段的保存和查询 |

### 数据库

| 表名 | 变更类型 | 说明 |
|-----|---------|------|
| `t_contract_record` | 修改 | 新增 dt_effective_date、dt_plan_end_date 字段 |

## 风险点

| 风险 | 影响 | 应对措施 |
|-----|------|---------|
| 移除校验后可能出现不合理的日期数据 | 低 | 业务层面由用户自行把控，系统不再强制限制 |
| 历史数据兼容性 | 无 | 仅移除校验，不影响现有数据 |

## 测试策略

### 单元测试

1. 后端：验证移除校验后保存接口正常工作
2. 前端：验证表单提交不再触发日期范围校验

### 集成测试

1. 合同起草流程：验证履约阶段日期可以超出生效时间范围
2. 合同备案登记：验证生效时间可编辑且正确保存
3. 历史合同录入：验证日期校验已移除

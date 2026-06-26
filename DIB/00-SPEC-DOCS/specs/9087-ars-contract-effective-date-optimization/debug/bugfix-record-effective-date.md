# Bugfix: 合同备案登记生效时间保存和回显问题

## 问题描述

1. 合同备案登记保存时传入了生效时间，但查询时没有返回
2. 备案详情页面的合同签订信息中生效时间没有正常回显
3. 基本信息中的生效时间没有隐藏（与合同签订信息中的生效时间重复显示）

## 根本原因

### 后端问题
1. `ContractRecordServiceImpl.add()` 方法没有设置 `effectiveDate` 和 `planEndDate` 字段
2. `ContractRecordServiceImpl.updateRecord()` 方法没有更新 `effectiveDate` 和 `planEndDate` 字段
3. `ContractRecordServiceImpl.getDetail()` 方法没有从备案记录读取 `effectiveDate` 和 `planEndDate` 字段

### 前端问题
1. `RegisterView.vue` 中 `form` 对象缺少 `effectiveDate`、`planEndDate`、`effectiveDateRange` 字段
2. `RegisterView.vue` 中 `getRecordInfo` 方法没有从备案记录读取生效时间
3. `ContractCommonFormCfg.ts` 中基本信息的生效时间字段没有隐藏控制

## 修复方案

### 后端修复

**文件**: `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/service/impl/ContractRecordServiceImpl.java`

1. `add()` 方法添加：
```java
entity.setEffectiveDate(vo.getEffectiveDate());
entity.setPlanEndDate(vo.getPlanEndDate());
```

2. `updateRecord()` 方法添加：
```java
recordEntity.setEffectiveDate(vo.getEffectiveDate());
recordEntity.setPlanEndDate(vo.getPlanEndDate());
```

3. `getDetail()` 方法添加：
```java
vo.setEffectiveDate(recordEntity.getEffectiveDate());
vo.setPlanEndDate(recordEntity.getPlanEndDate());
```

### 前端修复

**文件**: `ars-front-2/apps/a-front/src/views/Contract/record/register/RegisterView.vue`

1. `form` 对象添加字段：
```typescript
effectiveDate: '',
planEndDate: '',
effectiveDateRange: [] as string[],
```

2. `getRecordInfo` 方法添加读取逻辑：
```typescript
if (data.effectiveDate) {
  form.effectiveDate = data.effectiveDate
  form.planEndDate = data.planEndDate || ''
  form.effectiveDateRange = [data.effectiveDate, data.planEndDate || '']
}
```

**文件**: `ars-front-2/apps/a-front/src/fromConfig/ContractCommonFormCfg.ts`

生效时间字段添加隐藏控制：
```typescript
{
  label: '生效时间',
  widget: 'daterange',
  hidden: props.hideBasicEffectiveDate, // 新增
  // ...
}
```

**文件**: `RegisterView.vue`, `RegisterForm.vue`, `RegisterCheck.vue`

`commonProps` 添加：
```typescript
hideBasicEffectiveDate: true,
```

## 修改文件清单

| 文件 | 修改类型 |
|-----|---------|
| `ars-contract/.../ContractRecordServiceImpl.java` | 修改 add、updateRecord、getDetail 方法 |
| `ars-front-2/.../RegisterView.vue` | 添加字段和读取逻辑 |
| `ars-front-2/.../RegisterForm.vue` | 添加 hideBasicEffectiveDate 配置 |
| `ars-front-2/.../RegisterCheck.vue` | 添加 hideBasicEffectiveDate 配置 |
| `ars-front-2/.../ContractCommonFormCfg.ts` | 添加 hidden 属性支持 |

## 验证步骤

1. 打开合同备案登记页面
2. 填写生效时间并保存
3. 刷新页面，确认合同签订信息中的生效时间正确回显
4. 确认基本信息中的生效时间已隐藏

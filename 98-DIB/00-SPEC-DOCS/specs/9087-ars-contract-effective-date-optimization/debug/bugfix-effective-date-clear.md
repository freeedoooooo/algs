# Bugfix: 合同生效时间清空后无法保存为空

## 问题描述

用户在合同起草界面清空生效时间后，保存时数据库中的生效时间字段没有被更新为空，仍然保留旧值。

## 根本原因

### 前端问题
1. `ContractCommonFormCfg.ts` 中 `daterange` 字段的 `changeObj` hook 没有处理清空情况
2. `BasicInformation.vue` 中 `selectDatesChange` 函数没有正确处理空值

### 后端问题
`ContractInfoServiceImpl.saveOrUpdateData` 方法中，更新逻辑使用 `Objects.nonNull()` 判断：
```java
if (Objects.nonNull(contractInfo.getEffectiveDate())) {
    updateWrapper.set(ContractInfo::getEffectiveDate, contractInfo.getEffectiveDate());
}
```
当前端传空字符串时，Java 的 `LocalDate` 字段被解析为 `null`，条件不满足，字段不会被更新。

## 修复方案

### 前端修复

**文件**: `ars-front-2/apps/a-front/src/fromConfig/ContractCommonFormCfg.ts`

```typescript
hooks: {
  changeObj: ({ context, obj }) => {
    // 处理清空情况
    if (!obj || obj.length === 0 || !obj[0]) {
      context.model.basicInformationVO.effectiveDate = ''
      context.model.basicInformationVO.planEndDate = ''
    } else {
      context.model.basicInformationVO.effectiveDate = obj[0]
      context.model.basicInformationVO.planEndDate = obj[1]
    }
  }
}
```

**文件**: `ars-front-2/apps/a-front/src/views/Contract/drafting/common/BasicInformation.vue`

```typescript
const selectDatesChange = () => {
  if (!selectDates.value || selectDates.value.length === 0 || !selectDates.value[0]) {
    formData.value.effectiveDate = ''
    formData.value.planEndDate = ''
  } else {
    formData.value.effectiveDate = selectDates.value[0]
    formData.value.planEndDate = selectDates.value[1]
  }
  // ...
}
```

### 后端修复

**文件**: `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/service/info/impl/ContractInfoServiceImpl.java`

将 `saveOrUpdateData` 方法中的更新逻辑改为使用新的 `saveOrUpdateWithNullFields` 方法，该方法对 `effectiveDate` 和 `planEndDate` 字段不再判断非空，直接设置值（允许为 null）：

```java
// 生效时间允许设置为null（需求9087）
updateWrapper.set(ContractInfo::getEffectiveDate, contractInfo.getEffectiveDate());
updateWrapper.set(ContractInfo::getPlanEndDate, contractInfo.getPlanEndDate());
```

## 修改文件清单

| 文件 | 修改类型 |
|-----|---------|
| `ars-front-2/apps/a-front/src/fromConfig/ContractCommonFormCfg.ts` | 修改 |
| `ars-front-2/apps/a-front/src/views/Contract/drafting/common/BasicInformation.vue` | 修改 |
| `ars-contract/contract-ms/src/main/java/com/dibcn/ars/contract/service/info/impl/ContractInfoServiceImpl.java` | 修改 |

## 验证步骤

1. 打开合同起草界面
2. 选择一个已有生效时间的合同
3. 清空生效时间字段
4. 点击保存
5. 刷新页面，确认生效时间已被清空

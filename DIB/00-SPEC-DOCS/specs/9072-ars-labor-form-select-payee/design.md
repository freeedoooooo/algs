# 9072 劳务费信息新增"选择收款方"按钮 技术设计

## 概述
修改 `LaborForm.vue` 组件，新增"选择收款方"按钮并调整"新增"按钮的行为。

## 架构设计

### 整体架构
纯前端改动，不涉及后端 API 变更。

### 前端架构
- 所属应用：a-front
- 涉及页面：费用报销表单 - 劳务费信息
- 涉及组件：`LaborForm.vue`、`CustomTitle.vue`

## 技术方案

### 方案一：修改 CustomTitle 组件（推荐）

修改 `CustomTitle.vue` 组件，支持显示多个按钮：

```vue
<!-- CustomTitle.vue 改造后 -->
<template>
  <div class="labor-form-header">
    <div class="labor-form-title">{{ title }}</div>
    <div class="labor-form-header-btns">
      <el-button 
        v-if="!disabled && showSelectPayeeButton" 
        type="primary" 
        @click="onSelectPayeeClick"
      >
        选择收款方
      </el-button>
      <el-button 
        v-if="!disabled && showImportButton" 
        type="primary" 
        @click="onImportClick"
      >
        {{ btnText }}
      </el-button>
    </div>
  </div>
</template>
```

### 方案二：使用 tablePrefixList（备选）

参照 `SettlementForm.vue` 的实现，在表格配置中使用 `tablePrefixList` 添加按钮。但由于劳务费信息已使用 `CustomTitle` 组件作为标题，此方案会导致按钮位置不一致。

**选择方案一**，保持与现有"导入"按钮的一致性。

## 代码变更

### 1. CustomTitle.vue 组件改造

新增 props：
- `showSelectPayeeButton`: Boolean - 是否显示"选择收款方"按钮
- `onSelectPayeeBtnclick`: Function - 选择收款方按钮点击事件

新增 emit：
- `selectPayeeBtnclick` - 选择收款方按钮点击事件

### 2. LaborForm.vue 组件改造

#### 2.1 CustomTitle 配置变更
```typescript
{
  widget: 'CustomTitle',
  props: {
    title: '劳务费信息',
    showImportButton: true,
    showSelectPayeeButton: true,  // 新增
    onImportBtnclick: () => {
      showImportPersonDialog()
    },
    onSelectPayeeBtnclick: () => {  // 新增
      showDialog.value = true
    }
  }
}
```

#### 2.2 表格 addMethod 变更
```typescript
// 原代码
addMethod: (context, value) => {
  showDialog.value = true  // 打开弹窗
}

// 改为
addMethod: (context, value) => {
  // 直接添加空行
  context.model.laborDetailList.push({
    payeeId: '',
    payeeName: '',
    certType: '',
    certNo: '',
    phone: '',
    professionalLevel: '',
    orgType: '',
    calcUnit: '',
    workload: 0,
    feeStandard: 0,
    applyAmount: 0,
    personalTax: 0,
    preTaxAmount: 0
  })
}
```

## 影响范围

### 前端
- 需要修改的现有文件：
  - `ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/CustomTitle.vue`
  - `ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/LaborForm.vue`
- 需要新增的文件：无

### 影响分析
- `CustomTitle.vue` 是公共组件，新增的 props 都有默认值，不影响其他使用该组件的地方
- `LaborForm.vue` 同时被事前申请和费用报销使用，改动会同时影响两个场景

## 风险点
- 风险1：`CustomTitle.vue` 被多处使用，需确保新增 props 有默认值，不影响现有功能
  - 应对：新增 props 默认值为 `false`，不显示新按钮

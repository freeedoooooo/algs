# 指标编码字段分析文档

## 问题背景

在实现 9067 需求（指标内部调整单审批流程网关变量）过程中，发现前端保存时没有正确传递指标编码给后端。

## 问题分析过程

### 1. 初始问题

前端保存指标内部调整单时，`expenseDetails` 中没有 `mattersCode` 字段。

### 2. 调试过程

通过添加 `kaiao:` 前缀的 console 日志进行调试：

```javascript
console.log('kaiao: 选择的预算指标对象 obj =', obj)
console.log('kaiao: obj.details =', obj.details)
console.log('kaiao: detail.matterCode =', detail.matterCode)
```

### 3. 发现的问题

1. **字段名不匹配**：后端返回的是 `matterCode`（不带 s），前端使用的是 `mattersCode`（带 s）
2. **数据源问题**：后端 `fillExpenditureMatterDetails` 方法在补充支出事项时没有设置 `matterCode`
3. **字段混淆**：`mattersCode` 是支出事项编码，`indicatorCode` 才是指标编码

### 4. 字段定义澄清

| 字段名 | 含义 | 示例值 | 来源 |
|--------|------|--------|------|
| `indicatorCode` | 指标编码 | `zbbm-lyx26010402` | `getBudgetInfoPageWithAdjust` API 返回 |
| `mattersCode` | 支出预算事项编码 | `ZCSX-0141` | 指标对象的 `mattersCode` 字段 |
| `matterCode` | 支出事项编码（detail级别） | `ZCSX-0116` | detail 对象的 `matterCode` 字段 |

### 5. 最终方案

根据需求确认，前端表格中显示的"指标编码"应该使用 `indicatorCode` 字段：

```typescript
// 在 changeObj 中
row.indicatorCode = obj.indicatorCode

// 指标编码字段配置
const createIndicatorCodeField = (): FormFieldConfig => ({
  label: '指标编码',
  field: 'indicatorCode',
  widget: 'input',
  props: { disabled: true }
})
```

## 相关文件

- 前端配置：`ars-front-2/apps/a-front/src/views/budget/budgettarget/budgetAdjustments/internalAdjustments/configData/formCfg.ts`
- 后端 API：`getBudgetInfoPageWithAdjust`
- 后端 VO：`DecomposeDetailsRespVO`

## 结论

1. 前端表格"指标编码"列使用 `indicatorCode` 字段
2. 网关变量中的 `mattersCode` 需要从指标级别的 `obj.mattersCode` 获取
3. 后端 `fillExpenditureMatterDetails` 方法需要补充 `matterCode` 字段设置（如果需要 detail 级别的编码）

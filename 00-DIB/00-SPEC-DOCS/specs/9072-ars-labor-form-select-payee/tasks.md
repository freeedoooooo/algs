# 9072 劳务费信息新增"选择收款方"按钮 任务清单

## 任务概览
- 总任务数：3
- 前端任务：3
- 后端任务：0
- 预估工时：1 小时

## 前端任务

### 1. 改造 CustomTitle.vue 组件
- **描述**：新增"选择收款方"按钮支持
- **所属应用**：a-front
- **涉及文件**：
  - `ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/CustomTitle.vue`
- **依赖**：无
- **验收标准**：
  - 新增 `showSelectPayeeButton` prop，默认值为 `false`
  - 新增 `selectPayeeBtnclick` emit 事件
  - "选择收款方"按钮显示在"导入"按钮左侧
  - 禁用状态下按钮不显示
- [x] 完成 (2026-01-15)

### 2. 修改 LaborForm.vue 组件
- **描述**：配置"选择收款方"按钮，修改"新增"按钮行为
- **所属应用**：a-front
- **涉及文件**：
  - `ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/LaborForm.vue`
- **依赖**：任务 1
- **验收标准**：
  - CustomTitle 配置中启用 `showSelectPayeeButton`
  - 点击"选择收款方"按钮打开收款方选择弹窗
  - 点击"新增"按钮直接添加空行，不弹出弹窗
- [x] 完成 (2026-01-15)

### 3. 修复 setReceiver 方法逻辑
- **描述**：修复选择收款方后清空手动新增数据的问题
- **所属应用**：a-front
- **涉及文件**：
  - `ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/LaborForm.vue`
- **依赖**：任务 2
- **验收标准**：
  - 保留手动新增的行（payeeId 为空）
  - 保留选中的收款方行
  - 只移除取消选中的收款方行
- [x] 完成 (2026-01-15)

## 执行顺序
1 → 2 → 3

# 9063 单位收款方启用状态优化 任务清单

## 任务概览
- 总任务数：2
- 前端任务：1
- 后端任务：1
- 预估工时：0.5 小时

## 后端任务

### 1. 修改保存逻辑 - 自动设置启用状态
- **描述**：在 `saveData` 方法中，保存前强制设置 `isEnabled = "1"`
- **所属微服务**：fin-track-ms (18615)
- **涉及文件**：`ars-fin-track/fin-track-ms/src/main/java/com/dibcn/ars/finTrack/service/spendAllocation/impl/PayeeManagementServiceImpl.java`
- **依赖**：无
- **验收标准**：
  - 新增收款方后，启用状态为"已启用"
  - 编辑收款方保存后，启用状态为"已启用"
- [x] 完成 (2026-01-14 完成)

## 前端任务

### 2. 修改列表页 - 已启用隐藏删除按钮
- **描述**：境内和境外收款方列表的删除按钮添加 `v-if` 条件判断
- **所属应用**：a-front
- **涉及文件**：`ars-front-2/apps/a-front/src/views/fin-track/spendAllocation/payeeManagement/index.vue`
- **依赖**：任务 1
- **验收标准**：
  - 境内收款方列表，已启用的记录不显示删除按钮
  - 境外收款方列表，已启用的记录不显示删除按钮
  - 未启用的记录正常显示删除按钮
- [x] 完成 (2026-01-14 完成)

## 执行顺序
1 → 2

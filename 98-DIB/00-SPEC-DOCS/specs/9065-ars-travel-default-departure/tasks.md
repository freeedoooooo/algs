# 9065 事前申请-出差默认出发地点 任务清单

## 任务概览

- 总任务数：3
- 前端任务：2
- 后端任务：0
- 配置任务：1
- 预估工时：1 小时

## 前端任务

### 1. 修改 use-travel.ts - 支持默认出发地点参数

- **描述**：修改 `useTravel` hooks，支持传入默认出发地点参数，在 `getDefaultTravelData()` 方法中填充默认值
- **所属应用**：a-front
- **涉及文件**：`ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/hooks/use-travel.ts`
- **依赖**：无
- **验收标准**：
  - `useTravel` 接受 `defaultDeparture` 参数
  - `getDefaultTravelData()` 返回的数据包含默认出发地点
  - 不影响现有功能
- [x] 完成

### 2. 修改 TravelForm.vue - 获取并使用默认出发地点

- **描述**：在组件初始化时获取默认出发地点参数，并传递给 `useTravel` hooks
- **所属应用**：a-front
- **涉及文件**：`ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/TravelForm.vue`
- **依赖**：任务 1
- **验收标准**：
  - 组件初始化时调用 `BaseListApi.getByKey('ft_travel_default_departure')` 获取参数
  - 新建行程时出发地点自动填充配置值
  - 编辑已有行程时不覆盖已保存的出发地点
  - 用户可以手动修改自动填充的出发地点
  - 参数获取失败时不影响正常功能
- [x] 完成

## 配置任务

### 3. 配置系统参数

- **描述**：在系统参数管理中新增 `ft_travel_default_departure` 参数
- **所属模块**：common-ms（系统参数管理）
- **涉及操作**：通过系统管理界面或数据库添加参数
- **依赖**：无
- **验收标准**：
  - 参数 key 为 `ft_travel_default_departure`
  - 参数值格式为逗号分隔的地区代码（如 `110000,110100,110101`）
  - 参数可通过 `BaseListApi.getByKey()` 正常获取
- [x] 完成 (2026-01-14 完成，配置值：330000,330300,330302 浙江省温州市鹿城区)

## 执行顺序

```
1 → 2 → 3（可并行）
```

## 备注

- 任务 1 和任务 2 为代码修改任务，需要按顺序执行
- 任务 3 为配置任务，可以与代码任务并行进行
- 配置任务需要系统管理员在系统参数管理界面完成，或通过数据库直接插入

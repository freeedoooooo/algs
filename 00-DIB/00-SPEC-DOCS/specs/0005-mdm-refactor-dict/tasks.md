# 字典模块代码重构 任务清单

> 编号：`0005` | 模块：`mdm` | 服务：`data-cloud-mdm` | 创建时间：2026-03-18
> 关联文档：`requirements.md` | `design.md`

---

## 工时评估

| 任务 | 预计工时 |
|------|---------|
| 1. 重构 DictDefConverter | 15 min |
| 2. 重构 DictItemConverter | 15 min |
| 3. 重构 DictDefAggregate | 30 min |
| 4. 重构 DictItemAggregate | 20 min |
| 5. 调整 DictController | 10 min |
| 合计 | 90 min |

---

## 任务列表

- [x] 1. 重构 DictDefConverter（预计 15 min）
  - [x] 1.1 添加 `componentModel = "spring"` 到 `@Mapper` 注解
  - [x] 1.2 新增 `fromSaveReqToEntity(DictDefSaveReq req)` 方法

- [x] 2. 重构 DictItemConverter（预计 15 min）
  - [x] 2.1 添加 `componentModel = "spring"` 到 `@Mapper` 注解
  - [x] 2.2 将 `fromEntityListToReq` 重命名为 `fromEntityListToBO`
  - [x] 2.3 新增 `fromEntityToResp(DictItemEntity entity)` 方法
  - [x] 2.4 新增 `fromSaveReqToEntity(DictItemSaveReq req)` 方法
  - [x] 2.5 新增 `fromBOToEntity(DictItemBO bo)` 方法

- [x] 3. 重构 DictDefAggregate（预计 30 min）
  - [x] 3.1 `listDictDef`：手动 `LambdaQueryWrapper` 改为 `lambdaQuery()` 链式写法，补充 `del_flag = false` 过滤（字典定义和字典项两处）
  - [x] 3.2 `pageDictDef`：手动 `LambdaQueryWrapper` 改为 `lambdaQuery()` 链式写法
  - [x] 3.3 `getDefById`：`BeanUtils.copyProperties` 替换为 `DictDefConverter.INSTANCE.fromEntityToResp`
  - [x] 3.4 `addDictDef`：`BeanUtils.copyProperties`（def）替换为 `DictDefConverter.INSTANCE.fromSaveReqToEntity`；`BeanUtils.copyProperties`（item）替换为 `DictItemConverter.INSTANCE.fromBOToEntity`；`CollectionUtils.isEmpty` 改为 `CollUtil.isNotEmpty`
  - [x] 3.5 `updateDictDef`：同 3.4 替换；删除字典项改为 `lambdaUpdate().eq(...).remove()`
  - [x] 3.6 `deleteDictDef`：删除操作改为 `lambdaUpdate().eq(...).remove()`

- [x] 4. 重构 DictItemAggregate（预计 20 min）
  - [x] 4.1 `listDictItem`：`DictItemConverter.INSTANCE.fromEntityListToReq` 改为 `fromEntityListToBO`
  - [x] 4.2 `addDictItem`：不再修改入参，改为在 entity 上设置 id，方法返回值改为 `Long`；`BeanUtils.copyProperties` 替换为 `DictItemConverter.INSTANCE.fromSaveReqToEntity`
  - [x] 4.3 `updateDictItem`：`BeanUtils.copyProperties` 替换为 `DictItemConverter.INSTANCE.fromSaveReqToEntity`
  - [x] 4.4 `getDictItem`：`BeanUtils.copyProperties` 替换为 `DictItemConverter.INSTANCE.fromEntityToResp`
  - [x] 4.5 `mapItemCodeToName`：手动 `LambdaQueryWrapper` 改为 `lambdaQuery()` 链式写法

- [x] 5. 调整 DictController（预计 10 min）
  - [x] 5.1 `addDictItem` 方法：改为接收 `dictItemAggregate.addDictItem(saveReq)` 返回的 `Long id`，不再依赖 `saveReq.getId()`

---

## 任务状态说明

| 标记 | 含义 |
|------|------|
| `- [ ]` | 未开始 |
| `- [-]` | 进行中 |
| `- [x]` | 已完成 |

---

## 验收标准对照

| 验收标准 | 对应任务 |
|---------|---------|
| DictDefConverter 添加 `componentModel = "spring"` + 新增 `fromSaveReqToEntity` | 1.1, 1.2 |
| DictItemConverter 重命名 `fromEntityListToBO` + 新增 3 个方法 | 2.1~2.5 |
| DictDefAggregate 全部 BeanUtils 替换为 Converter | 3.3, 3.4, 3.5 |
| DictDefAggregate 全部手动 QueryWrapper 改为 lambdaQuery | 3.1, 3.2, 3.6 |
| listDictDef 补充 del_flag 过滤 | 3.1 |
| DictItemAggregate 全部 BeanUtils 替换为 Converter | 4.2, 4.3, 4.4 |
| addDictItem 不再修改入参 | 4.2 |
| DictItemConverter 方法名同步更新 | 4.1 |
| Controller addDictItem 同步调整 | 5.1 |
| 所有现有接口行为保持不变 | 全部任务 |


# 字典模块代码重构 需求文档

> 编号：`0005` | 模块：`mdm` | 服务：`data-cloud-mdm` | 创建时间：2026-03-18

---

## 背景

字典模块（DictDef + DictItem）现有代码存在多处不符合公共宪法和 MDM 专属宪法的问题：
- Aggregate 层大量使用 `BeanUtils.copyProperties` 而非 MapStruct Converter
- 查询条件使用 `LambdaQueryWrapper` 手动构建而非 `lambdaQuery()` 链式写法
- 模型类存在冗余（`DictItemBO` 与 `DictItemSaveReq` 字段几乎完全重复）
- Converter 方法命名不规范（`fromEntityListToReq` 应为 `fromEntityListToBO`）
- `DictDefConverter` 未使用 `componentModel = "spring"`
- `listDictDef` 查询字典定义时未过滤 `del_flag`
- `DictItemAggregate.deleteDictItem` 使用 `removeById` 而非逻辑删除

本次重构目标是在**不改变任何 API 行为和数据库结构**的前提下，使代码符合项目规范。

---

## 目标用户

开发团队（内部代码质量改善，不影响前端/调用方）

---

## 功能描述

对字典模块的以下文件进行代码规范重构，不新增功能，不修改 API 路径、请求/响应结构、数据库表结构：

- `DictDefAggregate.java`
- `DictItemAggregate.java`
- `DictDefConverter.java`
- `DictItemConverter.java`
- `DictItemBO.java`（评估是否可合并 `DictItemSaveReq`）
- `DictItemSaveReq.java`（评估是否可合并）
- `DictController.java`（仅补全缺失的 Swagger 注解）

---

## 所属模块

- 服务：`data-cloud-mdm`（端口 `20002`）
- 模块：`data-cloud-mdm-web`
- 业务域：字典管理（DictDef + DictItem）
- 涉及文件/目录：
  - `src/main/java/com/dib/data/cloud/mdm/aggregate/DictDefAggregate.java`
  - `src/main/java/com/dib/data/cloud/mdm/aggregate/DictItemAggregate.java`
  - `src/main/java/com/dib/data/cloud/mdm/converter/DictDefConverter.java`
  - `src/main/java/com/dib/data/cloud/mdm/converter/DictItemConverter.java`
  - `src/main/java/com/dib/data/cloud/mdm/model/dict/DictItemBO.java`
  - `src/main/java/com/dib/data/cloud/mdm/model/dict/req/DictItemSaveReq.java`
  - `src/main/java/com/dib/data/cloud/mdm/controller/dict/DictController.java`

---

## 核心业务规则

### 约束（不可变更）
1. **API 兼容性**：所有接口路径、HTTP 方法、请求参数结构、响应结构保持不变
2. **数据库兼容性**：表名 `p_mdm_dict_def` / `p_mdm_dict_item` 保持不变（`p_` 为 platform 前缀，属于历史规范）
3. **删除逻辑**：保持现有删除行为不变（物理删除），不引入逻辑删除变更
4. **feign 模块**：不在本次重构范围内

### 重构规则
| 问题 | 重构方式 |
|------|---------|
| `BeanUtils.copyProperties` | 替换为 MapStruct Converter 方法 |
| 手动 `LambdaQueryWrapper` 构建 | 替换为 `lambdaQuery()` / `lambdaUpdate()` 链式写法 |
| `DictDefConverter` 缺少 `componentModel = "spring"` | 补充注解 |
| `DictItemConverter.fromEntityListToReq` 命名错误 | 重命名为 `fromEntityListToBO` |
| `DictItemBO` 与 `DictItemSaveReq` 字段重复 | 合并：`DictItemSaveReq` 继承或复用 `DictItemBO`，保持 API 不变 |
| `listDictDef` 未过滤 `del_flag` | 补充 `.eq(DictDefEntity::getDelFlag, false)` 条件 |
| `DictController` 部分接口缺少 `@ApiModelProperty` / `@ApiParam` | 补全 Swagger 注解 |
| `DictItemAggregate.addDictItem` 中 `saveReq.setId()` 直接修改入参 | 改为在 entity 上设置 id |

---

## 输入参数

> 本次为重构，不新增接口，输入参数结构保持不变。现有接口入参如下：

| 接口 | 入参类 | 关键字段 |
|------|--------|---------|
| `POST /dict/list` | `DictDefQuery` | `dictCodeList` |
| `POST /dict/definition/page` | `DictDefQuery` | `pageNum`, `pageSize`, `dictCodeOrName`, `dictType` |
| `POST /dict/definition/add` | `DictDefSaveReq` | `dictCode`, `dictName`, `dictType`, `dictDesc`, `account`, `dictItemList` |
| `POST /dict/definition/update` | `DictDefSaveReq` | 同上 + `id` |
| `POST /dict/definition/delete` | `List<String>` | dictCode 列表 |
| `GET /dict/definition/get/{id}` | PathVariable `id` | - |
| `POST /dict/item/list` | `DictItemQuery` | `dictCode`, `dictCodeList`, `itemCode`, `itemName`, `activeFlag` 等 |
| `POST /dict/item/add` | `DictItemSaveReq` | `dictCode`, `itemCode`, `itemName` 等 |
| `POST /dict/item/update` | `DictItemSaveReq` | 同上 + `id` |
| `POST /dict/item/delete/{id}` | PathVariable `id` | - |
| `GET /dict/item/get/{id}` | PathVariable `id` | - |
| `POST /dict/item/map` | `@RequestParam dictCode` | - |

---

## 输出结果

> 保持不变，现有接口响应如下：

| 接口 | 响应类 | 说明 |
|------|--------|------|
| `/dict/list` | `List<DictDefDetailResp>` | 字典定义+字典项列表 |
| `/dict/definition/page` | `PageResp<DictDefInfoResp>` | 分页 |
| `/dict/definition/add` | `Integer`（新增 ID） | - |
| `/dict/definition/update` | `Integer`（更新 ID） | - |
| `/dict/definition/delete` | `Integer`（固定 0） | - |
| `/dict/definition/get/{id}` | `DictDefInfoResp` | - |
| `/dict/item/list` | `List<DictItemBO>` | - |
| `/dict/item/add` | `Long`（ID） | - |
| `/dict/item/update` | `Long`（ID） | - |
| `/dict/item/delete/{id}` | `Integer`（ID） | - |
| `/dict/item/get/{id}` | `DictItemResp` | - |
| `/dict/item/map` | `Map<String, String>` | itemCode → itemName |

---

## 用户故事

- 作为开发者，我希望字典模块代码符合项目宪法规范，以便后续维护和扩展更加一致
- 作为开发者，我希望消除冗余模型类，以便减少维护成本

---

## 验收标准

- [ ] `DictDefAggregate` 中所有 `BeanUtils.copyProperties` 替换为 Converter 方法
- [ ] `DictItemAggregate` 中所有 `BeanUtils.copyProperties` 替换为 Converter 方法
- [ ] `DictDefAggregate` 中手动 `LambdaQueryWrapper` 替换为 `lambdaQuery()` 链式写法
- [ ] `DictDefConverter` 添加 `componentModel = "spring"`
- [ ] `DictItemConverter.fromEntityListToReq` 重命名为 `fromEntityListToBO`，调用方同步更新
- [ ] `DictItemConverter` 补充 `fromEntityToBO`、`fromEntityToResp`、`fromSaveReqToEntity` 等必要方法
- [ ] `DictDefConverter` 补充 `fromSaveReqToEntity`、`fromEntityToResp` 等必要方法
- [ ] `listDictDef` 查询字典定义时补充 `del_flag = false` 过滤条件
- [ ] `DictItemAggregate.addDictItem` 不再直接修改入参对象
- [ ] 所有现有接口行为（路径、请求结构、响应结构）保持不变
- [ ] 编译通过，无新增警告

---

## 边界条件

| 场景 | 处理方式 |
|------|---------|
| `DictItemSaveReq` 与 `DictItemBO` 合并时 | 保持两个类存在（`DictItemSaveReq` 字段与现有一致），仅通过 Converter 统一转换，不合并为同一个类（避免破坏 API） |
| `DictDefConverter` 改为 Spring 注入后 | `DictDefConverter.INSTANCE` 静态引用需同步改为 `@Autowired` 注入 |
| Converter 方法重命名后 | 所有调用方（Aggregate）必须同步更新 |

---

## 非功能需求

- **可维护性**：重构后代码必须符合公共宪法第五、九、十条规范
- **安全性**：不引入任何行为变更，不影响现有数据

---

**状态**：已确认

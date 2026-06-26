# 指标结果字段映射管理功能 需求文档

> 编号：`0020` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-04-22

---

## 背景

当前系统已经存在 `com_data_index_value_field` 表及其聚合逻辑，作为“指标结果表字段”与“维度”的映射配置来源，被 `ComDataIndexValueFieldAggregate` 用于：

- 生成指标结果维度字段列表
- 根据 `dimId` 或 `indexValueFieldName` 查询映射关系
- 在指标结果展示时补充维度值名称
- 在指标依赖字段解析时完成维度字段映射校验

但目前该表缺少独立的管理接口，导致这类基础配置无法通过标准后端管理能力维护，影响指标结果字段映射的新增、修改、查询和清理。

## 目标用户

- 指标配置管理员：维护指标结果表维度字段映射
- 开发/实施人员：排查指标结果字段缺失、维度映射错误等问题

## 功能描述

在现有 `index` 业务域中，为 `com_data_index_value_field` 新增管理功能，并放到独立的 `index_value_field` controller 中，提供针对映射配置的标准管理能力。

管理对象为 `ComDataIndexValueFieldEntity`，核心字段包括：

- `indexValueFieldName`：指标结果表字段名
- `dimId`：维度元数据主键
- `dimName`：维度名称
- `dimLevel`：维度层级

该功能面向配置维护，不改变 `ComDataIndexValueFieldAggregate` 现有的消费方式，但要保证新增接口维护后的数据能够被现有聚合逻辑直接读取和使用。

本次需求明确需要提供完整 CRUD 能力：

- `add`：新增映射配置
- `edit`：修改映射配置
- `delete`：逻辑删除映射配置
- `get`：查询单条映射配置详情
- `page`：分页查询映射配置

## 所属模块

- 服务：`dib-agent-service-data`（端口 `30003`）
- context-path：`/api/data`
- 业务域：`index`
- 涉及文件/目录：
  - `com.dib.agent.data.web.controller.index`
  - `com.dib.agent.data.web.aggregate.index`
  - `com.dib.agent.data.web.entity.index`
  - `com.dib.agent.data.web.service.index`
  - `com.dib.agent.data.web.mapper.index`
  - `com.dib.agent.data.web.model.index`

## 核心业务规则

1. 管理对象为 `com_data_index_value_field` 表中的映射配置。
2. 一条映射记录表示一个“指标结果字段”与一个“维度”的对应关系。
3. 现有聚合逻辑默认按 `del_flag = 0` 查询，因此管理接口必须遵循逻辑删除规范，不能物理删除。
4. 映射配置变更后，应能立即被 `ComDataIndexValueFieldAggregate` 的查询逻辑使用。
5. `dimId` 是当前聚合逻辑的关键关联字段，新增和编辑时必须校验其为真实存在的维度。
6. `indexValueFieldName` 是指标结果表中的标准字段名，应保证命名有效且可稳定用于查询与展示。
7. `indexValueFieldName` 必须在有效数据范围内唯一，即基于 `delFlag = 0` 的记录做唯一性校验，避免同一结果字段名对应多条有效映射。
8. `dimId` 单字段不要求唯一，但 `dimId + dimLevel` 组合必须在有效数据范围内唯一，即基于 `delFlag = 0` 的记录做联合唯一校验，避免同一维度同一层级出现重复配置。
9. 管理接口需覆盖完整 CRUD，便于配置排查和日常维护。

## 输入参数

| 参数名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| id | Long | 路径/请求体 | 映射配置主键 |
| indexValueFieldName | String | 请求体 | 指标结果表字段名 |
| dimId | Long | 请求体/查询 | 维度元数据主键 |
| dimName | String | 请求体/查询 | 维度名称 |
| dimLevel | Integer | 请求体/查询 | 维度层级 |
| pageNum | Integer | 请求体 | 分页页码 |
| pageSize | Integer | 请求体 | 分页大小 |

## 输出结果

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Long | 映射配置主键 |
| indexValueFieldName | String | 指标结果表字段名 |
| dimId | Long | 维度元数据主键 |
| dimName | String | 维度名称 |
| dimLevel | Integer | 维度层级 |
| delFlag | Boolean | 逻辑删除标识 |
| addUserId | String | 创建人账号 |
| addUserName | String | 创建人姓名 |
| addTime | Date | 创建时间 |
| updateUserId | String | 更新人账号 |
| updateUserName | String | 更新人姓名 |
| updateTime | Date | 更新时间 |

## 用户故事

- 作为指标配置管理员，我希望分页查询已有的指标结果字段映射，以便排查某个维度是否已正确配置。
- 作为指标配置管理员，我希望新增一条字段映射，以便让指标结果表能够识别新的维度字段。
- 作为指标配置管理员，我希望修改已有映射配置，以便修正错误的字段名、维度名称或维度层级。
- 作为指标配置管理员，我希望删除失效映射，以便避免错误配置继续影响指标结果展示和校验。

## 验收标准

- [ ] 提供 `com_data_index_value_field` 的独立管理 controller，归属 `index` 业务域。
- [ ] 支持完整 CRUD：`add / edit / delete / get / page`。
- [ ] 支持查询映射配置列表，能够按管理场景返回标准配置数据。
- [ ] 支持新增映射配置，新增后可被现有 `ComDataIndexValueFieldAggregate` 查询到。
- [ ] 支持编辑映射配置，编辑后现有聚合逻辑读取到的是最新数据。
- [ ] 支持删除映射配置，并遵循逻辑删除规范。
- [ ] 新增和编辑时校验 `dimId` 对应维度真实存在。
- [ ] 新增和编辑时校验 `indexValueFieldName` 在 `delFlag = 0` 的有效记录中唯一。
- [ ] 新增和编辑时校验 `dimId + dimLevel` 在 `delFlag = 0` 的有效记录中联合唯一。
- [ ] 所有接口统一使用 `GeneralResult<T>` 响应。
- [ ] 接口与代码结构符合公共宪法和 `data` 模块宪法要求。

## 边界条件

| 场景 | 处理方式 |
|------|---------|
| 新增时字段名为空 | 返回明确的参数校验错误 |
| 新增时 `dimId` 为空 | 返回明确的参数校验错误 |
| 新增/编辑时 `dimId` 不存在 | 返回明确的业务校验错误 |
| 新增/编辑时 `indexValueFieldName` 重复 | 返回明确的业务校验错误 |
| 新增/编辑时 `dimId + dimLevel` 组合重复 | 返回明确的业务校验错误 |
| 编辑时记录不存在 | 返回明确的业务异常 |
| 删除时记录不存在 | 按系统原有风格返回明确的业务异常 |
| 查询结果为空 | 返回空列表或空分页，不报错 |
| 映射被逻辑删除 | 不应被现有聚合逻辑当作有效配置读取 |

## 非功能需求

- **性能**：管理接口以配置维护为主，单次分页查询应满足后台管理场景的常规响应要求。
- **可维护性**：沿用现有 `index` 域命名、分层和返回结构，不引入与现有风格冲突的新模式。
- **一致性**：新增接口不得破坏 `ComDataIndexValueFieldAggregate` 当前对该表的读取方式。
- **安全性**：遵循服务现有认证鉴权与操作日志规范。

## 待确认问题

---

**状态**：草稿

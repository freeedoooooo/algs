# 指标结果字段映射管理功能 技术设计

> 编号：`0020` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-04-22
> 关联需求：`requirements.md`

---

## 概述

在 `index` 业务域内补齐 `com_data_index_value_field` 的完整 CRUD 管理链路，新增独立的 `index_value_field` 管理 controller，并复用现有 `entity / mapper / service / aggregate` 结构，保证配置维护后的数据可被 `ComDataIndexValueFieldAggregate` 现有读取逻辑直接消费。

---

## 架构设计

### 整体架构

```
ComDataIndexValueFieldController
    -> ComDataIndexValueFieldAggregate
        -> IComDataIndexValueFieldService
            -> ComDataIndexValueFieldMapper
                -> com_data_index_value_field

ComDataIndexValueFieldAggregate
    -> ComDataAggregate.dimValueList(DimValueReq.of(dimId, null))
        -> 维度元数据/维度值查询
```

### 涉及文件

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/controller/index/ComDataIndexValueFieldController.java` | 指标结果字段映射管理 controller |
| 修改 | `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/aggregate/index/ComDataIndexValueFieldAggregate.java` | 补充 CRUD、校验与分页查询能力 |
| 新增 | `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldAddReq.java` | 新增请求对象 |
| 新增 | `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldEditReq.java` | 编辑请求对象 |
| 新增 | `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldQuery.java` | 分页查询请求对象 |
| 新增 | `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/resp/DataIndexValueFieldResp.java` | 管理场景响应对象 |
| 新增 | `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/converter/index/ComDataIndexValueFieldConverter.java` | 请求/实体/响应转换 |

> 现有 `ComDataIndexValueFieldEntity`、`ComDataIndexValueFieldMapper`、`IComDataIndexValueFieldService`、`ComDataIndexValueFieldServiceImpl` 保持复用，不新增数据库表，不新增 SQL 脚本。

---

## 数据模型

### 输入

| 参数/字段 | 类型 | 来源 | 说明 |
|----------|------|------|------|
| id | Long | `edit/get/delete` | 主键 |
| indexValueFieldName | String | `add/edit/query` | 指标结果字段名 |
| dimId | Long | `add/edit/query` | 维度主键 |
| dimName | String | `add/edit/query` | 维度名称 |
| dimLevel | Integer | `add/edit/query` | 维度层级 |
| pageNum | Integer | `page` | 页码 |
| pageSize | Integer | `page` | 页大小 |

### 输出

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Long | 主键 |
| indexValueFieldName | String | 指标结果字段名 |
| dimId | Long | 维度主键 |
| dimName | String | 维度名称 |
| dimLevel | Integer | 维度层级 |
| delFlag | Boolean | 逻辑删除标识 |
| addUserId | String | 创建人账号 |
| addUserName | String | 创建人姓名 |
| addTime | Date | 创建时间 |
| updateUserId | String | 更新人账号 |
| updateUserName | String | 更新人姓名 |
| updateTime | Date | 更新时间 |

### 涉及数据库表

| 表名 | 操作 | 说明 |
|------|------|------|
| `com_data_index_value_field` | `SELECT/INSERT/UPDATE` | 指标结果字段映射主表 |
| 维度元数据来源 | `SELECT` | 通过 `ComDataAggregate.dimValueList` 间接校验 `dimId` 是否真实存在 |

---

## 接口设计

### API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/comDataIndexValueField/add` | 新增映射配置 |
| POST | `/comDataIndexValueField/edit` | 编辑映射配置 |
| GET | `/comDataIndexValueField/get` | 查询单条详情 |
| POST | `/comDataIndexValueField/page` | 分页查询 |
| DELETE | `/comDataIndexValueField/delete` | 删除映射配置 |

### 请求/响应示例

```json
// add/edit 请求
{
  "id": 189000000000000001,
  "indexValueFieldName": "dim_company_code",
  "dimId": 10001,
  "dimName": "公司",
  "dimLevel": 1
}
```

```json
// get/page 响应 data 示例
{
  "id": 189000000000000001,
  "indexValueFieldName": "dim_company_code",
  "dimId": 10001,
  "dimName": "公司",
  "dimLevel": 1,
  "delFlag": false,
  "addUserId": "admin",
  "addUserName": "管理员",
  "addTime": "2026-04-22 15:00:00",
  "updateUserId": "admin",
  "updateUserName": "管理员",
  "updateTime": "2026-04-22 15:30:00"
}
```

```json
// 通用响应
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

---

## 核心逻辑设计

### 主流程

#### 1. 新增

```
1. 校验必填参数：indexValueFieldName、dimId、dimName、dimLevel
2. 调用 ComDataAggregate.dimValueList(DimValueReq.of(dimId, null)) 校验 dimId 对应维度真实存在
3. 查询有效记录中是否存在同名 indexValueFieldName
4. 查询有效记录中是否存在相同 dimId + dimLevel 组合
5. 使用 converter/request 构建实体，补齐 id、addUser、delFlag
6. 保存到 com_data_index_value_field
```

#### 2. 编辑

```
1. 根据 id 查询有效记录，不存在则抛业务异常
2. 校验必填参数
3. 校验 dimId 对应维度真实存在
4. 排除当前 id 后，校验有效记录中 indexValueFieldName 唯一
5. 排除当前 id 后，校验有效记录中 dimId + dimLevel 联合唯一
6. 更新字段并设置 updateUser
7. updateById 持久化
```

#### 3. 查询详情

```
1. 根据 id 查询 delFlag = 0 的记录
2. 不存在则抛业务异常
3. 转为 DataIndexValueFieldResp 返回
```

#### 4. 分页

```
1. 基于 query 构造 lambdaQuery
2. 统一过滤 delFlag = 0
3. 支持按 indexValueFieldName、dimId、dimName、dimLevel 条件查询
4. 默认按 updateTime desc 排序
5. 返回 PageResp<DataIndexValueFieldResp>
```

#### 5. 删除

```
1. 根据 id 查询 delFlag = 0 的记录
2. 若不存在，按系统原风格抛业务异常
3. 设置 delFlag = true，补齐 updateUser
4. 逻辑删除
```

### 关键技术点

1. 真实维度校验
   复用现有 `ComDataAggregate.dimValueList(DimValueReq.of(dimId, null))`。
   该方法内部会先通过 `metadataInfoService.getTableMetadata(dimId)` 获取维度元数据，若维度不存在会抛出业务异常，因此可直接作为“真实存在”校验入口。

2. 唯一性校验范围
   所有唯一性校验都仅针对 `delFlag = 0` 的有效记录。
   具体包括：
   - `indexValueFieldName` 唯一
   - `dimId + dimLevel` 联合唯一

3. 与现有读取逻辑兼容
   现有 `ComDataIndexValueFieldAggregate` 已基于 `delFlag = 0` 查询并构建：
   - `dimId -> entity`
   - `indexValueFieldName -> entity`
   因此本次管理功能不修改其下游消费逻辑，只保证新增/修改/删除符合其读模型预期。

4. 返回模型与 `BaseEntity` 对齐
   管理响应对象包含业务字段和 `BaseEntity` 常用审计字段，避免再次出现“返回字段与基类不一致”的问题。

---

## 数据库变更（如有）

无数据库结构变更。

本次仅对既有表 `com_data_index_value_field` 增加管理接口，不新增表、不改字段、不新增迁移脚本。

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| 新增/编辑时 `indexValueFieldName` 为空 | 参数校验失败 | `指标结果字段名不能为空` |
| 新增/编辑时 `dimId` 为空 | 参数校验失败 | `维度ID不能为空` |
| 新增/编辑时 `dimLevel` 为空 | 参数校验失败 | `维度层级不能为空` |
| `dimId` 对应维度不存在 | 业务异常 | `维度不存在` 或底层统一异常信息 |
| 新增时 `indexValueFieldName` 重复 | 业务异常 | `指标结果字段名已存在` |
| 新增时 `dimId + dimLevel` 重复 | 业务异常 | `该维度与层级组合已存在` |
| 编辑时排除自身后仍重复 | 业务异常 | 同上 |
| 查询详情时记录不存在 | 业务异常 | `指标结果字段映射不存在` |
| 删除时记录不存在 | 业务异常 | `指标结果字段映射不存在` |

---

## 影响范围

### 新增文件

- `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/controller/index/ComDataIndexValueFieldController.java` - 暴露管理接口
- `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldAddReq.java` - 新增请求对象
- `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldEditReq.java` - 编辑请求对象
- `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldQuery.java` - 分页查询请求对象
- `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/resp/DataIndexValueFieldResp.java` - 管理响应对象
- `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/converter/index/ComDataIndexValueFieldConverter.java` - 对象转换

### 修改文件

- `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/aggregate/index/ComDataIndexValueFieldAggregate.java` - 增加 CRUD、详情、分页与校验逻辑

### 无需修改

- `ComDataIndexValueFieldEntity`、`ComDataIndexValueFieldMapper`、`IComDataIndexValueFieldService`、`ComDataIndexValueFieldServiceImpl` 现有定义可直接复用
- `ComDataIndexInfoAggregate`、`IndexValueCacheUtil`、指标任务执行等现有读取逻辑无需改动

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 维度存在性校验依赖 `dimValueList`，若某些维度无有效值但元数据存在，可能出现误判 | 新增/编辑被误拦截 | 实现时优先确认 `dimValueList` 对 `dimId` 的失败条件；必要时改为直接校验维度元数据是否存在 |
| 唯一性校验只在应用层做，若并发新增同一配置可能产生竞态 | 低概率重复数据 | 在 aggregate 中先查后写；若后续发现并发风险，再补数据库唯一索引 |
| 删除采用逻辑删除，历史脏数据可能影响唯一性判断 | 误报重复或放过重复 | 所有唯一性查询显式限定 `delFlag = 0` |

---

**状态**：草稿

# 数据资讯指标收藏功能 需求文档

> 编号：`0008` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-03-26

---

## 背景

用户在浏览数据资讯指标（`com_di_index`）时，需要能够收藏感兴趣的指标，方便后续快速访问。

## 目标用户

- **前端用户**：对指标进行收藏/取消收藏，查看自己的收藏列表

## 功能描述

新增指标收藏功能，支持用户收藏/取消收藏指标，并查询自己的收藏列表。收藏列表关联 `com_di_index` 表，在内存中按指标名称排序后返回。

## 所属模块

- 服务：`dib-agent-service-data`（端口 `30003`）
- context-path：`/api/data`
- 业务域：`di`
- 涉及目录：
  - `com.dib.agent.data.web.entity.di`
  - `com.dib.agent.data.web.mapper.di`
  - `com.dib.agent.data.web.service.di`
  - `com.dib.agent.data.web.model.di`（resp）
  - `com.dib.agent.data.web.aggregate.di`
  - `com.dib.agent.data.web.controller.di`

---

## 数据库表设计

### 表名
`com_di_index_favorite`

### 字段清单

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | BIGINT | ✅ | 主键 |
| index_id | BIGINT | ✅ | 指标 ID（关联 com_di_index.id） |
| user_id | VARCHAR(50) | ✅ | 用户账号 |
| del_flag | TINYINT(1) | ✅ | 删除标识（0-正常，1-已删除） |
| add_user_id | VARCHAR(50) | ✅ | 创建人账号 |
| add_user_name | VARCHAR(100) | ✅ | 创建人姓名 |
| add_time | DATETIME | ✅ | 创建时间（即收藏时间） |
| update_user_id | VARCHAR(50) | ✅ | 更新人账号 |
| update_user_name | VARCHAR(100) | ✅ | 更新人姓名 |
| update_time | DATETIME | ✅ | 更新时间 |

---

## 接口清单

### 1. 收藏指标

- **方法**：`POST /di/index-favorite/add/{indexId}`
- **说明**：当前用户收藏指定指标。若已收藏（`del_flag=0`）则幂等忽略，不报错

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| indexId | Long | ✅ | 指标 ID |

---

### 2. 取消收藏

- **方法**：`POST /di/index-favorite/cancel/{indexId}`
- **说明**：当前用户取消收藏指定指标，执行逻辑删除（`del_flag=1`）。若未收藏则幂等忽略

**路径参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| indexId | Long | ✅ | 指标 ID |

---

### 3. 查询我的收藏列表

- **方法**：`GET /di/index-favorite/my-list`
- **说明**：查询当前用户所有有效收藏（`del_flag=0`），关联 `com_di_index` 获取指标信息，在内存中按 `indexName` 升序排序后返回

**响应字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| indexId | Long | 指标 ID |
| indexName | String | 指标名称 |
| addTime | LocalDateTime | 收藏时间 |

---

## 核心业务规则

1. **用户标识**：从 `ServletRequestContext` 获取当前用户的 `userId`（即 `addUserId`）
2. **收藏幂等**：收藏时若该用户对该指标已有 `del_flag=0` 的记录，直接返回成功，不重复插入
3. **取消收藏**：逻辑删除（`del_flag=1`），若记录不存在或已取消则幂等忽略
4. **收藏列表排序**：先查收藏记录，再批量查 `com_di_index`，在内存中按 `indexName` 升序排序
5. **数据一致性**：收藏列表只返回 `com_di_index` 中仍存在的指标

---

## 用户故事

- 作为用户，我希望能收藏感兴趣的指标，以便快速找到常用指标
- 作为用户，我希望能取消收藏，以便管理我的收藏列表
- 作为用户，我希望查看我的收藏列表，并按指标名称排序展示

---

## 验收标准

- [ ] 收藏接口：同一用户对同一指标重复收藏，幂等处理不报错
- [ ] 取消收藏接口：执行逻辑删除，未收藏时幂等忽略
- [ ] 收藏列表：返回当前用户有效收藏，关联指标名称，按 indexName 升序排序
- [ ] 用户标识从 ServletRequestContext 获取，不由前端传入
- [ ] 所有接口响应格式符合 `GeneralResult<T>` 规范
- [ ] 代码符合公共宪法和 data 服务宪法规范

---

## 边界条件

| 场景 | 处理方式 |
|------|---------|
| 重复收藏同一指标 | 幂等忽略，返回成功 |
| 取消未收藏的指标 | 幂等忽略，返回成功 |
| 收藏列表中指标已被删除 | 过滤掉，不返回 |
| 收藏列表为空 | 返回空列表，不报错 |

---

## 非功能需求

- **性能**：`user_id` + `index_id` 建联合索引，支持快速查重和查询
- **可维护性**：遵循 data 服务宪法规范，分层清晰

---

**状态**：草稿

# 数据资讯快讯 需求文档

> 编号：`0007` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-03-26

---

## 背景

数据服务需要向前端展示数据资讯快讯信息，包括新库、新表、新报告、新功能等主题的动态资讯。后台管理人员手动维护快讯内容，前端通过接口查询轮播展示或按主题分类展示。

## 目标用户

- **后台管理员**：录入、编辑、删除快讯内容
- **前端/客户端**：查询轮播资讯、按主题分类浏览快讯

## 功能描述

新增数据资讯快讯管理功能，支持后台对快讯进行 CRUD 管理，并提供前端查询接口（轮播资讯、按主题分类查询）。

## 所属模块

- 服务：`dib-agent-service-data`（端口 `30003`）
- context-path：`/api/data`
- 业务域：`di`
- 涉及目录：
  - `com.dib.agent.data.web.entity.di`
  - `com.dib.agent.data.web.mapper.di`
  - `com.dib.agent.data.web.service.di`
  - `com.dib.agent.data.web.model.di`（req / resp / query）
  - `com.dib.agent.data.web.converter.di`
  - `com.dib.agent.data.web.aggregate.di`
  - `com.dib.agent.data.web.controller.di`
  - `com.dib.agent.data.web.config.enums`（主题标签枚举）

---

## 数据库表设计

### 表名
`com_di_news_flash`

### 字段清单

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | BIGINT | ✅ | 主键 |
| news_topic_type | VARCHAR(50) | ✅ | 主题标签（枚举：NEW_DB/新库、NEW_TABLE/新表、NEW_REPORT/新报告、NEW_FUNC/新功能），Java 类型：`String` |
| title | VARCHAR(200) | ✅ | 标题 |
| start_date | DATE | ✅ | 开始日期 |
| end_date | DATE | ✅ | 结束日期 |
| important_flag | TINYINT(1) | ✅ | 是否为重大资讯（0-否，1-是） |
| link_url | VARCHAR(500) | ❌ | 跳转链接 |
| description | TEXT | ❌ | 描述 |
| enable_flag | TINYINT(1) | ✅ | 激活状态（0-禁用，1-启用） |
| del_flag | TINYINT(1) | ✅ | 删除标识（0-正常，1-已删除） |
| add_user_id | VARCHAR(50) | ✅ | 创建人账号 |
| add_user_name | VARCHAR(100) | ✅ | 创建人姓名 |
| add_time | DATETIME | ✅ | 创建时间 |
| update_user_id | VARCHAR(50) | ✅ | 更新人账号 |
| update_user_name | VARCHAR(100) | ✅ | 更新人姓名 |
| update_time | DATETIME | ✅ | 更新时间 |

---

## 接口清单

### 1. 分页查询（后台管理）

- **方法**：`POST /di/news-flash/page`
- **说明**：支持多条件筛选，返回分页结果

**查询条件**：

| 参数名 | 类型 | 说明 |
|--------|------|------|
| pageNum | Integer | 页码（从 1 开始） |
| pageSize | Integer | 每页条数 |
| newsTopicType | String | 主题标签（可选） |
| startDateBegin | Date | 开始日期范围-起（可选） |
| startDateEnd | Date | 开始日期范围-止（可选） |
| title | String | 标题关键词（可选，模糊匹配） |

**响应字段**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Long | 主键 |
| newsTopicType | String | 主题标签枚举值 |
| title | String | 标题 |
| startDate | Date | 开始日期 |
| endDate | Date | 结束日期 |
| importantFlag | Boolean | 是否重大资讯 |
| linkUrl | String | 跳转链接 |
| description | String | 描述 |
| enableFlag | Boolean | 激活状态 |
| addTime | String | 创建时间 |
| updateTime | String | 更新时间 |

---

### 2. 新增

- **方法**：`POST /di/news-flash/add`

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| newsTopicType | String | ✅ | 主题标签枚举值 |
| title | String | ✅ | 标题 |
| startDate | Date | ✅ | 开始日期 |
| endDate | Date | ✅ | 结束日期 |
| importantFlag | Boolean | ✅ | 是否重大资讯 |
| linkUrl | String | ❌ | 跳转链接 |
| description | String | ❌ | 描述 |

---

### 3. 编辑

- **方法**：`POST /di/news-flash/edit`

**请求参数**：同新增，额外增加 `id`（必填）

---

### 4. 删除

- **方法**：`POST /di/news-flash/delete/{id}`

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Long | ✅ | 主键（Path Variable） |

---

### 5. 激活

- **方法**：`POST /di/news-flash/enable/{id}`
- **说明**：将指定快讯的 `enable_flag` 设为 `true`（启用）

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Long | ✅ | 主键（Path Variable） |

---

### 6. 禁用

- **方法**：`POST /di/news-flash/disable/{id}`
- **说明**：将指定快讯的 `enable_flag` 设为 `false`（禁用）

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Long | ✅ | 主键（Path Variable） |

---

### 7. 查询轮播资讯

- **方法**：`GET /di/news-flash/carousel`
- **说明**：查询当前有效的快讯（`start_date <= 今天 < end_date`，`enable_flag = 1`，`del_flag = 0`），按 `start_date` 倒序排列

**响应字段**：同分页查询的响应字段

---

### 8. 按主题标签查询

- **方法**：`GET /di/news-flash/list-by-topic`
- **说明**：指定主题标签，查询该标签下所有激活的快讯(`enable_flag = 1`，`del_flag = 0`)，按 `start_date` 倒序排列

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| newsTopicType | String | ✅ | 主题标签枚举值 |

**响应字段**：同分页查询的响应字段

---

## 核心业务规则

1. **轮播资讯过滤条件**：`start_date <= 当天日期 < end_date`，且 `enable_flag = 1`，`del_flag = 0`
2. **主题标签枚举**：`NEW_DB`（新库）、`NEW_TABLE`（新表）、`NEW_REPORT`（新报告）、`NEW_FUNC`（新功能）
3. **删除方式**：逻辑删除，设置 `del_flag = 1`
4. **激活状态**：新增时默认 `enable_flag = 1`（启用）
5. **排序**：轮播查询和按主题查询均按 `start_date` 倒序排列

---

## 用户故事

- 作为后台管理员，我希望能新增/编辑/删除快讯，以便维护最新的数据资讯内容
- 作为后台管理员，我希望能激活或禁用某条快讯，以便灵活控制快讯的展示状态而无需删除数据
- 作为后台管理员，我希望能按主题标签、日期范围、标题关键词筛选快讯，以便快速定位记录
- 作为前端页面，我希望能查询当前有效的轮播资讯，以便在首页展示动态快讯
- 作为前端页面，我希望能按主题标签查询快讯列表，以便分类展示不同类型的资讯

---

## 验收标准

- [ ] 分页查询支持主题标签、日期范围（开始日期）、标题关键词三个维度筛选
- [ ] 新增接口校验必填字段，`end_date >= start_date`
- [ ] 编辑接口校验 id 存在且未删除
- [ ] 删除接口执行逻辑删除
- [ ] 激活接口（`POST /di/news-flash/enable/{id}`）将 `enable_flag` 设为 `true`，id 不存在时返回业务异常
- [ ] 禁用接口（`POST /di/news-flash/disable/{id}`）将 `enable_flag` 设为 `false`，id 不存在时返回业务异常
- [ ] 轮播接口返回 `start_date <= 今天 < end_date` 且已启用的记录，按 `start_date` 倒序
- [ ] 按主题标签查询接口返回指定标签下已启用的记录，按 `start_date` 倒序
- [ ] 所有接口响应格式符合 `GeneralResult<T>` 规范
- [ ] 代码符合公共宪法和 data 服务宪法规范

---

## 边界条件

| 场景 | 处理方式 |
|------|---------|
| `end_date < start_date` | 新增/编辑时返回业务异常提示 |
| 轮播查询无有效数据 | 返回空列表，不报错 |
| 按主题查询传入非法枚举值 | 返回业务异常提示 |
| 删除不存在的记录 | 返回业务异常提示 |
| 编辑不存在的记录 | 返回业务异常提示 |
| enable/disable 操作 id 不存在或已删除 | 返回业务异常提示"快讯记录不存在" |

---

## 非功能需求

- **性能**：轮播查询和按主题查询为高频接口，需确保有索引支撑（`start_date`、`end_date`、`news_topic_type`、`enable_flag`）
- **可维护性**：遵循 data 服务宪法规范，分层清晰

---

**状态**：草稿

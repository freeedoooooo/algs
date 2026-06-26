# 数据资讯快讯 任务清单

> 编号：`0007` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-03-26
> 关联文档：`requirements.md` | `design.md`

---

## 工时评估

| 任务 | 预计工时 |
|------|---------|
| 1. 数据库脚本 | 10 min |
| 2. 枚举 + 实体 + Mapper + Service | 20 min |
| 3. Model 层（Req / Query / Resp） | 15 min |
| 4. Converter | 10 min |
| 5. Aggregate | 15 min |
| 6. Controller | 15 min |
| 合计 | 85 min |

---

## 任务列表

- [x] 1. 数据库脚本（10 min）
  - [x] 1.1 创建 `docs-c1/00 AI-DOCS/specs/0007-data-di-news-flash/scripts/V0007__create_com_di_news_flash.sql`，包含建表 DDL 和索引

- [x] 2. 基础层：枚举 / 实体 / Mapper / Service（20 min）
  - [x] 2.1 创建 `config/enums/di/String.java`
  - [x] 2.2 创建 `entity/di/ComDiNewsFlashEntity.java`（继承 BaseEntity，LocalDate 日期字段加 `@DateTimeFormat` + `@JsonFormat`）
  - [x] 2.3 创建 `mapper/di/ComDiNewsFlashMapper.java`（继承 BaseMapper）
  - [x] 2.4 创建 `service/di/IComDiNewsFlashService.java` 和 `service/di/impl/ComDiNewsFlashServiceImpl.java`

- [x] 3. Model 层（15 min）
  - [x] 3.1 创建 `model/di/req/DiNewsFlashAddReq.java`（必填字段加 `@NotNull` / `@NotBlank` 校验）
  - [x] 3.2 创建 `model/di/req/DiNewsFlashEditReq.java`（继承或复用 AddReq，额外加 `id` 字段）
  - [x] 3.3 创建 `model/di/query/DiNewsFlashQuery.java`（newsTopicType、startDateBegin、startDateEnd、keyword、pageNum、pageSize）
  - [x] 3.4 创建 `model/di/resp/DiNewsFlashResp.java`

- [x] 4. Converter（10 min）
  - [x] 4.1 创建 `converter/di/DiNewsFlashConverter.java`（fromAddReq、fromEditReq、toResp、toRespList，新增时 enableFlag=true、delFlag=false）

- [x] 5. Aggregate（15 min）
  - [x] 5.1 创建 `aggregate/di/ComDiNewsFlashAggregate.java`，实现以下方法：
    - `page(DiNewsFlashQuery query)` — 多条件分页查询
    - `add(DiNewsFlashAddReq req, AddingUser addingUser)` — 日期校验 + 保存
    - `edit(DiNewsFlashEditReq req, UpdatingUser updatingUser)` — 存在校验 + 日期校验 + 更新
    - `delete(Long id)` — 存在校验 + 逻辑删除
  - [x] 5.2 在 `ComDiNewsFlashAggregate.java` 中新增 `enable(Long id)` 方法 — 存在校验 + 设置 `enableFlag=true` + 更新操作人/时间
  - [x] 5.3 在 `ComDiNewsFlashAggregate.java` 中新增 `disable(Long id)` 方法 — 存在校验 + 设置 `enableFlag=false` + 更新操作人/时间

- [x] 6. Controller（15 min）
  - [x] 6.1 创建 `controller/di/ComDiNewsFlashController.java`，实现 6 个接口：
    - `POST /di/news-flash/page` → `page()`，调用 Aggregate
    - `POST /di/news-flash/add` → `add()`，调用 Aggregate
    - `POST /di/news-flash/edit` → `edit()`，调用 Aggregate
    - `POST /di/news-flash/delete/{id}` → `delete()`，调用 Aggregate
    - `GET /di/news-flash/carousel` → `carousel()`，直接调用 Service
    - `GET /di/news-flash/list-by-topic/{newsTopicType}` → `listByTopic()`，直接调用 Service
  - [x] 6.2 在 `ComDiNewsFlashController.java` 中新增 `POST /di/news-flash/enable/{id}` → `enable()`，调用 Aggregate
  - [x] 6.3 在 `ComDiNewsFlashController.java` 中新增 `POST /di/news-flash/disable/{id}` → `disable()`，调用 Aggregate

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
| 分页查询支持主题标签、日期范围、标题关键词筛选 | 5.1、6.1 |
| 新增接口校验必填字段，end_date >= start_date | 3.1、5.1 |
| 编辑接口校验 id 存在且未删除 | 5.1 |
| 删除接口执行逻辑删除 | 5.1 |
| 激活接口将 enable_flag 设为 true，id 不存在时返回业务异常 | 5.2、6.2 |
| 禁用接口将 enable_flag 设为 false，id 不存在时返回业务异常 | 5.3、6.3 |
| 轮播接口返回 start_date <= 今天 < end_date 且已启用记录，按 start_date 倒序 | 6.1 |
| 按主题标签查询接口返回指定标签下已启用记录，按 start_date 倒序 | 6.1 |
| 所有接口响应格式符合 GeneralResult<T> 规范 | 6.1、6.2、6.3 |
| 代码符合公共宪法和 data 服务宪法规范 | 全部任务 |

---

## 进度记录

| 时间 | 完成任务 | 备注 |
|------|---------|------|
| | | |

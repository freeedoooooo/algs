# 数据资讯指标收藏功能 任务清单

> 编号：`0008` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-03-26
> 关联文档：`requirements.md` | `design.md`

---

## 工时评估

| 任务 | 预计工时 |
|------|---------|
| 1. 数据库脚本 | 10 min |
| 2. 实体 / Mapper / Service | 15 min |
| 3. Model 层（Resp） | 5 min |
| 4. Aggregate | 20 min |
| 5. Controller | 10 min |
| 合计 | 60 min |

---

## 任务列表

- [x] 1. 数据库脚本（10 min）
  - [x] 1.1 创建 `docs-c1/00 AI-DOCS/specs/0008-data-di-index-favorite/scripts/V0008__create_com_di_index_favorite.sql`，包含建表 DDL 和联合索引 `idx_user_id_index_id`

- [x] 2. 基础层：实体 / Mapper / Service（15 min）
  - [x] 2.1 创建 `entity/di/ComDiIndexFavoriteEntity.java`（继承 BaseEntity，字段：indexId、userId）
  - [x] 2.2 创建 `mapper/di/ComDiIndexFavoriteMapper.java`（继承 BaseMapper）
  - [x] 2.3 创建 `service/di/IComDiIndexFavoriteService.java` 和 `service/di/impl/ComDiIndexFavoriteServiceImpl.java`

- [x] 3. Model 层（5 min）
  - [x] 3.1 创建 `model/di/resp/DiIndexFavoriteResp.java`（字段：indexId、indexName、addTime）

- [x] 4. Aggregate（20 min）
  - [x] 4.1 创建 `aggregate/di/ComDiIndexFavoriteAggregate.java`，实现以下方法：
    - `add(Long indexId)` — 幂等收藏：查重 → 已存在则返回，否则 new Entity + setAddUser() + save()
    - `cancel(Long indexId)` — 幂等取消：查记录 → 不存在则返回，否则逻辑删除
    - `myList()` — 查收藏 → 批量查指标 → 组装 Resp → 内存按 indexName 升序排序

- [x] 5. Controller（10 min）
  - [x] 5.1 创建 `controller/di/ComDiIndexFavoriteController.java`，实现 3 个接口：
    - `POST /di/index-favorite/add/{indexId}` → `add()`
    - `POST /di/index-favorite/cancel/{indexId}` → `cancel()`
    - `GET /di/index-favorite/my-list` → `myList()`

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
| 收藏接口幂等处理 | 4.1 |
| 取消收藏逻辑删除，幂等忽略 | 4.1 |
| 收藏列表关联指标名称，按 indexName 升序 | 4.1 |
| 用户标识从 ServletRequestContext 获取 | 4.1 |
| 所有接口响应格式符合 GeneralResult<T> | 5.1 |
| 代码符合公共宪法和 data 服务宪法规范 | 全部任务 |

---

## 进度记录

| 时间 | 完成任务 | 备注 |
|------|---------|------|
| | | |

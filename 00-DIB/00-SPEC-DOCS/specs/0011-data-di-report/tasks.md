# 数据资讯报告 任务清单

> 编号：`0011` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-04-16
> 关联文档：`requirements.md` | `design.md`

---

## 工时评估

| 任务 | 预计工时 |
|------|---------|
| 1. 基础设施（枚举 + 建表 SQL + pom） | 30 min |
| 2. 实体 + Mapper + Service 层 | 60 min |
| 3. Converter 层 | 30 min |
| 4. Model 层（Req / Resp） | 40 min |
| 5. 报告目录管理（Aggregate + Controller） | 40 min |
| 6. 报告管理（Aggregate + Controller） | 50 min |
| 7. 简介异步生成组件 | 40 min |
| 8. 客户端查询（Aggregate + Controller） | 60 min |
| 合计 | 350 min |

---

## 任务列表

- [x] 1. 基础设施（预计 30 min）
  - [x] 1.1 `DiAuthObjTypeEnum` 新增 `REPORT_DIR("资讯报告目录")` 枚举值（5 min）
  - [x] 1.2 新增 `DiReportIntroGenStatusEnum`（PENDING/GENERATING/GENERATED/FAILED）（5 min）
  - [x] 1.3 新增 `DiReportOptTypeEnum`（VISIT/DOWNLOAD）（5 min）
  - [x] 1.4 创建建表 SQL `scripts/V0011__add_di_report_tables.sql`（4 张表：目录、报告、标签、操作日志）（15 min）
  - [x] 1.5 `pom.xml` 新增 `dib-cloud-ai-starter` 依赖（5 min）

- [x] 2. 实体 + Mapper + Service 层（预计 60 min）
  - [x] 2.1 新增 `ComDiReportDirEntity`（15 min）
  - [x] 2.2 新增 `ComDiReportEntity`（15 min）
  - [x] 2.3 新增 `ComDiReportTagEntity`（5 min）
  - [x] 2.4 新增 `ComDiReportOptRecordEntity`（5 min）
  - [x] 2.5 新增 4 个 Mapper 接口（`ComDiReportDirMapper` / `ComDiReportMapper` / `ComDiReportTagMapper` / `ComDiReportOptRecordMapper`）（10 min）
  - [x] 2.6 新增 4 个 Service 接口 + 实现类（`IComDiReportDirService` / `IComDiReportService` / `IComDiReportTagService` / `IComDiReportOptRecordService`）（10 min）
  - [x] 2.7 新增 `ComDiReportMapper.xml`（含热点报告统计 SQL：近 30 天按 report_id 分组 COUNT 倒序）（15 min）

- [x] 3. Converter 层（预计 30 min）
  - [x] 3.1 新增 `DiReportDirConverter`（含 `fromAddReq`、`fromEditReq`、`toResp`、`toTreeNodeProperty`、`toTreeNodePropertyList`）（15 min）
  - [x] 3.2 新增 `DiReportConverter`（含 `fromAddReq`、`fromEditReq`、`toResp`、`toRespList`、`fromTagName`）（15 min）

- [x] 4. Model 层（Req / Resp）（预计 40 min）
  - [x] 4.1 新增目录相关 Model：`DiReportDirAddReq`、`DiReportDirEditReq`、`DiReportDirResp`（10 min）
  - [x] 4.2 新增报告管理端 Model：`DiReportAddReq`、`DiReportEditReq`、`DiReportPageReq`、`DiReportResp`（15 min）
  - [x] 4.3 新增客户端 Model：`DiReportQueryPageReq`、`DiReportOptRecordAddReq`（10 min）

- [x] 5. 报告目录管理（Aggregate + Controller）（预计 40 min）
  - [x] 5.1 新增 `ComDiReportDirAggregate`（`add`、`update`、`delete`、`enable`、`disable`、`listTree`）（20 min）
  - [x] 5.2 新增 `ComDiReportDirController`（`add`、`edit`、`delete`、`enable`、`disable`、`listTree`）（20 min）

- [x] 6. 报告管理（Aggregate + Controller）（预计 50 min）
  - [x] 6.1 新增 `ComDiReportAggregate`（`add`、`update`、`delete`、`enable`、`disable`、`page`、`get`、`retryGenIntro`）（30 min）
  - [x] 6.2 新增 `ComDiReportController`（对应 Aggregate 方法）（20 min）

- [x] 7. 简介异步生成组件（预计 40 min）
  - [x] 7.1 新增 `ComDiReportIntroGenComponent`，实现 `asyncGenIntro(reportId)` 方法（PDF 下载 → TXT 转换 → TXT 上传 → AiInvoker 调用 → 回写简介 + 状态）（40 min）

- [x] 8. 客户端查询（Aggregate + Controller）（预计 60 min）
  - [x] 8.1 新增 `ComDiReportQueryAggregate`（`listTree`、`page`、`listNew`、`listHot`、`saveOptRecord`）（35 min）
  - [x] 8.2 新增 `ComDiReportQueryController`（对应 Aggregate 方法）（25 min）

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
| `DiAuthObjTypeEnum` 新增 `REPORT_DIR` | 任务 1.1 |
| 4 张表建表 SQL 正确 | 任务 1.4 |
| 报告目录 CRUD + 启用/禁用，最多两级 | 任务 5.1、5.2 |
| 报告 CRUD + 启用/禁用，字段完整 | 任务 6.1、6.2 |
| 报告标签增删（先删后插） | 任务 6.1 |
| 保存报告后自动触发简介生成 | 任务 6.1、7.1 |
| 简介生成失败支持重试 | 任务 6.1、7.1 |
| 目录授权复用现有接口，仅改枚举 | 任务 1.1 |
| 客户端目录树含 `DiConst.KEY_AUTH_FLAG` 授权标识 | 任务 8.1 |
| 客户端报告列表支持年份/标签/关键词/目录路径筛选 | 任务 8.1 |
| 上新报告（最新 10 条）含授权标识 | 任务 8.1 |
| 热点报告（近 30 天操作次数倒序）含授权标识 | 任务 2.7、8.1 |
| 操作日志记录接口（浏览/下载） | 任务 8.1、8.2 |

---

## 进度记录

| 时间 | 完成任务 | 备注 |
|------|---------|------|
| | | |

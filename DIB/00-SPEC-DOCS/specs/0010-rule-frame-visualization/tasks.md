# 框架准备-可视化 实施任务列表

> 编号：`0010` | 模块：`rule` | 服务：`dib-agent-service-rule` | 创建时间：`2026-04-14`

---

## Task 1 — 数据库建表

- [x] 1.1 创建主表 `com_frame_visualization`（含 `id`、`frame_id`、`stat_level` 及 BaseEntity 标准字段）
- [x] 1.2 创建子表 `com_frame_visualization_level`（含 `visualization_id`、`level_name`、`score_range`、`level_color`、`order_num` 及 BaseEntity 标准字段）
- [x] 1.3 为 `frame_id` 和 `visualization_id` 分别添加索引

---

## Task 2 — Entity & Mapper

- [x] 2.1 新增 `ComFrameVisualizationEntity`，`@TableName("com_frame_visualization")`，继承 `BaseEntity`
- [x] 2.2 新增 `ComFrameVisualizationLevelEntity`，`@TableName("com_frame_visualization_level")`，继承 `BaseEntity`
- [x] 2.3 新增 `ComFrameVisualizationMapper`，继承 `BaseMapper<ComFrameVisualizationEntity>`
- [x] 2.4 新增 `ComFrameVisualizationLevelMapper`，继承 `BaseMapper<ComFrameVisualizationLevelEntity>`
- [x] 2.5 新增 `ComFrameVisualizationMapper.xml`（namespace 对应 Mapper 全限定名，本期无复杂 SQL 可留空骨架）
- [x] 2.6 新增 `ComFrameVisualizationLevelMapper.xml`（同上）

---

## Task 3 — Service 层

- [x] 3.1 新增 `IComFrameVisualizationService`，继承 `IService<ComFrameVisualizationEntity>`
- [x] 3.2 新增 `ComFrameVisualizationServiceImpl`，继承 `ServiceImpl`，实现上述接口
- [x] 3.3 新增 `IComFrameVisualizationLevelService`，继承 `IService<ComFrameVisualizationLevelEntity>`
- [x] 3.4 新增 `ComFrameVisualizationLevelServiceImpl`，继承 `ServiceImpl`，实现上述接口

---

## Task 4 — Model（Req / Resp）

- [x] 4.1 新增 `FrameVisualizationSaveReq`（含 `frameId`、`statLevel`、`levelConfigs` 列表；内部类 `LevelConfigItem` 含 `levelName`、`scoreRange`、`levelColor`、`orderNum`）
- [x] 4.2 新增 `FrameVisualizationResp`（含 `visualizationId`、`frameId`、`frameName`、`statLevel`、`levelConfigs`、`updateTime`；内部类 `LevelConfigItem` 与 Req 保持字段对齐）

---

## Task 5 — Converter

- [x] 5.1 新增 `FrameVisualizationConverter`（MapStruct，`componentModel = "spring"`）
  - `fromSaveReqToEntity(FrameVisualizationSaveReq req) → ComFrameVisualizationEntity`
  - `fromLevelItemToEntity(LevelConfigItem item) → ComFrameVisualizationLevelEntity`
  - `fromEntityToResp(ComFrameVisualizationEntity entity) → FrameVisualizationResp`
  - `fromLevelEntityToItem(ComFrameVisualizationLevelEntity entity) → LevelConfigItem`

---

## Task 6 — 分值区间解析工具

- [x] 6.1 新增内部 BO 类 `ScoreRangeBO`（`leftOpen`、`leftVal`、`rightVal`、`rightOpen`，`-inf`/`+inf` 用 `null` 表示无界）
- [x] 6.2 在 Aggregate 或 util 包中实现 `ScoreRangeParser.parse(String scoreRange) → ScoreRangeBO`
  - 校验首末括号合法性
  - 解析左右数值，支持 `-inf` / `+inf`
  - `leftVal < rightVal`（无穷端跳过数值比较）
  - 格式非法时抛 `BizValidateException`
- [x] 6.3 实现 `ScoreRangeParser.isOverlap(ScoreRangeBO a, ScoreRangeBO b) → boolean`
  - 考虑开闭区间边界，边界相切不算重叠
  - 无穷端按无限大/小处理

---

## Task 7 — Aggregate 业务编排

- [x] 7.1 新增 `ComFrameVisualizationAggregate`，注入 `IComFrameInfoService`、`IComFrameVisualizationService`、`IComFrameVisualizationLevelService`、`FrameVisualizationConverter`
- [x] 7.2 实现 `getVisualization(Long frameId) → FrameVisualizationResp`
  - 按 `frame_id` 查主表（`del_flag=0`），未找到返回 `null`
  - 查子表按 `visualization_id` + `del_flag=0`，按 `order_num` 升序
  - 组装 `frameName`（从 `IComFrameInfoService` 取）
- [x] 7.3 实现 `saveVisualization(FrameVisualizationSaveReq req)`（`@Transactional`）
  - 校验框架状态为 `RELEASE`
  - 校验等级名称非空、不重复
  - 逐条解析 `scoreRange`，校验格式合法
  - 两两比较区间互斥性
  - upsert 主表（存在则 update，不存在则 insert）
  - 逻辑删除旧子表记录（`lambdaUpdate set del_flag=1`）
  - 批量 insert 新子表记录
- [x] 7.4 实现 `listReleaseFrame() → List<FrameInfoResp>`
  - 查询 `frame_status=RELEASE`、`del_flag=0`、`enable_flag=true` 的框架列表
  - 复用现有 `FrameInfoConverter` 转换

---

## Task 8 — Controller

- [x] 8.1 新增 `ComFrameVisualizationController`
  - `@Api(tags = "框架准备-可视化")`
  - `@RequestMapping("/comFrameVisualization")`
- [x] 8.2 实现 `getVisualization(@PathVariable Long frameId)`
  - `GET /comFrameVisualization/getVisualization/{frameId}`
  - 返回 `GeneralResult<FrameVisualizationResp>`
- [x] 8.3 实现 `saveVisualization(@Validated @RequestBody FrameVisualizationSaveReq req)`
  - `POST /comFrameVisualization/saveVisualization`
  - 返回 `GeneralResult<Void>`
- [x] 8.4 实现 `listReleaseFrame()`
  - `GET /comFrameVisualization/listReleaseFrame`
  - 返回 `GeneralResult<List<FrameInfoResp>>`

---

**状态**：草稿

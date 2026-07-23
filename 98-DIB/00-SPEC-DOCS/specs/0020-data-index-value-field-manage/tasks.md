# 指标结果字段映射管理功能 任务清单

> 编号：`0020` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-04-22
> 关联文档：`requirements.md` | `design.md`

---

## 工时评估

| 任务 | 预计工时 |
|------|---------|
| 1. Model / Converter 层 | 20 min |
| 2. Aggregate 管理能力 | 30 min |
| 3. Controller 层 | 15 min |
| 4. 验证 | 20 min |
| 合计 | 85 min |

---

## 任务列表

- [ ] 1. Model / Converter 层（20 min）
  - [ ] 1.1 创建 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldAddReq.java`，定义新增请求对象并补充必填校验
  - [ ] 1.2 创建 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldEditReq.java`，定义编辑请求对象并补充 `id` 校验
  - [ ] 1.3 创建 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/req/DataIndexValueFieldQuery.java`，定义分页查询对象
  - [ ] 1.4 创建 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/model/index/resp/DataIndexValueFieldResp.java`，返回业务字段和 `BaseEntity` 审计字段
  - [ ] 1.5 创建 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/converter/index/ComDataIndexValueFieldConverter.java`，实现请求、实体、响应之间的转换

- [ ] 2. Aggregate 管理能力（30 min）
  - [ ] 2.1 修改 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/aggregate/index/ComDataIndexValueFieldAggregate.java`，新增 `add()`，实现真实维度校验、`indexValueFieldName` 唯一校验和 `dimId + dimLevel` 联合唯一校验
  - [ ] 2.2 修改 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/aggregate/index/ComDataIndexValueFieldAggregate.java`，新增 `edit()`，实现存在性校验、排除自身后的唯一性校验和更新逻辑
  - [ ] 2.3 修改 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/aggregate/index/ComDataIndexValueFieldAggregate.java`，新增 `get()` 和 `page()`，统一按 `delFlag = 0` 查询有效数据
  - [ ] 2.4 修改 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/aggregate/index/ComDataIndexValueFieldAggregate.java`，新增 `delete()`，按系统原风格对不存在记录抛异常并执行逻辑删除
  - [ ] 2.5 在 `ComDataIndexValueFieldAggregate.java` 中补充公共私有校验方法，集中处理真实维度校验和有效数据范围内的唯一性校验

- [ ] 3. Controller 层（15 min）
  - [ ] 3.1 创建 `dib-agent-service-data/dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/controller/index/ComDataIndexValueFieldController.java`，实现 `POST /comDataIndexValueField/add`
  - [ ] 3.2 在 `ComDataIndexValueFieldController.java` 中实现 `POST /comDataIndexValueField/edit`、`GET /comDataIndexValueField/get`、`POST /comDataIndexValueField/page`
  - [ ] 3.3 在 `ComDataIndexValueFieldController.java` 中实现 `DELETE /comDataIndexValueField/delete`，并统一返回 `GeneralResult<T>` 与补齐操作日志注解

- [ ] 4. 验证（20 min）
  - [ ] 4.1 执行代码自检，确认命名、分层、`GeneralResult<T>`、逻辑删除和 `BaseEntity` 审计字段返回符合宪法规范
  - [ ] 4.2 验证新增/编辑场景下 `dimId` 真实存在校验、`indexValueFieldName` 唯一校验、`dimId + dimLevel` 联合唯一校验均基于 `delFlag = 0`
  - [ ] 4.3 验证详情、分页和删除不存在记录的边界行为符合需求与设计约束

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
| 提供 `com_data_index_value_field` 的独立管理 controller，归属 `index` 业务域 | 3.1、3.2、3.3 |
| 支持完整 CRUD：`add / edit / delete / get / page` | 2.1、2.2、2.3、2.4、3.1、3.2、3.3 |
| 支持新增映射配置，新增后可被现有 `ComDataIndexValueFieldAggregate` 查询到 | 2.1 |
| 支持编辑映射配置，编辑后现有聚合逻辑读取到的是最新数据 | 2.2 |
| 支持删除映射配置，并遵循逻辑删除规范 | 2.4 |
| 新增和编辑时校验 `dimId` 对应维度真实存在 | 2.1、2.2、2.5 |
| 新增和编辑时校验 `indexValueFieldName` 在 `delFlag = 0` 的有效记录中唯一 | 2.1、2.2、2.5 |
| 新增和编辑时校验 `dimId + dimLevel` 在 `delFlag = 0` 的有效记录中联合唯一 | 2.1、2.2、2.5 |
| 所有接口统一使用 `GeneralResult<T>` 响应 | 3.1、3.2、3.3 |
| 接口与代码结构符合公共宪法和 `data` 模块宪法要求 | 全部任务 |

---

## 进度记录

| 时间 | 完成任务 | 备注 |
|------|---------|------|
| | | |

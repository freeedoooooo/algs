# 设计稿：文档 ETL 数据链路（Sources → Extract → Template → Staging → Review → Load）

> 状态：**设计稿（待批准，未动代码）**，2026-11-20。
> 范围：产品主干六步（资料文件 / 资料提取 / 数据收集 / 数据转换 / 数据入库）+ 人工校验、血缘追溯、异常隔离区；
> 数据库选型 **SQLite**（最轻量，带演进约束）；文件存储保持**本地目录 + 相对路径**（可整体迁移部署）。
> 原则：增量演进、不推倒 mvp；**模板与目的地解耦**；**Preview 是一等公民**；提取层「官方 JSON 为唯一事实源」不变。
> 配套图：`data-pipeline.drawio`（链路 + 对象关系）。

---

## 1. 链路总览

```
源文件库 Sources
   │ 选文件 / 临时上传（自动登记入库）/ 上次文件重跑
   ▼
提取 Extract ──→ 官方 JSON（事实源，现 mvp pipeline，零改动）
   │
   ▼  模板 Template = 字段定义 Schema + 字段映射 Mapping + 转换规则 Transform
   │  （无配置 = passthrough：整表原样作为暂存记录）
   ▼
暂存数据 Staging Records（标准化中间记录，落盘 + 入库索引）
   │
   ▼
人工校验 Review（对照原图：确认 / 修改 / 拒绝；复用单元格坐标回溯）
   │
   ▼  目的地 Destination（连接 + 表字段映射 + 写入方式）——可选绑定，独立实体
   ▼
入库 Load ──→ 业务表（upsert）+ 血缘表 cv_lineage
                失败 / 拒绝 ──→ 异常隔离区 Quarantine（可修复重放）
```

- **Preview 模式**：Run 只算到 Staging 即停（状态 `previewed`），页面直接看模板处理后的数据，不碰任何业务数据库。测试验证的默认路径：`选文件 → 选模板 → Preview`，三步闭环。
- **Load 模式**：校验确认后，**同一份暂存数据**直接发起入库，不重跑提取。
- 人工校验插在 Staging 之后、Load 之前；Load 只放行「已确认 / 已修改」记录。

---

## 2. 命名总表（中英对照，取业内通用词）

| 概念 | 英文名 | 中文名 | 说明 |
|---|---|---|---|
| 源文件库 | Sources | 资料文件（页面名沿用） | 待提取文件统一管理，哈希去重 |
| 提取 | Extract | 资料提取 | 现 mvp 能力 |
| 模板 | Template | 模板 | 按文档类型复用，含版本 |
| 字段定义 | Schema | 字段定义 | 目标记录有哪些字段、什么类型 |
| 字段映射 | Mapping | 字段映射（原「数据收集」） | 从提取结果哪张表 / 哪个块 / 哪列取值 |
| 转换规则 | Transform | 数据转换 | 值级清洗：trim / 日期解析 / 金额转数值等 |
| 暂存数据 | Staging Records | 暂存数据 | Mapping + Transform 后的标准化中间记录 |
| 人工校验 | Review | 数据校验 | 对照原图核对 / 修改暂存数据 |
| 目的地 | Destination | 入库目的地 | 独立实体，可选；连接 + 入库映射 |
| 入库 | Load | 数据入库（执行动作） | 只入已校验数据 |
| 运行 | Run | 运行记录 | 一次流水线执行实例 |
| 血缘 | Lineage | 血缘追溯 | 库内记录 → 源文件页格坐标 |
| 隔离区 | Quarantine | 异常隔离区 | 失败 / 拒绝记录，可修复重放 |
| 预览 / 入库模式 | Preview / Load | 预览模式 / 入库模式 | Run 的两种模式 |

参照系：Kettle（任意步骤 Preview）、dbt（model 与 materialization 分离、`dbt show`）、
Rossum（Schema 与 Export Connector 分离）、Airbyte（Source / Destination 独立实体）、
Informatica（Mapping + Data Viewer）。

---

## 3. 对象模型（字段级草案）

### 3.1 SourceFile 源文件

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| name | str | 原始文件名（不改名） |
| sha256 | str UNIQUE | 内容哈希，**去重键**：重复上传直接复用已有记录 |
| kind | enum | pdf / image / text（沿用 config 的扩展名分类） |
| size_bytes | int | |
| rel_path | str | 库内规范副本相对路径，见 §5.1 |
| tags / note | str | 标签、备注（可空） |
| created_at | datetime | UTC |

### 3.2 Template 模板 / TemplateVersion 模板版本

Template：`id, name UNIQUE（如「银行流水」）, description, current_version, created_at, updated_at`。

TemplateVersion（**修改模板 = 产生新版本，不改旧版**）：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| template_id | FK | |
| version | int | 从 1 递增，UNIQUE(template_id, version) |
| schema_json | JSON | `[{field, label, type: string/number/date/bool, required, note}]` |
| mapping_json | JSON | 每字段 → 来源选择器：`{table: 表序号或表头匹配, column: 列名/列序号, block: 版面块角色}`；**整体为空 = passthrough** |
| transform_json | JSON | 每字段 → 有序规则列表：`[{op: trim/date_parse/amount/regex_replace/enum_map/..., args}]` |
| created_at | datetime | |

- 模板**不含任何入库信息**（解耦结论；早期「入库映射放模板里」的说法作废）。
- 每个 Run 锁定 template_version_id —— 血缘可复现的关键。
- 内置种子模板「原始透传」（schema/mapping/transform 全空），P0 唯一模板。

### 3.3 Destination 入库目的地 / LoadMapping 入库映射

Destination：`id, name, db_type(mysql/postgresql/...), conn_ref, created_at`。
**conn_ref 是引用名，不是密码**：指向环境变量或本地 secrets 文件中的连接串（§5.6），DB 里永不存明文凭据。

LoadMapping（模板 × 目的地 多对多绑定）：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| destination_id | FK | |
| template_id | FK | 绑定到模板（版本兼容范围默认「同名 schema 字段即可」） |
| target_table | str | 目标业务表 |
| column_map_json | JSON | `[{field, column, col_type}]`，字段 → 列 + 类型 |
| write_mode | enum | append / upsert（默认 upsert） |
| business_key_json | JSON | upsert 的业务主键字段列表 |
| UNIQUE | | (destination_id, template_id, target_table) |

一个连接配一次、N 个模板共用；换目标库不改模板。

### 3.4 Run 运行记录 / RunFile 运行文件

Run：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| batch_tag | str | 14 位批次戳，关联 input/output 目录（沿用现机制） |
| mode | enum | preview / load |
| template_version_id | FK | 锁定版本 |
| destination_id / load_mapping_id | FK 可空 | preview 模式为空 |
| params_json | JSON | 提取参数快照（沿用 params.describe()） |
| state | enum | 见 §4 状态机 |
| error | str 可空 | 失败摘要 |
| created_at / updated_at | datetime | |

RunFile（一次 Run 可含多文件，逐文件状态）：
`id, run_id FK, source_file_id FK, state, output_rel_dir（output/<批次戳_名>/）, UNIQUE(run_id, source_file_id)`。
Run 状态由 RunFile 聚合（全部成功才推进；部分失败标 partial）。

### 3.5 StagingRecord 暂存记录

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| run_id / run_file_id | FK | |
| record_index | int | 表内行序，UNIQUE(run_file_id, record_index) |
| values_json | JSON | 当前值（已类型化；校验修改后更新这里） |
| original_json | JSON | 首次转换产出值，**修改不覆盖原值**，审计可查 |
| lineage_json | JSON | 每字段 → `{source_file_id, page(1起), table_index, cell_bbox, coord_space, raw_text, score}` |
| review_state | enum | pending / confirmed / edited / rejected |
| reviewed_at | datetime 可空 | |

- passthrough 模板下 values = 整行原样字符串，lineage 仍逐格携带（坐标回溯现成）。
- **事实源划分**见 §5.4：DB 是暂存与校验状态的系统记录；`output/<批次>/staging.json` 是导出快照（可再生），保批次自包含。

### 3.6 Quarantine 异常隔离区

`id, run_id FK, staging_record_id FK 可空, stage(transform/review/load), reason, payload_json, state(open/replayed/ignored), created_at, resolved_at`。

- 转换失败、校验拒绝、入库类型错误 → 进隔离区，**不静默丢弃、不阻塞整批**。
- 修复后**从失败阶段重放**，不重跑提取。

### 3.7 LoadLog 入库回执

`id, run_id FK, staging_record_id FK, destination_id FK, target_table, target_pk, action(insert/update), loaded_at`，
UNIQUE(staging_record_id, destination_id, target_table)。

- 幂等回执：同一暂存记录对同一目标表只入一次（重放按 upsert 语义更新）。
- 业务表行反查血缘的入口（配合 §4.3）。

---

## 4. Run 状态机与关键语义

### 4.1 状态机

```
pending → extracting → transforming → awaiting_review → reviewed → loading → loaded
                          │                  │
                          │                  └─ preview 模式终点：previewed
                          └─ 转换失败记录 → quarantine（其余继续）
任一阶段 → failed / partial（部分成功合法：成功照走，失败进隔离区）
```

- preview 模式：`transforming` 完成即 `previewed`，暂存数据可看、可校验。
- `previewed / reviewed` 的 Run 可**原地发起 Load**（补绑 destination，mode 改 load），不重跑提取。
- 重提取 = 新 Run（新批次戳），旧暂存 / 旧血缘保留，产物不覆盖（沿用 mvp 约定）。

### 4.2 语义约定

| 主题 | 约定 |
|---|---|
| 幂等 | 源文件按 sha256 去重；Load 默认 upsert（业务主键）；LoadLog 回执防重复入库 |
| 事实源 | 提取层官方 JSON（result.json）唯一事实源；暂存是它的投影 + 清洗，血缘随时回溯 |
| 校验边界 | Load 只放行 confirmed / edited；pending / rejected 不入业务库 |
| 错误策略 | 部分成功合法；失败进隔离区，Run 标 partial；从失败阶段重放 |
| 阶段解耦 | Mapping / Transform 只面对标准中间结构，不回头碰原始 JSON；转换规则可单测 |
| 模板版本 | Run 锁定版本；模板改版不影响历史 Run 的可复现性 |

### 4.3 血缘追溯（Lineage）

追溯链：`业务表行 → cv_lineage → StagingRecord → Run(+模板版本) → 源文件 + 页 + 格`。

- 本地侧：lineage_json 随暂存记录存（§3.5），坐标体系沿用 `coord.space`（source/rectified）、页码 1 起。
- 目标库侧：独立血缘表 `cv_lineage`，**业务表只加一列 `staging_record_id`**（列名可在 LoadMapping 配置），不污染业务结构：

```sql
CREATE TABLE cv_lineage (
  id            INTEGER PRIMARY KEY,
  target_table  TEXT NOT NULL,
  record_pk     TEXT NOT NULL,      -- 业务表行主键
  staging_record_id INTEGER NOT NULL,
  run_id        INTEGER NOT NULL,
  source_name   TEXT NOT NULL,      -- 源文件名
  page          INTEGER,            -- 1 起
  table_index   INTEGER,
  field         TEXT,               -- 字段级血缘，逐字段一行
  cell_bbox     TEXT,               -- JSON [x0,y0,x1,y1]
  coord_space   TEXT,
  raw_text      TEXT,
  loaded_at     TEXT NOT NULL
);
```

- 前端点库内字段 → 跳回原图格子：复用现成单格定位 / lightbox / 矫正图切换。

---

## 5. 存储设计

### 5.1 文件存储：DATA_ROOT + 相对路径

**选型：保持本地目录，不引入对象存储。** 所有路径以 DATA_ROOT 为基准的**相对路径**存储与流转。

```
DATA_ROOT（默认 = mvp/ 根目录；环境变量 CV_MVP_DATA_ROOT 可覆盖）
├── sources/     # 新增：源文件库规范副本，<sha256前8位>_<原始文件名>
├── input/       # 现有：批次工作副本 <批次戳>_<名>，机制不变
├── output/      # 现有：批次产物（自包含）；新增 staging.json 导出快照
├── logs/        # 现有：运行日志
└── data/        # 新增：cv.db（SQLite，WAL 模式）
```

规则：

1. **DB 与 JSON 中只存相对路径**，统一正斜杠（`sources/ab12cd34_103.pdf`、`output/<批次>/result.json`）。
2. `config.py` 新增 `DATA_ROOT` 与两个 helper：`to_abs(rel)` / `to_rel(abs)`；全仓唯一换算点，别处禁止拼绝对路径。
3. 现有 `INPUT_DIR/OUTPUT_DIR/LOG_DIR` 改为 `DATA_ROOT` 派生；默认值不变 → **现有批次零迁移**。
4. sources/ 存规范副本（按哈希去重、一份）；提取时仍复制到 input/<批次>（批次自包含约定不动）。
   库文件与批次副本职责分离：清理旧批次不影响源文件库。
5. URL 服务沿用现有挂载方式（/inputs、/output），路径换算对前端透明。

**服务器部署**：整个 DATA_ROOT 拷到目标机（如 `/srv/cv-data`），设 `CV_MVP_DATA_ROOT=/srv/cv-data`，
代码零改动。DB 内相对路径天然跟随迁移。

### 5.2 数据库选型：SQLite

**选 SQLite**，理由：

- Python 标准库 `sqlite3` 自带，**零新增依赖**（符合本项目依赖约定）；
- 单文件（`data/cv.db`），随 DATA_ROOT 整体迁移，备份 = 拷文件；
- WAL 模式下读并发足够；当前服务 `--workers 1` 单写者，与 SQLite 单写模型天然匹配；
- 本产品现阶段是单机 / 小团队工具，量级（万级暂存记录）远未到 SQLite 上限。

**演进约束（为将来换 PostgreSQL / MySQL 预留，现在就要遵守）**：

1. 不用 SQLite 方言：主键一律 `INTEGER PRIMARY KEY`（不用 AUTOINCREMENT 关键字、不用 WITHOUT ROWID）；
2. JSON 一律 `TEXT` + 应用层序列化（将来 → JSONB / JSON）；
3. 时间一律 UTC ISO8601 `TEXT`（将来 → TIMESTAMPTZ / DATETIME）；布尔用 INTEGER 0/1；
4. **所有 SQL 收敛在 `mvp/store/` 数据访问层**（类比 JDBC + DAO：业务层只调 repo 方法，不写 SQL）；
   换库只改 store/db.py 连接与迁移脚本方言，业务代码不动；
5. 迁移用编号脚本 `store/migrations/001_init.sql ...` + `PRAGMA user_version` 记录版本（轻量、无 Alembic 依赖）；
6. 多实例 / 高并发部署前必须先换库 —— 这是已知边界，不在 SQLite 上硬撑。

### 5.3 表结构（SQLite DDL，001_init.sql）

```sql
-- 源文件库
CREATE TABLE source_file (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  sha256      TEXT NOT NULL UNIQUE,
  kind        TEXT NOT NULL,                 -- pdf / image / text
  size_bytes  INTEGER NOT NULL,
  rel_path    TEXT NOT NULL,                 -- 相对 DATA_ROOT
  tags        TEXT,
  note        TEXT,
  created_at  TEXT NOT NULL
);

-- 模板（头）与模板版本（内容）
CREATE TABLE template (
  id              INTEGER PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,
  description     TEXT,
  current_version INTEGER NOT NULL DEFAULT 1,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE TABLE template_version (
  id             INTEGER PRIMARY KEY,
  template_id    INTEGER NOT NULL REFERENCES template(id),
  version        INTEGER NOT NULL,
  schema_json    TEXT NOT NULL DEFAULT '[]',
  mapping_json   TEXT NOT NULL DEFAULT '{}',
  transform_json TEXT NOT NULL DEFAULT '{}',
  created_at     TEXT NOT NULL,
  UNIQUE (template_id, version)
);

-- 入库目的地与映射（凭据只存引用名）
CREATE TABLE destination (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE,
  db_type    TEXT NOT NULL,                  -- mysql / postgresql / ...
  conn_ref   TEXT NOT NULL,                  -- 环境变量名或 secrets 文件键
  created_at TEXT NOT NULL
);
CREATE TABLE load_mapping (
  id                INTEGER PRIMARY KEY,
  destination_id    INTEGER NOT NULL REFERENCES destination(id),
  template_id       INTEGER NOT NULL REFERENCES template(id),
  target_table      TEXT NOT NULL,
  column_map_json   TEXT NOT NULL,           -- [{field, column, col_type}]
  write_mode        TEXT NOT NULL DEFAULT 'upsert',
  business_key_json TEXT NOT NULL DEFAULT '[]',
  UNIQUE (destination_id, template_id, target_table)
);

-- 运行与逐文件状态
CREATE TABLE run (
  id                  INTEGER PRIMARY KEY,
  batch_tag           TEXT NOT NULL,
  mode                TEXT NOT NULL,         -- preview / load
  template_version_id INTEGER NOT NULL REFERENCES template_version(id),
  destination_id      INTEGER REFERENCES destination(id),
  load_mapping_id     INTEGER REFERENCES load_mapping(id),
  params_json         TEXT NOT NULL DEFAULT '{}',
  state               TEXT NOT NULL DEFAULT 'pending',
  error               TEXT,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);
CREATE TABLE run_file (
  id             INTEGER PRIMARY KEY,
  run_id         INTEGER NOT NULL REFERENCES run(id),
  source_file_id INTEGER NOT NULL REFERENCES source_file(id),
  state          TEXT NOT NULL DEFAULT 'pending',
  output_rel_dir TEXT NOT NULL,
  UNIQUE (run_id, source_file_id)
);

-- 暂存记录（含血缘与校验状态）
CREATE TABLE staging_record (
  id            INTEGER PRIMARY KEY,
  run_id        INTEGER NOT NULL REFERENCES run(id),
  run_file_id   INTEGER NOT NULL REFERENCES run_file(id),
  record_index  INTEGER NOT NULL,
  values_json   TEXT NOT NULL,
  original_json TEXT NOT NULL,
  lineage_json  TEXT NOT NULL DEFAULT '{}',
  review_state  TEXT NOT NULL DEFAULT 'pending',
  reviewed_at   TEXT,
  UNIQUE (run_file_id, record_index)
);
CREATE INDEX idx_staging_run ON staging_record(run_id, review_state);

-- 异常隔离区
CREATE TABLE quarantine (
  id                INTEGER PRIMARY KEY,
  run_id            INTEGER NOT NULL REFERENCES run(id),
  staging_record_id INTEGER REFERENCES staging_record(id),
  stage             TEXT NOT NULL,           -- transform / review / load
  reason            TEXT NOT NULL,
  payload_json      TEXT NOT NULL,
  state             TEXT NOT NULL DEFAULT 'open',
  created_at        TEXT NOT NULL,
  resolved_at       TEXT
);

-- 入库回执（幂等）
CREATE TABLE load_log (
  id                INTEGER PRIMARY KEY,
  run_id            INTEGER NOT NULL REFERENCES run(id),
  staging_record_id INTEGER NOT NULL REFERENCES staging_record(id),
  destination_id    INTEGER NOT NULL REFERENCES destination(id),
  target_table      TEXT NOT NULL,
  target_pk         TEXT NOT NULL,
  action            TEXT NOT NULL,           -- insert / update
  loaded_at         TEXT NOT NULL,
  UNIQUE (staging_record_id, destination_id, target_table)
);
```

种子数据：内置模板「原始透传」（template + template_version v1，三个 JSON 全空）。

### 5.4 文件与 DB 的事实源划分

| 数据 | 事实源 | 派生 / 快照 |
|---|---|---|
| 提取结果 | `output/<批次>/result.json`（官方 JSON，不变） | 报告 HTML、boxes.png 等 |
| 暂存数据 + 校验状态 | **DB staging_record**（要查询、要改状态） | `output/<批次>/staging.json` 导出快照（可再生，保批次自包含 / 可拷走） |
| 源文件内容 | `sources/` 规范副本（不可变） | input/<批次> 工作副本 |
| 模板 / 目的地 / Run | DB | 无 |

与「官方 JSON 为源 + 薄投影」同一哲学：文件产物自包含可离线核对，DB 承担运营状态；快照永远可从 DB 再生，不双写竞争。

### 5.5 数据访问层 `mvp/store/`（新增模块）

```
mvp/store/
├── __init__.py
├── db.py          # 连接（WAL、外键开关）、迁移执行（user_version）
├── migrations/001_init.sql
└── repo.py        # 每实体一组 DAO 函数：source_repo / template_repo / run_repo / staging_repo ...
```

- 沿用 mvp 包相对导入约定（`from .. import config`），零 IDE 配置。
- 懒加载：首次调用才建连接 / 跑迁移，不拖累 `import app` 0.5s 的现有指标。
- 业务层（app.py / pipeline）只调 repo，不出现 SQL 字符串。

### 5.6 凭据管理（轻量、可部署）

- DB 的 `destination.conn_ref` 只存引用名，如 `CV_DEST_BANK_DB`。
- 解析顺序：环境变量 → `DATA_ROOT/data/secrets.json`（本地文件，.gitignore 排除）。
- 单机阶段明文存本地文件可接受；**部署服务器前**升级为加密存储或注入式环境变量（届时再议，不提前引入 cryptography 依赖）。

---

## 6. 页面与 API 草案

| 页面（中文） | 英文 | 核心内容 |
|---|---|---|
| 资料文件 | Sources | 上传（哈希去重提示）、列表、预览、标签 |
| 资料提取 | Extract | 临时上传 / 从库选 / 上次重跑；选模板；Preview / Load 发起；进度日志（已有） |
| 模板管理 | Templates | Schema / Mapping / Transform 配置；版本历史；passthrough 默认 |
| 数据校验 | Review | 左原图右暂存值；单格高亮回溯；确认 / 修改 / 拒绝 |
| 入库目的地 | Destinations | 连接管理（conn_ref）；模板 × 表字段映射；写入方式 |
| 运行记录 | Runs | 状态机看板；各阶段产物入口；隔离区入口 |

API 草案（沿用现 FastAPI 风格）：

```
GET/POST  /api/sources                      # 列表 / 上传登记（sha256 去重）
GET/POST  /api/templates                    # 列表 / 新建
POST      /api/templates/{id}/versions      # 改版 = 新版本
GET/POST  /api/destinations                 # 连接与映射管理
POST      /api/runs                         # {source_ids | 上传, template_version_id, mode, destination?}
GET       /api/runs/{id}                    # 状态机 + 进度（复用 /api/status 轮询机制）
GET       /api/runs/{id}/staging            # 暂存数据（Preview 结果页）
PATCH     /api/staging/{record_id}          # 校验修改（保留 original）
POST      /api/runs/{id}/review             # 批量确认
POST      /api/runs/{id}/load               # previewed/reviewed → 发起入库
GET/POST  /api/quarantine                   # 隔离区列表 / 修复重放
```

---

## 7. 与现有 mvp 的映射（增量，不推倒）

**分层边界**：DB 只接在编排层（app.py + store/）。`run_batch` 本就在 app.py，pipeline 只认注入的
`emit` 回调与文件产物（11-17 解耦约定），不 import store、不写 DB ——「提取零改动」指 pipeline/
算法模块，app.py 编排层需改（登记源文件、建 Run、emit 回调里更新状态、新路由）。

| 已有资产 | 新链路角色 | 改动量 |
|---|---|---|
| pipeline 提取 + 官方 JSON | Extract 阶段 | 零改动 |
| output/ 批次自包含 + 重跑不覆盖 | Run 产物与幂等基础 | 零改动（新增 staging.json 快照） |
| 单元格坐标回溯 / lightbox / 单格定位 | Review 校验台 + 血缘跳转 | 复用 |
| params 面板 + params_snapshot | Run 参数快照 | 零改动 |
| rerun / 上次文件 | Extract 入口之一 | 小改（登记 source_file） |
| runlog / 进度条 | Run 状态机观测层 | 小改（挂到 run_id） |
| config.py | DATA_ROOT 派生 + to_abs/to_rel | 小改（默认值不变） |

新增：`store/`（DB）、`sources/` 目录、Mapping/Transform 引擎、Review 页、Load 执行器、隔离区。

---

## 8. 分期（每期独立可验证）

| 期 | 内容 | 引入的表 / 模块 | 验收 |
|---|---|---|---|
| **P0 最小闭环** | 源文件库 + Run 模型 + Preview（passthrough） | source_file / template(+种子) / template_version / run / run_file；store/ 骨架；sources/ | 上传 → 提取 → 页面看到暂存数据，三步闭环；现有提取回归零变化 |
| **P1 模板与校验** | Mapping/Transform 配置 UI + 转换引擎 + Review 校验台 | staging_record；staging.json 快照 | 银行流水模板：收集指定列 + 日期/金额清洗 + 对照原图改值 |
| **P2 入库链路** | Destination 管理 + Load(upsert) + 血缘表 + 隔离区 | destination / load_mapping / load_log / quarantine；目标库 cv_lineage | 校验后一键入库；重跑不重复；库内字段跳回原图格子 |
| **P3 加厚** | 转换规则库扩充、批量调度、运行看板统计 | — | 按需 |

P0 完成即有端到端真链路；配置能力逐期加厚。每期动手前按惯例出该期细化设计待批准。

---

## 9. 开放问题（待裁决）

1. **P2 首个目标库类型**：MySQL 还是 PostgreSQL？（Load 执行器先支持一种，另一种后续加驱动）
2. **sources/ 规范副本**：本稿选「独立 sources/ 目录 + 批次工作副本并存」（职责分离，清旧批次不伤库）；备选「复用首个批次副本」（省空间但耦合）。默认按本稿。
3. **多用户校验**：现阶段单机单用户，staging_record 暂不设 reviewed_by；将来多用户再加列。默认按本稿。
4. **凭据方案**（§5.6）：环境变量 / 本地 secrets 文件引用制，部署前再升级加密。默认按本稿。
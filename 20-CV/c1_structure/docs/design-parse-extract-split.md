# design-parse-extract-split — 解析／抽取两层拆分方案

状态：**PARKED 搁置，不实施**（2026-11-22 与用户过目推演后裁决，见下）。

## 零、过目结论（为什么整体搁置）

推演链，三环相扣：

1. **缓存表不需要**——运行隔离天然存在：工件键 `UNIQUE(task_file_id,name)`，每次解析都是新 task→新 task_file→新行，同文件多次解析互不影响、互不覆盖（「重跑不覆盖历史」是现状不变量）。缓存表要解决的"陈旧"问题在显式指定来源的模型下不存在。
2. **血缘兜底/复制也不需要**——它们只为"重放"服务；重放不做，就不欠任何工件账。
3. **重放功能本身不做**——它不补能力（新任务重跑一遍现流程，旧任务的记录/校验/回执/血缘完好无损，入库靠应用层 upsert 按去重依据覆盖、不插重复行，**今天全都走得通**），只省 OCR 时间。当前文档量级（数十任务、单文件秒~分钟级），这个痛不存在。

**恢复实施的触发条件**（满足再回来捡这份底稿）：引擎更换落地（Docling/MinerU，见 project-engine-swap）＋模板跨单据类型复用、迭代频率上来，"改模板要重跑 OCR"成为主诉。届时最小实现＝重放端点（指定源 task_file 只读 extract.json）＋collect 旁路＋工件复制＋入口，**仍是零 schema 变更**。

**期间只需守住的纪律（零成本）**：
① task_file 工件自包含不变量保留；
② `extract.json` 继续带契约标签（现 `c1-structure/1`），改形状必须升版本，不许悄悄改；
③ `collect.build/apply_mapping` 保持「输入只有 doc＋mapping」的纯函数，勿把 OCR 流程逻辑掺进来。

「模板页样本拣选」（§B3.5）与以上解耦、独立有价值（省手写 mapping JSON），等模板创建痛出现时单独评估，不随本方案复活。

以下原文保留作将来细案底稿。

---

## A. 大白话版

### A1. 一句话目标

把现在一步到位的「提取」拆成两件事：
**解析**（OCR＋表格识别，慢，产出全量 JSON，按「文件×参数」缓存复用）和
**抽取**（套模板拣字段，快，秒级，可以随便换模板重跑）。

### A2. 现在 vs 将来

现在（融合一步）：

```
文件 ──► 提取(选参数+选模板) ──► 暂存记录 ──► 校验 ──► 入库
              ▲
              └ 换模板/改字段名 = 整条重跑一遍 OCR（几分钟）
```

将来（两层）：

```
文件 ──► 解析(选参数) ──► 全量解析JSON(缓存) ──► 抽取(选模板,秒级) ──► 暂存记录 ──► 校验 ──► 入库
              ▲                    │                    ▲
              └─ 参数没变就不再跑 ──┘                    └ 换模板=只重放这一步
```

### A3. 例子走一遍（发票明细表）

1. 你上传 `发票A.pdf`，参数默认，模板「发票明细 v1」，跑完＝解析＋抽取，正常出记录；
2. 发现想把「价税合计」列改名叫「含税金额」、再丢弃「规格」列——
   今天：调参数没用、只能新建模板 v2 后**重新提取**，OCR 再跑几分钟；
   拆层后：改出模板 v2 → 点「重放抽取」→ 系统看到 `发票A.pdf`＋同样的解析参数
   已经算过了，直接读缓存里的全量 JSON，几秒出新一批暂存记录；
3. 只有当你改了 DPI/检测阈值这类**解析参数**时，才真正重跑 OCR；
4. 校验、入库、回执、血缘回溯全程无感知——它们拿到的记录格式一字不差。

### A4. 用户会看到什么变化

**第 1 阶段（不动流程、不动页面名字）：**
- 提取页用同一批文件、同一组参数再跑时，日志区多一行「命中解析缓存（N 个文件），仅执行抽取」；
- 模板页新增「在样本上拣选」：选一份已解析过的资料 → 直接列出它解析出的表头 → 勾选、改名、定字段 → 自动生成模板的字段映射（不用再对着 JSON 手写）；
- 资料页每个已解析资料多一个动作「按模板抽取…」→ 秒级建一个新任务。

**第 2 阶段（页面显式分层，另行细化，见 §B5）：**
- 导航「提取」更名「解析」（参数只剩模型类：页码/表格策略/检测阈值/DPI/矫正）；
- 「抽取」成为模板＋资料上的动作，任务台账把两类任务分开展示。

### A5. 为什么分两阶段

第 1 阶段全部是**加法**：新表、新列（可空）、新端点、新入口；旧任务流、旧状态、旧 API、两套验收套件、回执幂等键一概不碰。收益（改模板不用重跑 OCR）在阶段 1 就能全部拿到。第 2 阶段动的是**状态机和全站话术**，是风险最高也最可延后的一半——等阶段 1 用稳了、引擎更换（Docling/MinerU）落地后再做，两层拆分和换引擎各改一次，不叠加。

---

## B. 技术契约

### B1. 术语与层次定义

| 层 | 名称 | 输入 | 输出 | 参数 | 成本 |
|---|---|---|---|---|---|
| L0 | 资料 | 上传字节 | `extract_file`（sha256 唯一，原件 BLOB） | 无 | — |
| L1 | **解析** | 资料原件 | 全量 JSON（契约 `c1-structure/1`，现为 `extract.json`）＋页面图/框图/CSV/对照报告 等工件 | params.py 全部（页码/表格策略/检测阈值/DPI/矫正…）＋引擎及模型版本 | 秒~分钟（GPU/CPU 模型） |
| L2 | **抽取** | 解析工件＋模板版本 | 暂存记录（values/original/lineage/review，形状不变） | template_version.mapping_json | 毫秒~秒 |
| L3+ | 校验/入库 | 暂存记录 | 回执/隔离 | 入库规则 | 不动 |

关键口径：**解析的缓存键＝(file_id, params_hash, parse_schema_version, engine_id)**。

### B2. 现有事实（方案的立足点，均已核到行号）

- 解析产物已存在：`extract_one()` 产 doc（`pipeline/runner.py:170,293`），信封契约 `adapter/base.py:4-21`，`extract.json` 紧凑落盘（`runner.py:294-296`）后随整目录进 `extract_artifact` BLOB 表（`service.py:151-162,264`，UNIQUE(task_file_id,name)＋sha256 列，`artifact_db.py:13-27`）。磁盘 scratch 即焚（`service.py:265`）。
- 抽取已分离在纯函数里：`collect.build(doc, tpl)` → 原始透传 `passthrough` 或 `apply_mapping`（表选择器 `table{index|header_contains}` × 列选择器 `column{name|index}`，`collect.py:41-152`）；lineage 锚点在 `collect.py:24-38`，随记录进 `extract_staging_record/_field/_lineage`（`content_db.py:114-173`）。
- 内容寻址已就绪：`extract_file.sha256` UNIQUE（`001_baseline.sql:8-19`），`register_file` 即做去重（`service.py:74-80`）。params 快照存 `extract_task.params_json`（`catalog/tasks.py:14-25`）＋`extract.json['params']`（`runner.py:192-194`）。
- 融合点在 `service.task_batch` 的 per-file 循环（`service.py:232-266`）：extract_one → 对照报告 → collect → save_records → _ingest_case。
- 下游全部以 `task_file_id` 为血缘/幂等键：暂存（`content_db.py:123-134`）、入库回执（`extract_load_log`，键 `(task_file_id, record_index, datasource_id, target_table)`）、工件服务 `/files/<task_file_id>/<rel>`（`app.py:137-155`，`raw/` 403）。**因此重放抽取必须落在新的 task_file 上，绝不复用旧 task_file 覆盖记录**（否则清掉人工校验状态＋破坏回执幂等）。
- 一个任务一个模板（`service.py:100-104`），无重抽/重放端点（现状提示语让用户重新上传，`upload.js:287`）。引擎全局单任务串行 `STATE+LOCK`（`service.py:26-36`）。

### B3. 第 1 阶段设计：解析缓存＋抽取重放

#### B3.1 平台库变更（migrations/002，全部是加法）

```sql
CREATE TABLE extract_parse (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  file_id       INT  NOT NULL,              -- extract_file.id
  params_hash   CHAR(64) NOT NULL,          -- sha256(canonical JSON)
  parse_schema  VARCHAR(32) NOT NULL,       -- 'c1-structure/1'
  engine        VARCHAR(64) NOT NULL,       -- 'paddle-ocr:3.x+pp-struct' 等
  source_task_file_id INT NOT NULL,         -- 首次产出该解析的 task_file（工件住址）
  created_at    DATETIME NOT NULL,
  hit_count     INT NOT NULL DEFAULT 0,
  UNIQUE KEY uq_parse (file_id, params_hash, parse_schema, engine)
);
ALTER TABLE extract_task_file
  ADD COLUMN parsed_from_task_file_id INT NULL;  -- 非空＝该文件行的工件走解析缓存住址
```

- `params_hash` 取 `params.normalize()` 后**非下划线键**的规范 JSON 摘要（与 `extract.json['params']` 同口径，`runner.py:192-194`）；`parse_schema`/`engine` 常量进 `config.py`。**换引擎或改工件契约自动击穿旧缓存**，这是引擎更换计划的保险丝。
- 不复制任何 BLOB：缓存命中时新 task_file 只写 `extract.json` 一行（内容同字节），其余工件（页面图/框图/CSV/raw）由工件服务按 `parsed_from_task_file_id` 兜底解析（见 B3.4）。存储零增长。

#### B3.2 task_batch 流程改造（唯一动到执行逻辑的地方）

`service.py:232-266` per-file 循环内，`extract_one` 之前插入查缓存：

```
key = (file_id, params_hash, parse_schema, engine)
hit = SELECT ... FROM extract_parse WHERE key
if hit and 允许命中(新参 force_reparse=off):
    doc = 读 hit.source_task_file 的 extract.json → 反序列化校验 schema
    UPDATE hit_count
    工件登记: 新 task_file 写 extract.json 行, parsed_from_task_file_id=source
    日志: 「命中解析缓存 #tf, 跳过 OCR」
else:
    doc = extract_one(...)  # 原路径, 产完整工件
    INSERT extract_parse ... ON DUPLICATE KEY UPDATE ...  # 首次登记
collect.build(doc, tpl) → save_records → …（原样）
```

- 失败降级：缓存里的 `extract.json` 读不到/校验不过 → 回退全量解析，不算错误。
- 任务参数新增可选 `reparse: true`（强制重解析，默认 false），UI 提取页放小勾选「忽略缓存重新解析」。
- 对照报告：命中缓存时 `对照报告.html` 不再重新生成（它本质是解析层工件），新 task_file 直接登记源 task_file 的报告引用（工件兜底即可取到）；任务详情与校验台跳报告处沿用现链接，用户无感。

#### B3.3 抽取重放入口（复用现任务模型）

「重放抽取」＝新建一个 task（新 task_id/新 task_file 行）＋**必然命中缓存**的 task_batch：

- 新端点 `POST /api/tasks/recollect`（`/api/*` 只增不改）
  body: `{file_ids|task_file_ids: [...], template_version_id}`；
  params 缺省＝该文件最近一次解析所用参数（`extract_parse.params_hash` 反查 `source_task_file` 的任务 params）；
  服务端把 (file, params) 组好直接走 launch 线程池，前端仍轮询 `/api/status`。
- 入口两处：①资料页行操作「按模板抽取…」（弹模板下拉）；②任务页详情抽屉「用新模板重放」（同批文件一键）。
- 台账语义：重放产生的是**新任务**（`重跑不覆盖历史` 原则 001_baseline.sql 注释既有），校验台/入库规则零改动即兼容；旧任务的回执继续有效。

#### B3.4 工件兜底读取（血缘回溯不破）

`app.py:137-155` `/files/<task_file_id>/<rel>`：本地无该行且 `parsed_from_task_file_id` 非空 → 以源 task_file 重试一次。`raw/` 403 规则不变。校验台的 boxes.png/页面图/坐标回溯全部透明可用。

#### B3.5 模板页「在样本上拣选」

- 新只读端点 `GET /api/files/{file_id}/parse-tables`：取该文件最新解析的 `extract.json`，返回候选表清单（scope/页/表序/表头/行数，数据源即 `collect._candidate_tables` 的口径 `collect.py:41-55`）。
- 模板编辑抽屉加「从样本资料拣选」：选样本 → 列表勾选表头列（可改名＝mapping 的 `target`，可全不选）→ 生成/回填 `mapping_json`（`table{index|header_contains}`×`column{name}`，与现契约一致 `collect.py:110-144`）→ 走既有版本保存。
- 该功能同时是第 2 阶段拣选 UI 的雏形；表单类 KV 拣选**不在本期**（要先扩解析产物，见 B9）。

### B4. 明确不改的东西（红线核对）

| 项 | 结论 |
|---|---|
| 目标业务库表结构／write_mode 存库值／launch_load 绑定语义 | 不碰 |
| 既有 `/api/*` 路径与响应字段 | 只增不改（`/api/tasks` 项可加 `parsed_from` 展示字段，向后兼容） |
| 暂存记录形状 values/original/lineage/review、`(task_file_id, record_index)` 键 | 不变——入库回执/门禁/隔离的根基 |
| 状态机 pending/extracting/previewed/loaded/partial/failed | 第 1 阶段不变（重放任务照样 extracting→previewed） |
| 两套验收套件 | 应全绿；新增用例见 B8 |
| 平台库既有表列 | 不加不改语义；新增 1 表＋1 可空列（migrations/002，加法） |

### B5. 第 2 阶段概要（本轮只列边界，实施前另出细案）

1. 路由与话术：`/extract`→解析（去掉模板下拉），模板操作承接「抽取」；导航/页头/文案全站一次改齐（UI 统一令）。
2. 任务分型：`extract_task.kind = parse | collect`，台账/工作台卡片按类计数；`/api/tasks` 加性字段 `kind`。
3. 资料页成为解析中心：每个资料显示最新解析（参数、时间、工件）＋重解析/重放入口。
4. 表单类解析产物扩展（文本块/KV 候选进 extract.json，schema 升 `c1-structure/2`）＋KV 锚定/LLM 选择器（§B9）。
5. 与「规则版本化（第 3 层）」合并考虑解析×模板的版本兼容治理（§B7-R2）。

### B6. 与引擎更换计划的关系（project-engine-swap）

单元格 bbox 是决定点 → 换引擎的适配面恰好在 L1 之内（adapter 契约 `c1-structure/1`）。`engine` 进缓存键后，Docling/MinerU/PaddleX 产物天然分区共存、可灰度对比（同一文件不同 engine 各留一份解析）。**建议顺序：先落地本方案阶段 1，再做引擎 A/B**，否则两件事混在一次改动里没法归因。

### B7. 风险清单与对策

| # | 风险 | 对策 |
|---|---|---|
| R1 | extract.json 反序列化出的 doc 与 extract_one 活对象有差异（日期/元组/浮点）→ 重放结果与首跑不一致 | 回归用例强制「同文件同参数同模板：重放记录 ≡ 首跑记录」（按 values+lineage 全等断言）；runner 落盘已是紧凑 JSON（`runner.py:294`），改造集中在读取侧 |
| R2 | 缓存陈旧：模板/血缘引用了被删资料、或解析参数改了没进 hash | `params_hash` 全参数覆盖；删资料时联动 `extract_parse` 失效（Conflict 检查走既有血缘约束） |
| R3 | 台账任务数膨胀（重放=新任务），用户困惑 | 任务列表加「解析自 #tf」标记与去重展示（第 1 阶段仅在详情抽屉显示）；工作台口径按记录数不受影响 |
| R4 | 并发/竞态：同文件同时首发解析 | 现状本就是全局串行单任务（STATE+LOCK），天然无竞态；第 2 阶段并行化时再引入行锁 |
| R5 | 磁盘即焚+DB-only 约定（accept_artifacts_db 6 项断言）被破坏 | 本方案不落新盘，工件全部走 BLOB＋兜底读取，约定保持 |

### B8. 验收标准（第 1 阶段）

1. 新套件 `accept_parse_cache.py`（沿用假 DSN/独占窗口流程）：
   首发无缓存→全解析；二跑同参数→日志含「命中解析缓存」且 extract 阶段耗时骤降、记录全等；
   改一参数→不命中；`reparse=1`→强制不命中；`/files` 兜底取 boxes.png 成功；
   重放新 task_file 且旧 task_file 记录/回执不受扰；`extract_parse` 唯一键与 hit_count 正确。
2. 既有两套验收套件全绿（不改任何断言）。
3. 冒烟：提取页连跑两次、模板拣选生成 mapping、资料页重放入口、校验台血缘图、向导 dry-run。

### B9. 明确不做（本期外）

- 表单类文档的 KV/文本块解析产物与锚定/LLM 抽取（依赖 schema 升级，属第 2 阶段）；
- 解析任务的独立队列/并行化；
- 入库侧任何改动；
- 模板 mapping 契约变更（拣选 UI 只是生成器，产物仍是现格式）。

### B10. 需要你拍板的决策点

- **D1 范围**：按「阶段 1 全量（缓存＋重放＋样本拣选）」开工？还是先只做缓存＋重放、拣选 UI 下一轮？
- **D2 平台库加法**：确认接受 migrations/002＝新增 `extract_parse` 表＋`extract_task_file.parsed_from_task_file_id` 可空列（不动任何既有列语义）。
- **D3 命中策略**：默认命中、页面给「忽略缓存重新解析」勾选（推荐）；还是每次让用户显式选择？
- **D4 重放粒度**：重放=新建任务（推荐，保历史/保回执）；旧任务标记不隐藏，台账可能出现同文件多任务，接受吗（R3 有缓解项）？
- **D5 对照报告**：命中缓存时复用解析层旧报告（推荐，秒级）；还是每任务重生成（多花报告渲染时间，但每任务自带全套工件）？

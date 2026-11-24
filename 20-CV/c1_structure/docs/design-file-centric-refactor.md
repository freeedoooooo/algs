# 以资料为主键的重构设计稿（删除 task / task_file）

> 状态：**✅ 全部实施完成（2026-11-24 22:20）**。P0 准备 → P1 数据层 → P2 编排层 → P3 API/验收 → P4 前端 → P5 文档收尾，各期均先汇报验证结果并获用户确认后推进。D1/D2/D5 用户拍板，D3~D8 按推荐默认执行。日期：2026-11-24。
> 目标：把"一次上传 = 一个 task（可含多文件）"改为"一条资料记录 = 一次运行（单文件）"，删除 `c1_task`、`c1_task_file`，以 `c1_doc_file.id`（下称 `file_id`）作为唯一运行主键。
>
> **已拍板三点**：① 抽取规则表**保留**（与入库规则配置一并留）；② 哈希去重**去除**（每次上传插新行，同字节允许多条独立运行）；③ preview/parse **保留独立页**，由资料清单作唯一入口，不并入弹窗。

---

## 1. 用户裁决与落地口径

| 用户原话 | 落地口径 |
|---|---|
| 存量数据可以清了，只保留入库规则配置 | 清运行数据（task/task_file/产物/暂存/回执/隔离）；**配置表建议全留**——抽取规则资产与入库规则是绑定的（`c1_load_table.rule_id` 指向抽取规则），只留后者会悬空。见 §9 决策 D1 |
| 重放解析放在资料清单上 | 重放按钮从 tasks 详情抽屉迁到 sources 行操作/流程弹窗，语义改为**原地覆盖该资料行的运行态**（见 §9 D4） |
| 多文件批次改单文件、文件页签去掉精简 | 上传限制一份；parse 报告页签、preview 暂存页签全部删除；URL 去掉 `file=` 参数 |
| 资料页流程追踪弹窗保留 | 保留四节点（解析/抽取/校验/入库），去掉顶部"任务切换下拉"（一文件只有一条链路），节点详情链接改 `file_id` 键 |
| 任务 nav 及任务相关功能迁到资料清单 | nav 8 项减为 7 项（删"任务"）；**sources 成为唯一功能入口**（列表/筛选/重放/入库/回执/预览/流程），preview/parse 保留为二级详情页但不在 nav 中（见 §9 D5） |

## 2. 目标数据模型

### 2.1 保留且不动的表（5 张，纯配置）

| 表 | 说明 |
|---|---|
| `c1_extract_rule` | 抽取规则（资产，**强烈建议保留**，见 D1） |
| `c1_extract_rule_version` | 规则版本快照（三段 JSON，含 spec_version 2/3） |
| `c1_load_datasource` | 业务库连接配置 |
| `c1_load_table` | 入库规则（数据源 × 目标表 × 规则 × write_mode） |
| `c1_load_table_field` | 入库字段映射 |

### 2.2 改键的表（4 张）

| 表 | 现键 | 新键 | 变化 |
|---|---|---|---|
| `c1_parse_artifact` | `task_file_id + name` | `file_id + name` | 列名改名，唯一键语义不变 |
| `c1_staging_record` | `task_file_id` | `file_id` | 列名改名；field/lineage 经 `record_id` 关联，**不动** |
| `c1_load_log` | `task_id + task_file_id + record_index` | `file_id + record_index` | 删两列加一列；唯一键改 `(file_id, record_index, datasource_id, target_table)` |
| `c1_load_quarantine` | 同上 | 同上 | 同上 |

### 2.3 吸收运行态的表（1 张）

`c1_doc_file` 加列，成为"资料 + 运行"一体表：

| 新列 | 来源 | 说明 |
|---|---|---|
| `state` | `c1_task.state` | pending / parsing / to_extract / to_review / to_load / loading / loaded / failed |
| `error` | `c1_task.error` | 失败原因 |
| `rule_version_id` | `c1_task.rule_version_id` | 抽取时绑定的规则版本 |
| `params_json` | `c1_task.params_json` | 解析参数 |
| `load_datasource_id` / `load_table_id` | `c1_task` | 入库目标绑定 |
| `updated_at` | `c1_task.updated_at` | 更新时间 |

现有列（`name/sha256/kind/size_bytes/content/tags/note/created_at`）不变。

### 2.3b 去哈希去重的连锁改动（D2 已定：去除）

"每次上传插新行、同字节允许多条独立运行"不只是删一段查重 SQL，以下六处必须同步：

| 位置 | 现行为 | 新行为 |
|---|---|---|
| `store/catalog/files.py:13-30` `register_file` | 先 `SELECT id ... WHERE sha256=%s`，命中回 `(id, True)` | 去掉 SELECT，直接 INSERT，恒回 `(new_id, False)` |
| **DB 索引 `uk_file_sha`** | `c1_doc_file.sha256` 上有唯一索引（历史 001 基线推断） | **必须 DROP 唯一索引**（可改普通索引供检索）；否则同字节第二次 INSERT 撞唯一键报错。这是最容易漏、且只在运行时才暴露的一处 |
| `service.py:74-80` `register_file` | 计算 sha 后透传 dedup | sha 仍算（资料页显示/ETag 用），dedup 恒 False |
| `app.py:387-406` `/api/sources` | 响应含 `dedup` | 字段保留（恒 False）避免前端改协议；docstring 改"不查重，每次登记新行" |
| `web/sources.js:98,104` | "内容相同，已复用 N 个" | 去掉复用分支文案，统一"已登记 N 个" |
| `accept_records_db.py` | `register_file` 多处断言 `dup` 为 True（L~390、L~等） | 改为断言 `dup` 恒 False / 删去重相关断言 |

**语义变化**：资料清单同一份文件可出现多行（各自有独立 state/rule/产物/回执）。流程追踪弹窗的"任务切换下拉"去掉后，一条资料行 = 一条链路，不冲突。"重放解析"与"重新上传同文件"两种操作并存：前者**原地覆盖本行**，后者**新建一行**。

### 2.4 删除的表（2 张）

`c1_task`、`c1_task_file` —— 全部状态机（rollup 上卷）消失，一张资料行自己就是运行状态。

### 2.5 业务表溯源列

`store/loader.py:111` 的 `TRACE_COLS` 从 `('task_id','task_file_id','record_id')` 改为 `('file_id','record_id')`。写入侧 `service.py:656-661` 的 `extra_values` 同步。回读侧 `loader.query_rows` 置顶展示、`dashboard.js` 的 `TRACE` 常量、`record_id_map`/`locate_record` 同步。

**存量业务表的旧两列不自动处理**（平台无权修改用户业务表 DDL）；新代码不写它们。验收脚本的合成目标表（`accept_records_db.py:571-575,955-959`）改为两列。见 D6。

## 3. 后端改动清单（按文件）

### store 层

- `store/catalog/files.py`
  - `register_file`（L13-30）：决策 D2 决定去重去留；`list_files`（L33-59）返回新增运行态列；新增 `set_state` / `set_rule` / `set_load`（原 tasks.py 的 `set_task_state`/`set_task_rule`/`set_task_load` 合并进来）。
  - `delete_file`（L89-101）去掉 `c1_task_file` 引用守卫，改为"运行中禁删"或直接允许。
  - 吸收 `tasks.py` 的 `add_quarantine`/`list_quarantine`，键改 `file_id`。
- `store/catalog/tasks.py`：**整文件删除**（`file_pipeline` 简化版挪入 files.py）。
- `store/catalog/load.py`：`set_task_load`（L366-375）→ `set_file_load`；`add_load_log`（L378-400）、`list_load_logs`（L403-421）改 `file_id`；`get_load_table`（L233-235）等三处 `task_refs` 守卫改为 file 引用数或直接取消。
- `store/catalog/rules.py`：`delete_rule`（L189-207）的 task 引用守卫改口径（D7）。
- `store/content_db.py`：`_task_files`（L28-36）删除；`get_records`（L74-148）信封去掉 `task_id`/`task_file_id`，改 `file_id`；`record_id_map`（L39-52）、`locate_record`（L55-71）、`gate_counts`（L358-386）、`ledger`（L389-446）、`query_fields`（L323-355）全部 SQL 改 `file_id`；`save_records`（L199-247）按 `file_id` 落库；`patch_record`/`set_review`/`purge_records` 参数改 `file_id`。
- `store/artifact_db.py`：全部 `task_file_id` → `file_id`；`latest_task_file_with`（L97-107）改为 latest file。
- `store/loader.py`：`TRACE_COLS`（L111）及预检（L114-126）改两列。

### service 层（`service.py`）

| 函数 | 现行为 | 新行为 |
|---|---|---|
| `launch`（L97-134） | `create_task` + 每文件 `add_task_file` | 不建 task；单文件直接以 `file_id` 初始化该资料行运行态 |
| `task_batch`（L181-285） | 逐 task_file 推 state | 单资料行推进；去掉 `set_task_state` 上卷 |
| `run_extract`（L289-346） | 按 task 找 files、绑规则、rollup | 按 `file_id` 取 parse.json、绑规则、置 to_review |
| `derive_review_state`（L349-368） | 按 task 聚合门禁、rollup | 单资料行门禁判定 |
| `reparse`（L371-435） | 复用 task_file、清产物、保留 load_log | 原地覆盖：清产物/暂存/隔离/回执（D4），state 回 pending |
| `launch_load`/`preview_load`/`run_load`（L440-733） | 全程 task 粒度 | 全程 `file_id` 粒度；`set_file_load`、`record_id_map(file_id)`、`extra_values` 两列、回执/隔离按 file |

### API 层（`app.py`）

删除全部 12 个 `/api/tasks/{task_id}/...` 端点（L615-692, 695-714, 731-833）和 `/api/tasks`（L695-698, 836-879），改为 `/api/sources/{file_id}/...` 一组：

| 新端点 | 承接原功能 |
|---|---|
| `GET /api/sources/{id}/pipeline` | 保留，简化为单链路四节点（L415-422 保留并改写，不再按 task 分组） |
| `POST /api/sources/{id}/parse` | 原 `/api/upload` + 单文件解析 |
| `POST /api/sources/{id}/reparse` | 原 reparse |
| `POST /api/sources/{id}/extract` | 原 extract |
| `GET /api/sources/{id}/staging` + `PATCH .../staging/{index}` + `POST .../staging/review` | 原 staging 三端点（去掉中间 file 段） |
| `GET /api/sources/{id}/gate` | 原 gate |
| `POST /api/sources/{id}/load` + `/load-preview` | 原 load 两端点 |
| `GET /api/sources/{id}/load-log` + `/quarantine` | 原回执/隔离 |
| `GET /api/sources/{id}/parse-json` | 原 `/api/tasks/{id}/parse` |
| `GET /api/sources/state` 或扩展 `/api/sources` | 原 `/api/tasks` 列表（供工作台/筛选），带 state 过滤参数 |
| `GET /api/sources/ledger` | 原 `/api/staging/ledger` |
| `GET /api/staging/locate/{record_id}` | 保留，返回 `file_id + record_index` |

其他：`/files/{path}`（L139-157）首段由 task_file_id 改 file_id；`/parse-report`（L359-371）改 latest file；`/api/status` 去掉 `task_id` 或改为 `file_id`；`/api/upload` 改为单文件。

## 4. 前端改动清单（按文件）

### 删除 / 精简

- `web/tasks.html`、`web/tasks.js`：**整页删除**。独有功能（重放解析、gate 展示）迁入 sources。
- 9 个 HTML 的 nav 删"任务"项：home.html:20、parse.html:20、preview.html:21、review_home.html:19、extract.html:20、rules.html:21、sources.html:19、dashboard.html:19（tasks.html 随整页删除）；preview 高亮改"资料"，dashboard 保持"入库"。
- parse 报告页签（parse.js:316-340）与 preview 暂存页签（preview.js:24-42）删除；URL 去掉 `file=` 参数。
- preview 的"无 task 时任务台账入口"模式（preview.html:31-39,49-67；preview.js:860-957,935-957,972-986）整体移到 sources；preview 只保留单资料详情页。
- `review_home.html`（L31-35）指向改 sources/preview 新键。

### sources 成为主操作台（sources.html/js）

- 列表列扩展：状态徽标、抽取规则、入库目标、时间（承接 tasks 台账列）；加 state 筛选（承接 `?state=` 深链）。
- 行操作：查看流程（已有）、下载（已有）、**解析/重放解析**（新增，承接 tasks.js:120-139）、**预览数据**（新增）、**入库/回执**（新增）。
- 流程弹窗：去掉 task 切换下拉（sources.js:235-241,284-286）；四节点节点详情链接改 `file_id`；补 gate 计数（入库节点）；修 L172-173 失效的 `/extract?rule=` 深链。
- 上传登记：单文件限制（sources.js:83-109 去掉循环）；去留去重见 D2。

### 预览页入口映射（原 `?task=&file=` → 新 `?file=`）

**nav 层面只有资料清单一个入口**；但深链保留——工作台、看板、解析页可直接跳到某条资料的预览页，不必绕资料清单。

| 入口位置 | 现状 | 改后 |
|---|---|---|
| 资料清单行操作「预览数据」 | 无（原在任务台账详情里） | **新增主入口**：`/preview?file=<file_id>` |
| 资料清单流程弹窗→校验节点 | `/preview?task=&file=` | `/preview?file=`（弹窗已按资料行单链路，无切换下拉） |
| 工作台待办卡片（待抽取/待校验/失败） | `/preview?task=<task_id>` | `/preview?file=<file_id>`（卡片取数改 `/api/sources/state`） |
| 工作台快速解析完成提示 | `/preview?task=<task_id>` | `/preview?file=<file_id>` |
| 解析页解析完成「预览数据」 | `/preview?task=<task_id>` | `/preview?file=<file_id>` |
| 数据看板点行→血缘回溯 iframe | `/preview?embed=1&task=&file=&index=` | `/preview?embed=1&file=<file_id>&index=<n>` |
| preview 自身页签/返回/台账点击 | `/preview?task=&file=`、`/tasks?task=` | `/preview?file=`；返回按钮改 `/sources` |
| review 占位壳页文案 | 提示 `/preview?task=任务ID` | 改 `/preview?file=资料ID` |

URL 形态：`/preview?file=<资料ID>&index=<记录序号>`；embed 额外带 `embed=1`。`index` 保留（记录定位用）。

### 改键（保留页面）

| 文件 | 改动 |
|---|---|
| `preview.js`（985 行） | `task`/`file` 参数改 `file`（L8-11）；所有 API/深链/产物链接改 file 键（L29-42,428-447,687-745,799-857,928-970）；返回按钮 L925 改 sources；embed 模式保留（L928-934）但 iframe URL 改新键 |
| `parse.js` | 单文件 + 去页签；历史报告下拉（L365-383）改按资料；`POST /api/tasks`（L501）改新端点；`from_source`（L522-524）保留；产物链接/报告 URL 改 file 键 |
| `home.js` + `home.html` | `/api/tasks` → `/api/sources/state`（L216,226）；卡片/待办计数改按资料 state（L97-140,155-195）；链接 `/tasks?state=` → `/sources?state=`（html:58,64,70,76）；快速解析产物链接改 file 键（L90） |
| `extract.js` | 参考文件下拉（L411-457）从 `/api/tasks` 改 `/api/sources`；`/api/tasks/{id}/parse` 改新端点 |
| `rules.js` | `lt.task_refs`（L297）改 file 引用口径；rules.html:161 文案同步 |
| `dashboard.js` | `TRACE` 改两列（L5,18）；`locate` 返回 file_id；iframe URL 改新键（L83-85） |
| `shell.js` | 回执抽屉（L124-167）改 file 键与文案；`fileUrl`（L74-76）改；动画/分页/徽标不动 |
| `wizard.js` | `wz.taskId` 全程改 `fileId`（L53-61,348-403），标题文案改"资料 #…" |

## 5. 验收与测试改动

- `accept_records_db.py`（七项）：baseline（L145-153）守恒口径重建；`[1/7]` task 投影往返改为配置表/资料行往返或删；`cleanup_tasks`（L283-331）重写；`[5/7]~[7/7]` 全部 URL 与状态断言改 file 键；重放段（L799-833）按 D4 重写；合成表 DDL 改两列。
- `accept_artifacts_db.py`（六项）：孤儿 artifact 断言（L273-277）改 file 键；`[2/6]~[6/6]` URL/task 投影/导出 `--task` 改 `--file`；导出目录 `output/task_<id>/` 改 `output/file_<id>/`。
- `export_artifacts.py`：参数 `--task` → `--file`，目录名改。
- `tests/test_service_smart_dispatch.py`：mock 里 task_id/task_file_id 改 file_id。
- `tests/verify_real_extract.py`：`DEFAULT_TASK=446` 与 8765 依赖失效，改本地 parse.json 或删除。
- 纯抽取层 5 个测试（`test_collect_*`、`test_smart_extract.py`）**原样保留**。
- README.md：存储模型（L158-176）、入库链路（L178-197）、导出（L199-210）、验收（L399-411）整段重写；顺带修 `partial` 旧词与"各六项"笔误。

## 6. 清库与建表

- 用户有意删除了 `store/migrations/`，但 git 历史可只读取回原始 DDL 作参考：`git show 76d4f36:20-CV/c1_structure/store/migrations/001_baseline.sql`（以及 002/003/004）。
- 建议产出**全新基线脚本**（如 `store/migrations/001_file_baseline.sql`）：按 §2 的表结构重建，不叠加历史迁移。是否重新启用 migrations 目录见 D3。
- 保留表的数据（抽取规则、入库规则）需在清库前导出备份，清库后导回；`c1_doc_file` 原件是否保留见 D2。
- **8765 是用户自起常服，全程不启停**。清库 + 代码切换必须同一窗口，由用户安排停机；我只在 8799 上验证。

## 7. 分期施工（每期完成先汇报、确认后再进下一期）

| 期 | 内容 | 验证点 |
|---|---|---|
| P1 | 数据层：新基线 DDL、store 层全部改键、清库/导回脚本 | paddle python 编译、repo 级 CRUD 自测、8799 不启 |
| P2 | 计算编排层：service.py 全管线、loader TRACE_COLS、collect 信封改键 | 纯抽取 5 项单测 + smart dispatch 单测全绿 |
| P3 | 后端 API：app.py 全路由改键 | 8799 冒烟全端点 200/409/503 正确；两套验收脚本重写并顺序跑通 |
| P4 | 前端：删 tasks、nav 改造、sources 主操作台、各页改键 | node --check 全过、HTML 标签配平、8799 静态资源冒烟；视觉效果由用户在 8765 实测 |
| P5 | 收尾：README/设计稿/测试更新、备份、清理临时脚本 | git diff 全审、8765 未动确认 |

## 8. 功能取舍总表

| 功能 | 处置 |
|---|---|
| 任务台账列表 / 详情抽屉 | **删除**，状态列与 gate 迁入 sources |
| 重放解析 | **迁移**到 sources（原地覆盖） |
| 多文件批次 + 文件页签 | **删除** |
| 资料流程追踪弹窗 | **保留并简化**（去任务切换） |
| 数据预览 / 校验改值 / 血缘 / 入库 / 回执 / 入库向导 | **保留**，入口统一从 sources 进入，preview 作二级页 |
| 解析页上传 / 参数 / 报告 | **保留**，改为单文件 + file 键，从 sources 进入 |
| 抽取规则配置（三种模式 + 版本） | **保留**，仅参考文件下拉改键 |
| 入库规则配置（业务库 / 映射 / 字段对齐） | **保留**，引用锁口径改 |
| 数据看板 + 血缘回溯 | **保留**，溯源列与 iframe URL 改键 |
| 工作台四卡 + 待办 | **保留**，改按资料 state 取数 |
| review 占位壳页 | 保留，链接改向 |

## 9. 待用户拍板的 8 个决策点

| # | 决策 | 我的推荐 | 理由 / 代价 |
|---|---|---|---|
| D1 | 抽取规则表是否随清库保留？ | ✅ **已定：保留** | 用户 21:13 拍板。与入库规则一并留，`c1_load_table.rule_id` 有依赖 |
| D2 | 资料清单 sha256 去重去留？ | ✅ **已定：去除** | 用户 21:13 拍板。每次上传插新行；**必须 DROP `uk_file_sha` 唯一索引**，连锁改动见 §2.3b |
| D3 | 是否重建 migrations 目录与全新基线脚本？ | **推荐：重建**（待确认） | 存量已清，历史迁移无意义；原 DDL 可从 git 只读取回作模板。你之前有意删了 migrations，需重新确认 |
| D4 | 重放解析时旧回执/暂存/产物如何处理？ | **推荐：全清**（含 load_log 与 isolation），state 回 pending（待确认） | file_id 唯一键下保留旧回执会导致新记录被唯一键 skip；代价=历史入库记录丢失（用户已同意清库） |
| D5 | preview / parse 是并入 sources 弹窗还是保留二级页？ | ✅ **已定：保留独立页** | 用户 21:13 拍板，认可"塞进弹窗难用"的理由；sources 作唯一入口 |
| D6 | 业务表旧溯源列（task_id/task_file_id）怎么办？ | **推荐：新代码只写 file_id + record_id，旧列留着不管**（待确认） | 平台无权改用户业务表 DDL；若需彻底清理请你手工 DROP |
| D7 | 规则删除的"被引用禁删"守卫如何改？ | **推荐：改为"有资料行引用该规则版本时禁删"**（待确认） | 保住审计约束；只需把 guards 的查询表从 c1_task 换到 c1_doc_file |
| D8 | 工具私有键（`/files/` 首段、导出目录 `task_<id>`、日志名）是否一并改名？ | **推荐：全改为 file**（待确认） | 名字统一才不留 task 残渣；代价=旧日志/旧导出目录名与新键不一致（存量可清则无碍） |

> 剩余待确认 5 点（D3/D4/D6/D7/D8）均为工程默认项，如无异议按推荐执行；若有不同意见，请在开工前指出。

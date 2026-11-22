# 功能映射表（页面 ↔ 代码 ↔ 表）

日期：2026-11-21 ｜ 配套：结构 B 轮（catalog 按域拆分＋前端资产迁 web/）＋P2c（单一提取入口，入库时绑定目标）。
用途：从产品功能/页面/表名任一入口，一跳定位到代码。目录分层不变
（路由 app.py · 引擎 service.py · 存储 store/ · 提取 pipeline/），
本表补上「层 ↔ 功能」的横向对照。

## 〇、目录总览

```
c1_extract/
├── app.py              HTTP 路由＋请求校验＋异常分类（不含引擎）
├── service.py          运行引擎：STATE/LOCK 单任务串行、launch/launch_load/run_load
├── config.py           唯一配置源（路径/模型/服务/凭据引用名 C1_EXTRACT_DB）
├── params.py           调试参数 schema/校验/说明（上传页面板）
├── collect.py          记录收集：build/apply_mapping（模板选择器）
├── tasklog.py          运行日志（logs/ 纯文本＋结构化进 STATE）
├── store/              数据访问层（DB 唯一事实源）
│   ├── catalog/        目录 repo，按域拆分（__init__ 全量重导出）
│   │   ├── files.py      源文件域
│   │   ├── templates.py  模板域
│   │   ├── tasks.py      任务域（含隔离区）
│   │   └── load.py       入库域（数据源/映射/回执）
│   ├── content.py      暂存内容门面（extract 经 artifact；records 经三表）
│   ├── content_db.py   暂存三表读写＋跨任务查询/台账
│   ├── artifact.py     产物附件接缝
│   ├── artifact_db.py  产物 BLOB repo（task_file 粒度）
│   ├── loader.py       目标业务库：连接/introspection/字段校验/写入/transform/门禁
│   ├── db.py           conn_ref 解析＋connect_direct（目标库）；纯连接不建表
│   ├── errors.py       类型化业务错误（StoreError.code → HTTP）
│   └── migrations/001_baseline.sql
├── pipeline/           提取引擎：engines/ocr/pdf/plain/ppstruct/resplit/structure/runner
├── adapter/            引擎信封 → c1-extract 标准（base/paddle/pdfplumber/plain）
├── extract_report/     对照报告生成器：cards.py＋builder.py＋templates/（Jinja2）
├── web/                全部前端资产（七页＋共享件＋报告内联件，见 §二）
├── accept_records_db.py  验收套件 A（7 项，临时服务 8799）
├── accept_artifacts_db.py 验收套件 B（6 项，临时服务 8797）
├── export_artifacts.py   产物按需导出（审计/file:// 用）
├── check_env.py          环境自检（依赖/目录/模型缓存）
└── docs/ data/ logs/ tmp/
```

## 一、按页面查（产品功能 → 代码）

| 页面 | 路由（app.py） | 引擎/逻辑 | 存储模块 | 表 | 前端（web/） |
|---|---|---|---|---|---|
| 工作台 `/` | `GET /`（计数复用 `/api/tasks`＋`/api/staging/ledger`，无新端点） | 快速提取＝`POST /api/upload` 同通道 | — | — | home.html/js/css ＋ shell ＋ wizard |
| 提取 `/extract` | `GET /extract` · `POST /api/upload` · `GET /api/status` · `/api/logs` · `/api/params` | service.launch/run（task_batch）· register_file · resolve_template；pipeline 提取；adapter 投影；collect 收集 | catalog.files/tasks/templates · content_db · artifact_db | extract_file · task · task_file · template(_version) · staging 三表 · artifact | upload.html/js/css ＋ shell ＋ hint |
| 资料 `/sources` | `GET/POST /api/sources` · `DELETE /api/sources/{id}` · `GET /srcfiles/{id}` | service.register_file（sha 去重） | catalog.files | extract_file(+content) | sources.html/js ＋ shell |
| 模板 `/templates` | `/api/templates` CRUD · `…/versions` CRUD | —（纯目录 CRUD） | catalog.templates | extract_template · extract_template_version | templates.html/js/css ＋ shell |
| 校验 `/review` | `GET /api/tasks/{id}/staging` · `PATCH …/staging/{tf}/{idx}` · `POST …/review` · `GET /api/staging/query` · `/api/staging/ledger` | app._review_target（只读守卫） | content.patch_record/set_review/get_records · content_db.query_fields/ledger | extract_staging_record/field/lineage | staging.html/js/css ＋ stage ＋ shell ＋ wizard |
| 入库规则 `/rules` | `/api/load/datasources` CRUD/test/tables/columns · `/api/load/tables` CRUD | loader.connect_datasource/list_tables/list_columns/validate_fields | catalog.load | extract_load_datasource · load_table · load_table_field | load.html/js/css ＋ templates.css（表单 token）＋ shell |
| 任务 `/tasks` | `GET /api/tasks(+/{id})` · `POST /api/tasks`（资料库发起）· `POST /api/tasks/{id}/load`（可带目标）· `GET …/load-log` · `…/quarantine` · `…/extract` | service.launch_load（目标解析→预检→门禁→**全过才绑定**→写入）/run_load（回执→隔离→重试）· loader.preflight/write_record/apply_transform/review_gate | catalog.tasks/load · content · artifact | extract_task/task_file · load_log · quarantine · staging 三表 · 目标业务表 | tasks.html/js ＋ shell ＋ wizard（回执抽屉＋入库向导） |
| 对照报告 | `GET /extract-report`（重定向）· `GET /files/{tf}/{path}`（白名单，raw 403） | extract_report.builder.build（生成期内联资产）· artifact_db 读 | artifact_db | extract_artifact | 报告 BLOB 自包含（内联 report/stage/hint/lightbox，不走 /static） |

## 二、web/ 资产归属

- **七页私有**：home.* · upload.* · sources.*（无 css，用 shell）· templates.* · staging.* · load.* · tasks.*（无 css，用 shell）
- **页面共享**：shell.css/js（全局壳＋列表小件＋回执抽屉＋流程条）· wizard.css/js（四步入库向导，home/tasks/staging 挂载）· hint.css/js（「?」悬浮说明：提取页＋报告）· stage.css/js（舞台：校验台＋报告）
- **地址＝产品名词（2026-11-22 修理历史命名）**：页面 URL 用 `/extract /review /rules`，模板文件名仍是历史内部名（upload.html=提取、staging.html=校验、load.html=入库规则）；`/api/*` 路径是内部契约未动，与页面地址无关。
- **报告专用（生成时内联进 BLOB）**：report.css/js · lightbox.html
- 页面引用一律绝对路径 `/static/<file>`（app.py 挂载 web/）；改文件名须同步 HTML 引用。
- 已入库的 9 份报告是静态 BLOB，资产搬迁不影响它们；新报告由 builder 从 web/ 内联。

## 三、按表名反查（表 → 代码）

| 表 | 模块 |
|---|---|
| extract_file | store/catalog/files.py |
| extract_template / extract_template_version | store/catalog/templates.py |
| extract_task / extract_task_file / extract_quarantine | store/catalog/tasks.py |
| extract_load_datasource / extract_load_table(_field) / extract_load_log | store/catalog/load.py |
| extract_staging_record / field / lineage | store/content_db.py（门面 content.py） |
| extract_artifact | store/artifact_db.py（门面 artifact.py） |
| （建表/升级） | store/migrations/001_baseline.sql 人工安装脚本（无自动迁移器，2026-11-21 裁决删门禁） |

## 四、按命令查

| 想做什么 | 命令 |
|---|---|
| 起服务（8765） | `D:/miniforge3/envs/paddle/python.exe c1_extract/app.py` |
| 单测（36） | `python -m unittest c1_extract.test_load_rules c1_extract.test_collect_selectors` |
| 验收 A（7 项，8799） | `python c1_extract/accept_records_db.py` |
| 验收 B（6 项，8797） | `python c1_extract/accept_artifacts_db.py`（与 A 严禁并行） |
| 导出产物 | `python c1_extract/export_artifacts.py` |
| 环境自检 | `python c1_extract/check_env.py` |

## 五、跨功能共享件（改一处动全身）

- **service.py STATE/LOCK**：单任务串行闸门，上传/资料库发起/入库共用。
- **store/db.py**：平台库凭据只经 conn_ref（C1_EXTRACT_DB）；建表/升级人工跑
  migrations/001_baseline.sql（自动迁移门禁已删）；
  目标库走 connect_direct（数据源行参数，明文裁决仅限 load 数据源）。
- **store/errors.py ＋ app.py 异常处理器**：StoreError→400/404/409，
  DB 故障→503，编程错误→500。
- **task/task_file 键**：所有产物/暂存/回执/隔离都挂 task_file 粒度，
  重跑不覆盖历史。
# C1 提取（c1_extract）

把 week-02 验证过的提取能力封装成一个**本地 Web 工具**：浏览器上传文件 → 后端提取 → 生成对照报告。
**DB 是唯一事实源**（MySQL）：原件字节、产物附件、暂存记录全部入库，磁盘只有跑完即清的
临时 scratch。每个 task_file 一份独立自包含的 `对照报告.html`（BLOB，经 `/files/<task_file_id>/`
白名单路由访问），每次上传各自独立、互不覆盖；页面与报告资产（`web/`）只有一份。
支持**多页 PDF 逐页提取 + 报告翻页切换 + 跨页表格拼接**（页码留空 = 全部页）。
`weekly/week-02/` 的代码与产物**完全不改动**，本目录自包含。
存储设计见 [docs/design-task-schema.md](./docs/design-task-schema.md)（任务化命名 + 去外键，
取代 [design-c1-storage.md](./docs/design-c1-storage.md) 的表名/列名表述）。
**找代码**：[docs/feature-map.md](./docs/feature-map.md)——页面↔路由↔引擎↔存储↔表↔前端文件对照。

## 启动

```bash
D:\miniforge3\envs\paddle\python.exe c1_extract/app.py
# 浏览器打开 http://127.0.0.1:8765
```

服务栈是 **FastAPI + uvicorn**（本机已装）。生产式启动（从 `20-CV/` 目录）：

```bash
uvicorn c1_extract.app:app --host 0.0.0.0 --port 8765 --workers 1
```

- **平台库必选**：DSN 配在 `config.PLATFORM_DB`（形如 `mysql://user:pass@host:3306/db`，
  环境变量 `C1_EXTRACT_DB` 优先，方便部署覆盖）。**建表/升级人工执行**
  `store/migrations/001_baseline.sql`（无自动迁移器，2026-11-21 裁决删除；
  脚本全 IF NOT EXISTS＋INSERT IGNORE，重跑无副作用）。DB 不可达：上传 503 不建任务、
  运行中写失败整任务 failed、读端点 503，不降级。
- 加载大模型的服务建议 **workers=1**：多 worker 会各自加载一份模型，内存翻倍；要扩容应横向起多实例，前面挂 Nginx 反代。
- 内置 `GET /healthz` 健康检查；配置（端口、模型、阈值、路径）集中在 `config.py`。

## 独立部署

整个 `c1_extract/` 目录拷到目标机器即可运行：不依赖仓库其它目录、不 import week-02、路径全部由 `config.ROOT` 推导。

```bash
# 1) Python 3.10（3.9~3.12 均可），建议独立虚拟环境
python -m venv .venv && .venv\Scripts\activate     # Linux: source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt

# 2) 配置平台库（二选一）
#    改 config.PLATFORM_DB 默认值，或 环境变量 C1_EXTRACT_DB=mysql://...

# 2.5) 人工建表（无自动迁移器）：对平台库执行 store/migrations/001_baseline.sql
#      mysql -h <host> -u <user> -p <db> < store/migrations/001_baseline.sql
#      脚本全 IF NOT EXISTS＋INSERT IGNORE，已建库重跑无副作用；升级改表 likewise 人工执行

# 3) 装完自检（只读、不加载模型，秒级）
python check_env.py

# 4) 启动
python app.py                                     # http://127.0.0.1:8765
uvicorn c1_extract.app:app --host 0.0.0.0 --port 8765 --workers 1    # 生产式（从上级目录）
```

`requirements.txt` 锁的是本机实测版本，几个容易踩的点：

- `paddleocr 3.7.0` **不声明 paddlepaddle**，必须单独安装；GPU 机器把 `paddlepaddle==3.2.0` 换成对应 CUDA 版 `paddlepaddle-gpu`。
- `cv2` 来自 `opencv-contrib-python==4.10.0.84`（paddlex 的 `ocr` extra 指定），**不是** `opencv-python`，两个都装会冲突。
- `paddlex[ocr]`（不是 `[ocr-core]`）：图片/扫描件路线的 PP-StructureV3 依赖门禁要完整 ocr extra；ocr-core 只够 PDF 文本层路线的 OCR 文字识别。
- 上传走 base64 JSON，所以不需要 `python-multipart`；Starlette 1.x 的静态文件也不需要 `aiofiles`。
- `pdfplumber` / `PyMuPDF` 是本项目自己用的，paddle 不带，别漏。
- `jinja2` 渲染报告 HTML 模板（`extract_report/templates/`），纯 Python 无二进制依赖。

**离线 / 内网部署**：PaddleX 官方模型在首次推理时联网下载到 `${PADDLE_PDX_CACHE_HOME:-~/.paddlex}/official_models`（数百 MB）。先在联网机器跑一次把模型下全，再把该目录一起拷贝，并设置 `PADDLE_PDX_CACHE_HOME` 指向其**上级**目录。`check_env.py` 会检查缓存是否就绪。

**环境变量**（除 `C1_EXTRACT_DB` 外全部可选，默认值见 `config.py`）：

| 变量 | 默认 | 用途 |
|---|---|---|
| `C1_EXTRACT_DB` | 无（默认用 `config.PLATFORM_DB` 内置 DSN） | 平台库 DSN（回显仅 host/库名，不带密码） |
| `C1_EXTRACT_DATA_ROOT` | 包内 `data/` | secrets / 备份等数据根目录 |
| `C1_EXTRACT_HOST` | `127.0.0.1` | 监听地址，服务器设 `0.0.0.0` |
| `C1_EXTRACT_PORT` | `8765` | 端口 |
| `C1_EXTRACT_MAX_FILE_MB` | `20` | 单文件上限（改它时同步改 `upload.js` 的前端 20MB 校验） |
| `C1_EXTRACT_WARMUP` | `0` | 设 `1` 则启动时预加载模型 |
| `PADDLE_PDX_CACHE_HOME` | `~/.paddlex` | 模型缓存根目录，离线部署必设 |

容器化时把 `official_models` 缓存打进镜像，`CMD python app.py`、`HEALTHCHECK curl -f http://127.0.0.1:8765/healthz`，并保持 `--workers 1`。

## 模型加载时机（默认全程懒加载）

| 阶段 | 发生了什么 | 耗时 |
|---|---|---|
| 服务启动 `import app` | 只有 FastAPI + config，**连 paddleocr 库都不 import**（实测 0.53s） | ~0.5s |
| 首次上传 → 后台线程动态加载 `pipeline` 包 | 才 import cv2 / pdfplumber / pymupdf / PIL，仍不碰模型权重 | 1~3s |
| 首次 OCR `engines.ocr()` | 构造 PaddleOCR（仅「PDF 文本层」路线的文字源 / resplit 子格重 OCR 用） | 20~40s |
| 首次表格 `engines.structure()` | 构造 PPStructureV3 **单次推理**：parsing / layout / 整页投影 / 表格 / 矫正图一次产出 | 20~40s |
| 后续文件 | `_OCR` / `_STRUCT` 模块级单例复用 | 每张几秒 |

- 两级懒加载：包级 import 在后台线程，权重只在第一次真正用到时实例化。上传页、`/healthz`、`/extract-report` 都不会触发模型。
- **CSV / 有文本层 PDF 完全不加载表格结构模型**（直读 / pdfplumber）；图片 / 扫描件一律单次 PPStructureV3 推理（无网格预筛门槛）。
- 单例按**进程**缓存，重启会重新加载；`--workers 1` 保证只有一份。
- 想改成「启动即加载、首个请求不等」：设 `C1_EXTRACT_WARMUP=1`，在 FastAPI lifespan 里同步预热，`python app.py` 与 `uvicorn c1_extract.app:app` 都生效。默认关闭。

## 目录结构（模块化）

```
c1_extract/
├── requirements.txt           独立部署依赖（实测版本锁定）
├── check_env.py               部署自检：缺包 / 目录 / 模型缓存 / 平台库
├── config.py                  唯一配置源：模型 / DPI / 阈值 / 路径 / 环境变量
├── params.py                  调试参数 schema（顺序=优先级）+ 校验 + 快照
├── tasklog.py                 结构化运行日志（service.STATE + logs/task_<id>.log）
├── app.py                     FastAPI 路由 + 请求校验 + 包自举 + 异常处理器
├── service.py                 运行引擎：STATE/LOCK + launch + launch_load/run_load（入库）
├── __init__.py                支持 uvicorn c1_extract.app:app 包方式启动
├── accept_records_db.py       records 入库七项验收（临时服务 8799/8797，含 P2b 入库链路）
├── accept_artifacts_db.py     产物入库六项验收（两套脚本严禁并行）
├── export_artifacts.py        DB → 磁盘树按需导出（file:// 直开 / 审计 / 迁移）
├── store/                     存储层（DB 唯一事实源）
│   ├── db.py                  驱动接缝 + conn_ref 解析（纯连接，不建表）
│   ├── errors.py              类型化业务异常（StoreError/BadRequest/NotFound/Conflict→HTTP 码）
│   ├── migrations/            001_baseline.sql 人工安装脚本（部署/改表时手动对库跑）
│   ├── catalog/               目录元数据 repo，按业务域拆分（__init__ 全量重导出，
│   │   │                      调用方 catalog.xxx() 不感知边界）
│   │   ├── files.py           源文件域（extract_file ＋ content 原件字节）
│   │   ├── templates.py       模板域（template / template_version）
│   │   ├── tasks.py           任务域（task / task_file / quarantine）
│   │   └── load.py            入库域（load_datasource / load_table(+field) / load_log）
│   ├── content.py             内容门面（extract 经 artifact，records 直委托 content_db）
│   ├── content_db.py          staging 三表：get/save/patch/set_review/query_fields
│   ├── loader.py              入库引擎接缝：数据源直连 / introspection / 字段契约
│   │                          / transform（trim·number）/ write_record（应用层 upsert）
│   ├── artifact.py            附件门面（kind/mime 推断）
│   └── artifact_db.py         extract_artifact BLOB（键＝task_file_id，应用层级联删）
├── adapter/                   提取信封 → 模板记录的适配层（base.py hydrate 派生视图）
├── pipeline/                  提取层
│   ├── engines.py             模型单例（懒加载；表格模型按 doc_unwarp 分槽缓存）
│   ├── ocr.py                 逐行文字 / 置信度 / 四点框 + 带框 PNG
│   ├── pdf.py                 页数 / 逐页渲染 / 文本层 / pdfplumber 表格 + bbox
│   ├── plain.py               CSV / TXT 直读
│   ├── ppstruct.py            PPStructureV3 单次推理：官方 parsing / 表格 / 矫正图
│   ├── resplit.py             图片人工列边界：切黏连格 + 子格重 OCR 归位
│   ├── structure.py           表头分离 / cells 网格 / CSV 导出 / 跨页续表拼接
│   └── runner.py              extract_one() 统一入口：逐页提取 + pages 信封编排
├── extract_report/            对照报告生成器（纯 Python＋Jinja2，不含页面资产）
│   ├── cards.py               数据准备 + 选模板（坐标 rect / 行 / 文档块 / data URI）
│   ├── builder.py             组装对照报告（内联 web/ 资产，每 task_file 一份）
│   └── templates/             Jinja2 HTML 模板（autoescape，结构与逻辑分离）
├── web/                       全部前端资产（/static 挂载于此）
│   ├── <page>.html/js/css     六页：upload / sources / templates / staging / load / tasks
│   ├── shell.css/js           全局壳＋列表页共用小件＋回执抽屉
│   ├── stage.css/js           舞台共用件（校验台＋报告）
│   ├── hint.css/js            「?」悬浮说明（上传页＋报告）
│   └── report.css/js · lightbox.html   报告专用（生成时内联进 BLOB）
├── data/                      backup/（迁移前整库备份；DSN 已入 config.py，无 secrets.json）
├── logs/                      任务日志（运行时生成，每任务一个 task_<id>.log）
└── docs/                      设计稿与交接文档
```

### 存储模型：task / task_file id，无批次戳、无外键

一次上传 = 一个 **task**（`extract_task` 行），批内每个文件 = 一个 **task_file**。
没有批次时间戳、没有持久 input/output 目录：

- 原件字节进 `extract_file.content`（sha256 去重，重复上传不重复入库）。
- 产物附件进 `extract_artifact`（键＝task_file_id + 相对名，LONGBLOB，应用层级联删）。
- 暂存记录进 staging 三表（record / field / lineage，field 是查询投影）。
- **校验台**（`/staging`，P1a）：双击格改值→edited，✓ 确认 / ✗ 拒绝（review_state），
  状态筛选＋批量确认待审；改值格琥珀标记（title 显原值），original 永不覆盖；
  loaded 任务只读（前端横幅＋后端 409）。无 task 参数时渲染**任务级校验台账**
  （`/api/staging/ledger`：每任务汇总记录数＋待校验/已修改/已确认/已拒绝计数，
  点任务行展开其文件子行，点文件行进入）。
- 提取期间的工作目录与输入副本都是 tempfile scratch（`tmp/input/in_*` / `tmp/work/case_*`），跑完即清。
- URL 全用 id：`/staging?task=<task_id>&file=<task_file_id>`、`/files/<task_file_id>/<产物>`、
  `/srcfiles/<file_id>`。`GET /extract-report` 重定向到最新 task_file 的报告真实地址。
- 重复上传同一文件不覆盖历史：新 task 新 task_file 新附件，旧 task 完整可回溯。
  批内重名文件加 `-2` 区分。task id 在上传响应与 `/api/status` 的 `task_id` 字段可见。
- **无外键约束**：引用完整性归应用层（delete_file 引用守卫；重跑覆盖显式先删子表）。

### 入库链路（P2b/P2c，design-p2b-datasource.md＋design-p2c-load-entry.md）

- **数据源**（`extract_load_datasource`）：一个数据源＝一个 MySQL 库，
  host/port/账号/密码/库名**明文存库、页面可见可编辑**（2026-11-21 裁决，暂不加密）；
  首启幂等种「产品库」默认行（解析 `C1_EXTRACT_DB`）。日志与测试连接回显永不打印凭据
  （仅 host:port/库名）。平台库自身凭据仍走 conn_ref。
- **映射**（`extract_load_table` ＋ `extract_load_table_field`）：一行＝数据源×目标表×模板
  ＋write_mode（upsert/insert/update），字段行＝模板字段→目标列＋业务键勾选。
  只写已有表（不自动建表）；同物理表可被不同模板各建一行（UNIQUE 三元组）。
- **审计守卫**：数据源被映射引用后 host/port/库名锁定（409，账号密码可改，换目标＝新建）；
  映射被任务引用后只读（PATCH/DELETE 409，回执语义）。
- **流程（P2c 单一提取入口）**：上传只选文件＋模板（不再携带 mode/入库目标，旧契约键 400）
  → 提取校验（门禁：全部 confirmed 才可入库，否则 409 带计数）→ 任务详情/校验台「入库…」
  抽屉选数据源＋映射（按 数据源×任务模板 双过滤）→ **校验/门禁/预检全过才绑定目标并写入**
  （失败不留绑定，可另选；已绑定任务重试沿用原目标，带新目标 409）→ 逐条回执
  （`extract_load_log`，唯一键幂等，重跑跳过）＋数据级隔离（`extract_quarantine` stage=load，
  重试无回执记录）。transform（trim/number）只在入库时消费，暂存原值永不改。
  loaded/partial 任务记录只读。
- **/load 页**：左数据源列表（试连/编辑/删除）右映射列表（字段行抽屉编辑）；
  入库目标在任务入库时选择（tasks/staging 共用抽屉，shell.js）。

**按需导出**（file:// 直开 / 审计 / 迁移出口）：

```bash
D:\miniforge3\envs\paddle\python.exe c1_extract/export_artifacts.py --out D:/tmp/c1_export
# 可选 --task <id> 只导一次任务
```

```
<out>/output/task_<id>/<源文件名>/…   产物 BLOB 原字节（对照报告.html 在树内，file:// 直开）
<out>/output/task_<id>/records.json   DB 三表重建的任务级信封
<out>/sources/<源文件名>              原件字节（重名加 _<id> 区分）
```

**源码模块化，产物自包含**：`builder.py` 生成报告时会把 `hint.css` / `stage.css` / `report.css` /
`hint.js` / `stage.js` / `report.js` / `lightbox.html` 内联进 HTML（stage 件与校验台共享，先于页面件），
图片 / extract.json / CSV 链接一律**相对路径**，
所以报告经 `/files/<task_file_id>/` 访问时资源全部成立；导出后**双击用 `file://` 直接打开也能正常显示图片与全部交互**；
整份信封 JSON 以紧凑 `<script type="application/json">` 嵌在报告里（全报告仅一份，首次打开 tab 才美化），
不依赖在线 fetch。上传页是线上页面，走 `/static/` 外链资源。
**多文件批次**：上传页报告区顶部出现**文件页签**（单文件不显示），点击在下方 iframe 切换各文件自己的报告；
`GET /extract-report` 重定向到最新 task_file 报告的 `/files/` 真实地址（相对路径资源需在该 task_file URL 下解析）。

HTML 结构全部在 `extract_report/templates/*.html`（Jinja2，**autoescape 默认开启**，
不再手写转义），CSS / JS 在 web/ 独立文件，Python 只做数据准备与模板选择——
IDE 高亮、改结构 / 样式不必碰 Python 逻辑。迁移经「重构前后 DOM 逐节点对比」
验证（15 个真实 case + 3 个合成边界 case 全部等价），交互零回归。

## 支持格式与产物

| 输入 | 路线 | 主要产物 |
|---|---|---|
| png / jpg / bmp / webp / tif | PPStructureV3 单次推理（无预筛门槛） | `source.<ext>`、`boxes.png`、`pages/rectified.png`、`table_N.csv` |
| PDF 有文本层 | 逐页渲染 + OCR + pdfplumber 直读表格 | 单页 `source.png`/`pages/p1.png`；多页 `pages/p{n}.*`；表格带单元格 bbox |
| PDF 无文本层 | 同图片路线（逐页单次推理） | 同上 |
| CSV / TXT / MD | 纯文本直读，不跑 OCR | `source.<ext>`、`table_N.csv`（CSV） |

每个 task_file 固定有一份 `extract.json` 附件（**紧凑 JSON**），统一为**文件信封**：
`file/kind/encoding/params_snapshot/page_count` + `pages:[pageRec…]` + `stitched_tables`。
单页文件也是 `pages:[1]`（无双形态、无兼容 shim）。每页 `pageRec` 只存三样：官方 `parsing`（裁掉代码不读的死字段）+ `structured_tables`（加工后的表 + 单元格坐标）+ 该页元信息/诊断。
文字投影 `texts/scores/boxes`、版面 `layout`、行数/均值**不落盘**，由 `adapter.base.hydrate()` 在渲染期**逐页**从 `parsing` 现算（官方 JSON 为唯一事实源，派生视图不重复存储）；raw 表中间态已删。
文本层 PDF / CSV 路线无 `parsing`，其 OCR 投影是唯一文字记录，直接存储。
跨页续表合并进 `stitched_tables`（每格带 `page/space`，供报告页感知回溯）。详见 [docs/result-json-anatomy.md](./docs/result-json-anatomy.md)。
`rectified.png` 只在真正抽到表的图片 / 扫描件里生成（多页为 `p{n}_rectified.png`）。

## 「横线端点自动还原」是怎么做到的（有文本层 PDF）

问题背景：像 103 那种银行流水，**表格有大量横线、却没有竖线**（列靠对齐排出来）。
按文字位置猜列边界会把页眉混进来、还会漏列 —— 实测 103 只能猜出 7 列，真表是 8 列。
根因是表头「余额」「摘要」是两个单元格，但「额」和「摘」的字间距只有 **2.0pt**
（其它列之间是 14~90pt），小于 pdfplumber 默认的词合并阈值 3pt，于是被拼成一个
「余额摘要」词，文字法就少看到一个列起点。调小 `x_tolerance` 到 1.5 虽能拆开，
但那是碰巧适合这份 PDF 的魔法数字，换份文件就失效；读矢量线接缝才是稳定的解法。

关键观察：**视觉上横线是贯通的一条线，但 PDF 内部把它存成了多段首尾相接的独立线段**
（103 表头下沿那一行就是 8 段，接缝空隙 0.0pt，所以肉眼看不出断口）。
每段的左右端点 `x0/x1`，恰好就是相邻两列的分界线；这些"接缝 x"在每一数据行重复出现
（103 每条出现 26 次）。算法读的是 PDF 矢量对象里的这些端点，不是去图上找视觉断口 ——
这也是为什么肉眼看不出短段、自动还原却依然成立。所以：

```
原始 PDF 矢量线（每张表 26 行横线）
   ├─ 取所有横线的 x0 与 x1 端点
   ├─ 只在「出现 ≥2 次」的端点里留候选   ← 滤掉噪声短线
   ├─ 8pt 内的近邻端点合并成一条边界     ← 抗坐标抖动
   └─ 得到 9 条竖边界 = 8 列 → 喂给 pdfplumber 的 explicit_vertical_lines
```

实测这条边界序列还原出的表，与当初人工抄的模板**逐字一致**（25×8，含换行）。
**为什么不处处都用端点法**：一页里有多张表时，各表的横线端点会混在一起
（21/23/26 端点法给出 11 条边界，实际每表只有 5~6 列）。所以用判据区分：

| 情况 | 端点数 vs 文字数 | 用哪种 |
|---|---|---|
| 单表 + 有列名被粘连 | 端点 = 文字 + 1（103：9 vs 8）| **端点法**（补上被粘的列）|
| 单表、列边界清晰 | 端点 = 文字（20：7 vs 7）| 文字法 |
| 一页多表端点混叠 | 端点 ≫ 文字（21：11 vs 7）| 文字法（避免列数虚高）|

一句话：**端点法负责补「文字看不出的隐藏列」，文字法负责「多表时各管各的」，
判据就是两者边界数是否只差 1。** 这整套逻辑在 `pipeline/pdf.py`，没有任何文件名 / 数字
被写死；真遇到判据都不适用的特殊版式，才在上传页用 `column_lines` 临时给一组 x 坐标。

## 报告包含什么

- **多页文件翻页切换 + 单行整合页头**：页码留空（默认）的多页 PDF 渲染成 `.filecard` 容器 + 逐页子卡片（只显示激活页），左图吸顶、右栏 tab 与单页一致。翻页组件为**窗口式页码胶囊**（« ‹ 页码窗口 › » + 跳页输入框）：常显首末页与当前页±1，其余收进 …，页数再多也只占一小条；支持点页码、首/末/上/下页、输入页码回车跳转（不在提取范围的页码就近落位）、焦点在卡片内时左右方向键翻页。**悬浮叠在源图底缘之上**（绝对定位、不占布局、**不压缩图宽**；`report.js alignPagers` 按当前激活 imgwrap 的实测底缘/水平中心锚定，窗口伸缩、切页、切视图、图片加载后仍贴在源图上；窄屏回退为横向静态条）。页头**只保留一个文件级整合头、单行**（实测约 42px），做成**色带 + 左侧 accent 竖条 + 2px 下边线**，**上边线由所在卡片/文件外框提供（上下都有线）**；多页 `.filecard` 自带**外框 + 圆角 + 投影**（内部逐页卡去自身边框避免双线），文件区域边界一眼可分（文件间距 34px、单页卡 26px，外框色 `#c9d4e4`）：**左**=标题(15px/600)+类型/页数标签+跨页合并标签；**右**（`.fh-right`，多页为 `.pagehead-slot`）=路线/行数/表格/可疑行(仅>0 琥珀警示)/图链接/extract.json，切页时由 JS 从该页 inert `<template>` 注入更新。**诊断类（平均置信度/耗时）不进页头**（在文字行/JSON/日志里查），可疑行为 0 时不显示——页头只留 actionable 信息且全部右置，不再两行堆高。整份信封 JSON 独立成**「整份 JSON」tab**（与本页 JSON/文字/表格/文档同款面板），不再塞在跨页 tab 底部。切页**保留当前激活 tab 与合并表子页签**，并**同步合并表滚动位置**（页交接行悬停不再高频来回抖动），翻页不丢上下文。
- **跨页表格拼接**：相邻页「同列数 + 同坐标空间 + 列 x 边界对齐 + 表头相同（空白归一化）」的续表合并成一张逻辑表（去重复表头、行连续），每格保留来源 `page/space`；悬停/点击合并表单元格**自动切到对应页**并高亮该格（页感知回溯）。回溯走 **filecard 级 mousemove 委托 + 格键去重**（切页会换掉光标底下的 DOM 副本，逐副本 enter/leave 会被 stale mouseleave 清掉高亮而「卡住」）；切页**同步合并表滚动位置**，页交接行悬停不再高频来回抖动。判据保守，宁可不拼不误拼。另支持**无重复表头续页**（2026-11-20）：列位置子集对齐 + 续页贴顶 + 首行像数据 → 回收被误标成表头的首行数据、被裁空列（含中间列）按主表布局补齐，报告以琥珀徽标提示「无表头续页首行已回收」；判据与落地细节见 [docs/design-headerless-stitch.md](./docs/design-headerless-stitch.md)。**一个文件可有多条独立跨页链**，各链以子页签区分。合并表不再单列底部面板，而是收进**每个页卡片的「跨页合并」tab**（与文字行/表格/文档/JSON 并列），消除割裂感。
- **CSV 下载/预览按 tab 分口径**（2026-11-20）：**表格 tab** 的下载/预览只给**当前页这张表**（`table_N.csv`，自包含 data URI）；被并入合并表的页表保留「跨页合并 N」徽标与分段说明，但下载/预览仍是本页片段。**跨页合并 tab** 的下载/预览给**完整合并表**（`stitched_N.csv`）。提取层**逐页碎片 CSV 全部入 BLOB**（与表格 tab 口径一致），合并表另存 `stitched_N.csv`。「打开 CSV」改为**弹窗直接预览**（复用辅助弹窗，渲染成表格可滚动），不再是变相下载。
- **原图 / 矫正图**切换（有矫正图时才出现切换条），点击图片全屏放大：滚轮以光标为中心缩放、拖拽平移、1:1 原像素、双击切换、Esc 关闭、叠加框开关、新窗口打开原图。
- **提取内容**：逐行 OCR 文字 + 置信度条，与左图识别框双向高亮；有文本层 / 纯文本另给全文折叠区。**文字叠加框默认隐藏**（报告初始干净不画常显框，点图右上角「显示叠加框」开启）；悬停文字行仍即时高亮对应框、点击钉住，全屏放大默认跟随内联的隐藏状态。
- **表格内容**：带表头的 HTML 表格、多表 tab 切换；下载 CSV 仅本页这张表（自包含 data URI），「预览 CSV」弹窗直接看表（不下载）。
- **单元格坐标回溯**：默认一个框都不画，悬停只高亮那一格、点击钉住（再点取消），并自动切到该表的坐标宿主视图；「显示整表网格」是默认关闭的调试开关。
- **完整 JSON**：折叠查看、下载 `extract.json`、一键复制。单页卡片 JSON tab 展示**文件信封存储形态**（含 pages/stitched_tables，ppstruct 页含 parsing、不含派生投影）；多页给「本页 JSON」tab 展示该页 `pageRec`、另给独立「整份 JSON」tab 展示文件信封（不再塞跨页 tab 底部）；**整份信封以紧凑 JSON 嵌在 filecard 的 `<script type="application/json">` 里（全报告仅一份），首次打开 tab 时才解析美化**——不逐页卡片内联（避免多页大文件报告平方级膨胀），也不 fetch（`file://` 直开时浏览器禁止 fetch 本地文件）；美化结果按 filecard 缓存、多页卡片共享；复制按钮按所在面板取 `jsonpre`，多份不串。BLOB 紧凑存储，tab 渲染时再 `indent=2` 美化。

三套坐标来源严格互斥，用 `coord.space` 区分：文本层 bbox 与 OCR 框基于 `source.<ext>`；
表格模型**开矫正**时单元格框基于 `pages/rectified.png`（转正 + 去扭曲，1:1 无需逆变换）；
表格模型**关矫正**时 `output_img` 与原图逐像素一致，框直接叠 `source.<ext>`。
纯文本标注「无图像载体」。报告里的「坐标宿主」标签会写明本次用的是哪种。

## 运行日志与进度

上传页自带**运行日志面板**，处理过程中实时显示，不用另开终端：

- 顶部进度条 + 当前阶段（load / case / ocr / table / report / done），完成后 100%。
- 结构化日志按级别配色：`INFO` 灰、`OK` 绿、`STEP` 蓝、`WARN` 黄、`ERROR` 红。
  每条带 **相对运行时间 `t`、相对上条耗时 `ms`、阶段名**，可直接看出瓶颈
  （例：`+90640ms` 落在表格模型那条 = 首次加载十来个子模型）。
- 记录了过去看不到的内部决策：载体判定、预筛横竖线数、模型加载开关、
  表格策略命中、坐标空间、OCR 行数/置信度、每张表行列数与填充率。
- 日志同时落盘到 `logs/task_<id>.log`（每任务各一份，历史可查），
  页面「下载日志」或 `GET /api/logs` 可取当前任务纯文本。

实现在 `tasklog.py`：一个 `TaskLog` 实例对应一次任务，同时写 `service.STATE['logs']`
（页面轮询 `/api/status` 拿结构化数组）、`logs/task_<id>.log` 和控制台（同格式实时打印）。**pipeline 只认一个
`emit(level, stage, msg)` 回调**，由 service 注入，提取层不 import Web 层，保持分层干净。

## 调试参数面板（badcase 用，按优先级排）

上传页的「调试参数」面板可直接调参，**只对本次上传生效**，改完即可对比效果。
参数定义（默认值 / 范围 / 说明 / 顺序）全在 `params.py::SCHEMA` 一处，前端从
`GET /api/params` 动态渲染，后端用同一份 schema 校验 —— 不存在前后端默认值漂移。
按重要 / 优先级自上而下：

| 优先级 | 参数 | 默认 | 调它能救什么 |
|---|---|---|---|
| ① 页面范围 | `page` | 留空 | **留空（默认）= 逐页全量提取整份 PDF** + 报告翻页切换 + 跨页续表拼接；填页码（1 起）= 只提取该页（超页数自动夹到末页）。`all` / 「全部」/ `*` 等同留空。多页即可能跨页，故默认全量并尝试拼接 |
| ② 表格识别 | `table_strategy` | auto | 强制 `text` 救无线框表；`lines` 按矢量线；避免纯文字页被伪抽 |
| ② | `column_lines` | 空 | 人工列边界，填 `x1,x2,x3,…`（≥1 个递增数字）。**文本层 PDF** 用 PDF 点（像素×72/DPI，单条不成列自动回退）覆盖自动推断；**图片/扫描件** 用原图像素，单条即可沿竖线切开模型黏连格并重 OCR 归位（仅 `doc_unwarp=off`）。常规无需填 |
| ③ 文字识别 | `det_thresh` / `box_thresh` | 0.3 / 0.6 | 漏检调低（0.2/0.4）、误检调高；predict 按次覆盖，不重建模型 |
| ④ 渲染精度 | `dpi` | 110 | 小字 / 密集表提到 150~200 更清晰；坐标同步缩放 |
| ⑤ 坐标回溯 | `doc_unwarp` | on | **电子版平整截图（如 108）设 off**：关闭方向分类 + UVDoc，单元格框直接叠原图、1:1 精确；旋转/弯曲扫描件保持 on（框叠矫正图）|

**参数快照**：每次上传的生效参数写进 `extract.json` 文件信封的 `params_snapshot`，
页码写进每页 `pageRec.page`；报告页头统计行内的「参数快照 · N 项」小胶囊点开悬浮下拉，
按优先级列出全部参数（不独立占行，点外部收起；`page=all` 显示「全部页」），运行状态 `/api/status` 也能看到。填错的参数会回退默认并在日志里给出警告，不会中断整批。

技术分界：`det/box_thresh`、`page`、`table_strategy`、`column_lines`、`dpi`
全是 predict 级 / 纯参数，**每批可不同、零额外开销**。
`doc_unwarp` 是唯一的引擎构造级参数：`engines.structure(use_unwarp)` 按开关
**分两个槽位缓存单例**，所以两种配置各只加载一次模型、互不污染，切换不会反复重建。
移动端 / server 识别模型仍未放页面（换模型要改 `config.py`，属实验模式）。

### `doc_unwarp=off` 适用与实测

108 是 103 那份 PDF 渲染出的**电子版平整截图**（910×1287，不旋转、不弯曲）。
UVDoc 默认无条件执行，对它会做无谓的非线性形变：实测单元格框被撑到
x=0.1~910（贴满整页），而真实表格只到 x≈882；`<td>` 还多出 25 个空格子。
关掉矫正后 `angle=-1`、矫正图与原图**逐像素差 0**、框范围 x=23.5~882 贴合真实表格，
于是 `coord.space='source'`、不再生成 `rectified.png`、报告无需视图切换。

> 注意与 week-02 那条「不要为拿坐标关 UVDoc」不矛盾：那条针对 **107 旋转扫描件**
> （关掉后 50 格有 12 格文字退化、且需要方向分类转正）。**按载体选**：
> 平整电子版 → off；旋转 / 弯曲扫描件 → on。107 与 108 是现成的 A/B 对照。

### 图片路线人工列边界重切（`pipeline/resplit.py`）

模型（PPStructureV3）会把相邻两列看成一格（108「摘要+余额」黏连，且 OCR 行本身
也跨列）。`column_lines` 在图片路线（含扫描 PDF）下触发确定性后处理：沿用户给的
竖线把黏连格切开 → 每个子格从原图 crop 单独重 OCR（检测器只看到一列，天然分开）
→ 文字按列归位。只治**结构**（谁归哪格），不治**识别**（字符级错字仍靠识别模型）。

- 坐标空间 = 原图像素（报告左图可直接量），仅 `doc_unwarp=off` 生效；on 时框在
  矫正图空间、与原图裁剪对不上，日志 warn 跳过。
- 108 实测：摘要/余额间空白竖带 x≈494–498，填 `496` + `doc_unwarp=off` → 23×7，
  余额、摘要分离（升级后无网格预筛，108 无竖线也自动进模型）。
- 已知边界：换版式需重新量 x（同版式可复用）；表头标签若模型框 y 范围偏到首行数据，
  重切后表头仍可能带噪（旧问题，非重切引入）；弯曲扫描件不适用（列线非直线）。

## 与 week-02 的关系（重要）

- **算法自包含复制**，没有 import week-02，满足「week 目录不动」。代价是存在**逻辑漂移风险**：以后改了 week-02 的提取逻辑，c1_extract 不会自动同步。稳定后建议把公共部分抽成单一真相源供两边复用（那一步需要动 week 目录，需另行确认）。
- **定位不同**：week-02 是 25 个 case 的批量回归 + 汇总指标 + 标准答案对照 + bad case 库；c1_extract 是单文件即时预览。新来一张图先看效果用 c1_extract，改完算法验证没跑偏仍要跑 `weekly/week-02/a_batch_ocr.py`。
- 有文本层 PDF 的列边界**不再写死任何 case**：`pipeline/pdf.py::_lines_from_edges()` 从 PDF 横线端点聚类还原（实测 103 与原先人工模板逐字一致），`auto_column_lines()` 用「端点数 == 文字数+1」判据决定用端点法还是文字法，避免一页多表时端点混叠。特殊版式才在上传页用 `column_lines` 参数临时覆盖。改名 / 换编号的 PDF 都不需要登记。

## FAQ：IDE 报 `No module named 'config'`（已解决，零 IDE 配置）

早期版本内部用**顶层绝对导入**（`import config` / `pipeline` / `report`）。运行时靠
`sys.path` 兜底没问题，但 PyCharm / Pylance 的静态分析**不会执行** `sys.path.insert(...)`，
它默认把工作区根（`algs/`）当模块搜索起点，那里没有 `config.py`，于是 9 个文件一起标红。

**现在改成代码自洽的方案，不需要改任何 IDE 配置**（`.idea` / `.vscode` / `pyrightconfig` 都不用动）：

| 位置 | 写法 | 作用 |
|---|---|---|
| `pipeline/*.py`、`extract_report/*.py` | `from .. import config` | 包内相对导入，静态分析器按目录层级就能解析 |
| `app.py`、`check_env.py` | `importlib.import_module(PKG + '.config')` 等动态加载 | 入口文件不再有静态的顶层绝对导入；`PKG` 取 `os.path.basename(ROOT)` |

关键是让所有内部模块**始终以「包」方式加载**：相对导入才成立，静态分析器也无需把 `c1_extract/`
标成 Sources Root / extraPaths。下面四种启动方式都实测通过：

```bash
python c1_extract/app.py                         # 从 20-CV/，脚本方式
cd c1_extract && python app.py                   # 从 c1_extract/，脚本方式
cd 20-CV && uvicorn c1_extract.app:app --workers 1
```

整个 `c1_extract/` 拷走、甚至改目录名也能跑（包名动态取）。**模型仍然懒加载**：`pipeline` / `report`
只在后台处理线程里动态导入，`import app` 依旧 0.5s、连 paddleocr 库都不碰。

如果 IDE 还显示旧报错，刷新一下语言服务缓存（PyCharm: File → Reload All from Disk；
VS Code: Reload Window）即可 —— 代码里已经没有任何顶层绝对导入了。

## 验收（配置库，不用 Docker）

```bash
# 从 20-CV/，两套脚本严禁并行（共用临时端口 8799/8797）
D:\miniforge3\envs\paddle\python.exe -u c1_extract/accept_records_db.py
D:\miniforge3\envs\paddle\python.exe -u c1_extract/accept_artifacts_db.py
```

各六项契约：records＝连接零副作用+投影往返 / 重跑级联 / patch / 跨任务查询 /
真链路（8799）/ 断库 503（8797 不可达 DSN）；artifacts＝连接零副作用+sha 自洽 /
真链路无持久磁盘+BLOB / /files mime+ETag 304+raw 403 / tasks+报告+暂存全查库 /
导出逐字节一致+records 重建 / 断库 503。破坏性操作只落合成 task，验完按 id 清理
（应用层级联：先子表后父表）；真实 task/file 只读；用户的 8765 全程不动。

## 已知限制 / 下一步

- 单任务串行、无鉴权、默认仅监听 `127.0.0.1`（可用 `C1_EXTRACT_HOST=0.0.0.0` 放开）；上传用 base64 JSON，单文件上限 20MB。**平台库必选**（`C1_EXTRACT_DB`），断库显式 503 不降级。
- 首次运行需联网下载 PaddleX 官方模型（数百 MB）；离线部署要预置缓存，见「独立部署」。
- 多页 PDF 默认（页码留空）**逐页全量提取 + 报告翻页切换 + 跨页续表拼接**（2026-11-19）；填页码只提取该页。拼接两条通路：重复表头（相邻页 + 同列 + 列对齐 + 表头相同）与无表头续页（列位置子集对齐 + 续页贴顶 + 首行像数据，2026-11-20）；判据保守，宁可不拼不误拼，版式差异大的续表保持各页独立。
- 参数面板现覆盖 9 项（第一梯队 8 项 + `doc_unwarp`）+ 参数快照 + 运行日志；识别模型 mobile/server 仍未放（换模型要改 `config.py`，属实验模式）。
- 自动列边界对「一页多表且各表端点混叠」的复杂版式仍是尽力而为；遇到新固定版式，直接在上传页填 `column_lines` 即可，不必改代码。

# 进度交接 · C1 存储演进完成态（2026-11-21）

> 用途：下次上班继续处理的入口文档。C1 五项演进已全部落地并验收。
> 设计稿：[design-c1-storage.md](design-c1-storage.md)（已批准并实现，取代
> [design-artifacts-db.md](design-artifacts-db.md) 的表结构/接缝表述；
> DB-only 契约仍有效）。records 三表设计见 [design-records-db.md](design-records-db.md)。

---

## 〇、最新一轮：任务化命名 + 去外键（2026-11-21，已完成，取代下文旧命名）

设计稿 [design-task-schema.md](design-task-schema.md)（已批准并实现）。下文 §一~§三 的
run / run_file / source_file / 001-006 等旧命名仅存档意义，**当前代码与库一律用新命名**：

- 表：`extract_task` / `extract_task_file` / `extract_file` / `extract_load_dest`；
  列 task_id / task_file_id / file_id / load_dest_id。**无外键**，级联归应用层
  （save_records 重跑显式先删 field/lineage；清理先子后父；delete_file 引用守卫 409）。
- 迁移：001–006 压成 **001_baseline.sql**（13 业务表全注释 + schema_version + 种子）。
  配置库已一次性升级（备份 `data/backup/pre_task_20261121011801.sql`，FK 17→0，
  schema_version=[1]，行数守恒），升级脚本用完即删。
- API/URL：`/api/tasks`、`/tasks` 页、`/staging?task=&file=`、`/api/staging/query?task=`；
  日志 `logs/task_<id>.log`；导出 `output/task_<id>/`、CLI `--task`。
- scratch 收进包内 `tmp/input`（in_*）/ `tmp/work`（case_*），跑完即清；
  app.py `_rmtree_retry` 应对 Windows 杀软瞬态句柄锁。
- 模板名不硬编码：`catalog.get_template_version()` 无参取第一个模板当前版本
  （用户已把种子模板改名「默认空模板」）。
- 验收：两套脚本各 **6/6 PASS**（顺序跑，严禁并行）；浏览器验证 tasks/staging/
  sources/上传金路径全过；用户 8765 跑新代码真实上传成功（task 41/42）。
- **当前库态**：task 21/30/41/42 全 previewed；file 3/19/26（建行/交行/招行流水）。
- **环境缺口已修（2026-11-21，用户批准）**：paddlex 3.7.2 原只装 `[ocr-core]`，
  图片/扫描件路线 PP-StructureV3 门禁要完整 `[ocr]` extra（21 包）→ 已
  `pip install "paddlex[ocr]==3.7.2"` 补齐 13 缺失包，requirements.txt 同步改
  `paddlex[ocr]`；paddlepaddle/numpy/opencv-contrib 锁版本零变动。
  **运行中的 8765 进程须重启才生效**（deps.is_dep_available 有 lru_cache，
  旧进程缓存了「缺包」判定）——当日已获授权重启并 Web 验证（task 57，合成已清）。
- **git 历史凭据**：secrets.json 与 pre_005/pre_006 备份曾在 git 历史（已推到公开仓库
  origin/feat-extract-pipeline）。**用户裁决（2026-11-21）：DB 密钥无所谓，不清历史、
  不轮换**——此事项关闭，不再提醒。

---

## 〇.5、P1a 校验台（2026-11-22，已完成；下一步 P1b）

设计稿 [design-p1-review.md](design-p1-review.md)（已批准并实现）。用户裁决：
P1a 先做；拒绝＝`review_state='rejected'`（不进 quarantine，隔离表只管引擎级失败）；
P1b 模板消费＝选择器＋重命名（transform 留 P2）。

- staging 页原地升级校验台（不另起页，血缘舞台整套复用）：双击改值（PATCH→edited）、
  ✓ 确认 / ✗ 拒绝（POST review 批量）、状态筛选 chips＋批量确认待审（仅当前文件
  pending+edited）、改值格琥珀标记（title 显原值）、loaded 只读（横幅＋409）、
  无 task 参数渲染任务选择器；各页 nav「校验」启用。
- 新路由：`PATCH /api/tasks/{id}/staging/{tf}/{index}`、
  `POST /api/tasks/{id}/staging/{tf}/review`；store 加 `set_review`，
  `patch_record` 拒未知键。**零 DDL**（VARCHAR 无枚举约束；baseline 注释补
  rejected，线上库注释未动——装饰性，不 ALTER 共享库）。
- 验收：两套脚本顺序跑各 **6/6 PASS**；浏览器金路径全过（8799 临时服务＋合成
  task，验完清净）。修了一处测试数据依赖：[1/6] src_real 改要求 ≥2 条记录
  （用户新增单记录 task 53–56 居 DESC 首位会让 2→1→2 级联退化 1→1→1）。
- **当前库态**：task 21/30/41/42/51–56（51/52 failed＝修复前依赖错误；
  53–56＝用户截图 jpg previewed）；file 3/19/26/33；records 126 / field 1819 /
  lineage 1819 / artifact 90。合成数据全清，用户数据零变动。
- **8765 已跑 P1a 代码**：用户 2026-11-21 13:31 自行以 `python app.py` 重启
  （PID 19696，取代 agent 上轮的 uvicorn 后台进程）；PATCH 路由探针证实新代码在跑。
- 下一步 **P1b**：模板管理页（CRUD＋版本）＋ collect 选择器/重命名——模板三段
  JSON 现存而无人消费（collect.py 仍 P0 透传），管理页与消费须同轮做。

---

## 〇.6、小重构轮（2026-11-21，已完成；P1b 前置）

用户裁决「小重构后再 P1b」。范围＝A 错误分类＋B 前端去重（C collect 单测骨架
随 P1b 同轮）；路由拆分押后。两轮均已落地并验收。

- **A 错误分类**：`store/errors.py` 类型化异常 StoreError(code,msg)/BadRequest(400)/
  NotFound(404)/Conflict(409)；app 异常处理器 StoreError→对应码、
  MySQLError/OSError/LookupError→503『平台库不可用』、其余→500；移除 22 处 catch-all；
  upload/tasks_create 加 launched 标志＋finally `_rmtree_retry`（修 scratch 泄漏）。
- **B 前端去重**：新建 `assets/stage.js`（cardOf/wantViewOf/toast/cursorHint/hitCell
  含 polygon 射线法/pagerPages/renderPagerInto/alignPagerTo/bindStageLightbox 工厂）
  ＋`assets/stage.css`（舞台/框族/pager/lightbox 共享规则）；report.js 821→~600 行、
  staging.js 807→~640 行改钩子调用；report.css/staging.css 只留页面特有规则；
  builder 内联 stage 件（hint→stage→report 顺序）保 file:// 自包含；staging.html
  经 /static 外链 stage 件。shell.js 归一 escHtml/fmtSize/kindOf/thumbHtml/b64 等，
  upload.js/sources.js 删本地副本。上传页自己的取坐标 lightbox 未动。
- **验收**：A、B 两轮各两套脚本顺序跑 **6/6 PASS ×2**；B 轮浏览器金路径全过
  （8799 临时服务＋合成 task 105＝CCB 3 页 29 记录）：报告页 3 页卡/pager 锚定/
  hover-pin/Alt+click lightbox 钩子/boxes 克隆/点克隆框回跳 pin/翻页；校验台
  29 行/共享 hitCell 点图定位/血缘 lightbox（153 框 syncBoxes）/双击改值→edited/
  ✓确认→confirmed/翻页 page2；两页控制台零消息。合成 task 105 child-first 清净，
  基线还原 records 135/field 1867/lineage 1867/artifact 98(14870953B)/file 5。
- **当前库态**：tasks 21/30/41/42/51/52/53–56/80（51/52 failed）；files 3/19/26/33/56。
- **8765 注意**：前端改动经 /static 即时生效，但 **A 轮 app.py/store 改动需用户
  重启 8765 才载入**（当前进程仍是 P1a 代码）——方便时重启一次即可。

---

## 〇.7、UI 打磨轮（2026-11-21，已完成；用户四条需求）

用户提出并裁决：跨任务搜索**删 UI 留 API**；校验入口做**文件级台账**。

1. **跨任务搜索清理**：staging 页折叠面板（HTML/JS/CSS）已删；
   `/api/staging/query` 保留（验收 [4/6] 仍测，台账/P2 可复用）。
2. **导航改名**：四页 nav「记录」→「任务」；tasks 页 title/h1/空态同步；
   校验台「返回记录」→「返回任务」。
3. **文件级校验台账**：新端点 `GET /api/staging/ledger`（content_db.ledger()，
   按 task_file GROUP BY 记录数＋pending/edited/confirmed/rejected 四态计数，
   INNER JOIN record 只列有记录的文件，新文件在前）。/staging 无 task 参数
   渲染台账表（任务/文件/模板/记录/四态/状态/时间），点行进入
   `/staging?task=&file=`；替换原下拉选择器。
4. **提取页历史报告**：右侧 idle 占位改为默认加载**最新 previewed/loaded 任务**
   的报告；顶部 histbar 下拉（任务号·文件名·时间）切换历史；多文件任务
   filetabs 下移一层（histbar 38px＋tabs 38px，iframe top 76px）；
   上传开始切进度态、完成后落新任务并刷新下拉（skipRender 防重复加载）。
   单文件 showResult 改直接落 cases[0] 的 /files/ 地址（不再依赖最新重定向）。
- **验收**：两套脚本顺序跑 **6/6 PASS ×2**（基线不变 135/1867/1867/98/5）；
  浏览器只读验证（8799 临时服务，未产生合成数据）：台账 10 行计数正确、
  点行→task 80 校验台 9 条；提取页默认 task 80 报告、切 task 42 双文件页签
  布局 38/76px、iframe 报告真实加载、页签切换正常；控制台零消息。
- **8765 注意**：前端经 /static 即时生效，但 **/api/staging/ledger 是新后端
  路由，8765 重启前台账入口会报读取失败**（连同 A 轮错误分类一起，重启一次全载入）。

---

## 〇.8、任务级台账反转 + 报告/校验台打磨 + B 编排拆分（2026-11-21，已完成）

用户四条需求。台账方向**反转**上轮裁决（文件级→任务级）；目录重构用户授权
「最彻底是 B 就按 B，收益不大改 A」→ 执行 **B 核心（拆编排）**，**不挪验收/CLI
脚本**：A 的脚本挪动会破坏脚本自举（ROOT/PKG）与套件硬编码路径＝改安全网换装饰。

1. **任务级校验台账**：`content_db.ledger()` SQL 不变（per-task_file GROUP BY），
   Python 聚合为 task 级 items（含 `files` 子列表，四态计数求和）。/staging 无 task
   渲染任务行（▸ caret＋「N 个文件」），点任务行展开文件子行，点文件子行进入
   `/staging?task=&file=`。API 形状变化对验收无影响（套件不引用 ledger）。
2. **报告参数快照不独立占行**：paramsnap 移入页头 `.sub` 统计行内，改 `<details>`
   小胶囊「参数快照 · N 项」，点开 absolute 悬浮下拉（440px/64vh/sticky 表头），
   点外部收起（report.js）；页头高度零增长（82→82px）。
3. **校验台分页与报告页对齐**：根因＝旧 renderViewer 每次切页 innerHTML 重建→
   新 img 未 load→高度塌缩→alignPagerTo 锚高→load 后落回＝「上跳」。修复＝与
   report 同架构**全页预渲染**（buildViews 一次 innerHTML，showPage 只切 hidden）
   ＋img width/height 属性预留宽高比＋方向键（scoped `.stgwrap`，跳过输入控件）
   ＋切页保留 curView；stage.js lightbox 克隆已 removeAttribute 宽高，兼容。
4. **B 编排拆分**：新建 `service.py`（292 行）＝STATE/LOCK＋step/_on_log＋
   safe_name/_now/_kind_of＋register_file/resolve_template＋launch＋
   _STAGE_FRAC/_ingest_case/rmtree_retry/task_batch；`app.py` 813→543 行只剩
   路由＋请求校验＋异常处理器＋_dedup_name/_json_body/asset。4 个函数去下划线
   改公开名，其余**逐字迁移**（AST 逐块比对 HEAD 确认 14/14 一致）。所有入口
   不变（python app.py / uvicorn c1_extract.app:app / 两套验收 / export）。
- **验收**：两套顺序 **6/6 PASS ×2**（基线 135/1867/1867 · 98/14870953 · 5 不变）；
  8799 只读浏览器（台账展开/导航、三页预渲染切页 pager 零位移、方向键、lightbox、
  新报告胶囊）＋冒烟（healthz/status 形状/logs 404/task21 live=None/ledger 9 任务
  task42=2 文件 47 条）；控制台零消息；scratch 无残留。
- **存量报告 caveat**：报告是上传时生成的**静态 BLOB**（extract_artifact），
  模板/CSS 改动只对新上传生效；存量 9 份报告仍是旧 paramsnap 独立行排版。
  如需统一须一次性重建报告 BLOB＝修改真实数据，**先备份＋用户批准**再做（可选后续）。
- **8765 注意**：本轮 ledger 任务级形状＋B 拆分＋A 轮错误分类都需**用户重启 8765**
  才载入（前端 /static 即时生效）。

---

## 〇.9、校验台按钮层级＋血缘细竖条＋序号/标题微调（2026-11-21，已完成；三轮迭代）

1. **任务页「预览数据」→校验台是刻意设计**（P1a 裁决：暂存页原地升级成校验台，
   不另建预览页）。用户问是否刻意→答是；「文案暗示只读、实际可改值」的盲点已提出，
   用户裁决**先不动**（tasks.js 未改）。
2. **页头按钮层级**：「对照报告」＝实心主色 `btn mini`（#2563eb 白字，最醒目）；
   「返回任务」统一改名**「返回」**（全工程仅此一处返回钮），保持 ghost mini 白底退后。
   第一版淡蓝底 .reportbtn 被用户否（不够显眼、反被返回压过）→ 改实心主色并删 .reportbtn。
3. **血缘回溯收起 bug＋样式（两轮迭代到终态）**：根因＝hideLineage 整块 `hidden=true`，
   只有 initViewer（换文件）复显，pinField/selectRecord 不展开→收起后永久打不开。
   终态＝**默认收起成右侧 34px 细竖条**（用户裁决）：`.lineage.collapsed`
   width/max-width:34px＋align-self:stretch（随表格等高）＋lhead 竖排
   （#ltitle/.ltoggle writing-mode:vertical-rl，隐藏 .stage/.lsub/.lhint）；
   整条竖栏可点展开（lhead 委托），展开态仅箭头钮折叠；
   **点单元格/行自动弹出**（pinField/selectRecord 调 showLineage()）；
   收起时 clearSel＋closeLb；换文件保留折叠偏好；窄屏 media 回退横条。
   按钮 `btn ghost mini ltoggle`（id ltoggle）＝**左右小箭头**（第三轮用户裁决，
   取代文字「收起/展开」）：收起态 ‹（title 展开血缘回溯）／展开态 ›（title 收起），
   竖条内 writing-mode:horizontal-tb 保持横排；aria-expanded 同步。
   staging.css 局部 .dclose 覆盖已删（shell.css 共享 .dclose 仍供任务/上传页使用，未动）。
4. **第三轮三条微调**：① 箭头见上；② **ltitle 去冗余**——恒为「血缘回溯」，
   选中记录号只在 lsub 显示一次（`页N · 原图/矫正图 · 选中记录 #N`／未选 `· 全表`），
   不再「记录 #N 血缘回溯」重复；③ **显示序号 1 起**——renderTable idx 格与
   `recordNo(i)`（框提示/lsub）统一 `(r.index==null?i:r.index)+1`；
   **data-i 与 PATCH/review API 下标仍 0 起**（契约未动）；报告页本就 1 起，无需改。
- **验证**：node --check；8799 只读浏览器：默认 34×943 竖条＋表格 1044 全宽、三页图
  仍预加载（展开瞬时）；点格弹出 527px＋钉住框 1＋胶囊 18px/262px 图高 714 零位移；
  竖条点击/按钮/点格三路展开全通；光箱开→收起即关；task42 换页签保留折叠；
  返回 href=/tasks?task=21；控制台零消息；截图确认默认/展开两态。
  第三轮 DOM 级复核（8799 task21/file25，只读未 PATCH）：idx 首=1 尾=29 共 29、
  recordNo(0)=1、框提示「记录 #1」、data-i=0 且 API index=0 不变；竖条 arrow=‹
  title=展开·w=34·横排；点格后 arrow=› title=收起·lsub「选中记录 #1」·ltitle 恒「血缘回溯」；
  再收起 arrow=‹；控制台零消息（视口隐藏未截图，DOM 断言为准）。
  **本轮纯前端页面资产**（staging.html/css/js）：builder 只内联 stage/report 资产，
  报告 BLOB 与后端零改动→两套验收无回归面，未重跑（node＋浏览器金路径为准）。
- **8765**：/static 即时生效，本轮改动无需重启即可见。

---

## 〇.10、三页紧凑规整统一＋「未指定任务」遗留清理（2026-11-21，已完成）

用户裁决：资料/校验/任务三页统一**紧凑、规整**（实施操作向，降认知负担）；
范围＝**全局壳收紧**（shell.css 共享，上传页/资料选择抽屉一并生效）；
页头开发向说明句**删除**。

1. **「未指定任务」遗留**：staging.js 无 task 时写死「（未指定任务）」是旧下拉
   选择器时代产物（现无 task＝任务级台账入口）。改＝无 task 时 tasktag 置空＋hidden。
2. **shell.css 共享 token 收紧**：body 行高 1.6→1.5；pagebody padding 18/20/40→14/18/28；
   pagehead gap 10→8、margin 14→10、h1 17→16；table th 8/12→6/10、td 7/12→5/10；
   namecell gap 9→8；**thumb 40→28**；toolbar input 6/10→5/9、btn 6/16→5/14、
   btn.mini 3/10→2/9；banner 8/14→6/12、margin 12→10；empty 34→24；pager 10/12→8/10；
   drawer dhead/dbody 12/16→10/14、dfoot 10/16→8/14。
3. **页头说明句删除**：sources「上传即登记（sha256 去重）…」、tasks「任务目录来自
   平台库 task / task_file 表投影」整行删（操作指引已在空态/工具栏）。
4. **导航文案统一（四页）**：模板禁用提示 P1→**P1b 开放**（upload/sources/tasks，
   staging本就P1b）；navnote 相位前缀 P0→**P1**（upload/sources/tasks「P1 · 预览链路」，
   staging「P1 · 校验台」）。
5. **staging.css 间距对齐**：filetabs/reviewbar margin 10→8、lhead 9/12→7/10、
   pickbar 12/14→10/12。**上轮终态的 34px 竖条/箭头/序号规则一律未动**。
6. **台账入口与资料/任务同构（用户指出三处不一致后修）**：删 pickbar 整行
   （「校验台账＋长提示」多余行，.pickbar CSS 一并删）；无 task 时**隐藏「返回」**
   （tasklink）＋filelinks＋tplbadge，页头 h1 改「校验台账」；**新增右对齐工具栏**
   `#ledgerbar`＝搜索 `#lq`（任务 id/文件名/模板，客户端过滤）＋进度筛选 `#lprog`
   （全部/有待校验/有已修改/校验完）。staging.js 台账渲染抽成 `renderLedger()`
   （ledgerItems＋ledMatch＋ledCnt），fetch 后与 input/change 时重渲染；
   无匹配空态文案区分「没有匹配的任务」vs「暂无可校验的记录」；任务行加
   title 提示展开。面板内直接表格（.ledgerwrap 顶边框删）。**工作态页头不变**
   （返回/对照报告/模板徽标在、ledgerbar 隐藏）。
- **验证**：node --check；8799 只读浏览器三页：资料行高 39（原约54）/thumb28/td5-10/
  页头32/说明句无；任务行高33/页头32（与资料一致）；台账入口「未指定任务」消失、
  tasktag hidden、9 任务行、**页头32 与资料/任务齐＋右对齐搜索220px/进度筛选、
  无返回、无 pickbar、面板首子即表格**；搜索「建设」→1、「默认空模板」→9、「80」→1、
  清空→9；筛选 todo→7/done→2/edited→0；点任务行展开子行1；无匹配空态文案正确；
  工作态页头不变（返回 href=/tasks?task=21、对照报告、模板徽标在、ledgerbar 隐藏、29 行）；
  工作态行高32/序号1–29/竖条34箭头‹/点格自动弹出›/lhead展开7-10/ltitle恒「血缘回溯」/
  lsub选中#1（上轮无回归）；控制台零消息；截图确认校验台＋资料页紧凑规整
  （台账页截图时视口隐藏，DOM 断言为准）。验完停服务、8799/8797 free、tmp 空。
  **纯前端页面资产**（shell/staging css＋四页 html 文案＋staging.js 一行）：
  builder 只内联 stage/report 件，报告 BLOB 与后端零改动→两套验收无回归面，未重跑。
- **8765**：/static 即时生效，无需重启。

---

## 〇.11、P1b 模板管理＋collect 选择器消费（2026-11-21，已完成）

设计稿 [design-p1b-templates.md](design-p1b-templates.md) 已批准并实现。用户拍板：
编辑器＝**结构化字段行表单**；源表/源列取值＝**参考文件预览辅助**（无参考回落手填）。
**零 DDL**（三段 JSON 语义由设计稿 §二约定；transform 存而不消费，留 P2）。

1. **collect.py**：`_candidate_tables(doc)` 候选表有序列表（非合并页表在前、
   stitched 在后，passthrough 与选择器共用此序）；`build(doc, tpl)` 分发——
   mapping 空/无 fields＝passthrough **逐字保留**；`apply_mapping` 单源表
   `table{index|header_contains}` × `column{name|index}`＋重命名（target＝记录键）。
   缺表→0 条（previewed 不 failed）；缺列→''＋lineage[]；lineage 复用 `_anchor`
   （字段级溯源不变）。
2. **service.py**：`resolve_template` 补带 schema/mapping/transform 三段 JSON
   （原先丢弃→选模板等于没选）；task_batch 消费点 `collect.build(rec, tpl)`；
   collect 日志区分「passthrough」/「映射 N 字段」。
3. **catalog/API**：`get_template/create_template/create_version/update_template/
   delete_template/list_versions`（版本＝不可变快照＋current 前移；改名/说明不建版本；
   删除被任务引用→409；重名→409；JSON 非对象→400）；`list_templates` 补 version_count。
   app 7 路由（POST/GET/PATCH/DELETE templates＋versions 三 route）＋`/templates` 页。
4. **前端 templates.html/css/js**：列表 panel＋页头工具栏（搜索＋新建）与资料/任务
   同构；编辑抽屉＝名/说明＋参考文件 select（previewed 任务文件→
   `/api/tasks/{id}/extract`→候选表 select「#i · page/stitched · 表头预览」）＋
   字段行（目标名 input＋源列 select/按列序号＋删行＋添加字段）＋保存为新版本＋
   版本历史（设为当前）；无参考回落手填 index/header_contains；删除 confirm＋409 提示。
   候选表/键序 JS 与 collect 同规则（合并页表跳过、col_n/重名下标）。
   **nav「模板」四页启用**（off→href=/templates）。
5. **单测骨架（C 项）**：`test_collect_selectors.py` 11 项（无 DB 纯函数）：
   空映射＝passthrough 逐字一致/index＋name 重命名键序/header_contains 首命中/
   column index/缺列''＋[]/缺表 0 条/stitched scope/合并页表跳过/重名表头键/无 target 跳过。

- **验证**：单测 11/11 OK；**两套验收顺序 6/6 全 PASS**（本轮动 service/catalog/app
  有后端回归面，重跑；基线 135/1867/1867＋98/14870953＋5 守恒）。浏览器金路径（8799）：
  UI 新建「P1b验证模板」（参考 21:25→1 张 stitched 候选表 17 源列；3 字段含按序号 6）
  →保存 v1→改名保存 v2（current 前移）→版本历史设当前 v1↔v2 往返→上传下拉见 v2→
  API 上传 CCB 原件（template_version_id=5）→task 154 previewed 29 条，键序
  [账号,交易借方,对方姓名]，lineage stitched/page1/bbox/raw_text 齐全→校验台徽标
  「P1b验证模板 v2」＋点格钉住（lsub 页1·原图·选中#1，1 定位框）→删除守卫 409
  「该模板已被任务引用，禁止删除」；控制台仅预期 409 无 JS 错。合成 task 154
  child-first 清净＋模板删除 200，**基线全还原**（tasks 21/30/41/42/51–56/80、
  templates 1/versions 1）；停服务 8799/8797 free、tmp/input+tmp/work 空。
- **8765**：须用户重启一次载入 P1b（模板 CRUD 路由＋/templates 页＋collect 消费）。
  重启前 nav「模板」点击 404、选模板不生效（旧 resolve_template 丢 JSON）。

---

## 〇.12、P2 入库模式（2026-11-21，已完成；dest/mapping 形状已被 §〇.13 P2b 取代）

设计稿 [design-p2-load.md](design-p2-load.md) 已批准并实现。用户拍板 6 项：
① 触发＝**上传时选 mode=load**＋目的地＋映射（预登记入库意图）；② 执行＝**校验完
手动点「入库」**；③ 门禁＝**仅 confirmed**（pending/edited/rejected 任一存在整任务
409 带计数）；④ **rejected 也阻止**（出口＝校验台 ✓ 重新确认）；⑤ **只写已有表**
（不自动建表）；⑥ transform＝**最小集 trim＋number**（入库时消费，暂存值保真）。
**零 DDL**（load 三表已在 001 baseline）。

1. **db.connect(ref, autocommit, migrate=True)**：`migrate=False` 用于目标业务库
   ——绝不把平台表建进人家库（设计级陷阱，先于 loader 修掉）。
2. **store/loader.py**：`connect_dest`（LookupError→BadRequest）；`list_tables/
   list_columns`（information_schema，DATABASE() 内）；`validate_column_map`
   （全覆盖/无重复目标列/upsert·update 须业务键）；`preflight`（目标表存在＋列存在）；
   `apply_transform`（trim/number 纯函数，失败保留原值＋error 条目）；`review_gate`；
   `write_record`＝**应用层 upsert**（SELECT 1 WHERE bk→UPDATE 非键列/INSERT，
   不依赖唯一索引）；`_ident` 反引号双写防注入＋值全参数化。
3. **catalog**：dest/mapping CRUD（重名/引用守卫 409；透传模板禁建映射 400）；
   `set_task_load`；`add_load_log`（SELECT-then-INSERT，UNIQUE 回执防重）；
   `list_load_logs`；task 投影补 load 信息块。
4. **service**：`launch_load`（STATE 单任务串行复用，mode/stage='load'；门禁 409
   带四态计数；二次 preflight）；`run_load`（回执跳过→transform→写目标库→回执；
   **错误分类**：IntegrityError/DataError/ProgrammingError/LoadRecordError→单条
   隔离继续；其他 MySQLError/OSError→连接级中止保留回执→partial；平台库写失败→
   failed）；终态 loaded/partial；loading/partial/loaded 记录只读（_review_target 守卫）。
5. **app**：upload/tasks_create mode=load 早失败预检（`_load_preflight`：dest/mapping
   归属＋模板匹配＋目标库 preflight，失败不建 task）；/load 页＋dests/mappings CRUD
   路由＋test（仅 safe_detail）/tables/columns introspection＋load-log/quarantine
   读路由＋POST /api/tasks/{id}/load。
6. **前端**：/load 双 panel 页（目的地抽屉＋映射抽屉：dest→tables→columns→模板
   字段行→列 select＋业务键 checkbox）；upload mode radio＋destsel/mapsel（按模板＋
   目的地过滤）；tasks 详情入库信息行＋门禁计数＋入库/回执按钮；staging 入库按钮＋
   loading 轮询自动刷新＋只读横幅；**shell.js 共用回执/隔离抽屉**（两页同 markup）；
   templates 编辑器 transform 下拉（无转换/trim/trim+number，路由原先丢 transform 已修）；
   nav「入库」五页启用。
7. **单测**：test_load_rules.py 22 项（transform/gate/column_map/write_record，
   FakeCur 无 DB）＋collect 11 项＝33 OK。

- **验证**：**两套验收顺序 7/7＋6/6 全 PASS**（records 新增第 7 项：合成目标表
  `_accept_p2_load`＋合成模板/映射，dest conn_ref=C1_EXTRACT_DB 同实例；覆盖
  introspection/映射契约 400/上传预检 400×3/门禁 409（pending·rejected）/全确认→
  loaded/回执逐条/loaded 重入 409＋只读 409/引用禁删 409/transform 消费＋超长值
  DataError 隔离→partial/ALTER 后重试幂等（回执跳过）/partial 只读 409/跨 task
  upsert 命中→update 行数不增；**新增全量基线守恒检查**（清理后逐项比对）。
  浏览器金路径（8799）：/load 抽屉建目的地＋测试连接（仅 host:port/库名）→映射
  抽屉 introspection→字段行＋业务键→保存→提取页 mode=load 三 select 联动→UI 上传
  CCB 原件 task 184（29 条预登记）→校验台门禁横幅 409→全部确认→入库→loading
  横幅＋自动刷新→loaded 只读→回执抽屉 29 条（首 insert 余 update，账号列恒同值
  upsert 收敛 1 行）→任务详情入库信息行＋gateinfo 计数（task 185）＋入库 alert 409
  →模板 transform 下拉往返；控制台仅预期 409 无 JS 错。合成 task 184/185 child-first
  清净＋映射/目的地/模板删除＋DROP 表，**基线全还原**（135/1867/1867＋98/14870953
  ＋5 files＋tasks 21/30/41/42/51–56/80＋templates 1/versions 1＋load 三表空）；
  8799/8797 free、tmp/input+tmp/work 空。
- **已知缺口（不预埋）**：无 reviewer 身份（B 轮审计平台化首补）；隔离区只读无解决
  UI；partial 记录只读→坏值记录无法修值只能重试（永久坏值＝永久 partial，裁决接受）；
  无回滚/删除已入库数据；单目的地单表（无多表 union/多目的地扇出）。
- **8765**：须用户重启一次载入 P2（load 路由＋/load 页＋upload mode＋入库按钮）。
  重启前 nav「入库」404、上传页无入库模式。

---

## 〇.13、P2b 入库数据源重构（2026-11-21，已完成；取代 §〇.12 的 dest/mapping 形状）

设计稿 [design-p2b-datasource.md](design-p2b-datasource.md) 已批准并实现。用户三裁决：
① **数据源含库名（扁平）**——一个数据源＝一个库，左列表主从布局，不做两级树；
② **默认数据源明文落行**——迁移解析 C1_EXTRACT_DB 写「产品库」行（host/账号/密码
明文，与手建同形态、页面可编辑；secrets 轮换后过期需手动同步，接受）；
③ **extract_load_table＝映射绑定**——一行＝数据源×表×模板＋write_mode，同物理表
可被不同模板各建一行（UNIQUE 三元组），字段行＝模板字段→目标列＋is_business_key。
**明文例外范围**：只覆盖 load 数据源密码（存库明文、页面可见可编辑）；日志永不打印
凭据、测试连接回显仅 host:port/库名；**平台库自身凭据仍走 conn_ref 不变**。

1. **表**（001 重写）：`extract_load_dest`→`extract_load_datasource`（name UNIQUE/
   host/port/user/password/db_name）；`extract_load_mapping`→`extract_load_table`
   （UNIQUE ds×tpl×table）＋`extract_load_table_field`（UNIQUE table×field、
   table×column）；`extract_task.load_datasource_id/load_table_id`；
   `extract_load_log.datasource_id`＋UNIQUE(task_file_id,record_index,
   datasource_id,target_table)——数据源身份锁定，回执无需 db_name 列。
2. **迁移**（零成本窗口：旧 3 表 0 行＋task 无引用）：先查状态→整库逻辑备份 31.8MB
   `data/backup/pre_load_ds_20261121_201236.sql`（**本机无 mysqldump**，Python
   SHOW CREATE TABLE＋INSERT、BLOB→X'hex'）→DROP/CREATE/ALTER→种产品库→基线守恒
   →脚本用完即删。**坑**：升级脚本漏重建 extract_load_log（DROP 了没 CREATE），
   套件首跑发现、按 001 原 DDL 补建（空表）——迁移脚本须逐表对照 001 清单。
3. **db.connect_direct(p)**：数据源行直连（不 migrate、utf8mb4、connect_timeout=5）；
   平台库 connect 门禁不变。catalog.ensure_default_datasource 幂等种子（尽力而为，
   断库启动不炸）。
4. **契约**：loader.validate_fields 改字段行形（全覆盖/无重复列/无重复字段/
   upsert·update 须业务键；列存在性归 preflight）；fields_to_map→(cm,bk)；
   write_record/transform/gate/回执跳过/错误分类**全不动**。
   **两条新审计规则**：数据源被映射引用→host/port/db_name 锁定 409（账号密码可改，
   换目标＝新建）；映射被任务引用→只读 409（PATCH/DELETE 均禁，回执语义）。
5. **前端**：/load 左数据源列表（试连/编辑/删除＋映射数 badge、选中高亮）右映射列表；
   数据源抽屉（密码 type=text 明文＋目标锁定 hint）；宽映射抽屉（模板→introspection
   目标表→列 select＋业务键 checkbox；编辑回填字段行 data-col；任务引用→全禁用＋
   只读 hint）；upload destsel→dssel（选项「名称 · host/库名」），loadFields→
   load_datasource_id/load_table_id；tasks 详情「入库数据源」行（datasource_name＋
   db_name＋目标表）；shell.js 回执抽屉零改动。
6. **单测**：test_load_rules column_map→validate_fields 12 项（字段行形）＋
   transform/gate/write_record 不变＋collect 11＝**36 OK**。

- **验证**：两套验收顺序 **7/7＋6/6 全 PASS**（records item7 重写：产品库种子/
  数据源 CRUD＋试连/introspection/映射×2 同表不同模板/字段行详情/契约 400×2/
  重复映射 409/目标锁定 409＋密码可改 200/上传预检 400×3/无引用可删可编辑/
  门禁 409（pending·rejected）/全确认→loaded/回执逐条/loaded 重入 409＋只读 409/
  被引用禁删禁改 409/transform＋隔离→partial/重试幂等/跨 task upsert→update；
  清理后基线守恒）。浏览器金路径（8799）：/load 左右布局＋种子自动选中→抽屉建
  数据源（凭据程序内自种子行复制、不回显）→试连回显 host:port/库名→映射抽屉
  introspection→字段行＋业务键→保存→编辑回填正确→合成 task 201（2 条 confirmed）
  →任务详情门禁通过＋入库按钮→点击入库→loaded→回执抽屉 2 条 insert（trim 消费）
  ＋隔离 0→映射编辑只读锁/数据源编辑目标锁 UI 全对→upload mode=load dssel/mapsel
  模板＋数据源双过滤→控制台无错。合成 task 201/file 162/tf 217 child-first 清净
  （**staging field/lineage 键＝record_id**，须子查询先清）＋ds3/lt4/tpl11 删除＋
  DROP _browser_p2b_load（用户批准），**基线全还原**（135/1867/1867＋98/14870953
  ＋5 files＋tasks 21/30/41/42/51–56/80＋task_file 12＋templates 1/versions 1＋
  数据源仅产品库 id1＋load 三表/回执/隔离全 0＋schema [1]）；8799/8797 free、
  tmp/input+tmp/work 空。
- **已知缺口（不预埋）**：沿用 §〇.12（reviewer 身份 B 轮/隔离处置 UI/loaded 回滚/
  多表 union/扇出）；新增：数据源密码明文（裁决接受，加密未立项）；secrets 轮换后
  产品库行需手动同步。
- **8765**：须用户再重启一次载入 P2b。累计未重启载入：A 轮错误分类＋台账任务级＋
  B 拆分＋P1b＋P2＋P2b。

---

## 〇.14、B 结构清理轮（2026-11-21，已完成；零功能变更）

用户质疑「工程代码与业务模型没有对应、前端全在 extract_report」→ 诊断两个真实
坏味道：catalog.py 935 行上帝模块（7 域混杂）＋extract_report 历史名误导（页面
资产混在报告生成器里）。给 A（垂直功能模块，更彻底/业内现代趋势）vs B（保层
结构清理，推荐）；用户裁决「先按照 B 搞…先保证功能啥的不受影响」。**A/混合
（共享核心＋域分组）留作未来轮，设计先行**。

1. **catalog.py → store/catalog/ 包**（按域拆）：files.py（6 函数）/templates.py
   （10）/tasks.py（10 含 quarantine）/load.py（18）＋_common.py（_rows/_j）。
   `__init__.py` 全量重导出 37 个公开函数＝**包门面**，~60 处调用
   （`catalog.xxx()`/`from . import catalog`）零改动——非兼容 shim，标准做法。
   **AST 逐字验证**：删旧文件前对 45 个函数（含私有映射到子模块）逐一
   ast.dump 对比，零差异；旧 catalog.py＋陈旧 pyc 已删。
2. **前端资产 extract_report/assets → web/**（25 文件平铺）：六页
   （upload/sources/templates/staging/load/tasks）＋shell＋共享 hint.css/js
   （上传页＋报告）＋stage.css/js（校验台＋报告）＋报告专用 report.css/js＋
   lightbox.html。HTML 引用全是绝对路径 `/static/<file>` → **HTML 零改动**；
   仅 config（ASSETS_DIR→WEB_DIR）/app（mount＋asset()）/builder._asset/
   check_env 四处路径常量改。extract_report 缩为纯报告生成器
   （builder/cards/templates），**内联耦合保留**（套件 B item5 导出字节级
   一致＋file:// 报告自包含渲染证明）。18 个文件头路径注释同步。
3. **docs/feature-map.md**（新）：目录树＋页面→路由→引擎函数→store→表→
   前端文件映射表（7 行含报告）＋web/ 资产归属（页面私有/页面共享/报告专用
   内联）＋表名→模块反查＋命令表＋跨功能共享件（STATE/LOCK、conn_ref vs
   connect_direct、errors→HTTP）。README 树同步。
4. **验证**：36 单测 OK；两套验收顺序 **7/7＋6/6 全 PASS**（基线守恒
   135/1867/1867＋98/14870953；item7 P2b 全链；导出字节级一致；断库 503×5）；
   浏览器 8799 六页 200＋真实数据（upload 10 控件 16 hints/sources 5/templates
   默认空模板/staging 台账 19 行/load 数据源列表＋抽屉回填＋0 映射无锁/tasks
   11 基线 ids）＋报告 BLOB 自包含渲染＋控制台零错。8799/8797 free、tmp 空、
   scratch 已删。
5. **发现（待用户答复，未动）**：extract_load_datasource 多一行
   **(2,'产品库2')**，与产品库同 host/port/db（10.0.6.161:3306/co_dev），
   **两行 created_at 同为迁移秒 2026-11-21 20:12:40**；load_tables 0、无任务
   引用。早于本轮套件（纯代码移动不写库），疑迁移脚本重复插入或用户在 DB
   GUI 复制行。基线是守恒式对比故套件 PASS 不受影响。**未经批准不删**；
   「datasources=1」旧基线预期已过期，现＝2。
- **8765**：须用户再重启一次载入本轮（web/ 静态挂载＋catalog 包）。累计未重启
  载入：A 轮错误分类＋台账任务级＋B 拆分＋P1b＋P2＋P2b＋**B 结构清理轮**。
  重启前旧进程 /static 挂载的 extract_report/assets 已移走 → 静态 404
  （页面样式/脚本缺失）。

---

## 〇.15、P2c 单一提取入口＋入库时绑定＋删迁移门禁（2026-11-21，已完成）

设计稿 docs/design-p2c-load-entry.md（大白话版批准后实施）。三件事一轮做完：
**P2c 功能改造**、**用户实测撞出的 run_load 首绑崩溃修复**、**schema_version
事故→用户裁决「连门禁一起删」**。

### A. P2c：提取就是提取，入库时再选目标

1. **上传不再有模式**：upload/tasks_create 携带退役键
   mode/load_datasource_id/load_table_id → 400「上传不再携带入库目标，
   请在任务入库时选择」（防旧浏览器缓存，非兼容 shim）。上传页只剩
   文件＋模板＋参数。
2. **绑定只随一次成功的入库启动落库**（service.launch_load 单一接缝，
   原 app._load_preflight 删除）：状态守卫→已绑定带 target 键 409
   「已绑定入库目标，不可改（重试沿用原目标）」／未绑定必须带 target→
   归属/模板匹配/透传 400、lt·ds 存在 404、loader.preflight→records→
   review_gate 409→**全过才 set_task_load**→起线程。门禁/预检失败
   **不留绑定**，下次随便另选——不需要专门改绑功能。partial 重试沿用
   原绑定（回执键 ds×table 不变）。
3. **extract_task.mode 列已删**（零成本窗口核过：当时 11 任务全 preview、
   绑定 0、回执 0）：先查状态→整库备份 pre_p2c_20261121_222705.sql→
   ALTER DROP COLUMN→守恒 PASS→脚本用完即删。
4. **前端**：tasks「模式」列→「入库目标」（target_table·write_mode 或 —）、
   fmode 筛选删；previewed 未绑定→「入库…」开抽屉；shell.js 新增共享
   **openLoadTargetDrawer(taskId, templateId, onDone)**（与回执抽屉同构）：
   数据源 select→映射 select（ds×templateId 双过滤）→门禁计数→提交；
   0 候选引导去 /load；400/409 内联；选择内存保留（ltKeep，门禁失败
   修完重开不必重选）。staging.js 同形改造。/load 页零改动。
5. **run_load 首绑崩溃（用户实测撞出，已修）**：run_load 从**绑定前**取的
   task 快照读 `task['load']['datasource_id']`，首次绑定 load=None →
   TypeError 崩在 try 外 → STATE 卡 running=True、任务停在 previewed。
   修复：`datasource_id = ds['id']`（launch_load 已解析的数据源行）。

### B. schema_version 事故 → 裁决：连门禁一起删

**事故链**：用户在 8765 实测入库，把测试数据写进了平台簿记表
schema_version（映射 lt9 目标＝schema_version）；又在 DB 客户端把该表
手动重建为 VARCHAR(255)（两份备份 20:12/22:27 均证明原为 INT 单行 (1)）。
门禁 `_migrate` 拿 int 文件名编号比原始列值：VARCHAR 返回 str '1'，
`1 in {'1'}` False → 重跑 001 → 非幂等 INSERT '1' → 1062 →
**每次 db.connect 都 503，全平台瘫痪**。

**用户裁决**（先拒「门禁加固」：「是不是给我增加了不必要的麻烦」；
再「我不需要这个功能，给我彻底清理掉这些不必要的麻烦」；最终
**「连门禁一起删」**，代价已告知：以后部署/升级须人工跑 SQL）：

1. **db.py 门禁整体删除**：_migrate/_READY/_LOCK/migrate 参数全删，
   connect()＝纯连接（不建表不迁移）；connect_direct 保留。
   store/__init__、loader、check_env 文案同步。
2. **001_baseline.sql 改人工安装脚本**：schema_version DDL 删除，
   头部注明用法；全 IF NOT EXISTS＋INSERT IGNORE，重跑无副作用。
   README 部署步骤加「2.5) 人工建表」。
3. **库手术**（先整库备份 **pre_gate_removal_20261121_231838.sql** 32MB→
   子级清净→DROP→守恒 PASS→脚本删）：任务 228（loaded，绑 lt9）全子级
   删除（staging field/lineage 各 6→record 6→artifact 8→quarantine 12→
   load_log 6→tf246→task）；**lt8、lt9 两条映射都指向 schema_version，
   一并删**（lt8 无引用，lt9 仅 228 引用；字段行先清）；DROP TABLE
   schema_version。**file 56 保留**（tasks 80/226 共享的真实文件）；
   tasks 217–226、测试模板1、产品库/产品库2 全无损。
4. **验收 item1 改写**（两套）：「迁移门禁幂等」→「连接零副作用」
   （重开连接行数/字节零变更）；db._READY.clear() 等门禁引用全删。
5. **教训（已入记忆）**：① 入库目标可选到平台系统表（loader 无守卫）——
   祸根是拿簿记表当业务表，不是门禁本身；② 用户会在 DB 客户端手改平台表，
   schema 漂移是真实故障模式；③ 跑套件期间不建议用户重启/重试（独占窗口
   包括用户自己的 8765 操作）；④ 事故修复只做最小修复，不夹带加固。

### C. 验证

（套件/浏览器结果待补）

- **8765**：须用户再重启一次。累计未载入：A 轮＋台账＋B 拆分＋P1b＋P2＋
  P2b＋B 结构＋**P2c＋run_load 修复＋删门禁**。重启前：上传页旧控件提交
  400、入库走旧契约；旧进程仍带门禁代码（视 _READY 缓存状态或 503 或
  重建 schema_version 表）——**务必重启载入新代码**。

---

## 一、C1 已完成（已验证）

用户 5 项演进（2026-11-20 提出，全部批准落地）：

1. **去 MVP 化**：包 `mvp/` → `c1_extract/`（git mv）；env `CV_MVP_*` → `C1_EXTRACT_*`；
   凭据键 `CV_PLATFORM_DB` → `C1_EXTRACT_DB`（secrets.json 旧键已删）；
   配置清理（INPUT/OUTPUT/SOURCES_DIR、to_abs/to_rel、BATCH_TS_FMT、RUN_JSON 等全删）。
2. **附件粒度＝run_file_id**（用户裁决，非 source_file）：`extract_artifact` 重建，
   UNIQUE(run_file_id, name)，FK→run_file ON DELETE CASCADE。重跑不覆盖旧 run 血缘。
3. **sources sha 前缀文件名退役**：原件字节进 `extract_source_file.content`（LONGBLOB），
   `/srcfiles/<source_id>` 按 id 取字节。
4. **relPath 废弃**：source_file.rel_path / run_file.output_rel_dir 列已删。
5. **批次戳退役**：run.batch_tag 列已删；URL 全改 id（`/staging?run=&file=`、
   `/files/<rf_id>/`、`/api/runs/<run_id>`）；run.json 退役，runs API 由表投影。

### 迁移与数据安全
- **005_c1_storage.sql**：数据保留迁移（非清库）——sources 附件按 sha8_name 回填
  source_file.content；artifact 按 output_rel_dir 映射 run_file_id；只删无字节且无引用的
  幽灵行。备份 `data/backup/pre_005_*.sql`。
- **006_fix_fks.sql**：配置库 schema 漂移修复——run_file/staging 三表建表时丢了 001/003
  的外键（删除不级联，曾积累 578 孤儿 field/lineage 行）。006 清孤儿＋条件补 5 个外键
  （information_schema 命中即跳过，新库走 001/003 不受影响）。备份 `pre_006_*.sql`。
- 当前配置库基线：schema_version 1-6；run 21（previewed，建设银行2022.12流水.pdf，
  29 记录×17 字段）；run_file 25；source 3（content 47922B）；artifact 17。

### 验收（2026-11-21，结果以脚本输出为准）
- `c1_extract/accept_records_db.py`：**6/6 PASS**。
- `c1_extract/accept_artifacts_db.py`：**6/6 PASS**（含 export --run 新布局逐字节核对）。
- **两套脚本严禁并行**（共用 8799/8797）；start_service 有端口空闲断言。
- 浏览器全链路验证（8765 新代码）：runs 列表+详情抽屉（id 链接）/ staging 29 条+
  血缘点格定位+lightbox+翻页+跨 run 搜索（20 命中）/ sources（/srcfiles/3）/
  报告重定向（3 图全加载）/ 上传 golden path（临时 run 29 验完已清理）；控制台零报错。
- **用户 8765 已运行新代码**（c1_extract/app.py，用户自行重启，PID 会变）。

### 脚本陷阱（已修，复用注意）
- 计数须每次新连接（MySQL REPEATABLE READ 旧快照）；长连接读他连接提交前先 commit。
- 清理先子后父：staging_record→run_file **无级联**须显式删（field/lineage 随 record 级联）；
  artifact 随 run_file 级联；quarantine/load_log 按 run_id 显式删。
- Starlette 回小写 header 名；If-None-Match 为 None 时不传 header。
- 合成 source 用假 sha 登记时，真链路误传合成字节会按**真实 sha** 新建行（去重不命中假 sha）——
  cleanup 已按合成内容 sha 兜底清未引用行；find_pdf_source 用 size>1KB 过滤合成假 PDF。
- 跨 run 搜索关键词注意：原始透传值保留 PDF 换行空格（如「电子汇 入」），LIKE 子串要避开断点。

---

## 二、挂起待办（沿用，未立项）

- **108 案例**：首行 / 错字问题挂起（见项目记忆 mvp-deferred-todos）。
- **曾问未立项**：Word 输出、双层 PDF 导出、漏提覆盖视图（11-20 问过，未立项）。
- **环境**：torch 残装 `shm.dll WinError127`（实为 paddle↔torch 加载顺序冲突，11-20 已修 check_env，torch 不能卸）。
- **P1a 校验台已完成**（见 §〇.5）；**P1b 模板管理＋collect 选择器/重命名已完成**（见 §〇.11）；**P2 入库模式已完成**（见 §〇.12）。后续候选：B 轮审计平台化（reviewer 身份首补）／隔离区解决 UI／多表 union／引擎升级研究（Docling vs MinerU，未立项）。
- 快照简化决策已被 C1 吞并（run.json 退役、records 三表为事实源、export 按需导出）。

---

## 三、验证方法与环境事实（下次复用）

- **临时服务**：从 `20-CV` 起 `python -m uvicorn c1_extract.app:app --host 127.0.0.1 --port 8799`
  （`C1_EXTRACT_WARMUP=0` 懒加载，启动≈0.5s）。**用户的 8765 全程不动**，验完停临时服务。
  端口约定：8799=真链路 / 8797=不可达 DSN（断库模拟）。
- **平台库**：`data/secrets.json` 键 `C1_EXTRACT_DB`（10.0.6.161:3306/co_dev），**不用 Docker**，**只做 MySQL**。
  凭据只经 conn_ref 解析，回显仅 host/库名（`db.safe_detail`）。断库模拟用假 DSN
  `mysql://nobody:unused@127.0.0.1:3399/co_dev`（本地无人监听），不触碰真实库可用性。
- **验收脚本**：`D:/miniforge3/envs/paddle/python.exe -u c1_extract/accept_records_db.py`（从 20-CV，`-u` 实时进度）。
  破坏性操作只落合成 run，验完按 id 清理；真实 run/source 只读。
- **真实用例**（全在 DB）：run 21 / run_file 25 / source 3「建设银行2022.12流水.pdf」
  （3 页，29 记录×17 字段，17 附件）。上传验收字节取自 source_file.content。
- **浏览器验证**：browser-use `navigate_page` + `evaluate_script`；隐藏 file input 先
  `style.cssText` 显示再取 snapshot uid 上传；staging.js 顶层变量全局可访问。
- **curl 中文 URL** 需要 percent-encode；控制台 cp936 乱码用 `PYTHONUTF8=1`。
- Python：`D:/miniforge3/envs/paddle/python.exe`；c1_extract 是包，脚本从 20-CV 跑
  （sys.path 需包的上级目录；入口自举 PKG=os.path.basename(ROOT) 改名自适应）。
- **破坏性迁移前必须先查当前库状态**（005 教训：用户已重新上传真实数据，清库式迁移会毁掉它）；
  迁移前整库备份（本机无 mysqldump，用 Python pymysql dump：SHOW CREATE TABLE + conn.escape INSERT）。

---

## 四、下次上班入口

1. C1 存储演进＋任务化命名/去外键＋P1a 校验台＋小重构轮（A/B）＋UI 打磨轮
   ＋任务级台账/报告打磨/B 编排拆分轮＋校验台两处打磨轮＋三页紧凑规整统一轮
   ＋P1b 模板管理＋collect 选择器消费轮＋P2 入库模式轮＋P2b 入库数据源重构轮
   ＋B 结构清理轮＋**P2c 单一提取入口/入库时绑定＋run_load 首绑修复＋
   删迁移门禁（schema_version 已 DROP，001 改人工安装脚本）**
   均已完成：代码＋验收＋浏览器＋文档全部收尾（见 §〇.6–§〇.15）。
2. 建议事项：**用户 8765 重启一次**——载入 A 轮错误分类＋台账任务级形状
   /api/staging/ledger＋B 拆分（app.py 路由 / service.py 引擎）＋P1b（模板 CRUD
   路由＋/templates 页＋collect 消费）＋P2（load 路由＋入库按钮＋回执抽屉）＋
   P2b（数据源/映射新路由＋/load 左右页）＋B 结构清理（web/ 静态挂载＋
   catalog 包）＋**P2c（上传无模式＋入库目标抽屉＋mode 列已删）＋run_load
   首绑修复＋删门禁（db.connect 纯连接）**。重启前：/static 404、nav 旧页、
   上传页旧控件提交 400、入库走旧契约、旧门禁代码视缓存状态或 503 或
   重建 schema_version。
   另：**「产品库2」数据源行来源待用户确认**（§〇.14.5，未动不删）；
   **tasks 217–225 卡 pending**（用户实测期重启孤儿，是否重跑由用户定）。
   **警示：入库目标别选平台系统表**（loader 无守卫；schema_version 事故
   根因，见 §〇.15.B；该表已删，但 extract_* 业务表同样不该当目标）。
3. 新需求候选（设计先行，用户确认后执行）：**B 轮审计平台化**（reviewer 身份首补，
   load_log 记「谁入的库」）／隔离区解决 UI／多表 union／引擎升级研究
   （Docling vs MinerU，未立项）／入库目标守卫（禁选 extract_* 平台表，
   小改可选）。对外文案用「字段级溯源/审计追溯」，
   UI「血缘回溯」保留（产品定位见项目记忆）。
4. 其余沿用 §二挂起项。
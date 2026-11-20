# 进度交接 · 待办与待裁决（2026-11-20）

> 用途：下次上班继续处理的入口文档。记录本次会话已完成项、用户新提的三项疑问的处理状态，
> 以及需要拍板的设计问题。配套设计稿见 [design-data-pipeline.md](design-data-pipeline.md)。

---

## 一、本次会话已完成（已验证）

### 1. 数据预览右侧「源图血缘回溯」（ Round-2 item4 + 三轮细化 A/B/C）
右侧舞台已**忠实复刻对照报告**的交互与视觉，不再另造一套：
- **默认零框**：回溯框默认隐藏，悬停临时揭示单格、点击钉住（橙）。
- **点图命中任意行**：移植报告 `hitCell`（viewBox 1:1 换算 + 最小面积命中），框隐藏时点图仍能定位**任意**记录行/格，不限当前选中行。
- **窗口式翻页**：移植报告 `renderPager`/`alignPagers`（首末页 + 当前±1 + …间隙、圆点页码、跳页输入框、实测锚定源图底缘）。
- **原图/矫正图**：报告同款双 `.view` 切换；**叠加框开关**「显示/隐藏叠加框」可选整表网格。
- **全屏浮层**：报告 lightbox（克隆 imgwrap、滚轮缩放/拖拽/双击 1:1、缩放百分比、点框关闭并回溯）。
- 光标跟随提示 pill、追溯失败 toast 一并移植。
- 文件：`extract_report/assets/staging.{js,css,html}`。匹配键 `data-i`（记录序）/`data-key`（字段）。

### 2. md 下载改为预生成（Round-2 item1）
`对照报告` 的 md 下载不再实时 data URI，改为生成真实 `.md` 落 `output/<case>/`（多页 `_pN.md`），
白名单放行顶层 `.md`，file:// 直开与在线两种打开都成立。文件：`extract_report/{cards,builder}.py`、`templates/md_pane.html`、`app.py`。

### 3. json 链接只在对照报告（细化 C3）
- 数据预览页脚链接只剩「对照报告」；banner 文案去掉 records.json 字样。
- `runs.js` 文件行去掉 extract/records 链接，保留「预览数据 | 对照报告」。
- 对照报告仍保留自身 extract.json 入口（符合「只在报告里」）。

### 4. 【今日 item1】cvdoc → c1-extract 全仓重命名 ✅
- 纯 token 替换 `cvdoc` → `c1-extract`，共 **65 处 / 11 文件**，无残留。
- schema 常量：`cvdoc/1`→`c1-extract/1`、`cvdoc-records/1`→`c1-extract-records/1`、`cvdoc-run/1`→`c1-extract-run/1`
  （`adapter/base.py` 的 `SCHEMA`/`RECORDS_SCHEMA`、`app.py` run.json）。
- 注释/文档/模板/drawio 同步：`collect.py`、`pipeline/runner.py`、`adapter/{base,paddle,__init__}.py`、
  `extract_report/{builder,cards}.py`、`templates/card.html`、`docs/design-data-pipeline.md`、`docs/data-pipeline.drawio`。
- **安全性**：schema 字符串只写不校验（全仓无读回比对），重命名不影响任何功能。
- **注意**：已落盘的旧 `output/<case>/extract.json|records.json` 仍带旧 `cvdoc/1` 字样，
  直到下次重跑提取才会更新；因无校验，旧文件照常可用，无需迁移。

### 5. 【今日 item3】翻页组件首次打开偏上挡字 ✅
- 根因：首次打开/切页时 `img` 尚未 `load`，`imgwrap` 高度≈0，`alignPagers` 把胶囊锚得偏上。
- 修复：与报告一致，`renderViewer` 给舞台每张 `img` 绑 `load → alignPagers`，加载完再精确锚定。
- 验证：合成多页 + 强制异步加载，加载后 `bottom=18px`（=预期 `sr.bottom-ir.bottom+8`），胶囊贴图底缘而非偏上。
- 文件：`extract_report/assets/staging.js`（`renderViewer` 尾部）。

---

## 二、item2 已裁决=B：记录入库（已实现 · 验收 6/6 PASS）

### 裁决过程
- 用户场景明确为「**跨批查未确认暂存记录**」→ 触发 B 条件；设计稿
  [design-records-db.md](design-records-db.md) 四项批准（EAV 三表 / D1 契约重写 /
  records.json 降格派生快照 / 先验证再推广）。原 v3「四层不双写」重新表述为
  **单写方向 DB→快照**（field 表是同事务可重建的查询投影，非独立事实源）。
- 验证库改用**用户配置库**（`data/secrets.json` 的 `CV_PLATFORM_DB` →
  10.0.6.161:3306/co_dev），**不用 Docker**（用户指示）。

### 实现清单
- `store/migrations/003_staging_records.sql`：extract_staging_record/field/lineage
  三表（values_json/original_json 保真 + review_state/at；field 投影索引；lineage 随 record 级联）。
- `store/content_db.py`：get/save/patch/query_fields；save 单事务删旧重建；patch FOR UPDATE。
- `store/content.py`：DB-only 门面（extract/run 经 artifact JSON 接缝，records 直委托
  content_db）；**无 file 实现、无开关**（file 模式已删，见 §二·续）。
- `app.py`：**DB 必选**（登记失败→503 不建 run；运行写库失败→整 run failed）；
  `/api/staging/query` 跨批查询；**完成态最后发布**（run.json 落库后才 `running=False`，修读旧快照竞态）。
- `migrate_records_to_db.py`：幂等回填（真实 case 只补 id + 刷新 schema，不改动内容）。
- 暂存页「跨批搜索」面板：`extract_report/assets/staging.{html,js,css}`。

### 验收（`mvp/accept_records_db.py` · 配置库 · DB-only 重写后）
1. 回填幂等＋真实 case 投影往返一致（get_records→save_records→get_records 逐记录相等，
   经合成 run_file  remap，不碰真实行）；
2. 重跑级联 2→1→2；3. patch edited＋original 不变＋DB 读回；4. 跨批查询命中；
5. 真链路 previewed＋无持久磁盘＋暂存/查询 API（8799）；
6. 断库显式 503（8797 不可达 DSN：上传不建 run / runs / 暂存 / 模板全 503，不降级）。
- 浏览器验证：面板关键词搜索、field 投影跨批、预览链接跨批跳转落点正确（file 时代验过，DB-only 待复验）。
- 脚本陷阱（已修，复用注意）：计数须每次新连接（MySQL REPEATABLE READ 旧连接快照不变，
  **长连接读他连接提交的登记前须先 commit 刷新快照**）；清理**先子后父**
  （run_file→run 外键无级联）；Starlette 回**小写 header 名**，断言须 lower()。

### 快照/降级简化：已裁决（被产物入库方案吞并）
- 用户质疑 D1＋records.json 快照多余 → 升级为「产物全量入库」方案
  （[design-artifacts-db.md](design-artifacts-db.md)），四项批准：全量入库 /
  DB 必选 D1 退役 / 自动快照退役 records 完整关系化 / **只做 MySQL**
  （方言留给以后框架重构）。实现见 §二·续。

---

## 二·续、产物全量入库（design-artifacts-db.md · 已实现）

### 契约（DB-only，file 模式已删除）
- **无存储开关**（2026-11-20 用户裁决：file 模式只是初期调试过渡产物，整体删除）。
  DB 是唯一模式：**DB 必选**——上传登记失败→503（不建 run）；运行写库失败→整 run failed；
  读端点断库→503；`/api/templates` 不再降级内置清单；check_env 平台库为必选项。
  旧 `staging_failed`/`partial`/快照只读回落全部退役。
- 磁盘仅 scratch：case 工作目录与 input 副本都是 tempfile，**报告先于 records 写库生成**
  （断库时引擎产物仍完整），随后 `_ingest_case` 遍历入 `extract_artifact` BLOB 即 rmtree
  （管线/builder/cards 零改动）。
- records.json 不再自动导出；`export_artifacts.py --out <dir>` 按需还原目录树
  （BLOB 原字节＋records.json 经 content_db 重建），file:// 直开报告恢复。
- `/files/`、`/srcfiles/` 恒为 API 路由：白名单/raw 403 不变，ETag=sha256→304；
  仅 /static 挂 StaticFiles。
- runs 列表/详情/报告重定向/批次戳去重全查库
  （`catalog.list_run_cases()/list_batch_tags()`）。

### 实现清单
- `store/migrations/004_artifacts.sql`（extract_artifact：case_rel+name 唯一，
  kind/mime/size/sha256/LONGBLOB）；`store/artifact.py`（DB-only 门面＋kind/mime 推断）
  ＋`store/artifact_db.py`（upsert/get/list/cases/delete）。
- `store/content.py`：DB-only 门面；`store/content_db.py`：`_export_snapshot` 删除。
- `app.py`：scratch＋ingest、DB 路由恒挂、上传/资料库/runs 全查库、DB 必选契约；
  OutputFiles/StaticFiles 产物挂载、file 分支、降级回落全删。
- `migrate_artifacts_to_db.py`（幂等回填，records.json/input 副本不迁）；
  `export_artifacts.py`（按需导出）；`migrate_records_to_db.py` 规范副本改入 BLOB。
- 已回填配置库：46 文件 7.2MB（5 case＋sources，2026-11-20）；磁盘 input/output/sources
  已被用户清空，**DB 为唯一数据副本**。

### 验收（DB-only 重写后，结果以脚本输出为准）
- `mvp/accept_records_db.py`：六项见 §二。
- `mvp/accept_artifacts_db.py`：六项＝回填幂等+读回 sha 自洽 / 真链路无磁盘+BLOB /
  /files mime+ETag 304+raw 403+records 404 / runs+报告重定向+暂存+查询 /
  导出逐字节一致+records 语义 / 断库 503。上传字节取自 sources BLOB（磁盘已空）。
- **两套脚本严禁并行**：共用 8799/8797 与合成 case，曾并行互踩（端口误连＋死锁＋
  合成行被对方清理）；start_service 已加端口空闲断言。
- 端口约定：8799=真链路 / 8797=不可达 DSN；8798(file) 已随 file 模式退役；8765 不动。

---

## 三、其他挂起待办（沿用，未立项）

- **108 案例**：首行 / 错字问题挂起（见项目记忆 mvp-deferred-todos）。
- **曾问未立项**：Word 输出、双层 PDF 导出、漏提覆盖视图（11-20 问过，未立项）。
- **环境**：torch 残装 `shm.dll WinError127`（实为 paddle↔torch 加载顺序冲突，11-20 已修 check_env，torch 不能卸）。
- 跨页/无表头拼接已实现；上传页单页循环。

---

## 四、验证方法与环境事实（下次复用）

- **临时服务**：从 `20-CV` 起 `python -m uvicorn mvp.app:app --host 127.0.0.1 --port 8799`
  （`CV_MVP_WARMUP=0` 懒加载，启动≈0.5s，不碰 paddle）。**用户的 8765 服务全程不动**，验完停临时服务。
  验收端口约定：8799=真链路 / 8797=不可达 DSN（断库模拟）；8798(file) 已退役。
- **平台库**：用户配置 `data/secrets.json`（`CV_PLATFORM_DB`，10.0.6.161:3306/co_dev），**不用 Docker**。
  凭据只经 conn_ref 解析，回显仅 host/库名（`db.safe_detail`）。D1 模拟用假 DSN
  `mysql://nobody:unused@127.0.0.1:3399/co_dev`（本地无人监听），不触碰真实库可用性。
- **验收脚本**：`D:/miniforge3/envs/paddle/python.exe -u mvp/accept_records_db.py`（从 20-CV，`-u` 看实时进度）。
  破坏性操作只落合成 case `_accept_tmp` 与临时批次，验完清理；真实 case 仅幂等回填。
- **真实用例**（磁盘已清空，全在 DB）：case `20261120211314_招行流水_已脱敏_`
  （单页，24 记录×8 字段）、`20261120214024_建设银行2022.12流水`（多页 17 产物）。
  上传验收字节取自 sources BLOB `83ef00a8_招行流水（已脱敏）.pdf`。翻页组件需用合成多页数据验证。
- **浏览器验证**：browser-use `navigate_page` + `evaluate_script`（截图需可见视口，本环境不可用）；
  staging.js 顶层变量是全局可访问；`renderViewer` 重建 svg 后旧 rect 引用会失效，测试须重新 query。
- **curl 中文 URL** 需要 percent-encode，改用 Python urllib（quote/urlencode）。
- **控制台 cp936 乱码**：`PYTHONUTF8=1 PYTHONIOENCODING=utf-8` + `grep -a`。
- Python：`D:/miniforge3/envs/paddle/python.exe`；mvp 是包，脚本从 20-CV 以 `from mvp.xxx import` 运行。

---

## 五、下次上班入口

1. 产物全量入库＋**file 模式删除**已完成（§二·续）：两套验收脚本 DB-only 重写，
   顺序重跑确认全 PASS 后收尾（**严禁并行跑两套脚本**）。剩余：浏览器复验 DB-only 页面。
   **用户 8765 仍是旧代码——重启即切 DB-only（无需任何 env 开关）**，
   重启方式由用户拍板；数据已全部在库（46 文件回填＋后续真链路验收）。
2. 观察项：用户 8765 出现两个失败批次 `20261120220957` / `20261120221713`（原因未查，用户未问）；
   若用户提起，先查 `logs/<batch>.log`，勿动 8765 服务。
3. item2=B 已实现＋验收 PASS，无需重做。
4. 其余沿用 §三挂起项或 P1 校验台。
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
- `store/content_db.py`：get/save/patch/query_fields；save 单事务删旧重建＋导出快照；patch FOR UPDATE。
- `store/content.py`：`RECORDS_STORE`（env `CV_MVP_RECORDS_STORE`，默认 file）分发；
  db 模式读 DB、DB 故障读快照只读（D1）；写错误上抛不静默回落。
- `app.py`：D1 显式降级（run_file `staging_failed` / run `partial`，引擎层照常）；
  `/api/staging/query` 跨批查询；**完成态最后发布**（run.json 落盘后才 `running=False`，修读旧快照竞态）。
- `migrate_records_to_db.py`：幂等回填（真实 case 只补 id + 刷新 schema，不改动内容）。
- 暂存页「跨批搜索」面板：`extract_report/assets/staging.{html,js,css}`。

### 验收（`mvp/accept_records_db.py` · 配置库 · 6/6 PASS · 2026-11-20）
1. 迁移幂等＋逐字段一致（3 真实 case 共 76 记录，含用户新上传的交行 case）；
2. 重跑级联 2→1→2；3. patch edited＋original 不变＋快照同步；4. 跨批查询命中；
5. 真链路 previewed＋D1（**8797 不可达 DSN 模拟断库**：引擎照常＋staging_failed＋旧快照只读）；
6. file 回滚（8798，DB 不可达照常）。
- 浏览器验证：面板关键词搜索、field 投影跨批（76 行跨 3 批）、预览链接跨批跳转落点正确。
- 脚本陷阱（已修，复用注意）：计数须每次新连接（MySQL REPEATABLE READ 旧连接快照不变）；
  `state` 读 **run.json**（records.json 无 state，且 D1 不写快照）；清理**先子后父**
  （run_file→run 外键无级联）。

### 新待裁决：快照与降级要不要简化（用户提出，未动代码）
- 用户质疑：D1 降级逻辑＋records.json 派生快照是否多余，不如直查 DB。
- 已澄清事实：**对照报告不读 records**（纯 extract 层渲染，builder.py）；records 的消费方＝暂存页。
- 权衡：降级＝核心管线不被远程 DB 绑架（建议保留）；快照＝断库旧数据可读＋
  **人工编辑层库外副本**（records = passthrough(extract) + 人工编辑/审核状态，后者仅存 DB）＋case 目录自包含。
  简化代价＝人工编辑单副本＋断库暂存页全 503。
- 倾向：保留 D1 显式失败；快照降格为手动导出/备份或删。**等用户拍板再动**（设计先行）。

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
  验收端口约定：8799=db 真链路 / 8797=db＋不可达 DSN（D1 模拟）/ 8798=file 回滚。
- **平台库**：用户配置 `data/secrets.json`（`CV_PLATFORM_DB`，10.0.6.161:3306/co_dev），**不用 Docker**。
  凭据只经 conn_ref 解析，回显仅 host/库名（`db.safe_detail`）。D1 模拟用假 DSN
  `mysql://nobody:unused@127.0.0.1:3399/co_dev`（本地无人监听），不触碰真实库可用性。
- **验收脚本**：`D:/miniforge3/envs/paddle/python.exe -u mvp/accept_records_db.py`（从 20-CV，`-u` 看实时进度）。
  破坏性操作只落合成 case `_accept_tmp` 与临时批次，验完清理；真实 case 仅幂等回填。
- **真实用例**（有 extract.json）：`output/20261120161507_招行流水_已脱敏_`（单页，24 记录×8 字段，batch=20261120161507）、
  `output/103_real_bank_statement_textlayer`（单页文本层）。**均单页**，翻页组件需用合成多页数据验证。
- **浏览器验证**：browser-use `navigate_page` + `evaluate_script`（截图需可见视口，本环境不可用）；
  staging.js 顶层变量是全局可访问；`renderViewer` 重建 svg 后旧 rect 引用会失效，测试须重新 query。
- **curl 中文 URL** 需要 percent-encode，改用 Python urllib（quote/urlencode）。
- **控制台 cp936 乱码**：`PYTHONUTF8=1 PYTHONIOENCODING=utf-8` + `grep -a`。
- Python：`D:/miniforge3/envs/paddle/python.exe`；mvp 是包，脚本从 20-CV 以 `from mvp.xxx import` 运行。

---

## 五、下次上班入口

1. 读 §二「新待裁决」：**快照/降级简化**——用户拍板后再动代码（设计先行）。
   若简化：删 content_db 导出＋content.py 读回落，保留 D1 显式失败；
   验收脚本第 5 项「旧快照只读」断言需同步改为断库 503。
2. 观察项：用户 8765 出现两个失败批次 `20261120220957` / `20261120221713`（原因未查，用户未问）；
   若用户提起，先查 `logs/<batch>.log`，勿动 8765 服务。
3. item2=B 已实现＋验收 6/6 PASS＋浏览器验证，无需重做；重跑验收直接跑脚本（幂等、自清理）。
4. 其余沿用 §三挂起项或 P1 校验台。
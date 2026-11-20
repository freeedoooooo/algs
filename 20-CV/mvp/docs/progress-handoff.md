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

## 二、待裁决设计问题（今日 item2，未实现，需拍板）

### 问题
> 「既然方案已经确定离不开数据库了，是不是 records.json，还有其他一些数据应该直接结构化入库保存？」

### 现状（设计稿已裁决，勿默认推翻）
- **v3 明确决定**：`records.json` 是 **L2 记录事实源**，**取消 DB staging_record 表**；MySQL 只管**目录元数据**
  （sources/templates/destinations/runs/quarantine/load_log）。见设计稿 §5.4「四层不双写」、§3.1。
- **四层事实源**：raw=引擎事实源 / extract.json=标准投影 / records.json=记录事实源 / MySQL=目录事实源。
  quarantine、load_log 用 `(run_file_id, record_index)` **引用**记录，DB 不存记录内容。
- **已预留「保存方式接缝」**：records/extract/run 的读写全部经 `store/content.py`
  （`get_records/save_records/patch_record/get_extract/...`，当前=文件原子写）。
  设计稿 §2.3/§5.5 写明：**将来改 DB/对象存储只换 content.py 实现，API 与页面不动**
  （正是用户当初「改个保存方式就行」的诉求）。

### 选项与权衡
| 选项 | 做法 | 代价 | 适用 |
|---|---|---|---|
| **A 维持文件事实源（现状，推荐）** | records.json 仍是事实源，DB 只存目录 + 引用 | 无改动；记录查询/聚合需读文件 | 单写者、本地工具、逐层审计比对 |
| **B 记录入库为事实源** | 新增 staging_record 表，content.py 换 DB 实现，records.json 退化为导出/快照 | 需建表 + 迁移 + PATCH 事务化 + lineage 存储；preview/review/load 改读 DB；**与「四层不双写」需重新表述** | 多用户并发校验、跨批次 SQL 查询/统计、记录级权限 |
| C 双写（DB 镜像 + 文件事实源） | DB 做查询索引镜像 | **违反不双写原则**，一致性维护成本高 | 不推荐 |

### 推荐
- **暂维持 A**。当前是单写者本地工具，文件事实源 + 逐层落盘审计是已批准设计的核心优势；
  「离不开 DB」指的是**目录元数据**离不开 DB，记录内容按设计本就不进 DB。
- 若确实需要**跨批次 SQL 查询/多人并发校验/记录级统计**，再走 **B**：
  因 content.py 接缝已就位，改动集中在「换 content.py 实现 + 建 staging_record/lineage 表 + 迁移」，
  API/页面理论上不动。**这是 P1+ 的架构变更，须先批准再动手**（设计先行约定）。

### 需要用户回答
1. 是否要把记录内容（records）从文件事实源迁到 DB（选项 B）？还是维持现状 A？
2. 若迁移动机是「查询/统计/并发」，具体场景是什么？据此判断 B 的必要性与表结构。
3. 「其他一些数据」具体指哪些？（extract.json 标准层？lineage 血缘？校验状态？）逐项确认是否入库。

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
- **真实用例**（有 extract.json）：`output/20261120161507_招行流水_已脱敏_`（单页，24 记录×8 字段，batch=20261120161507）、
  `output/103_real_bank_statement_textlayer`（单页文本层）。**均单页**，翻页组件需用合成多页数据验证。
- **浏览器验证**：browser-use `navigate_page` + `evaluate_script`（截图需可见视口，本环境不可用）；
  staging.js 顶层变量是全局可访问；`renderViewer` 重建 svg 后旧 rect 引用会失效，测试须重新 query。
- **curl 中文 URL** 需要 percent-encode，改用 Python urllib（quote/urlencode）。
- **控制台 cp936 乱码**：`PYTHONUTF8=1 PYTHONIOENCODING=utf-8` + `grep -a`。
- Python：`D:/miniforge3/envs/paddle/python.exe`；mvp 是包，脚本从 20-CV 以 `from mvp.xxx import` 运行。

---

## 五、下次上班入口

1. 先读本文档 §二，**拍板 item2（A/B）**——这是唯一阻塞性设计决策。
2. 若选 B：从 `store/content.py` 接缝入手，先出表结构 + 迁移设计（mermaid + 风险），批准后再实现。
3. 若维持 A：item2 关闭，继续 §三挂起项或 P1 校验台。
4. 今日 item1/item3 已完成验证，无需重做；如需重跑提取刷新旧文件 schema，注意 paddle 环境。
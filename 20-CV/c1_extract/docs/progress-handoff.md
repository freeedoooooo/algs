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
- **P1a 校验台已完成**（2026-11-22，见 §〇.5）；**P1b**：模板管理页＋collect 选择器/重命名；**P2**：入库模式。
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

1. C1 存储演进 + 任务化命名/去外键**均已完成**：代码＋迁移＋验收＋浏览器＋文档全部收尾。
2. 建议事项：① 用户 8765 方便时再重启一次（载入 `_rmtree_retry` scratch 修复，
   当前进程启动早于该修复落盘）；② 图片路线 paddlex[ocr] 依赖缺口（见 §〇）；
   ③ git 历史凭据清理（见 §〇）。
3. 新需求从 P1b 模板管理＋collect 消费起步（P1a 校验台已落地，见 §〇.5）。
4. 其余沿用 §二挂起项。
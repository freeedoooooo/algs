# 进度交接 · C1 存储演进完成态（2026-11-21）

> 用途：下次上班继续处理的入口文档。C1 五项演进已全部落地并验收。
> 设计稿：[design-c1-storage.md](design-c1-storage.md)（已批准并实现，取代
> [design-artifacts-db.md](design-artifacts-db.md) 的表结构/接缝表述；
> DB-only 契约仍有效）。records 三表设计见 [design-records-db.md](design-records-db.md)。

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
- **P1**：模板管理页 / 校验台（编辑/确认/拒绝，staging 已留 review_state）；**P2**：入库模式。
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

1. C1 存储演进**已完成**：代码＋迁移＋验收＋浏览器＋文档全部收尾，无剩余动作。
2. 新需求从 P1 校验台 / 模板管理页起步（staging review_state 与 quarantine 表已就位）。
3. 其余沿用 §二挂起项。
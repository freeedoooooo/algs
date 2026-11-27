# 环境事实与验证方法（2026-11-23 收敛版）

> 历史开发日志已随 C 批命名收敛清理，过程记录见 git 历史与项目记忆；本页只留复用事实。

## 产品结构（现状）

- 流水线四步：**解析 → 抽取 → 校验 → 入库**；页面＝工作台 `/` · 资料 `/sources` ·
  解析 `/parse` · 抽取规则 `/extract` · 校验 `/review`（自动化校验·待实现壳页） ·
  入库规则 `/rules` · 任务 `/tasks`。
- **任务数据预览 `/preview?task=<id>&file=<task_file_id>`**（2026-11-23 七点反馈落地）：
  原「校验台」review 页更名 preview，归属任务功能——nav 高亮「任务」，任务操作
  （执行/重新抽取、逐条校验、重放、入库）都从任务台账或此页进入；`/review` 只留
  待实现说明壳页（`web/review_home.html`）。
- 任务状态机（2026-11-23 落地，设计稿 `docs/design-task-states.md`）：
  `pending→parsing→to_extract→to_review→to_load→loading→loaded`（＋failed）；
  任务态＝文件态 min-rank 上卷（`catalog.rollup_task_state`，不动 error）；
  `to_load` 为派生态（该文件记录全部定论且>0，`service.derive_review_state`）；
  上传只解析，抽取在数据预览页右上角按钮执行（执行/重新抽取，重抽须 force 覆盖校验）；
  **方案A·抽取时绑规则**：解析阶段 `c1_task.rule_version_id=NULL`（004 迁移改可空），
  「执行/重新抽取」时选规则版本并回写绑定（默认＝已绑，未绑＝原始透传；换规则重抽即改绑）；
  上传带 `rule_version_id` 为退役契约键（400）；
  **原地重放** `POST /api/tasks/{id}/reparse`（`service.reparse`）：字节从 `c1_doc_file`
  回捞重走解析，任务 ID 不变、状态退回 `pending`，旧 records/artifact/quarantine 清空，
  `c1_load_log` 回执保留；守卫＝全局有解析在跑或任务 `loading/loaded` 时 409；
  八态八色徽标（待抽取橙 · 待入库黄 · 入库中青，`web/shell.js STATE_LABEL`）。
- 任务台账十列（2026-11-23）：序号|任务ID|资料|解析参数|抽取规则|校验规则|入库规则|
  状态|时间|操作（任务与各规则暂按 1 对 1 展示，缺＝「—」＋悬浮解释；已删「入库目标」列，
  入库规则＝`load.load_table_id` 映射的明细行悬浮）；「门禁」文案改称**「入库前预检」**
  （待校验/已修改未确认/已拒绝/已确认计数，全部确认才可入库）。
- 对照报告 `/parse-report`（重定向到最新 task_file 报告）；产物信封 `parse.json`；
  模块 `parse_report/`（Jinja2）；前端资产 `web/parse|extract|preview|rules.*` ＋ `web/review_home.html`。
- 平台库表 `c1_*` 前缀（`c1_extract_rule` / `c1_extract_rule_version` ＝抽取规则，`c1_task.rule_version_id`
  等）；无外键，级联归应用层；API JSON 键 `rule` / `rule_id` / `rule_version_id`。
- ⚠️ **2026-11-24 起模型已重构**：删除 `c1_task`/`c1_task_file`，以 `file_id` 为唯一运行主键；
  下表结构描述为**历史快照**。当前建表脚本为 `store/migrations/001_file_baseline.sql`，
  详见 `docs/design-file-centric-refactor.md`。以下安装说明保留作历史记录。
- 安装脚本（历史）：新库跑 `store/migrations/001_baseline.sql`（全 IF NOT EXISTS＋INSERT IGNORE，
  可重跑；state 列注释含新枚举）；存量库升级人工执行编号脚本（002＝命名收敛；
  003＝状态机迁移，2026-11-23 已对 c1_structure_dev 执行，备份
  `data/backup/c1_dev_pre003_20261123_135019.sql`；
  004＝`c1_task.rule_version_id` 改可空（方案A），同日已执行，备份
  `data/backup/c1_dev_pre004_20261123_145958.sql`）。
  **无自动迁移器**（schema_version 门禁 2026-11-21 裁决删除）。

## 环境事实

- Python：`D:/miniforge3/envs/paddle/python.exe`；FastAPI＋uvicorn；`c1_structure` 是包，
  脚本从 `20-CV/` 跑（入口自举 `PKG=os.path.basename(ROOT)`，改目录名也能跑）。
- 平台库 DSN：环境变量 `C1_STRUCTURE_DB` 优先，默认值内置
  `config.PLATFORM_DB`（10.0.6.161:3306/c1_structure_dev；secrets.json 引用制已退役）。
  回显仅 host:port/库名（`db.safe_detail`），日志永不打印凭据。
- 端口约定：8765＝用户自起常服（**agent 不启停不动**，重启由用户执行）；
  8799＝临时服务（真 DSN）；8797＝不可达 DSN 断库模拟
  （`mysql://nobody:unused@127.0.0.1:3399/c1_structure_dev`）。
- 临时产物：`tmp/input`、`tmp/work` 跑完即清；Windows 杀软句柄锁用
  `app._rmtree_retry`；计数须每次新连接（REPEATABLE READ 旧快照坑）。
- 控制台中文：`PYTHONUTF8=1` / `python -X utf8`；grep 加 `-a`；curl 中文 URL 要 percent-encode。

## 验证方法

1. **编译/自检**：`python -m compileall -q c1_structure`；`python c1_structure/check_env.py`
   （只读、秒级，不加载模型）。
2. **冒烟**：从 20-CV 起 `C1_STRUCTURE_WARMUP=0 python -m uvicorn c1_structure.app:app
   --host 127.0.0.1 --port 8799`，逐页 200＋关键 API＋浏览器控制台零错；验完停服务、
   确认 8799/8797 free、tmp 空。**用户的 8765 全程不动。**
3. **验收套件**：`accept_records_db.py`、`accept_artifacts_db.py` 顺序跑、严禁并行
   （共用 8799/8797）。**独占窗口规则**：跑前须用户明确暂停其手测/上传/重启；
   期间不建议用户重启或重试。破坏性操作只落合成 task，finally 里 child-first 清理
   （staging field/lineage 键＝record_id 须子查询先清）；真实 task/file 只读，
   守恒失败先分辨用户数据增量，绝不删用户行。
4. **浏览器**：browser-use `navigate_page`＋`evaluate_script`；隐藏 file input 先显示再传。
5. **迁移/破坏性 SQL 前**：先查当前库状态→整库备份（本机无 mysqldump，用 pymysql dump：
   SHOW CREATE TABLE＋conn.escape INSERT，BLOB→hex；产物落 `data/backup/`＋行数 manifest）
   →执行→information_schema 零残留断言→行数守恒比对。
6. **警示**：入库目标别选平台 `c1_*` 簿记/业务表（loader 无守卫，schema_version 事故根因）。

## 挂起项（未立项）

- 108 首行/错字；Word 输出、双层 PDF 导出、漏提覆盖视图（问过未立项）；
  B 轮审计平台化（reviewer 身份）；隔离区解决 UI；多表 union；Docling vs MinerU 研究；
  入库目标守卫（禁选平台表，小改可选）；抽取/入库规则版本耦合的结构性重设计
  （用户自研中）。

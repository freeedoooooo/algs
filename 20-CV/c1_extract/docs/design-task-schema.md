# 设计稿 · 任务化命名 + 去外键 + 表注释完善 + tmp 收敛 + 脚本清理

> 状态：**已批准**（2026-11-21 用户三项裁决：① run→task 全链条改；
> ② 目的表名 `extract_load_dest`；③ 历史迁移 001–006 压成单个 baseline）。
> 前置：[design-c1-storage.md](design-c1-storage.md)（DB-only / run_file 粒度，已实现）。
> 本稿取代其表名/列名与 FK 表述；DB-only 契约不变。

## 0. 用户 6 项提议与裁决

| # | 提议 | 裁决 |
|---|---|---|
| 1 | 表不要外键约束；表完善＋表/字段注释补全 | ✅ 去全部 FK；**级联责任移交应用层**（§2）；补 task_file 时间戳等（§1） |
| 2 | extract_run → extract_task（run 不好理解） | ✅ **全链条**：表/列/API/URL/日志/导出/前端文案一起改（§3） |
| 3 | extract_source_file → extract_file | ✅ 列 source_file_id → file_id |
| 4 | 目的表 → extract_load_dest | ✅（用户原文 extact 少 r，已确认补正）；列 destination_id → load_dest_id |
| 5 | input/output/source 目录还需要吗 | 持久目录 C1 已删尽；现存 scratch 收进包内 **tmp/input、tmp/work**（§4） |
| 6 | 清理无用中间/迁移/数据库脚本 | 包内无死脚本（collect.py 是活模块）；**001–006 压成 001_baseline.sql**，配置库一次性升级后删升级脚本（§5） |

## 1. 最终表结构（001_baseline.sql，13 业务表 + schema_version）

原则：**无 FK 约束**；引用列全部有索引覆盖（唯一键前缀或显式 KEY）；
每表 COMMENT、每列 COMMENT；时间 DATETIME 应用层 UTC；JSON 原生类型。

| 表 | 前身 | 变化 |
|---|---|---|
| `extract_file` | extract_source_file | 改名；content LONGBLOB NOT NULL（原件字节）；uk sha256 |
| `extract_template` | 同名 | 注释完善 |
| `extract_template_version` | 同名 | 去 fk_tv_template |
| `extract_load_dest` | extract_destination | 改名；conn_ref 凭据引用制不变 |
| `extract_load_mapping` | 同名 | 去 2 FK；destination_id→load_dest_id；**补 created_at** |
| `extract_task` | extract_run | 改名；destination_id→load_dest_id；去 3 FK；idx_state |
| `extract_task_file` | extract_run_file | 改名；run_id→task_id、source_file_id→file_id；去 2 FK；**补 created_at / updated_at**；uk(task_id,file_id) |
| `extract_quarantine` | 同名 | run_id→task_id、run_file_id→task_file_id；去 2 FK |
| `extract_load_log` | 同名 | 同上＋destination_id→load_dest_id；去 3 FK；uk 回执不变 |
| `extract_staging_record` | 同名 | run_file_id→task_file_id；去 FK；**补 updated_at**（patch 可追溯）；uk(task_file_id,record_index) |
| `extract_staging_field` | 同名 | 去 CASCADE FK；注释补全（id/record_id/created 无→有） |
| `extract_staging_lineage` | 同名 | 去 CASCADE FK；注释补全 |
| `extract_artifact` | 同名 | run_file_id→task_file_id；去 CASCADE FK；**id INT→BIGINT**（与他表一致）；uk(task_file_id,name) |
| `schema_version` | 同名 | 迁移器簿记，非业务表，不加前缀 |

「完善」克制清单：只补 task_file 时间戳、staging_record.updated_at、
load_mapping.created_at、artifact.id 升 BIGINT——不加预测性字段。

## 2. 去外键的代价与应用层级联（应力测试）

006 刚修完「无 FK＋应用不清子表 → 578 孤儿行」。去 FK 是常见生产做法
（分库分表/写入性能/DDL 灵活），但**孤儿防线从此只在应用层**。盘点全部删除路径：

| 路径 | 现状 | 去 FK 后 |
|---|---|---|
| `content_db.save_records` 重跑 | DELETE record，field/lineage 靠 FK CASCADE | **显式先删 field/lineage（record_id IN 子查询）再删 record**，同事务 |
| `catalog.delete_source` | 先 COUNT task_file 引用，有引用拒删 | 不变（守卫本就在应用层） |
| task 删除 | **API 未暴露** | 不新增；验收清理走 child-first |
| 验收/运维清理 | child-first 手写 | 顺序：field/lineage→record→artifact→quarantine→load_log→task_file→task→file |

验收「重跑级联」项改为验证**应用层级联**：重跑后 field/lineage 行数与 record
投影一致、无孤儿（LEFT JOIN 反查 = 0）。引用完整性不再有 DB 兜底，
**任何新增删除路径必须照 §2 清单补子表清理**——写入本稿与交接文档作为硬约束。

## 3. 全链条改名映射

| 层 | 旧 | 新 |
|---|---|---|
| 表/列 | 见 §1 | 见 §1 |
| Python 函数 | create_run / add_run_file / set_run_file_state / run_file_ids / list_runs / get_run | create_task / add_task_file / set_task_file_state / task_file_ids / list_tasks / get_task |
| API 路由 | /api/runs…、/runs 页 | /api/tasks…、/tasks 页 |
| URL 参数 | /staging?run=&file=、/runs?run= | /staging?task=&file=、/tasks?task= |
| 响应/请求键 | run_id / run_file_id / source_file_id / source_file_ids | task_id / task_file_id / file_id / file_ids |
| 日志 | logs/run_<id>.log | logs/task_<id>.log |
| 导出布局 | output/run_<id>/ | output/task_<id>/ |
| 前端 | runs.html / runs.js、文案「运行」 | tasks.html / tasks.js、文案「任务」 |
| 保留 | /srcfiles/<id>、/api/sources、资料库 UI 概念 | 不变（「源文件」语义仍成立，表名 extract_file 不影响 UI 叫法） |

本地工具无外部兼容负担，旧 URL 不做重定向 shim（用户裁决全链条改）。

## 4. 目录收敛（tmp/）

持久 input/output/sources 在 C1 已删尽，**不需要也不恢复**。现存磁盘：

| 目录 | 性质 | 处置 |
|---|---|---|
| 系统 temp 的 c1_in_/c1_case_ scratch | 运行期临时 | 收进 **tmp/input/**（上传副本，mkdtemp prefix=in_）、**tmp/work/**（提取工作区，prefix=case_），跑完即清；config.TMP_DIR=DATA_ROOT/tmp，启动 makedirs |
| logs/ | 运维日志（历史可查） | 留原位 |
| data/（secrets/backup） | 凭据/灾备 | 留原位 |
| export --out | 用户指定按需导出 | 不变 |

tmp/ 进 .gitignore（替换旧 input/output/sources 条目）。验收 scratch_clean
改查 tmp/input、tmp/work 无 in_*/case_* 残留。

## 5. 迁移压缩与一次性升级

- **001_baseline.sql**＝§1 最终态（CREATE TABLE IF NOT EXISTS＋内置模板种子）；
  002–006 删除。新库首连直接建最终态，schema_version={1}。
- **配置库一次性升级**（临时 Python 脚本，用完即删）：
  1. 先查库状态（行数基线：task 21 / task_file 25 / file 3 / record 29 / field 493 / lineage 493 / artifact 17）；
  2. pymysql 整库备份 data/backup/pre_task_*.sql（本机无 mysqldump）；
  3. **先 DROP 全部 extract_% 表 FK**（information_schema 生成），再 RENAME 4 表、
     CHANGE 列名（带完整定义＋注释）、补新列、MODIFY artifact.id、逐表 COMMENT、
     schema_version 重置 {1}；
  4. 验证行数基线不变＋无 FK＋注释齐全；失败回滚＝备份＋旧代码。
- **8765 协调**：升级即令旧代码失效（表名已改）——升级前停 8765（需用户授权/自停），
  升级＋验收完成后以新代码重启。
- db.py 执行器不动（编号门禁原样）；baseline 内注释/COMMENT 字符串**不含半角分号**
  （执行器按 ; 朴素切分）。

## 6. 脚本清理盘点

| 文件 | 判定 |
|---|---|
| collect.py | **活模块**（映射层），保留 |
| accept_records_db.py / accept_artifacts_db.py | 保留，随新名改写（§7） |
| export_artifacts.py / check_env.py | 保留，随新名改 |
| store/migrations/002–006 | **删除**（压入 baseline） |
| 一次性升级脚本 | 用完即删 |
| data/backup/pre_005/pre_006 | 保留（灾备历史，非脚本） |

## 7. 验收

两套 accept 随新名/新 tmp/门禁 [1] 改写，六项契约不变；顺序跑严禁并行；
级联项验应用层删除（§2）；合成数据验完 child-first 清理；真实数据只读；
断库仍用不可达 DSN 临时服务 8797，真链路 8799，用户 8765 协调后动。
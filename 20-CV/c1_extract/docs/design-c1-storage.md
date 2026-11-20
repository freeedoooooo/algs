# 设计稿 · C1 存储演进（命名去 MVP 化 + 附件模型纯关系化）

> 状态：**待批准**（2026-11-20 用户提出 5 项演进）。前置：
> [design-artifacts-db.md](design-artifacts-db.md)（DB-only 已实现）。
> 本稿批准后取代其 §4 表结构与 §5 接缝表述。

## 0. 用户 5 项提议与评估

| # | 提议 | 评估 |
|---|---|---|
| 1 | `CV_MVP_*` → `C1_EXTRACT_*`，清理多余配置，编码去 mvp 化 | ✅ 同意，含包名 mvp→c1_extract（待确认） |
| 2 | artifact 不要 case_rel，关联 source_file | ⚠️ **粒度盲点**：应关联 **run_file**，见 §1 |
| 3 | sources 的 sha 前缀文件名纯多余 | ✅ 同意，sha/name 已在 source_file 表 |
| 4 | run_file/source_file 的 relPath 废弃；source_file 加附件字段 | ✅ 同意，content LONGBLOB 直接进 source_file |
| 5 | 批次时间戳命名逻辑废弃（已有 run 表） | ✅ 同意，batch_tag 退役，URL 改 run id |

## 1. 盲点：附件粒度必须是 run_file，不是 source_file

产物是**某次运行**的输出，不是源文件的固有属性：

- 同一 source 可被多次运行（重跑/换模板/换参数）。staging 记录按 **run_file_id**
  保留各次运行的结果；若附件按 source_file_id 存，重跑会**覆盖**旧 run 的
  pages/rectified/extract.json → 旧 run 的暂存记录血缘（叠加框/原图回溯）
  指向新 run 的图，**跨 run 回溯断裂**。
- run_file ＝「这次运行里的这个文件」，与今天的 case 目录 **1:1**，
  迁移无损；重跑＝新 run 新 run_file 新附件，旧 run 完整可回溯（与 staging 同哲学）。

**结论**：`extract_artifact.run_file_id BIGINT NOT NULL`（FK→run_file，级联删），
UNIQUE(run_file_id, name)。case_rel 列删除。

## 2. 新表结构（005_c1_storage.sql）

```sql
-- source_file：原件字节进表（提案 3/4）
ALTER TABLE extract_source_file
  ADD COLUMN content LONGBLOB NOT NULL AFTER size_bytes,
  DROP COLUMN rel_path;
-- 回填：从 extract_artifact(case_rel='sources') 按 sha8_name 匹配搬入，随后删该行

-- run_file：目录路径退役（提案 4）
ALTER TABLE extract_run_file DROP COLUMN output_rel_dir;

-- run：批次戳退役（提案 5）
ALTER TABLE extract_run DROP COLUMN batch_tag;

-- artifact：重建为 run_file 粒度（提案 2，§1 裁决）
CREATE TABLE extract_artifact_v2 (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_file_id BIGINT NOT NULL,
  name VARCHAR(200) NOT NULL,          -- 'pages/p1.png'、'对照报告.html'
  kind VARCHAR(20) NOT NULL,
  mime VARCHAR(100) NOT NULL,
  size_bytes INT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  content LONGBLOB NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_artifact (run_file_id, name),
  KEY idx_artifact_sha (sha256),
  CONSTRAINT fk_art_rf FOREIGN KEY (run_file_id)
    REFERENCES extract_run_file(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
-- 迁移：旧 case_rel → output_rel_dir 匹配 run_file；sources 行搬入 source_file；
-- 无主孤儿行（run 已删）丢弃并记 warning；搬完 RENAME 替换旧表
```

**run.json 退役**（连带裁决）：run 级状态/params/template/文件 state 已全部在
run/run_file 表；runs API 直接由表投影组装（返回形状不变），不再存 run.json 附件。
少一类附件、少一个写点。

## 3. 命名与配置清理（提案 1）

| 旧 | 新 |
|---|---|
| env `CV_MVP_HOST/PORT/MAX_FILE_MB/WARMUP/DATA_ROOT` | `C1_EXTRACT_*` 同名 |
| env/secrets `CV_PLATFORM_DB` | `C1_EXTRACT_DB`（secrets.json 键同步改） |
| 包目录 `mvp/` | `c1_extract/`（待确认；uvicorn 命令随之变） |
| scratch 前缀 `cv_in_/cv_case_` | `c1_in_/c1_case_` |
| config `INPUT_DIR/OUTPUT_DIR/SOURCES_DIR`＋makedirs | **删除**（无持久目录；scratch 走 tempfile） |
| `migrate_records_to_db.py` / `migrate_artifacts_to_db.py` | **删除**（磁盘已空、回填已完成，一次性脚本退役；ensure_* 助手移入验收脚本） |
| `batch_tag()` 同秒去重、`<tag>_<name>` 文件命名、records name 前缀 | **删除**：run id 天然唯一；scratch 内用原名；files[].name＝源文件名 |

保留：LOG_DIR/DATA_DIR（运维态/凭据）、ASSETS_DIR/TEMPLATES_DIR、
`export_artifacts.py`（审计/file:// 出口，目录布局改 `output/run_<id>/<源名>/…`）。

## 4. API / 前端连锁

- `/files/{case}/{path}` → `/files/{run_file_id}/{path}`（白名单/raw 403/ETag 不变）。
- `/srcfiles/{sha8_name}` → `/srcfiles/{source_id}`（**名字会撞**：同名不同字节＝两行，
  sha 前缀原本就是消歧的；改 id 路由彻底解决）。
- `/api/runs/{batch}/…` → `/api/runs/{id}/…`；列表项带 id/created_at/源名，
  前端展示时间用 created_at（batch_tag 的显示职责由它承接）。
- staging `_run_files` 改按 run_id 查；`get_records(case)` → `get_records(run_id)`
  （files[] 投影不变，name＝源文件名）。
- 报告 iframe/预览链接：staging.js/runs.js/upload.js/sources.js 里 case 路径
  全部换 run_file_id/source_id（API 返回里带 id）。
- 报告内部相对引图（cards.file_url）**不变**——同 run_file 命名空间内兄弟相对路径。

## 5. 迁移与回滚

- 005 单迁移脚本内完成搬数（幂等：按 schema_version 门禁）；搬前逐件 sha 校验。
- 现有 8 个 run、76 条 staging、46 附件全量映射（case↔run_file 经 output_rel_dir）。
- 回滚＝005 前的 DB dump（迁移前自动 mysqldump 到 data/backup/）＋旧代码。
- 用户 8765 旧代码不受影响（重启才切新代码）；**secrets.json 键改名后旧代码读不到
  DB**——但旧代码本就 file 模式不读库，无实际影响。

## 6. 验收

两套 accept 脚本随新模型重写（run id/source id 路由、无 batch_tag、
source_file.content 直读）；顺序跑；六项契约不变（幂等/级联/patch/查询/真链路/断库 503）。

## 7. 待裁决

1. 附件粒度＝**run_file_id**（§1 盲点论证）——同意？
2. **run.json 退役**，runs API 由表投影——同意？
3. **包名 mvp → c1_extract**（命令/文档/脚本全改）——同意？还是只改 env 前缀？
4. batch_tag 列直接 DROP（展示用 created_at）——同意？
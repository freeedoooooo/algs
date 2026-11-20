# 设计稿 · 产物附件入库（MySQL BLOB）

> 状态：**已批准并实现**（2026-11-20）。动机：部署/迁移＝代码＋一个 DB dump，
> 不再 rsync 数据目录。配套：[design-records-db.md](design-records-db.md)（B 已实现）、
> [design-data-pipeline.md](design-data-pipeline.md)（四层分层，本稿再次重述）。
> 本稿**吞并**上一挂起决策「records.json 快照简化」：全量入库后自动快照退役，
> 导出命令承担备份/审计职责。
>
> **批准记录**：① 范围＝选项 1 全量入库；② DB 必选、D1 退役，file:// 改按需导出；
> ③ 自动快照退役，records 完整关系化（三表）存储；④ **只做 MySQL**——PG 方言接缝
> 现在不做，留给以后引入框架/ORM 重构时统一解决（用户裁决）。
> ⑤ **file 模式整体删除**（2026-11-20 用户裁决：file 模式只是初期调试过渡产物）——
> 无 `CV_MVP_RECORDS_STORE`/`CV_MVP_ARTIFACT_STORE` 开关，DB 是唯一模式；
> 回滚不再靠开关，靠 export_artifacts.py 导出＋旧版本代码。

---

## 0. 可行性事实（2026-11-20 实测）

| 项 | 值 | 结论 |
|---|---|---|
| 数据总量 | output 7.1M ＋ input 632K ＋ sources 484K ≈ **8.2MB** | 轻量级，BLOB 无压力 |
| 单件最大 | 对照报告.html 413K；多页 case 3.6M（pages/*.png 为主） | 远小于 packet |
| MySQL | 8.0.36，`max_allowed_packet`=**1GB**，buffer pool 4GB | LONGBLOB 可行 |
| 上传上限 | `MAX_FILE_MB`=20 | 单 BLOB ≤20M，安全 |
| 服务方式 | `/files/`=OutputFiles(StaticFiles) 白名单＋raw 403（app.py:86-107）；`/srcfiles/`=StaticFiles | 换 DB 流式路由，规则保留 |
| 报告引图 | **相对路径**引兄弟产物（cards.file_url） | DB 化后在线相对路径仍成立；**file:// 直开牺牲**（导出恢复） |
| runs 列表/报告重定向 | 扫 `output/*/run.json`、`os.path.isfile`（app.py:677-681、430） | db 模式须改查 DB |

引擎（paddle）仍需**临时 scratch 磁盘**读图路径——「不用本地磁盘」＝**无持久状态**，
不是零磁盘占用；scratch 用 tempfile，跑完即清。logs/、data/secrets.json 留磁盘
（运维态/凭据，非产物）。

## 1. 产物清单与读写点

| 产物 | 量级 | 写点 | 读点 |
|---|---|---|---|
| raw/*.json | 13K/case | pipeline | 不对外（403），审计导出 |
| extract.json | 33K | content.save_extract | content.get_extract、报告 json 段 |
| records.json | 42K | B 快照导出（**本稿退役**） | 暂存页（已走 DB） |
| run.json | 0.6K | content.save_run | runs 列表/详情 |
| 对照报告.html | 413K | builder/cards 直写 | /files/、iframe |
| *.md / table_*.csv | 4K/3K | cards 直写 | 报告相对链接下载 |
| source/rectified/boxes/pages/*.png | 0.3-3M | pipeline cv2 直写 | /files/、staging 回溯 |
| sources/{sha8}_* | 484K 总 | upload _register_source | /srcfiles/ 缩略图/原件 |
| input/{batch}_* | 632K 总 | upload 批次副本 | pipeline 读路径、迁移脚本 |

## 2. 选项

| 选项 | 做法 | 代价 | 判定 |
|---|---|---|---|
| **1 全量入库（推荐）** | 所有持久产物进 `extract_artifact` BLOB；磁盘仅 scratch；导出命令按需还原目录树 | DB 成唯一事实源（D1 退役）；file:///常驻审计改按需；重构读写点 | 与 B 的 trajectory 一致，单单元部署/迁移 |
| 2 仅文本入库 | html/json/md/csv 进 DB，图片留磁盘 | 迁移仍两单元；图片占 ~90% 体积，目标落空 | 半截子，不推荐 |
| 3 现状＋打包脚本 | mysqldump＋tar 数据目录，一键两件套 | 零架构改动；双存储漂移类问题仍在 | 保守兜底/回滚态 |

推荐 **1**，理由：用户已接受 DB 为核心（B），且上一轮已质疑 D1 价值；
全量入库消灭「DB 与文件漂移」整类问题（快照决策自然吞并）。
**但下列翻转必须显式再批准**（§3）。

## 3. 架构翻转与代价（应力测试）

1. **D1 退役，DB 必选**：DB 挂＝上传/登记即 503（run 都建不出来）；运行中写库失败
   ＝整 run 显式 failed；读 503。上一稿「DB 是可选索引、引擎层照常」哲学作废。
   ~~降级开关保留为 file 模式回滚~~ → **批准项⑤：file 模式已删除，无开关**。
2. **file:// 直开 / 常驻逐层审计 → 按需**：`export_artifacts.py`（DB→output/sources
   目录树，逐字节 sha 校验）恢复审计与 file://。md/CSV 下载改 HTTP stream（download 属性照旧）。
3. **自动快照退役**：records.json 不再每次写导出；staging 三表是唯一记录源；
   导出命令含 records.json 重建（get_records 投影）。
4. **DB 体积/dump 时间随图片增长**：现在 8MB  trivial；规模化后 seam 可换对象存储驱动
   （artifact 接缝与 content 接缝同构）。单事务批量写一个 case 的产物，限制 fsync。
5. **PostgreSQL 以后随框架重构解决**（用户裁决：现在只做 MySQL，不建方言接缝）。
   差异备忘（重构时参考）：LONGBLOB→BYTEA、AUTO_INCREMENT→IDENTITY、
   DATETIME→TIMESTAMP、lastrowid→RETURNING、`DELETE t FROM t JOIN`→`DELETE … USING`。
6. **raw 403 / 白名单规则保留**：DB 路由按 kind 拒 raw；路径不再落磁盘， traversal 面消失
   但 name 仍 sanitize。
7. **浏览器缓存**：no_cache 中间件已强制 revalidate；DB 路由带 `ETag=sha256`，未变 304。

## 4. 表结构（004_artifacts.sql，MySQL 方言）

```sql
CREATE TABLE extract_artifact (
  id INT AUTO_INCREMENT PRIMARY KEY,
  case_rel VARCHAR(160) NOT NULL,   -- '<case目录名>' 或 'sources'
  name VARCHAR(200) NOT NULL,       -- case 内相对路径：'pages/p1.png'、'对照报告.html'
  kind VARCHAR(20) NOT NULL,        -- json/html/md/csv/image/raw/source
  mime VARCHAR(100) NOT NULL,
  size_bytes INT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  content LONGBLOB NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_artifact (case_rel, name),
  KEY idx_artifact_sha (sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- 源原件＝`case_rel='sources'` 行（sha 去重已由 extract_source_file 保证）；
  **input 批次副本退役**（字节同源，upload 直接用请求字节→scratch）。
- 重跑＝同 (case_rel,name) upsert 替换（与 staging 级联同哲学）。
- JSON 三件（extract/run/records 导出）kind=json，content 存 utf8 字节，驱动无关。

## 5. 接缝与实现方式（已落地，DB-only）

- `store/artifact.py`＝门面，直接委托 `store/artifact_db.py`（BLOB upsert）；
  `store/content.py` 同构：extract/run 经 artifact JSON 接缝，records 经 content_db
  三表。**无 file 实现、无 env 开关**（批准项⑤）；未来 MinIO＝只换 artifact_db 驱动。
  API：`save/save_json/get/get_json/list/cases/delete/delete_case/exists`；
  kind/mime 由文件名推断（raw/ 前缀→kind=raw）。
- **写点＝scratch＋ingest（管线/报告生成零改动）**：case 工作目录是 tempfile
  scratch，pipeline/builder/cards 照旧写文件；报告先于 records 写库生成（断库时
  引擎产物仍完整），随后 `_ingest_case` 遍历 scratch 全量入 BLOB，随即 rmtree。
  input 批次副本同样落 scratch（字节事实源在 sources BLOB），run 结束 finally 清尽。
  run.json 直写 DB（不经 scratch）。目录状态写失败上抛→整 run failed，不降级。
- **读点**：`/files/{case}/{path:path}`、`/srcfiles/{name:path}` 恒为 API 路由
  （白名单 `_files_guard`，raw 403，ETag=sha256，If-None-Match→304）；仅 /static
  挂 StaticFiles。runs 列表/详情/`/extract-report` 重定向查
  `catalog.list_run_cases()`＋run.json BLOB；批次戳去重查 `catalog.list_batch_tags()`。
- **DB 必选**：上传时模板解析/目录登记失败→整批 503（不建 run）；运行中写库失败→
  整 run failed；读端点 DB 故障→503；`/api/templates` 不再降级内置清单。
  check_env.py 平台库连通性为**必选项**（不通即退出码 1）。
- **方言接缝不做**（批准项④）：SQL 全部 MySQL 方言收敛在 store/*_db.py，
  以后框架重构统一替换。

## 6. 迁移与导出

- `migrate_artifacts_to_db.py`：幂等扫 output/sources 逐件 sha 登记＋BLOB 写入；
  失败批次（缺件）跳过记 warning；input 副本不迁（退役）。磁盘清空后为 no-op。
- `export_artifacts.py`：DB→目录树（output/<case>/…＋sources/），含 records.json 重建；
  逐件 sha 校验；用途＝审计/file:// /灾备。
- 回滚：无开关（批准项⑤）。灾备＝export 导出目录树＋回退旧版本代码。

## 7. 验收清单（DB-only，`mvp/accept_*_db.py`，顺序跑严禁并行）

`mvp/accept_records_db.py`：1 回填幂等+真实 case 投影往返一致 · 2 重跑级联 ·
3 patch_record · 4 跨批查询 · 5 真链路（无持久磁盘）· 6 断库上传/runs/暂存/模板 503。

`mvp/accept_artifacts_db.py`：1 回填幂等+全量读回 sha 自洽 · 2 真链路无持久磁盘+BLOB ·
3 /files mime/ETag 304/raw 403/records.json 404/srcfiles · 4 runs/报告重定向/暂存/查询 ·
5 export 逐字节一致+records 语义+file:// 在树内 · 6 断库上传/runs/files/报告/暂存 503。

上传字节取自 sources BLOB（磁盘已清空）；断库用不可达 DSN 临时服务（8797），
真链路临时服务 8799；用户 8765 不动。

## 8. 批准项（已裁决 2026-11-20）

1. 范围＝**选项 1 全量入库** ✅
2. **DB 必选、D1 退役**；file:///常驻审计改**按需导出** ✅
3. **自动快照退役**，records 完整关系化存 DB（三表），导出命令承担备份 ✅
4. **只做 MySQL**，方言问题留给以后框架重构，现在不建方言接缝 ✅
5. **file 模式整体删除**（初期调试过渡产物）：无存储开关，DB 唯一模式 ✅
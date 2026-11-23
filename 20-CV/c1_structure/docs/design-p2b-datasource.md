# P2b 入库数据源重构设计稿（左数据源 · 右映射）

日期：2026-11-21 ｜ 状态：已批准并实现（两套验收 7/7＋6/6 PASS，浏览器金路径通过）
前置：P2 已交付（design-p2-load.md）。本轮把「目的地＝conn_ref 引用」改为
「数据源＝页面明文配置的库连接」，映射从 JSON 契约改为字段行表。

## 〇、用户裁决（2026-11-21）

1. **数据源含库名（扁平）**：一个数据源＝一个库（host/port/账号/密码/库名
   全在数据源行上）。左侧是数据源列表（每项已含库），右侧是该数据源下的
   映射列表——主从布局，不做「连接→库」两级树。
2. **默认数据源明文落行**：迁移时解析 C1_STRUCTURE_DB（env/secrets），把
   host/port/user/password/db_name 明文写入默认行（名「产品库」），与手建
   数据源同一形态、页面可编辑。代价：secrets 轮换后默认行过期，需手动同步
   （已提示，接受）。
3. **extract_load_table＝映射绑定**：一行＝数据源×表×模板＋write_mode；
   同一物理表可被不同模板各建一行（保住现 UNIQUE 契约与多模板语义）。
   字段行＝模板字段→目标列＋is_business_key。

### 附带边界（沿用既有裁决＋本轮补充）

- **明文裁决的范围**：数据源密码明文存库、配置页可见可编辑（用户明示
  「暂时不考虑配置加密」）。但**日志永不打印凭据**、测试连接回显仍仅
  host:port/库名。**平台库自身凭据仍走 conn_ref（C1_STRUCTURE_DB）不变**——
  明文例外只覆盖 load 数据源。
- **transform 留在模板版本**（P2 裁决⑥）：「怎么洗」是提取语义，不下沉到
  目标字段行；入库时消费，暂存值保真不动。
- **零成本迁移窗口**：现 extract_load_dest / extract_load_mapping /
  extract_load_log 全 0 行、无 task 引用 load 两列（刚验证）→ 直接换表结构，
  无数据搬迁。真实数据迁移铁律照旧：先查当前库状态＋全量备份再动。
- 只 MySQL；只写已有表；门禁仅 confirmed；回执幂等；单任务串行——全部不变。

## 一、新三表 DDL（替换 001 里的 load 三表）

```sql
-- 数据源（一行＝一个库；密码明文，用户裁决；日志永不打印）
CREATE TABLE IF NOT EXISTS extract_load_datasource (
  id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  name      VARCHAR(100) NOT NULL COMMENT '显示名，唯一',
  db_type   VARCHAR(20)  NOT NULL DEFAULT 'mysql',
  host      VARCHAR(255) NOT NULL,
  port      INT          NOT NULL DEFAULT 3306,
  user      VARCHAR(100) NOT NULL,
  password  VARCHAR(255) NOT NULL DEFAULT '' COMMENT '明文（2026-11-21 裁决）',
  db_name   VARCHAR(100) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_ds_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 映射绑定（一行＝数据源×表×模板；同物理表可多模板各一行）
CREATE TABLE IF NOT EXISTS extract_load_table (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  datasource_id BIGINT       NOT NULL,
  template_id   BIGINT       NOT NULL,
  target_table  VARCHAR(128) NOT NULL,
  write_mode    VARCHAR(16)  NOT NULL DEFAULT 'upsert' COMMENT 'insert|upsert|update',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_ds_tpl_table (datasource_id, template_id, target_table)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 字段映射行（column_map_json / business_key_json 退役）
CREATE TABLE IF NOT EXISTS extract_load_table_field (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  load_table_id   BIGINT       NOT NULL,
  template_field  VARCHAR(200) NOT NULL COMMENT '记录键＝模板 schema 字段名',
  target_column   VARCHAR(128) NOT NULL,
  is_business_key TINYINT      NOT NULL DEFAULT 0,
  sort_order      INT          NOT NULL DEFAULT 0 COMMENT '展示序＝schema 字段序',
  UNIQUE KEY uk_table_field  (load_table_id, template_field),
  UNIQUE KEY uk_table_column (load_table_id, target_column)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 连带变更

- `extract_load_log`：`load_dest_id` → `datasource_id`；唯一键改
  `(task_file_id, record_index, datasource_id, target_table)`。不加 db_name
  列——数据源身份被锁定（见下），id 已唯一确定库；回执抽屉显示
  「数据源名 · 库.表」。
- `extract_task`：`load_dest_id` → `load_datasource_id`、`load_mapping_id` →
  `load_table_id`（现全 NULL，CHANGE 零风险）。
- `schema_version` 保持 [1]（重写 baseline，不新增编号——沿用 task-schema
  轮先例：基线重写＋一次性升级脚本，跑完删除脚本文件）。

### 审计一致性规则（本轮新增，防「改配置换目标」暗坑）

- **数据源被映射引用后，host/port/db_name 锁定**（PATCH → 409「已被映射
  引用，目标不可改」）；name/user/password 可改（凭据轮换合法，不改目标
  身份）。要换目标库＝新建数据源。这保证历史回执指向的库永远可追溯。
- **映射被 task 引用后只读**（无 PATCH；DELETE → 409，沿用 P2）。未被引用
  的映射可整体编辑（字段行删旧插新＋write_mode）。

## 二、迁移（一次性升级脚本，用后删）

1. **先查当前库状态**（脚本第一步，不满足即中止）：
   `extract_load_dest / extract_load_mapping / extract_load_log` 行数＝0；
   `extract_task.load_dest_id / load_mapping_id` 全 NULL。
2. **全量备份** `data/backup/pre_load_ds_<ts>.sql`（mysqldump，沿用
   task-schema 轮命令形态；备份含旧三表 DDL，可回退）。
3. 裸 pymysql 连接（**不走 db.connect 门禁**——门禁会按新 001 先建出新表，
   老坑）：DROP 旧三表（log→mapping→dest 子先父后）→ CREATE 新三表 →
   ALTER extract_task CHANGE 两列。
4. **落默认数据源**：`db._parts(db.resolve_conn('C1_STRUCTURE_DB'))` →
   INSERT（name='产品库', db_type='mysql', host/port/user/password/db_name）。
   脚本输出仅 host:port/库名，不打印密码。
5. 验证：新三表存在、默认行 1 条、task 两列改名后全 NULL、真实基线不变
   （records 135 / field 1867 / lineage 1867 / artifact 98 / file 5 /
   tasks 11 / 模板 1）。删除升级脚本文件。
6. 001_baseline.sql 同步重写（新库直接得到新结构＋无默认行；默认行只在
   升级脚本落——新部署首启时由 app 启动钩子补种？不：保持简单，新库也走
   「首启自动种默认行」——db._migrate 后 catalog.ensure_default_datasource()
   幂等补种（name 已存在则跳过）。升级脚本与首启共用该函数。）

## 三、store 层（catalog / loader / db）

### db.py

- 新增 `connect_direct(p, autocommit=False)`：p＝{host,port,user,password,
  database}，pymysql 参数与 connect() 完全一致（utf8mb4 / connect_timeout=5），
  **不跑迁移**。平台库仍走 connect(ref)。

### catalog.py（dest/mapping 函数族整体改名换形）

- `list_datasources()` → [{id,name,db_type,host,port,user,password,db_name,
  table_count}]（含密码——页面明文裁决；API 响应同形）。
- `get_datasource(id)`；`create_datasource(name,host,port,user,password,
  db_name)`（name 非空唯一→Conflict；mysql only；host/db_name 非空；port int）。
- `update_datasource(id, …)`：name/user/password 恒可改；host/port/db_name
  被 extract_load_table 引用→Conflict。
- `delete_datasource(id)`：被引用→Conflict。
- `ensure_default_datasource()`：幂等种「产品库」（解析 C1_STRUCTURE_DB；
  解析失败静默跳过——断库启动不炸，页面可手建）。
- `list_load_tables(datasource_id=None)` → [{id,datasource_id,datasource_name,
  db_name,template_id,template_name,target_table,write_mode,field_count,
  business_keys}]。
- `get_load_table(id)` → 上行＋fields:[{template_field,target_column,
  is_business_key,sort_order}]（按 sort_order）。
- `create_load_table(datasource_id,template_id,target_table,write_mode,fields)`：
  数据源/模板存在；当前版本 schema fields（isinstance dict，passthrough→400）；
  覆盖校验（全字段、无多余、列不重复）；upsert/update 须 ≥1 业务键；
  UNIQUE→Conflict。fields 行按 schema 字段序写 sort_order。
- `update_load_table(id,write_mode,fields)`：被 task 引用→Conflict；否则同
  create 校验＋字段行删旧插新（target_table/template_id/datasource_id 不可改
  ——改这三者＝新绑定，走新建）。
- `delete_load_table(id)`：task 引用→Conflict；先删字段行再删主行。
- `set_task_load(task_id, datasource_id, load_table_id)`。
- `add_load_log / list_load_logs`：datasource_id 改名；回执行带
  datasource_name/db_name（JOIN）。
- task 文档 load 块：{datasource_id, load_table_id, datasource_name, db_name,
  target_table, write_mode}。

### loader.py

- `connect_datasource(ds)` → db.connect_direct（LookupError 不再出现——
  参数齐全；连接失败仍 OperationalError→503）。
- `list_tables(ds)` / `list_columns(ds, table)`：information_schema
  `WHERE table_schema=%s`（ds.db_name，显式库名不再依赖连接默认库）。
- `validate_fields(fields, schema_fields, write_mode)` 取代
  validate_column_map：覆盖/重复/业务键三校验（契约不变，载体变）。
- `preflight(ds, table_row)`：列存在性（不变）。
- `write_record / apply_transform / review_gate / LoadRecordError`：
  **纯函数零改动**（仍收 column_map dict＋bk list；service 从字段行组装）。
  单测 22 个里 transform/gate/write_record 部分原样保留。

## 四、service.py

- `launch_load(task_id)`：task.load → get_load_table（含字段行）→
  get_datasource → loader.preflight → review_gate（不变）→ launch。
- `launch(load=ctx)`：ctx={datasource_id, load_table_id}。
- `run_load`：cm={f.template_field: f.target_column}、bk=[f.target_column
  where is_business_key]；连接走 connect_datasource；回执 datasource_id；
  隔离/重试/错误分类/STATE/日志全不变。

## 五、app.py 路由

| 路由 | 说明 |
|---|---|
| GET/POST `/api/load/datasources` | 列表（含密码明文）/ 新建 |
| PATCH/DELETE `/api/load/datasources/{id}` | 编辑（目标锁定规则）/ 删除（引用 409） |
| POST `/api/load/datasources/{id}/test` | 试连，回显仅 host:port/db；失败 503 |
| GET `/api/load/datasources/{id}/tables` | 该库物理表 introspection |
| GET `/api/load/datasources/{id}/columns?table=` | 列 introspection |
| GET/POST `/api/load/tables` | 映射列表（?datasource_id= 过滤）/ 新建 |
| GET/PATCH/DELETE `/api/load/tables/{id}` | 详情（含字段行）/ 编辑（引用 409）/ 删除 |
| POST `/api/tasks/{id}/load`、load-log、quarantine | 不变（内部 id 改名） |

- 上传 `_load_preflight`：body `load_datasource_id`＋`load_table_id`（int）；
  映射存在→映射.datasource_id==传入数据源→模板匹配→schema 字段→
  loader.preflight。错误文案沿用「目的地/映射」措辞改「数据源/映射」。
- `db_error_status` 不变；503 语义不变（断库上传/列表/暂存/模板全 503）。

## 六、前端

### /load 页重做（左数据源 · 右映射）

- 布局：`.loadwrap{display:flex;gap:12px}`；左 `.panel` 宽 300px 数据源
  列表，右 `.panel flex:1` 映射列表。
- 左列表项：name（加粗）＋`host:port/db_name`（mono 小字）＋映射数 badge；
  点击选中（高亮）→ 右侧刷新；行内按钮：试连 / 编辑 / 删除（mini）。
  顶部「＋ 新建数据源」。
- 右列表列：目标表 · 模板 · 写入模式 · 字段数 · 业务键 · 操作（编辑/删除）；
  顶部「＋ 新建映射」（未选数据源禁用）；空态提示。
- **数据源抽屉**（复用 .drawer）：name/host/port/user/password/db_name 全
  type=text（明文裁决，密码可见可编辑）；编辑态被引用→host/port/db_name
  disabled＋提示「已被映射引用，目标锁定；账号密码可改」。保存→POST/PATCH；
  试连按钮→回显 host:port/db 或 503 原因。
- **映射抽屉**（宽抽屉，复用现 dmap 机制）：数据源（固定显示选中项）·
  模板 select · 目标表 select（introspection）· write_mode select ·
  字段行（模板字段只读＋列 select＋业务键 checkbox）；保存→POST/PATCH
  /api/load/tables（fields 数组）。编辑态被 task 引用→整抽屉只读＋提示。
- 删除走 confirm；409/400 原因直显（.msg）。
- 样式：load.css 新增 .loadwrap/.dslist/.dsitem(.active)/.dsmeta；
  其余复用 shell.css/templates.css token（紧凑规格不变）。

### upload.html/js

- destsel→数据源 select（选项「name · host/db」）；mapsel→映射 select
  （按 模板＋数据源 过滤，选项「target_table · write_mode」）；
  loadFields() 返回 {mode:'load', load_datasource_id, load_table_id}。

### tasks.js / staging.js / shell.js

- load 块字段改名：datasource_name/db_name/target_table/write_mode；
  modebanner/抽屉详情/回执抽屉头显示「数据源名 · 库.表」；
  gateinfo/门禁/重试逻辑零改动。

## 七、测试与验收

- **单测**：test_load_rules 增补 validate_fields（覆盖/重复列/无业务键）；
  write_record/transform/gate 22 个原样；test_collect_selectors 11 个不动。
- **套件 item 7 重写**（records 7 项结构不变）：
  - 数据源 CRUD：API 建合成数据源 `_accept_p2_ds`（参数取自
    db._parts(resolve_conn)，**不打印密码**）＋试连回显仅 host:port/db；
    默认「产品库」种子行存在断言。
  - 目标锁定：被引用数据源 PATCH host→409、PATCH password→200；
    映射被 task 引用 PATCH/DELETE→409。
  - 映射契约 400（覆盖不全/重复列/upsert 无业务键）＋上传预检 400×3
    （缺数据源/映射、数据源不匹配、模板不匹配、表不存在）。
  - Leg A/B/C 全保留（真链路 loaded、transform 隔离 partial、ALTER 重试
    幂等、跨任务 upsert→update），回执键 datasource_id。
  - baseline() 改数新三表；**期望含默认种子行 1**（datasources=1, tables=0,
    fields=0, log=0, quarantine=0）；清理后守恒照旧。
- **两套顺序跑**（8799/8797 共用，禁并行）＋浏览器黄金路径（左列表→右
  映射→两抽屉→上传 mode=load→门禁→入库→回执）＋合成全清理＋基线核对。
- 8765 用户自启服务需重启才见新页（不擅自 kill，收尾提示）。

## 八、实施顺序

1. 001 重写＋一次性升级脚本（查状态→备份→DROP/CREATE/ALTER→种默认行→
   验证→删脚本）＋db.connect_direct＋catalog.ensure_default_datasource
2. catalog/loader/service/app 后端改名换形＋单测
3. /load 左右布局＋两抽屉＋upload 联动＋tasks/staging/shell 改名
4. 套件 item 7 重写＋两套顺序跑＋浏览器黄金路径＋清理＋基线守恒
5. 文档/记忆收尾（含凭据规则例外：load 数据源明文，平台库仍 conn_ref）

## 九、已知缺口 / 盲点（明示）

- 明文密码会进 DB 备份/导出/dump——裁决接受；日志与回显边界守住。
- 默认数据源明文快照在 secrets 轮换后过期——手动同步（页面可编辑）。
- 数据源目标锁定（host/port/db_name）是本轮新增审计规则，换目标＝新建。
- 映射被 task 引用后只读（P2 即无更新路由，本轮成文）。
- reviewer 身份（B 轮）、隔离区处置 UI、loaded 数据回滚、多目的地扇出、
  多表 union——仍不在本轮。
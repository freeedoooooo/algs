# 设计稿 · P2 入库模式（2026-11-21，已批准并实现）

> 状态：**已批准并实现**（2026-11-21 落地：后端＋前端＋单测 33＋两套验收 7/7·6/6
> ＋浏览器金路径，见 progress-handoff.md §〇.12）。
> 上游裁决（2026-11-21 用户拍板，6 项）：
> ① 触发＝**上传时选 mode=load**＋目的地＋映射＝预登记入库意图；
> ② 执行＝**校验完后手动点「入库」**（任务详情/校验台按钮）；
> ③ 门禁＝**仅 confirmed**，存在 pending/edited/rejected 整任务阻止；
> ④ rejected 也阻止——出口＝校验台 ✓ 重新确认（现有能力，已核实无迁移守卫）；
> ⑤ 目标表＝**只写已有表**（不自动建表）；
> ⑥ transform＝**最小集 trim＋number**（入库时消费，暂存值保真不动）。
> 关联：[design-task-schema.md](design-task-schema.md)（load 三表/凭据引用制）、
> [design-p1-review.md](design-p1-review.md)（四态校验）、
> [design-p1b-templates.md](design-p1b-templates.md)（schema＝入库列雏形）。

---

## 〇、定位与已知缺口

闭环最后一块：**提取 → 字段级四态校验 → 人工闸门入库 → 幂等回执**。
审计叙事：先审后入、全确认才入、每条写入有回执、重跑不重复写。

- **无 reviewer 身份**（B 轮审计平台化首补）：本轮 load_log 记不了「谁入的库」，
  已知缺口，设计不预埋假字段。
- 只做 MySQL；凭据只经 conn_ref（env / data/secrets.json），永不打印/回显
  （测试连接只回 db.safe_detail 的 host:port/库名）。
- **透传模板不可入库**：passthrough 无固定目标字段（键＝表头原文，动态），
  无法建 column_map → 入库须用 P1b 映射模板（schema_json 有 fields）。

---

## 一、现状接缝（已核实）

- 表已建好（001_baseline，**零 DDL**）：`extract_load_dest`（conn_ref 引用制）、
  `extract_load_mapping`（target_table/column_map_json/write_mode/business_key_json，
  UNIQUE(dest,template,table)）、`extract_load_log`（幂等回执，
  UNIQUE(task_file_id,record_index,dest,table)）；task 表已有
  load_dest_id/load_mapping_id；状态 VARCHAR 无 enum（`loading` 可直接用，
  前端 STATE_LABEL 已有 loading/loaded 徽标）；quarantine 已有 stage='load'。
- 入口现状：upload 显式拒绝 mode≠preview（app.py:247）；tasks_create 硬编码
  preview；`_review_target` 已对 loaded→409 只读守卫（app.py:506）。
- **坑（必须修）**：`db.connect(ref)` 对任何 ref 自动跑平台迁移——直接连目标
  业务库会把 extract_* 平台表建进人家库。加 `connect(ref, migrate=True)` 开关，
  目标库连接一律 migrate=False。
- 记录读取：`content_db.get_records(task_id)` 全保真信封（values/review/lineage）。
- catalog 无 load_dest/load_mapping CRUD；无 loader 模块（db.py  docstring 预留）。
- rejected 出口已核实：`set_review` 无迁移守卫，校验台 ✓ 对 rejected 行可见。

---

## 二、数据契约

### column_map_json（模板目标字段 → 目标表列）
```json
{ "账号": "account_no", "交易借方": "debit_amount", "对方姓名": "counterparty" }
```
- 扁平对象；键＝模板 schema_json.fields 的 name；**须覆盖全部目标字段**
  （建映射时校验，缺字段 400）；值＝目标表真实列名（introspection 校验存在）。

### business_key_json（upsert/update 去重依据）
```json
["account_no", "交易日期"]
```
- 目标列名数组；write_mode=upsert/update 时必填且列须存在。
- **应用层 upsert**（SELECT 业务键 → 存在 UPDATE / 不存在 INSERT），不依赖
  目标表唯一索引（ON DUPLICATE KEY 需唯一索引才生效，业务键未必有——
  单任务串行无并发竞态，应用层判定足够且确定性）。

### transform_json（P1b 存而不消费 → 本轮消费；入库时应用）
```json
{ "fields": [ {"target": "交易借方", "apply": ["trim", "number"]} ] }
```
- 规则按序应用；P2 仅 `trim`（去首尾空白）/`number`（转数值：去千分位逗号/
  空白→float，失败→隔离 stage=load，不写库）。
- **暂存 values/original 永不改**（审计保真）；转换只发生在写目标库那一刻，
  回执记转换后的动作，隔离记原值快照。
- 模板编辑器每字段加规则下拉（无/trim/trim+number），镜像进 transform_json。

### write_mode
- `insert`：直插（重复运行靠回执唯一键跳过，不重复写）。
- `upsert`：业务键 SELECT→UPDATE/INSERT（默认）。
- `update`：业务键 SELECT→存在 UPDATE；不存在→隔离（原因「目标行不存在」）。

---

## 三、入库引擎语义（service.load_task ＋ store/loader.py）

### 预检（上传预登记时 ＋ 点入库时，两次）
1. conn_ref 可解析＋目标库可连（migrate=False）；失败 400/503 明确报错。
2. 目标表存在（information_schema）；column_map 各列存在；
   upsert/update 业务键非空且列存在。
3. mapping.template_id 须＝任务模板版本的 template_id（映射跟模板走，
   版本间字段可能不同——**以任务快照版本的 schema 字段校验 column_map 覆盖**）。
4. 上传时预检失败→400 不建 task（早失败，不留废任务）。

### 门禁（点入库时）
- task.mode='load' 且已登记 dest/mapping；state ∈ previewed/partial
  （loaded→409「已入库」；loading→409「入库中」；failed/pending/extracting→409）。
- **全部记录 confirmed**：存在 pending/edited/rejected → 409 带计数提示
  「N 条待校验 / N 条已修改未确认 / N 条已拒绝，请先处理完」。

### 执行（后台线程，复用 STATE 单任务串行）
1. task/file state→loading；`_review_target` 守卫扩到 loading/partial/loaded
   （入库中/已入库记录只读；partial 可再点入库但不可改值）。
2. 逐记录：已有回执（唯一键）→跳过（幂等重跑）；transform→失败隔离跳过；
   按 write_mode 写目标库→成功写回执（target_pk＝业务键值 JSON 串，
   insert 无业务键时＝目标表自增 id 字符串）。
3. 目标库写失败（单条）→隔离 stage=load＋继续下一条；连接级失败→中止，
   已写回执保留。平台库写失败→整任务 failed（DB 必选原则）。
4. 终态：全成功→task/file **loaded**；有隔离/中止→**partial**（error 带摘要）；
   partial 再点入库＝只处理无回执记录（隔离记录重试）。
5. 完成态最后发布（同 task_batch 约定）：STATE running=False 时 DB 必已写完。

---

## 四、catalog / API

catalog 新增（SQL 收敛；目标库业务 SQL 归 **store/loader.py** 新模块）：
- dest：list/create/delete（被 mapping 引用→409）；改名可选 P2 不做。
- mapping：list/create/delete（被 task 引用→409）；列覆盖/业务键校验在 create。
- `add_load_log`（唯一键冲突→跳过返回 False）/`list_load_logs(task_id)`。
- `set_task_load(task_id, dest_id, mapping_id)`（上传登记）＋
  `set_task_state` 复用（loading/loaded/partial）。

app 新增路由：
- `GET/POST /api/load/dests`、`DELETE /api/load/dests/{id}`、
  `POST /api/load/dests/{id}/test`（回 safe_detail，永不回显凭据）。
- `GET/POST /api/load/mappings`、`DELETE /api/load/mappings/{id}`。
- `GET /api/load/dests/{id}/tables`、`GET /api/load/dests/{id}/columns?table=`
  （information_schema 只读 introspection，映射编辑器用）。
- `POST /api/tasks/{id}/load`（手动闸门）；`GET /api/tasks/{id}/load-log`。
- upload / tasks_create：接受 mode=load＋load_dest_id＋load_mapping_id＋预检；
  mode=preview 行为逐字不变。

---

## 五、前端

- **上传页**：mode radio load 启用；选 load 展开目的地 select＋映射 select
  （按所选模板过滤）；提示「先提取校验，全部确认后手动入库」；P2 禁用 hint 退役。
- **/load 页**（nav「入库」启用）：双 panel 与资料/任务同构——
  目的地（名称/类型/conn_ref/测试连接/删除）＋新建抽屉；
  映射（目的地/模板/目标表/写入模式/业务键/删除）＋新建抽屉
  （选模板→字段列表→目标列下拉来自 introspection；write_mode；业务键多选）。
- **校验台/任务详情**：mode=load 且 previewed → 「入库」primary btn＋门禁计数提示；
  loading → 只读 banner＋进度；loaded → 徽标＋回执抽屉（load-log 表）；
  partial → 「重新入库」＋隔离计数。校验台写守卫随 §三扩展。
- **模板编辑器**：字段行加 transform 下拉（无/trim/trim+number）→ transform_json。
- 隔离区本轮**只读展示**（任务详情内计数/列表），解决 UI 留后续。

---

## 六、边界（明确不做）

- 不自动建表（裁决⑤）；不做 reviewer 身份（B 轮）；单目的地（无扇出）；
- 不做已入库数据的删除/回滚（回执 action=delete 预留）；
- 隔离解决 UI 不做（只读＋重试）；transform 仅 trim/number；
- 透传模板不可入库；多表 union 仍押后；只做 MySQL。
- **存量零回归**：preview 链路逐字不变；旧任务 mode=preview 不受影响；
  报告 BLOB 与入库无关（extract 层生成）。

---

## 七、测试与验收

- **单测（无 DB 纯函数）**：transform trim/number（千分位/空白/失败）、
  column_map 覆盖校验、门禁计数逻辑、upsert 语句构造。
- **两套验收顺序重跑**（动 upload/catalog/app/service＝有回归面）；
  records 套件扩入库项：合成目的地（conn_ref=C1_EXTRACT_DB 同实例）＋
  **合成表 `co_dev._accept_p2_load`**（raw 连接建表，验完 DROP）＋合成任务
  全确认→入库→目标行/回执断言→重跑幂等→门禁 409→child-first 清净。
- **浏览器金路径**（8799 临时）：建目的地（测试连接回显脱敏）→建映射
  （introspection 选列）→上传 mode=load→校验台全确认→点入库→目标表行＋回执→
  重跑幂等→pending 门禁 409→rejected 阻止→✓ 重新确认出口→partial 重试
  （合成坏列制造单条隔离）→清净＋DROP 合成表＋基线守恒。
- 基线守恒：135/1867/1867＋98/14870953＋5；真实任务/文件/模板不动。

---

## 八、实施顺序

1. db.connect migrate 开关＋store/loader.py（introspection/写入/回执）＋
   transform 纯函数＋单测。
2. catalog dest/mapping CRUD＋load_log＋app 路由＋upload/tasks_create mode=load 预检。
3. service.load_task＋门禁/只读守卫扩展＋POST /api/tasks/{id}/load。
4. 前端：/load 页＋上传 mode＋校验台/任务入库按钮＋模板 transform 下拉＋nav 启用。
5. 套件扩展＋两套顺序跑＋浏览器金路径＋清理。
6. 文档/记忆收尾（handoff §〇.12）。
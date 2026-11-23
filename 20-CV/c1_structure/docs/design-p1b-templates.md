# 设计稿 · P1b 模板管理＋collect 选择器消费（2026-11-21，已批准并实现）

> 状态：**已批准并实现**（2026-11-21；验证与收尾见 progress-handoff §〇.11）。
> 上游裁决：P1b＝选择器＋重命名（transform 留 P2）；模板管理页与消费**同轮**
> （管理页 alone 是死 UI）。本轮用户拍板：编辑器＝**结构化字段行表单**；
> 源表/源列取值＝**参考文件预览辅助**（无参考时回落手填）。
> 关联：[design-p1-review.md](design-p1-review.md)（P1a 校验台）、
> [design-task-schema.md](design-task-schema.md)（表结构/去外键）。

---

## 〇、为什么是确定性选择器，而不是 LLM

产品定位＝**本地部署的文档入库工作台**（outcome 导向，非「结构化」过程词）。
LLM 抽取是主流趋势（Unstract / MinerU 4.0 / TextIn Skill），但本平台的差异化＝
**提取 → 字段级四态校验 → 审计级追溯 → 可靠入库** 的闭环＋单库本地（数据不出域）。
模板选择器路线回答「为什么不是 LLM」：**确定性**（同输入同输出，可复跑）、
**零 token 成本**、**可审计**（每个目标字段能指回源表源列源格）。
对外文案用「字段级溯源 / 审计追溯」，**不用「血缘」**（易与 DataHub/OpenLineage
管道血缘混淆）；代码内部标识符 lineage 保留不改。
schema_json 的目标字段＝**未来入库表列的雏形**（P2 load_dest 消费），P1b 先定名/定序。

---

## 一、现状接缝（已核实，零 DDL）

- 表已存在：`extract_template`(id/name 唯一/description/current_version/时间)＋
  `extract_template_version`(id/template_id/version/schema_json/mapping_json/
  transform_json/created_at，UNIQUE(template_id,version))。**版本＝不可变快照**。
- [catalog.list_templates()](../store/catalog.py) 已回 current_version_id；
  [catalog.get_template_version()](../store/catalog.py) 按 id/名/无参(第一个当前)取三段 JSON。
- `GET /api/templates` 只读列表已有；上传页下拉已提交 `template_version_id`。
- **缺口 1**：[service.resolve_template()](../service.py) 只回
  `{name, version, version_id}`，**丢弃三段 JSON** → 消费无输入。须补带 JSON。
- **缺口 2**：[service.py:245](../service.py) `recs = collect.passthrough(rec)`
  无视模板 → 选模板等于没选。改为按模板分发。
- **缺口 3**：无模板 CRUD/版本路由、无 /templates 页（nav「模板」off）。
- 参考预览可复用 `GET /api/tasks/{id}/extract`（回 pages[].tables[].headers/cells
  ＋stitched_tables），无需新后端取数路由。

**零 DDL**：不改表结构；三段 JSON 语义由本稿约定。

---

## 二、JSON 契约（P1b 消费 schema＋mapping；transform 存而不消费）

### schema_json（目标字段定义；P2 入库列雏形）
```json
{ "fields": [ {"name": "账号", "type": "text"}, {"name": "交易金额", "type": "text"} ] }
```
- name＝目标字段名（记录 values 的键）；顺序＝记录列顺序。type P1b 仅存（text），P2 用。
- 编辑器由 mapping.fields 自动镜像生成，保持两者一致（单一事实源＝mapping）。

### mapping_json（源→目标；**空/缺省＝透传**，现状不变）
```json
{
  "table":  { "index": 0 },                  // 或 { "header_contains": "交易明细" }
  "fields": [
    { "target": "账号",     "column": { "name": "账号" } },
    { "target": "交易金额", "column": { "index": 3 } }
  ]
}
```
- **单源表/版本**：`table` 选一张源表；多表 union 留后续（见 §六边界）。
- `table.index`＝候选表有序列表下标（顺序＝passthrough 迭代序：各页非合并页表
  (scope=page,ti) 在前，stitched 表 (scope=stitched,si) 在后）。
- `table.header_contains`＝表头拼接串含该子串的**第一张**表（确定性）。
- `column.name`＝该表 `_keys(headers)` 产出的键（含空表头 col_n/重名下标）；
  `column.index`＝原始列下标。二者择一。
- `fields` 顺序＝记录键顺序；`target` 即重命名后的键。

### transform_json
P1b **存而不消费**（编辑器不暴露），P2 开放。

---

## 三、collect 消费语义

新增 `collect.build(doc, tpl)` 分发＋`apply_mapping(doc, mapping)`：
- `tpl.mapping_json` 空/无 fields → `passthrough(doc)`（**逐字保留现行为**）。
- 有映射：
  1. 解析候选表有序列表（与 passthrough 同序，跳过被合并页表）。
  2. `table` 命中→选中表；**未命中→0 条记录**（previewed＋warn 日志，不 failed；
     校验台空态「该文件未抽出表格行」复用）。
  3. 对选中表每行：按 `fields` 顺序取 `column` 命中格 → `values[target]`；
     `lineage[target]=[_anchor(scope,t,ti,cells,r,c,v,page_default)]`（**复用现
     _anchor，字段级溯源不变**）。
  4. 列未命中（name 不存在/index 越界）→ `values[target]=''`＋`lineage[target]=[]`。
  5. `original`＝values 副本；`review`＝pending（与 passthrough 同）。
- `build_records_doc` 不变；template 信封仍 {name, version}。
- 日志：`collect` 行区分「passthrough」/「映射 N 字段」。

**service 接缝**：resolve_template 补带 `schema/mapping/transform`；
:245 改 `recs = collect.build(rec, tpl)`；日志文案随模式。

---

## 四、catalog / API（CRUD＋版本，应用层守卫）

catalog 新增：
- `create_template(name, description, schema, mapping, transform=None)`→建模板＋v1＋current=1。
- `create_version(template_id, schema, mapping, transform=None)`→version=max+1 快照＋current 前移。
- `update_template(template_id, name=None, description=None, current_version=None)`
  （改名/说明不建新版本；current_version 须存在否则 400）。
- `delete_template(template_id)`：**被 extract_task.template_version_id 引用→409**
  （与 delete_file 同守卫）；无引用才删 template＋其 versions（先子后父）。
- `list_versions(template_id)`→版本倒序（id/version/created_at/是否当前）。

app 新增路由（错误归现有异常处理器）：
- `POST /api/templates`、`GET /api/templates/{id}/versions`、
  `POST /api/templates/{id}/versions`、`PATCH /api/templates/{id}`、
  `DELETE /api/templates/{id}`。
- 重名→409（uk_template_name）；未知 id→404；JSON 非对象→400。

---

## 五、/templates 管理页（结构化表单＋参考预览，紧凑规整同三页）

- nav「模板」四页启用（off→on，href=/templates）；新增 templates.html/css/js，
  挂 shell.css（复用紧凑 token/表格/抽屉/徽标）。
- **列表 panel**：模板名/说明/当前版本/版本数/更新时间/操作（编辑/版本/删除）。
  页头＝h1＋右对齐工具栏（搜索＋「新建模板」btn），与资料/任务同构。
- **编辑抽屉**（复用 .drawer）：
  - 模板名/说明 input。
  - **参考文件** select（列 previewed 任务的文件的下拉）→ fetch
    `/api/tasks/{id}/extract` → 候选表 select（label「#i · page/stitched · 表头预览」）。
    无参考时回落手填 index/header_contains。
  - **源表** select（来自参考）或手填。
  - **字段行**：目标字段名 input＋源列 select（该表 _keys 键／index）＋删行 btn；
    「＋添加字段」btn。行可拖序押后（P1b 用添加顺序）。
  - 「保存为新版本」btn → POST versions；成功后刷新列表＋版本历史。
  - **版本历史** list（version/时间/当前徽标/「设为当前」btn→PATCH）。
- 删除 confirm＋409 提示（被任务引用）。
- 校验台/报告/上传**不改**；上传下拉自动见到新模板（/api/templates）。

---

## 六、边界与风险（明确不做）

- **多表 union / 跨表拼接选择**：P1b 单源表；后续轮。
- **transform**：P2；transform_json 存而不消费、编辑器不暴露。
- **type/入库列映射**：schema.type 仅存；P2 load_dest 消费。
- **存量任务/报告不受影响**：旧 task 引用旧 version_id（mapping 空＝透传）；
  报告 BLOB 由 extract 信封生成（与 records 映射无关）→ 零回归面。
- **参考预览依赖 extract 信封**：failed/无 tables 的任务不可作参考（下拉过滤）。
- 选择器歧义（header_contains 多命中）＝取第一张，确定性优先，文案提示。

---

## 七、测试与验收

- **C 项单测骨架**（无 DB，纯函数）：`c1_structure/test_collect_selectors.py`
  （unittest）：空映射＝passthrough 逐字一致；index 表＋name 列；header_contains；
  column index；缺列→''＋lineage[]；缺表→0 条；重命名键序；lineage page/scope
  正确；重名表头键。合成 doc 直造，不碰真实库。
- **两套验收脚本顺序跑 6/6**（本轮动 service/catalog/app＝有后端回归面，**须重跑**）。
- 浏览器金路径（8799 临时＋合成模板/任务，验完 child-first 清净）：
  新建模板→参考预览选表选列→保存新版本→上传选该模板→校验台见重命名键＋
  字段级溯源点格定位→版本历史设当前→删除守卫 409。
- 基线守恒：records/field/lineage/artifact/file 计数验后还原。

---

## 八、实施顺序

1. collect.build/apply_mapping＋单测骨架（先纯函数，可独立验）。
2. service.resolve_template 带 JSON＋:245 分发＋日志。
3. catalog CRUD/版本/守卫＋app 路由。
4. templates.html/css/js＋nav 启用。
5. 两套验收顺序＋浏览器金路径＋清理。
6. 文档/记忆收尾（handoff §〇.11）。
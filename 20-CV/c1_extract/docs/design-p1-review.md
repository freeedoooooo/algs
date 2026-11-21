# P1a 校验台设计（staging 页原地升级）

> 状态：**已实现并验收**（2026-11-22）：两套验收脚本顺序跑各 6/6 PASS
> （[3/6] 扩 set_review/rejected/未知键，[5/6] 扩路由冒烟＋loaded 409）；
> 浏览器金路径（改值→确认→拒绝→筛选→批量确认＋任务选择器）全过；零 DDL。
> 用户裁决：① P1a 校验台先做，P1b（模板管理＋collect 选择/重命名）下一轮；
> ② 拒绝＝`review_state='rejected'`（记录属性，不进 quarantine——隔离表只管引擎级失败）；
> ③ P1b 模板消费＝选择器＋重命名，transform 留 P2。
> 前置：[design-task-schema.md](design-task-schema.md)（13 表无 FK）、
> [design-records-db.md](design-records-db.md)（records 三表事实源）。

---

## 0. 范围与盲点

**做**：staging 页从只读预览升级为校验台——双击改值、逐行确认/拒绝、
状态筛选、批量确认、已入库只读守卫；导航「校验」占位兑现。
**不做**：独立校验页（血缘舞台整套复用，另起一页＝重复 667 行）；
模板 CRUD / collect 消费（P1b）；入库（P2）；quarantine 处置 UI。

应力测试过的盲点：

| 盲点 | 处置 |
|---|---|
| 单击已被血缘钉住占用 | 编辑走**双击**单元格，单击/悬停/点图回溯全部不动 |
| 筛选后 data-i 错位 | records 数组不重排，渲染时跳过不匹配行，data-i 恒为真实下标 |
| 批量确认误伤未看过的记录 | 批量只作用**当前文件**的 pending+edited，按钮带计数＋confirm 对话框 |
| 改回原值仍标 edited | 接受：edited 表示「人动过」，值是否等于原值由格标记单独表达 |
| confirmed 后再编辑 | 允许，PATCH 天然回 edited，须重新确认（patch_record 现有语义） |
| rejected 反悔 | ✓ 可直接转 confirmed；✗/✓ 不做状态机限制，只锁 loaded |
| 入库后改值 | task.state='loaded' → 前端只读横幅＋后端 409（P2 前置守卫） |
| PATCH 塞新字段污染 field 表 | store 层拒绝未知键（400），字段集由提取/模板决定 |
| 共享库 schema 变更 | **零 DDL**：review_state 是 VARCHAR 无枚举约束；仅改 baseline 注释文本，线上库注释不动（装饰性，不 ALTER 共享库） |

## 1. 状态机

```
pending ──PATCH──▶ edited ──✓──▶ confirmed
   │                 ▲               │
   ├──✓──────────────┴───────PATCH───┘（回 edited）
   └──✗──▶ rejected ──✓──▶ confirmed
loaded（task 级）：一切写操作 409
```

`review_at` 每次写操作刷新；`original_json` / `field.original_text` /
`lineage.raw_text` 永不覆盖（patch_record 现有保证，改值留痕免费）。
P2 入库只取 confirmed（届时再议 rejected 是否可入库，本轮不定）。

## 2. API（app.py 新增两路由）

公共守卫 `_review_target(task_id, task_file_id)`：
task 不存在→404；task_file 不属于 task→404；task.state='loaded'→409；
返回 file_index（`catalog.get_task` files 序，与 `_task_files` ORDER BY tf.id 一致）。
DB 异常→`_db_unavailable`（503），与现有端点一致。

| 路由 | 体 | 语义 |
|---|---|---|
| `PATCH /api/tasks/{id}/staging/{tf}/{index}` | `{"values":{k:v,…}}` | 差量改值→edited；未知键/空体/非 dict→400；下标越界→404；返回最新单条 rec |
| `POST /api/tasks/{id}/staging/{tf}/review` | `{"indexes":[…],"state":"confirmed"\|"rejected"}` | 批量置状态；空 indexes/非法 state→400；返回 `{"ok":true,"updated":n}` |

store 签名不动（accept [3/6] 已覆盖 file_index 形态）：
`content_db.set_review(task_id, file_index, indexes, state)` 新增，
单事务 UPDATE review_state/review_at WHERE task_file_id + record_index IN (…)；
`patch_record` 加未知键守卫。`content.py` 接缝加 set_review 透传。

## 3. 前端（staging.html / js / css）

- **横幅**：只读提示→「双击单元格改值 · ✓ 确认 · ✗ 拒绝 · 改值自动转已修改」；
  loaded→「已入库 · 只读」。导航「校验」→ `/staging`（各页 nav 同步），
  「模板」仍占位到 P1b。
- **无 task 参数**：不再报错，渲染任务选择器（/api/tasks 列表，选中即跳转），
  「校验」成为独立入口。
- **工具条**：状态筛选 chips（全部/待校验/已修改/已确认/已拒绝，带计数）＋
  「确认全部待审 (N)」批量按钮（当前文件 pending+edited，confirm 对话框）。
- **表格**：新增「操作」列（✓/✗ mini 按钮，confirmed 隐 ✓、rejected 隐 ✗）；
  双击格→内联 input，Enter/blur 提交 PATCH、Esc 取消、值未变不发请求；
  成功后原位替换 records[i]＋重渲染（血缘/选中态保持）。
- **改值标记**：values[k]≠original[k] 的格加琥珀标记，title 显示原值。
- **跨任务搜索**：xs-state 下拉补 rejected。
- 徽标复用 shell.js STATE_LABEL（edited/confirmed/rejected 早已预留）。

## 4. 验收（核心路径，不过度）

1. accept_records_db.py [3/6] 扩展：set_review confirmed/rejected 往返、
   query_fields(state='rejected') 命中、patch 未知键拒绝；
   [5/6] 真链路补 PATCH/POST 路由冒烟＋loaded 409 守卫（合成 task，验完还原）。
2. 两套验收脚本**顺序**跑（共用 8799/8797，严禁并行），全 PASS。
3. 浏览器金路径一条（8799 临时服务＋合成任务）：双击改值→徽标已修改→
   ✓ 确认→筛选→✗ 拒绝→批量确认。验完停服务、清合成数据。
4. 用户 8765 不动；新路由须重启才生效，交付时注明。
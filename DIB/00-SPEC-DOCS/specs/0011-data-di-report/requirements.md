# 数据资讯报告 需求文档

> 编号：`0011` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-04-15

---

## 背景

数据资讯模块（di）已有快讯、指标等功能，本次新增"资讯报告"功能，为客户提供结构化的 PDF 报告浏览入口。报告按目录分类管理，支持客户授权控制，未授权目录客户只能查看不能进入。

---

## 目标用户

- **管理员**：在后台管理报告目录、报告内容及客户授权
- **客户用户**：在前台浏览已授权目录下的报告列表，预览 PDF 报告

---

## 功能描述

### 管理端功能
1. **报告目录管理**：新增/编辑/删除/启用/禁用报告目录（最多两级）
2. **报告管理**：新增/编辑/删除/启用/禁用报告，支持上传 PDF 附件、设置封面、标签等
3. **目录授权管理**：**完全复用**现有资讯客户授权功能（`ComDiCustomerAuthController` / `ComDiCustomerAuthAggregate` / `IComDiCustomerAuthService` / `ComDiCustomerAuthMapper`），无需开发新接口。仅需在 `DiAuthObjTypeEnum` 新增 `REPORT_DIR` 枚举值，前端传参时 `objType = REPORT_DIR` 即可

### 客户端功能
1. **目录列表**：展示所有启用的报告目录（两级卡片结构），未授权目录可见但不可点击进入
2. **报告列表**：进入已授权目录后，分页展示该目录下的报告列表
3. **报告预览**：点击报告后预览 PDF（通过 MDM 附件接口获取附件信息）

---

## 所属模块

- 服务：`dib-agent-service-data`（端口 `30003`）
- 模块：`di`（数据资讯）
- 业务域：资讯报告
- 涉及包路径：
  - `entity/di/`
  - `mapper/di/`
  - `service/di/`
  - `aggregate/di/`
  - `controller/di/`
  - `converter/di/`
  - `model/di/`
  - `config/enums/di/`

---

## 核心业务规则

### 目录结构
- 目录最多两级（一级目录 + 二级目录）
- 前端展示：一级为卡片，二级为卡片内的按钮
- 目录有启用/禁用状态，禁用目录不在客户端展示

### 客户授权规则
- 授权粒度：**目录级别**（一级或二级目录均可授权）
- 复用现有实体 `ComDiCustomerAuthEntity`（表 `com_di_customer_auth`）
- `objType` 使用新枚举值 `REPORT_DIR`（需在 `DiAuthObjTypeEnum` 新增）
- `objId` = 目录 ID，`objName` = 目录名称，`customerCode` = 客户编码
- 未授权客户：可看到目录卡片，但不能点击进入报告列表
- 已授权客户：可进入目录查看报告列表

### 报告标签
- 标签为自由文本输入（非预定义），一个报告可关联多个标签
- 标签通过独立关联表存储（报告 ID + 标签文本）

### 附件（PDF）
- 通过 MDM 模块的 `FeignMdmAttachmentService` 进行附件上传和查询
- 报告存储附件 ID（`Long attId`），查询时通过 `listByIds` 获取附件信息
- 报告封面同样通过附件 ID 关联（`Long coverAttId`）

### 报告简介异步生成
- **触发时机**：上传 PDF 附件并保存报告后，自动异步触发简介生成
- **生成流程**：
  1. 通过 `FeignMdmAttachmentService.download(attId)` 下载 PDF 文件流
  2. 将 PDF 转换为 TXT 文本（参考 extract 服务的 `ConverterFacade` 转换逻辑）
  3. 将 TXT 文件上传至 MDM，记录 `txtAttId`到报告表
  4. 读取 TXT 内容，通过 `dib-cloud-ai-starter` 的 `AiInvoker.invoke()` 调用大模型生成简介
  5. 将生成结果回写到报告的 `reportIntro` 字段，更新 `introGenStatus`
- **简介生成状态**（`introGenStatus`）枚举：
  - `PENDING`（待生成）：报告刚保存，尚未触发
  - `GENERATING`（生成中）：异步任务已触发，等待结果
  - `GENERATED`（已生成）：大模型已返回结果
  - `FAILED`（生成失败）：生成过程出现异常
- **重试机制**：生成失败后，管理员可手动点击"重试"按钮，重新触发生成流程
- **可编辑**：简介生成后，管理员可在编辑报告时手动修改简介内容

---

## 数据表设计

### 1. 资讯报告目录表 `com_di_report_dir`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| dir_name | VARCHAR(100) | 目录名称 |
| dir_desc | VARCHAR(500) | 目录说明 |
| parent_id | BIGINT | 父节点 ID（0 表示一级） |
| id_path | VARCHAR(500) | ID 完整层级路径 |
| current_level | INT | 当前层级（1 或 2） |
| order_num | INT | 排序序号 |
| enable_flag | TINYINT(1) | 是否启用 |
| + BaseEntity 基础字段 | | |

### 2. 资讯报告表 `com_di_report`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| report_title | VARCHAR(200) | 报告标题 |
| report_dir_id | BIGINT | 所属目录 ID |
| report_dir_id_path | VARCHAR(500) | 目录 ID 路径 |
| publish_date | DATE | 发布日期 |
| report_year | VARCHAR(10) | 报告年份 |
| report_date | DATE | 报告期（yyyy-MM-dd） |
| att_id | BIGINT | PDF 附件 ID（关联 MDM 附件） |
| txt_att_id | BIGINT | TXT 附件 ID（PDF 转换后的文本，用于 AI 生成简介） |
| cover_att_id | BIGINT | 封面附件 ID（关联 MDM 附件） |
| report_intro | VARCHAR(2000) | 报告简介（大模型生成，可手动修改） |
| intro_gen_status | VARCHAR(20) | 简介生成状态：PENDING/GENERATING/GENERATED/FAILED |
| enable_flag | TINYINT(1) | 是否启用 |
| + BaseEntity 基础字段 | | |

### 3. 报告标签关联表 `com_di_report_tag`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| report_id | BIGINT | 报告 ID |
| tag_name | VARCHAR(100) | 标签文本 |
| + BaseEntity 基础字段 | | |

### 4. 报告操作日志表 `com_di_report_opt_record`

参考 `com_di_index_opt_record`，记录用户浏览和下载行为（由前端触发调用）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| report_id | BIGINT | 报告 ID |
| report_title | VARCHAR(200) | 报告标题（冗余） |
| opt_type | VARCHAR(20) | 操作类型：VISIT（浏览）/ DOWNLOAD（下载） |
| + BaseEntity 基础字段 | | |

---

## 输入参数

### 管理端 - 新增/编辑报告目录
| 参数名 | 类型 | 说明 |
|--------|------|------|
| dirName | String | 目录名称（必填） |
| dirDesc | String | 目录说明 |
| parentId | Long | 父节点 ID（一级传 0 或 null） |


### 管理端 - 新增/编辑报告
| 参数名 | 类型 | 说明 |
|--------|------|------|
| reportTitle | String | 报告标题（必填） |
| reportDirId | Long | 所属目录 ID（必填） |
| reportDirIdPath | String | 目录 ID 路径（必填） |
| publishDate | Date | 发布日期 |
| reportYear | Integer | 报告年份 |
| reportDate | Date | 报告期（yyyy-MM-dd） |
| attId | Long | PDF 附件 ID |
| coverAttId | Long | 封面附件 ID |
| reportIntro | String | 报告简介（可手动填写或由 AI 生成后修改） |
| tagNames | List\<String\> | 标签文本列表 |

### 客户端 - 查询报告列表
| 参数名 | 类型 | 说明 |
| reportDirId | Long | 目录 ID（可选） |
| reportDirIdPath | String | 目录 ID 路径（可选，用于查询某目录及其子目录下的报告） |
| reportYear | Integer | 报告年份（可选，筛选） |
| tagName | String | 标签（可选，模糊匹配） |
| keyword | String | 关键词（可选，模糊搜索标题） |
| pageNum | Integer | 页码 |
| pageSize | Integer | 每页条数 |

---

## 输出结果

### 目录列表（客户端）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Long | 目录 ID |
| dirName | String | 目录名称 |
| currentLevel | Integer | 层级 |
| authorized | Boolean | 当前客户是否已授权 |
| children | List | 子目录列表（二级） |

### 报告列表
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Long | 报告 ID |
| reportTitle | String | 报告标题 |
| publishDate | Date | 发布日期 |
| reportYear | Integer | 报告年份 |
| reportDate | Date | 报告期 |
| coverAttId | Long | 封面附件 ID |
| coverUrl | String | 封面访问 URL（由附件信息填充） |
| reportIntro | String | 报告简介 |
| introGenStatus | String | 简介生成状态 |
| tagNames | List\<String\> | 标签列表 |
| attId | Long | PDF 附件 ID |

---

## 用户故事

- 作为管理员，我希望能管理报告目录（增删改查、启用禁用），以便对报告进行分类
- 作为管理员，我希望能上传 PDF 报告并配置封面、标签、简介，以便客户能浏览报告
- 作为管理员，我希望能为客户授权指定报告目录（复用现有授权接口，传 `objType=REPORT_DIR`），以便控制报告的可见范围
- 作为客户用户，我希望能看到所有目录卡片，未授权的目录置灰不可点击，以便了解有哪些报告类型
- 作为客户用户，我希望进入已授权目录后能分页浏览报告列表，以便找到需要的报告
- 作为客户用户，我希望能在线预览 PDF 报告，以便阅读报告内容
- 作为客户用户，我希望能看到上新报告列表（最新 10 条），以便快速发现新发布的报告
- 作为客户用户，我希望能看到热点报告列表（近 30 天浏览+下载最多），以便发现热门报告
- 作为系统，我希望记录用户的浏览和下载行为日志，以便统计热点数据

---

## 验收标准

- [ ] 管理端：报告目录支持增删改查、启用/禁用，最多两级
- [ ] 管理端：报告支持增删改查、启用/禁用，字段包含标题、目录、发布时间、年份、报告期、附件、封面、简介、标签
- [ ] 管理端：保存报告（含 attId）后自动异步触发简介生成，`introGenStatus` 初始为 `PENDING`
- [ ] 管理端：简介生成失败后，支持手动点击重试重新触发生成
- [ ] 管理端：简介生成后，编辑报告时可手动修改简介内容
- [ ] 管理端：报告标签支持自由文本，一个报告可关联多个标签，编辑时可增删
- [ ] 管理端：目录授权**复用现有接口**（`ComDiCustomerAuthController`），仅需新增 `REPORT_DIR` 枚举值，无需开发新接口
- [ ] 客户端：目录列表返回所有启用目录，含 `authorized` 字段标识是否已授权
- [ ] 客户端：未授权目录 `authorized = false`，前端据此控制是否可点击
- [ ] 客户端：报告列表支持按年份筛选、关键词搜索、分页
- [ ] 客户端：提供操作日志记录接口（浏览/下载），由前端在对应时机调用
- [ ] 客户端：上新报告接口，按 `add_time` 倒序返回最新 10 条启用报告，含目录授权标识
- [ ] 客户端：热点报告接口，按近 30 天浏览+下载次数合计倒序返回，含目录授权标识
- [ ] `DiAuthObjTypeEnum` 新增 `REPORT_DIR("资讯报告目录")` 枚举项

---

## 边界条件

| 场景 | 处理方式 |
|------|---------|
| 目录已有子目录时删除 | 抛出业务异常，提示"请先删除子目录" |
| 目录已关联报告时删除 | 抛出业务异常，提示"请先删除目录下的报告" |
| 报告编码重复 | 抛出业务异常，提示"报告编码已存在" |
| 客户端请求未授权目录的报告列表 | 抛出业务异常，提示"无权限访问该目录" |
| 简介生成中时用户点击重试 | 抛出业务异常，提示"简介正在生成中，请稍后" |
| PDF 转 TXT 失败 | 更新 `introGenStatus = FAILED`，记录错误日志 |
| 大模型调用失败 | 更新 `introGenStatus = FAILED`，记录错误日志 |
| 目录层级超过两级 | 抛出业务异常，提示"目录最多两级" |

---

## 非功能需求

- **性能**：报告列表分页查询，单页不超过 20 条
- **可维护性**：遵循 di 模块现有代码风格，复用 `ComDiCustomerAuthAggregate` 的授权查询方法
- **安全性**：客户端接口需校验当前登录客户的授权状态
**状态**：已确认
---

**状态**：草稿

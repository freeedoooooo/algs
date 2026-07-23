# 数据资讯报告 技术设计

> 编号：`0011` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-04-16
> 关联需求：`requirements.md`

---

## 概述

在 `dib-agent-service-data` 的 `di` 子模块下新增资讯报告功能，包含报告目录管理、报告管理（含 AI 异步生成简介）、客户端查询三部分。目录授权完全复用现有 `ComDiCustomerAuth` 体系，仅新增枚举值。

---

## 架构设计

### 整体调用链

```
管理端：
Controller → Aggregate → Service → Mapper → DB
                ↓（保存报告后异步）
         ComDiReportIntroGenComponent
                ↓
         FeignMdmAttachmentService（下载 PDF）
                ↓
         ConverterFacade（PDF → TXT）
                ↓
         FeignMdmAttachmentService（上传 TXT）
                ↓
         AiInvoker.invoke()（生成简介）
                ↓
         IComDiReportService（回写简介 + 状态）

客户端：
Controller → Aggregate → Service/Mapper → DB
                ↓（查询授权）
         ComDiCustomerAuthAggregate.listCurrentUserAuthId()
```

### 涉及文件总览

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `entity/di/ComDiReportDirEntity.java` | 报告目录实体 |
| 新增 | `entity/di/ComDiReportEntity.java` | 报告实体 |
| 新增 | `entity/di/ComDiReportTagEntity.java` | 报告标签关联实体 |
| 新增 | `mapper/di/ComDiReportDirMapper.java` | 目录 Mapper |
| 新增 | `mapper/di/ComDiReportMapper.java` | 报告 Mapper |
| 新增 | `mapper/di/ComDiReportTagMapper.java` | 标签 Mapper |
| 新增 | `resources/mapper/di/ComDiReportMapper.xml` | 报告 XML（含标签 JOIN 查询） |
| 新增 | `service/di/IComDiReportDirService.java` | 目录 Service 接口 |
| 新增 | `service/di/impl/ComDiReportDirServiceImpl.java` | 目录 Service 实现 |
| 新增 | `service/di/IComDiReportService.java` | 报告 Service 接口 |
| 新增 | `service/di/impl/ComDiReportServiceImpl.java` | 报告 Service 实现 |
| 新增 | `service/di/IComDiReportTagService.java` | 标签 Service 接口 |
| 新增 | `service/di/impl/ComDiReportTagServiceImpl.java` | 标签 Service 实现 |
| 新增 | `aggregate/di/ComDiReportDirAggregate.java` | 目录聚合（管理端） |
| 新增 | `aggregate/di/ComDiReportAggregate.java` | 报告聚合（管理端） |
| 新增 | `aggregate/di/ComDiReportQueryAggregate.java` | 报告查询聚合（客户端） |
| 新增 | `component/di/ComDiReportIntroGenComponent.java` | 简介异步生成组件 |
| 新增 | `controller/di/ComDiReportDirController.java` | 目录管理 Controller |
| 新增 | `controller/di/ComDiReportController.java` | 报告管理 Controller |
| 新增 | `controller/di/ComDiReportQueryController.java` | 客户端查询 Controller |
| 新增 | `converter/di/DiReportDirConverter.java` | 目录 Converter |
| 新增 | `converter/di/DiReportConverter.java` | 报告 Converter |
| 新增 | `model/di/req/DiReportDirAddReq.java` | 目录新增请求 |
| 新增 | `model/di/req/DiReportDirEditReq.java` | 目录编辑请求 |
| 新增 | `model/di/req/DiReportAddReq.java` | 报告新增请求 |
| 新增 | `model/di/req/DiReportEditReq.java` | 报告编辑请求 |
| 新增 | `model/di/req/DiReportPageReq.java` | 报告管理端分页查询请求 |
| 新增 | `model/di/req/DiReportQueryPageReq.java` | 客户端报告列表查询请求 |
| 新增 | `model/di/resp/DiReportDirResp.java` | 目录响应 |
| 新增 | `model/di/resp/DiReportResp.java` | 报告响应 |
| 新增 | `config/enums/di/DiReportIntroGenStatusEnum.java` | 简介生成状态枚举 |
| 修改 | `config/enums/di/DiAuthObjTypeEnum.java` | 新增 `REPORT_DIR` 枚举值 |
| 修改 | `dib-agent-service-data-web/pom.xml` | 新增 `dib-cloud-ai-starter` 依赖 |
| 新增 | `scripts/V0011__add_di_report_tables.sql` | 建表 SQL |

---

## 数据模型

### 实体设计

#### ComDiReportDirEntity（参考 ComDiIndexDirEntity）
```java
@TableName("com_di_report_dir")
public class ComDiReportDirEntity extends BaseEntity implements BaseTreeEntity {
    private String dirName;       // 目录名称
    private String dirDesc;       // 目录说明
    private Long parentId;        // 父节点 ID（0 或 null 表示一级）
    private String idPath;        // ID 完整层级路径
    private Integer currentLevel; // 当前层级（1 或 2）
    private Integer orderNum;     // 排序序号
    private Boolean enableFlag;   // 是否启用
}
```

#### ComDiReportEntity
```java
@TableName("com_di_report")
public class ComDiReportEntity extends BaseEntity {
    private String reportTitle;          // 报告标题
    private Long reportDirId;            // 所属目录 ID
    private String reportDirIdPath;      // 目录 ID 路径
    private Date publishDate;            // 发布日期
    private Integer reportYear;           // 报告年份
    private Date reportDate;             // 报告期（yyyy-MM-dd）
    private Long attId;                  // PDF 附件 ID
    private Long txtAttId;               // TXT 附件 ID（AI 生成简介用）
    private Long coverAttId;             // 封面附件 ID
    private String reportIntro;          // 报告简介
    private DiReportIntroGenStatusEnum introGenStatus; // 简介生成状态
    private Boolean enableFlag;          // 是否启用
}
```

#### ComDiReportTagEntity
```java
@TableName("com_di_report_tag")
public class ComDiReportTagEntity extends BaseEntity {
    private Long reportId;   // 报告 ID
    private String tagName;  // 标签文本
}
```

#### ComDiReportOptRecordEntity（参考 ComDiIndexOptRecordEntity）
```java
@TableName("com_di_report_opt_record")
public class ComDiReportOptRecordEntity extends BaseEntity {
    private Long reportId;           // 报告 ID
    private String reportTitle;      // 报告标题（冗余）
    private DiReportOptTypeEnum optType;  // 操作类型：VISIT / DOWNLOAD
}
```

#### DiReportOptTypeEnum
```java
public enum DiReportOptTypeEnum {
    VISIT("浏览"),
    DOWNLOAD("下载");
}
```

### Converter 设计

#### DiReportDirConverter
```java
@Mapper(componentModel = "spring")
public interface DiReportDirConverter {
    DiReportDirConverter INSTANCE = Mappers.getMapper(DiReportDirConverter.class);

    @Mapping(target = "id", expression = MapStructUtils.ID_EXP)
    @Mapping(target = "delFlag", constant = "false")
    ComDiReportDirEntity fromAddReq(DiReportDirAddReq req, AddingUser addingUser);

    ComDiReportDirEntity fromEditReq(DiReportDirEditReq req);

    DiReportDirResp toResp(ComDiReportDirEntity entity);

    List<DiReportDirResp> toRespList(List<ComDiReportDirEntity> entityList);

    // 用于管理端目录树构建（TreeNode 体系）
    @Mapping(target = "sortNum", source = "orderNum")
    @Mapping(target = "nodeType", constant = "DIR")
    TreeNodeProperty toTreeNodeProperty(ComDiReportDirEntity entity);

    List<TreeNodeProperty> toTreeNodePropertyList(List<ComDiReportDirEntity> entityList);
}
```

#### DiReportConverter
```java
@Mapper(componentModel = "spring")
public interface DiReportConverter {
    DiReportConverter INSTANCE = Mappers.getMapper(DiReportConverter.class);

    @Mapping(target = "id", expression = MapStructUtils.ID_EXP)
    @Mapping(target = "delFlag", constant = "false")
    @Mapping(target = "introGenStatus", constant = "PENDING")
    ComDiReportEntity fromAddReq(DiReportAddReq req, AddingUser addingUser);

    ComDiReportEntity fromEditReq(DiReportEditReq req);

    DiReportResp toResp(ComDiReportEntity entity);

    List<DiReportResp> toRespList(List<ComDiReportEntity> entityList);

    @Mapping(target = "id", expression = MapStructUtils.ID_EXP)
    @Mapping(target = "delFlag", constant = "false")
    ComDiReportTagEntity fromTagName(Long reportId, String tagName, AddingUser addingUser);
}
```

### 枚举设计

#### DiReportIntroGenStatusEnum
```java
public enum DiReportIntroGenStatusEnum {
    PENDING("待生成"),
    GENERATING("生成中"),
    GENERATED("已生成"),
    FAILED("生成失败");
}
```

---

## 接口设计

### 管理端 API

| 方法 | 路径 | Controller 方法 | 说明 |
|------|------|----------------|------|
| POST | `/api/data/report/dir/add` | `add()` | 新增目录 |
| POST | `/api/data/report/dir/edit` | `edit()` | 编辑目录 |
| POST | `/api/data/report/dir/delete/{id}` | `delete()` | 删除目录 |
| POST | `/api/data/report/dir/enable/{id}` | `enable()` | 启用目录 |
| POST | `/api/data/report/dir/disable/{id}` | `disable()` | 禁用目录 |
| POST | `/api/data/report/dir/listTree` | `listTree()` | 目录树（管理端，返回 `List<TreeNode>`） |
| POST | `/api/data/report/add` | `add()` | 新增报告 |
| POST | `/api/data/report/edit` | `edit()` | 编辑报告 |
| POST | `/api/data/report/delete/{id}` | `delete()` | 删除报告 |
| POST | `/api/data/report/enable/{id}` | `enable()` | 启用报告 |
| POST | `/api/data/report/disable/{id}` | `disable()` | 禁用报告 |
| POST | `/api/data/report/page` | `page()` | 报告分页列表（管理端） |
| GET  | `/api/data/report/get/{id}` | `get()` | 报告详情 |
| POST | `/api/data/report/retryGenIntro/{id}` | `retryGenIntro()` | 重试生成简介 |

### 管理端目录树实现说明

参考现有 `ComDiIndexDirController.listTree()` 模式：
- Controller 调用 `ComDiReportDirAggregate.listTree()`
- Aggregate 调用 `IComDiReportDirService.listTree()`
- Service 查询所有未删除目录 → `DiReportDirConverter.toTreeNodePropertyList()` → `TreeNode.buildTree()`
- 返回 `GeneralResult<List<TreeNode>>`

### 客户端 API

| 方法 | 路径 | Controller 方法 | 说明 |
|------|------|----------------|------|
| POST | `/api/data/report/query/listTree` | `listTree()` | 目录树（含授权标识，返回 `List<TreeNode>`） |
| POST | `/api/data/report/query/page` | `page()` | 报告列表（分页+筛选） |
| POST | `/api/data/report/query/listNew` | `listNew()` | 上新报告（最新 10 条，含授权标识） |
| POST | `/api/data/report/query/listHot` | `listHot()` | 热点报告（近 30 天操作次数倒序，含授权标识） |
| POST | `/api/data/report/query/saveOptRecord` | `saveOptRecord()` | 记录操作日志（浏览/下载，由前端触发） |

### 客户端目录树实现说明

与管理端目录树结构一致，均返回 `List<TreeNode>`，区别在于：
- 只返回 `enableFlag=true` 的目录
- 调用 `ComDiCustomerAuthAggregate.listCurrentUserAuthId(REPORT_DIR)` 获取当前客户已授权目录 ID 集合
- 将 `authorized` 标识写入 `TreeNode.ext`（`ext.put("authorized", true/false)`）

---

## 核心逻辑设计

### 1. 目录管理

**新增目录**：
1. 校验层级：若 `parentId` 不为空，查询父目录 `currentLevel`，若已为 2 则抛异常"目录最多两级"
2. 计算 `currentLevel = parentLevel + 1`（无父节点则为 1）
3. 保存后计算 `idPath`（父路径 + `/` + 新 ID）并更新

**删除目录**：
1. 查询是否有子目录（`parentId = id`），有则抛异常"请先删除子目录"
2. 查询是否有关联报告（`reportDirId = id`），有则抛异常"请先删除目录下的报告"
3. 逻辑删除

### 2. 报告管理

**新增/编辑报告**：
1. 保存报告基本信息及标签（先删后插）
2. 若 `attId` 不为空且为新增（或 attId 发生变更），触发异步简介生成：
   - 更新 `introGenStatus = PENDING`
   - 异步调用 `ComDiReportIntroGenComponent.asyncGenIntro(reportId)`

**标签处理**（新增/编辑统一逻辑）：
1. 逻辑删除该报告的所有旧标签（`del_flag = 1`）
2. 批量插入新标签列表

### 3. 简介异步生成流程（ComDiReportIntroGenComponent）

```
asyncGenIntro(reportId):
  1. 更新 introGenStatus = GENERATING
  2. 查询报告获取 attId
  3. FeignMdmAttachmentService.download(attId) → 获取 PDF 字节流
  4. ConverterFacade.toTxt(bytes, tmpTxtPath) → 转换为 TXT
  5. FeignMdmAttachmentService.upload(txtFile) → 上传 TXT，获取 txtAttId
  6. 更新报告 txtAttId
  7. 读取 TXT 内容（TextParser.parse）→ 拼接文本
  8. 构建 prompt，调用 AiInvoker.invoke(aiReq, "DATA", ApiTypeEnum.text)
  9. 成功：更新 reportIntro + introGenStatus = GENERATED
  10. 失败：更新 introGenStatus = FAILED，记录错误日志
```

**重试逻辑**：
- 校验当前 `introGenStatus != GENERATING`，否则抛异常"简介正在生成中，请稍后"
- 重置 `introGenStatus = PENDING`，重新触发 `asyncGenIntro`

### 5. 上新报告（listNew）

```
listNew():
  1. 查询 enableFlag=true、delFlag=false 的报告，按 add_time 倒序，取前 10 条
  2. 获取当前客户已授权目录 ID 集合 authorizedIds
     = ComDiCustomerAuthAggregate.listCurrentUserAuthId(REPORT_DIR)
  3. 每条报告设置 ext.put(DiConst.KEY_AUTH_FLAG, authorizedIds.contains(report.getReportDirId()))
  4. 批量查询封面附件信息，填充 coverUrl
  5. 批量查询标签，填充 tagNames
```

### 6. 热点报告（listHot）

```
listHot():
  1. 查询 com_di_report_opt_record，统计近 30 天（add_time >= now-30d）
     按 report_id 分组，COUNT(*) 倒序，取前 N 条 report_id 列表
  2. 根据 report_id 列表查询报告详情（enableFlag=true）
  3. 获取各报告的 report_dir_id
  4. 调用 ComDiCustomerAuthAggregate.listCurrentUserAuthId(REPORT_DIR)
     获取当前客户已授权目录 ID 集合 authorizedIds
  5. 每条报告设置 ext.put(DiConst.KEY_AUTH_FLAG, authorizedIds.contains(report.getReportDirId()))
  6. 批量查询封面附件信息和标签，填充响应
```

### 7. 操作日志记录（saveOptRecord）

```
saveOptRecord(DiReportOptRecordAddReq):
  1. 构建 ComDiReportOptRecordEntity，保存
  2. 无需返回业务数据，返回 GeneralResult<Void>
```

```
listTree():
  1. 查询所有 enableFlag=true、delFlag=false 的目录，按 orderNum + id 排序
  2. 调用 ComDiCustomerAuthAggregate.listCurrentUserAuthId(REPORT_DIR)
     → 获取当前客户已授权的目录 ID 集合 authorizedIds
  3. DiReportDirConverter.toTreeNodePropertyList() 转换，
     并在 ext 中写入 authorized = authorizedIds.contains(dir.getId())，
     key 使用 `DiConst.KEY_AUTH_FLAG`（即 `ext.put(DiConst.KEY_AUTH_FLAG, authorizedIds.contains(dir.getId()))`）
  4. TreeNode.buildTree(treeNodeProperties) 构建树
  5. 返回 GeneralResult<List<TreeNode>>
```

### 5. 客户端报告列表查询

```
page(DiReportQueryPageReq):
  1. 校验当前客户对 reportDirId 是否已授权（通过 authorizedIds 判断），未授权抛异常
  2. 通过 reportDirIdPath 做前缀匹配（LIKE 'xxx%'）查询该目录及子目录下的报告
  3. 支持 reportYear、tagName（JOIN com_di_report_tag）、keyword（LIKE reportTitle）筛选
  4. 只返回 enableFlag=true 的报告
  5. 批量查询封面附件信息（FeignMdmAttachmentService.listByIds），填充 coverUrl
  6. 批量查询标签列表，填充 tagNames
```

---

## 数据库变更

```sql
-- 1. 资讯报告目录表
CREATE TABLE `com_di_report_dir` (
  `id`            BIGINT       NOT NULL COMMENT '主键',
  `dir_name`      VARCHAR(100) NOT NULL COMMENT '目录名称',
  `dir_desc`      VARCHAR(500)          COMMENT '目录说明',
  `parent_id`     BIGINT                COMMENT '父节点ID（NULL表示一级）',
  `id_path`       VARCHAR(500)          COMMENT 'ID完整层级路径',
  `current_level` INT                   COMMENT '当前层级（1或2）',
  `order_num`     INT                   COMMENT '排序序号',
  `enable_flag`   TINYINT(1)   DEFAULT 1 COMMENT '是否启用',
  `del_flag`      TINYINT(1)   DEFAULT 0 COMMENT '删除标识',
  `add_user_id`   VARCHAR(50)           COMMENT '创建人账号',
  `add_user_name` VARCHAR(100)          COMMENT '创建人姓名',
  `add_time`      DATETIME              COMMENT '创建时间',
  `update_user_id`   VARCHAR(50)        COMMENT '更新人账号',
  `update_user_name` VARCHAR(100)       COMMENT '更新人姓名',
  `update_time`   DATETIME              COMMENT '更新时间',
  PRIMARY KEY (`id`)
) COMMENT='资讯报告目录';

-- 2. 资讯报告表
CREATE TABLE `com_di_report` (
  `id`                 BIGINT        NOT NULL COMMENT '主键',
  `report_title`       VARCHAR(200)  NOT NULL COMMENT '报告标题',
  `report_dir_id`      BIGINT                 COMMENT '所属目录ID',
  `report_dir_id_path` VARCHAR(500)           COMMENT '目录ID路径',
  `publish_date`       DATE                   COMMENT '发布日期',
  `report_year`        INT                    COMMENT '报告年份',
  `report_date`        DATE                   COMMENT '报告期',
  `att_id`             BIGINT                 COMMENT 'PDF附件ID',
  `txt_att_id`         BIGINT                 COMMENT 'TXT附件ID（AI生成简介用）',
  `cover_att_id`       BIGINT                 COMMENT '封面附件ID',
  `report_intro`       VARCHAR(2000)          COMMENT '报告简介',
  `intro_gen_status`   VARCHAR(20)  DEFAULT 'PENDING' COMMENT '简介生成状态',
  `enable_flag`        TINYINT(1)   DEFAULT 1 COMMENT '是否启用',
  `del_flag`           TINYINT(1)   DEFAULT 0 COMMENT '删除标识',
  `add_user_id`        VARCHAR(50)            COMMENT '创建人账号',
  `add_user_name`      VARCHAR(100)           COMMENT '创建人姓名',
  `add_time`           DATETIME               COMMENT '创建时间',
  `update_user_id`     VARCHAR(50)            COMMENT '更新人账号',
  `update_user_name`   VARCHAR(100)           COMMENT '更新人姓名',
  `update_time`        DATETIME               COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_report_dir_id` (`report_dir_id`),
  INDEX `idx_report_dir_id_path` (`report_dir_id_path`(255))
) COMMENT='资讯报告';

-- 3. 报告标签关联表
CREATE TABLE `com_di_report_tag` (
  `id`          BIGINT       NOT NULL COMMENT '主键',
  `report_id`   BIGINT       NOT NULL COMMENT '报告ID',
  `tag_name`    VARCHAR(100) NOT NULL COMMENT '标签文本',
  `del_flag`    TINYINT(1)   DEFAULT 0 COMMENT '删除标识',
  `add_user_id`   VARCHAR(50)  COMMENT '创建人账号',
  `add_user_name` VARCHAR(100) COMMENT '创建人姓名',
  `add_time`      DATETIME     COMMENT '创建时间',
  `update_user_id`   VARCHAR(50)  COMMENT '更新人账号',
  `update_user_name` VARCHAR(100) COMMENT '更新人姓名',
  `update_time`      DATETIME     COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_report_id` (`report_id`)
) COMMENT='报告标签关联';

-- 4. 报告操作日志表
CREATE TABLE `com_di_report_opt_record` (
  `id`                 BIGINT        NOT NULL COMMENT '主键',
  `report_id`          BIGINT        NOT NULL COMMENT '报告ID',
  `report_title`       VARCHAR(200)           COMMENT '报告标题',
  `opt_type`           VARCHAR(20)            COMMENT '操作类型：VISIT/DOWNLOAD',
  `del_flag`           TINYINT(1)   DEFAULT 0 COMMENT '删除标识',
  `add_user_id`        VARCHAR(50)            COMMENT '创建人账号',
  `add_user_name`      VARCHAR(100)           COMMENT '创建人姓名',
  `add_time`           DATETIME               COMMENT '创建时间',
  `update_user_id`     VARCHAR(50)            COMMENT '更新人账号',
  `update_user_name`   VARCHAR(100)           COMMENT '更新人姓名',
  `update_time`        DATETIME               COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_report_id_add_time` (`report_id`, `add_time`)
) COMMENT='报告操作日志';
```

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| 目录层级超过两级 | `BizValidateException` | "目录最多两级" |
| 删除有子目录的目录 | `BizValidateException` | "该目录下存在子目录，无法删除" |
| 删除有报告的目录 | `BizValidateException` | "该目录下存在报告，无法删除" |
| 客户端访问未授权目录 | `BizValidateException` | "无权限访问该目录" |
| 简介生成中时点击重试 | `BizValidateException` | "简介正在生成中，请稍后" |
| PDF 转 TXT 失败 | 更新 `introGenStatus=FAILED`，记录 ERROR 日志 | — |
| AI 调用失败 | 更新 `introGenStatus=FAILED`，记录 ERROR 日志 | — |

---

## 影响范围

### 新增文件
- `entity/di/` 下 4 个实体类（含 `ComDiReportOptRecordEntity`）
- `mapper/di/` 下 4 个 Mapper 接口 + 1 个 XML（报告含标签 JOIN 查询）
- `service/di/` 下 4 个接口 + 4 个实现类
- `aggregate/di/` 下 3 个 Aggregate
- `component/di/ComDiReportIntroGenComponent.java`
- `controller/di/` 下 3 个 Controller
- `converter/di/` 下 2 个 Converter
- `model/di/` 下若干 Req/Resp
- `config/enums/di/DiReportIntroGenStatusEnum.java`
- `config/enums/di/DiReportOptTypeEnum.java`
- `scripts/V0011__add_di_report_tables.sql`

### 修改文件
- `config/enums/di/DiAuthObjTypeEnum.java` — 新增 `REPORT_DIR("资讯报告目录")`
- `dib-agent-service-data-web/pom.xml` — 新增 `dib-cloud-ai-starter` 依赖

### 无需修改
- `ComDiCustomerAuthController` / `Aggregate` / `Service` / `Mapper` — 完全复用

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| data 服务未引入 `dib-cloud-ai-starter` | AI 调用编译失败 | pom.xml 新增依赖，参考 report 服务 |
| PDF 文件过大导致 TXT 转换超时 | 简介生成失败 | 异步执行，失败后支持重试；记录详细日志 |
| 客户端报告列表含标签 JOIN 查询性能 | 大数据量下分页慢 | `report_id` 加索引；分两步查询（先分页报告，再批量查标签） |

---

**状态**：已确认

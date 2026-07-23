# 数据资讯快讯 技术设计

> 编号：`0007` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-03-26
> 关联需求：`requirements.md`

---

## 概述

在 di 业务域下新增 `com_di_news_flash` 表及完整 CRUD 接口，提供后台管理和前端查询（轮播、按主题）能力。

---

## 架构设计

### 调用链

```
Controller → Aggregate → Service → Mapper → DB
```

- 分页查询、新增、编辑、删除：走 Aggregate 做业务校验
- 轮播查询、按主题查询：逻辑简单，Controller 直接调 Service

---

## 涉及文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `config/enums/di/String.java` | 主题标签枚举 |
| 新增 | `entity/di/ComDiNewsFlashEntity.java` | 实体类 |
| 新增 | `mapper/di/ComDiNewsFlashMapper.java` | Mapper 接口 |
| 新增 | `service/di/IComDiNewsFlashService.java` | Service 接口 |
| 新增 | `service/di/impl/ComDiNewsFlashServiceImpl.java` | Service 实现 |
| 新增 | `model/di/req/DiNewsFlashAddReq.java` | 新增请求 |
| 新增 | `model/di/req/DiNewsFlashEditReq.java` | 编辑请求 |
| 新增 | `model/di/query/DiNewsFlashQuery.java` | 分页查询条件 |
| 新增 | `model/di/resp/DiNewsFlashResp.java` | 响应对象 |
| 新增 | `converter/di/DiNewsFlashConverter.java` | MapStruct 转换器 |
| 新增 | `aggregate/di/ComDiNewsFlashAggregate.java` | 聚合层（业务校验） |
| 新增 | `controller/di/ComDiNewsFlashController.java` | Controller |
| 新增 | `scripts/V0007__create_com_di_news_flash.sql` | 建表脚本 |

> 所有路径均相对于 `dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/`

---

## 数据模型

### 实体类：`ComDiNewsFlashEntity`

继承 `BaseEntity`，字段如下：

| Java 字段 | 类型 | DB 列名 | 说明 |
|-----------|------|---------|------|
| newsTopicType | String | news_topic_type | 主题标签 |
| title | String | title | 标题 |
| startDate | LocalDate | start_date | 开始日期 |
| endDate | LocalDate | end_date | 结束日期 |
| importantFlag | Boolean | important_flag | 是否重大资讯 |
| linkUrl | String | link_url | 跳转链接 |
| description | String | description | 描述 |
| enableFlag | Boolean | enable_flag | 激活状态 |

> `BaseEntity` 已包含：id、delFlag、addUserId、addUserName、addTime、updateUserId、updateUserName、updateTime

### 枚举：`String`

```java
NEW_DB("新库"), NEW_TABLE("新表"), NEW_REPORT("新报告"), NEW_FUNC("新功能")
```

---

## 接口设计

### API 列表

| 方法 | 路径 | Controller 方法 | 调用链 |
|------|------|----------------|--------|
| POST | `/di/news-flash/page` | `page()` | Controller → Aggregate → Service |
| POST | `/di/news-flash/add` | `add()` | Controller → Aggregate → Service |
| POST | `/di/news-flash/edit` | `edit()` | Controller → Aggregate → Service |
| POST | `/di/news-flash/delete/{id}` | `delete()` | Controller → Aggregate → Service |
| POST | `/di/news-flash/enable/{id}` | `enable()` | Controller → Aggregate → Service |
| POST | `/di/news-flash/disable/{id}` | `disable()` | Controller → Aggregate → Service |
| GET | `/di/news-flash/carousel` | `carousel()` | Controller → Service |
| GET | `/di/news-flash/list-by-topic/{newsTopicType}` | `listByTopic()` | Controller → Service |

---

## 核心逻辑设计

### 1. 分页查询

```
1. 接收 DiNewsFlashQuery（newsTopicType、startDateBegin、startDateEnd、keyword、pageNum、pageSize）
2. lambdaQuery 构建条件：
   - eq(newsTopicType != null, newsTopicType)
   - ge(startDateBegin != null, startDate, startDateBegin)
   - le(startDateEnd != null, startDate, startDateEnd)
   - like(keyword != null, title, keyword)
   - eq(delFlag, false)
   - orderByDesc(addTime)
3. 转换为 PageResp<DiNewsFlashResp> 返回
```

### 2. 新增

```
1. 校验 endDate >= startDate，否则抛 BizValidateException
2. Converter 转 Entity，设置 enableFlag=true
3. service.save(entity)
```

### 3. 编辑

```
1. 查询记录是否存在（delFlag=false），不存在抛异常
2. 校验 endDate >= startDate
3. Converter 转 Entity，service.updateById(entity)
```

### 4. 删除

```
1. 查询记录是否存在（delFlag=false），不存在抛异常
2. lambdaUpdate().eq(id).set(delFlag, true).update()
```

### 5. 激活

```
1. 查询记录是否存在（delFlag=false），不存在抛 BizValidateException("快讯记录不存在")
2. lambdaUpdate().eq(id).set(enableFlag, true).set(updateUserId/Name/Time).update()
```

### 6. 禁用

```
1. 查询记录是否存在（delFlag=false），不存在抛 BizValidateException("快讯记录不存在")
2. lambdaUpdate().eq(id).set(enableFlag, false).set(updateUserId/Name/Time).update()
```

### 7. 轮播查询

```
1. 获取当天日期 today = LocalDate.now()
2. lambdaQuery 条件：
   - le(startDate, today)       -- start_date <= today
   - gt(endDate, today)         -- end_date > today
   - eq(enableFlag, true)
   - eq(delFlag, false)
   - orderByDesc(startDate)
3. 转换为 List<DiNewsFlashResp> 返回
```

### 8. 按主题标签查询

```
1. 校验 newsTopicType 不为空
2. lambdaQuery 条件：
   - eq(newsTopicType, newsTopicType)
   - eq(enableFlag, true)
   - eq(delFlag, false)
   - orderByDesc(startDate)
3. 转换为 List<DiNewsFlashResp> 返回
```

---

## 关键代码结构

### String

```java
package com.dib.agent.data.web.config.enums.di;

public enum String {
    NEW_DB("新库"),
    NEW_TABLE("新表"),
    NEW_REPORT("新报告"),
    NEW_FUNC("新功能");

    private final String desc;

    String(String desc) { this.desc = desc; }

    public String getDesc() { return this.desc; }
}
```

### ComDiNewsFlashEntity（关键字段）

```java
@TableName("com_di_news_flash")
public class ComDiNewsFlashEntity extends BaseEntity {
    private String newsTopicType;
    private String title;
    @DateTimeFormat(pattern = "yyyy-MM-dd")
    @JsonFormat(pattern = "yyyy-MM-dd", timezone = "GMT+8")
    private LocalDate startDate;
    @DateTimeFormat(pattern = "yyyy-MM-dd")
    @JsonFormat(pattern = "yyyy-MM-dd", timezone = "GMT+8")
    private LocalDate endDate;
    private Boolean importantFlag;
    private String linkUrl;
    private String description;
    private Boolean enableFlag;
}
```

### DiNewsFlashConverter

```java
@Mapper
public interface DiNewsFlashConverter {
    DiNewsFlashConverter INSTANCE = Mappers.getMapper(DiNewsFlashConverter.class);

    @Mapping(target = "id", expression = MapStructUtils.ID_EXP)
    @Mapping(target = "delFlag", constant = "false")
    @Mapping(target = "enableFlag", constant = "true")
    ComDiNewsFlashEntity fromAddReq(DiNewsFlashAddReq req, AddingUser addingUser);

    @Mapping(target = "delFlag", constant = "false")
    ComDiNewsFlashEntity fromEditReq(DiNewsFlashEditReq req, UpdatingUser updatingUser);

    DiNewsFlashResp toResp(ComDiNewsFlashEntity entity);
    List<DiNewsFlashResp> toRespList(List<ComDiNewsFlashEntity> list);
}
```

### ComDiNewsFlashAggregate（核心校验）

```java
// 新增
public void add(DiNewsFlashAddReq req, AddingUser addingUser) {
    validateDateRange(req.getStartDate(), req.getEndDate());
    ComDiNewsFlashEntity entity = converter.fromAddReq(req, addingUser);
    newsFlashService.save(entity);
}

// 编辑
public void edit(DiNewsFlashEditReq req, UpdatingUser updatingUser) {
    assertExists(req.getId());
    validateDateRange(req.getStartDate(), req.getEndDate());
    ComDiNewsFlashEntity entity = converter.fromEditReq(req, updatingUser);
    newsFlashService.updateById(entity);
}

// 删除
public void delete(Long id) {
    assertExists(id);
    newsFlashService.lambdaUpdate()
        .eq(ComDiNewsFlashEntity::getId, id)
        .set(ComDiNewsFlashEntity::getDelFlag, true)
        .update();
}

// 激活
public void enable(Long id) {
    assertExists(id);
    UpdatingUser updatingUser = ServletRequestContext.getUpdatingUser();
    newsFlashService.lambdaUpdate()
        .eq(ComDiNewsFlashEntity::getId, id)
        .set(ComDiNewsFlashEntity::getEnableFlag, true)
        .set(ComDiNewsFlashEntity::getUpdateUserId, updatingUser.getUpdateUserId())
        .set(ComDiNewsFlashEntity::getUpdateUserName, updatingUser.getUpdateUserName())
        .set(ComDiNewsFlashEntity::getUpdateTime, updatingUser.getUpdateTime())
        .update();
}

// 禁用
public void disable(Long id) {
    assertExists(id);
    UpdatingUser updatingUser = ServletRequestContext.getUpdatingUser();
    newsFlashService.lambdaUpdate()
        .eq(ComDiNewsFlashEntity::getId, id)
        .set(ComDiNewsFlashEntity::getEnableFlag, false)
        .set(ComDiNewsFlashEntity::getUpdateUserId, updatingUser.getUpdateUserId())
        .set(ComDiNewsFlashEntity::getUpdateUserName, updatingUser.getUpdateUserName())
        .set(ComDiNewsFlashEntity::getUpdateTime, updatingUser.getUpdateTime())
        .update();
}

private void assertExists(Long id) {
    boolean exists = newsFlashService.lambdaQuery()
        .eq(ComDiNewsFlashEntity::getId, id)
        .eq(ComDiNewsFlashEntity::getDelFlag, false)
        .exists();
    if (!exists) throw new BizValidateException("快讯记录不存在");
}

private void validateDateRange(LocalDate startDate, LocalDate endDate) {
    if (endDate.isBefore(startDate)) {
        throw new BizValidateException("结束日期不能早于开始日期");
    }
}
```

---

## 数据库变更

```sql
CREATE TABLE `com_di_news_flash` (
    `id`               BIGINT       NOT NULL COMMENT '主键',
    `news_topic_type`  VARCHAR(50)  NOT NULL COMMENT '主题标签（NEW_DB/NEW_TABLE/NEW_REPORT/NEW_FUNC）',
    `title`            VARCHAR(200) NOT NULL COMMENT '标题',
    `start_date`       DATE         NOT NULL COMMENT '开始日期',
    `end_date`         DATE         NOT NULL COMMENT '结束日期',
    `important_flag`   TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否重大资讯（0-否，1-是）',
    `link_url`         VARCHAR(500)          COMMENT '跳转链接',
    `description`      TEXT                  COMMENT '描述',
    `enable_flag`      TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '激活状态（0-禁用，1-启用）',
    `del_flag`         TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '删除标识（0-正常，1-已删除）',
    `add_user_id`      VARCHAR(50)           COMMENT '创建人账号',
    `add_user_name`    VARCHAR(100)          COMMENT '创建人姓名',
    `add_time`         DATETIME              COMMENT '创建时间',
    `update_user_id`   VARCHAR(50)           COMMENT '更新人账号',
    `update_user_name` VARCHAR(100)          COMMENT '更新人姓名',
    `update_time`      DATETIME              COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_news_topic_type` (`news_topic_type`),
    INDEX `idx_start_date` (`start_date`),
    INDEX `idx_end_date` (`end_date`),
    INDEX `idx_enable_flag` (`enable_flag`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '数据资讯快讯表';
```

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| endDate < startDate | 抛 BizValidateException | "结束日期不能早于开始日期" |
| 编辑/删除记录不存在 | 抛 BizValidateException | "快讯记录不存在" |
| newsTopicType 传入非法值 | Spring 枚举反序列化失败，返回 400 | 框架默认处理 |

---

## 影响范围

### 新增文件（共 13 个）

- `config/enums/di/String.java`
- `entity/di/ComDiNewsFlashEntity.java`
- `mapper/di/ComDiNewsFlashMapper.java`
- `service/di/IComDiNewsFlashService.java`
- `service/di/impl/ComDiNewsFlashServiceImpl.java`
- `model/di/req/DiNewsFlashAddReq.java`
- `model/di/req/DiNewsFlashEditReq.java`
- `model/di/query/DiNewsFlashQuery.java`
- `model/di/resp/DiNewsFlashResp.java`
- `converter/di/DiNewsFlashConverter.java`
- `aggregate/di/ComDiNewsFlashAggregate.java`
- `controller/di/ComDiNewsFlashController.java`
- `scripts/V0007__create_com_di_news_flash.sql`

### 无需修改的文件

- 现有 di 域所有文件均不受影响
- 无需修改 pom.xml、配置文件

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 枚举值数据库存储 | MyBatis-Plus 默认存枚举 name，需确认 | 使用 `@EnumValue` 或全局枚举处理器，与现有 `UpdateFrequencyEnum` 保持一致 |
| LocalDate 序列化 | 日期格式不一致 | 参考 `ComDiTableEntity` 加 `@DateTimeFormat` + `@JsonFormat` |

---

**状态**：草稿

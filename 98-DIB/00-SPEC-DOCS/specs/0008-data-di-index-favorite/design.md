# 数据资讯指标收藏功能 技术设计

> 编号：`0008` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-03-26
> 关联需求：`requirements.md`

---

## 概述

在 di 业务域下新增 `com_di_index_favorite` 收藏表，提供收藏、取消收藏、查询我的收藏列表三个接口。收藏列表关联 `com_di_index` 在内存中按指标名称排序。

---

## 架构设计

### 调用链

```
Controller → Aggregate → Service → Mapper → DB
```

- 三个接口均通过 Aggregate 处理业务逻辑
- 收藏列表在 Aggregate 中联查 `IComDiIndexService`，内存排序后返回

---

## 涉及文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `entity/di/ComDiIndexFavoriteEntity.java` | 实体类 |
| 新增 | `mapper/di/ComDiIndexFavoriteMapper.java` | Mapper 接口 |
| 新增 | `service/di/IComDiIndexFavoriteService.java` | Service 接口 |
| 新增 | `service/di/impl/ComDiIndexFavoriteServiceImpl.java` | Service 实现 |
| 新增 | `model/di/resp/DiIndexFavoriteResp.java` | 响应对象 |
| 新增 | `aggregate/di/ComDiIndexFavoriteAggregate.java` | 聚合层 |
| 新增 | `controller/di/ComDiIndexFavoriteController.java` | Controller |
| 新增 | `scripts/V0008__create_com_di_index_favorite.sql` | 建表脚本 |

> 所有路径均相对于 `dib-agent-service-data-web/src/main/java/com/dib/agent/data/web/`

---

## 数据模型

### 实体类：`ComDiIndexFavoriteEntity`

继承 `BaseEntity`，字段如下：

| Java 字段 | 类型 | DB 列名 | 说明 |
|-----------|------|---------|------|
| indexId | Long | index_id | 指标 ID |
| userId | String | user_id | 用户账号（冗余存储，便于查询） |

> `BaseEntity` 已包含：id、delFlag、addUserId、addUserName、addTime、updateUserId、updateUserName、updateTime
> `userId` 冗余存储 `addUserId`，在 `setAddUser()` 后手动赋值，用于查询条件

### 响应对象：`DiIndexFavoriteResp`

| Java 字段 | 类型 | 说明 |
|-----------|------|------|
| indexId | Long | 指标 ID |
| indexName | String | 指标名称（来自 com_di_index） |
| addTime | Date | 收藏时间 |

---

## 接口设计

### API 列表

| 方法 | 路径 | Controller 方法 | 说明 |
|------|------|----------------|------|
| POST | `/di/index-favorite/add/{indexId}` | `add()` | 收藏指标（幂等） |
| POST | `/di/index-favorite/cancel/{indexId}` | `cancel()` | 取消收藏（幂等） |
| GET | `/di/index-favorite/my-list` | `myList()` | 查询我的收藏列表 |

---

## 核心逻辑设计

### 1. 收藏（幂等）

```
1. 从 ServletRequestContext 获取当前用户 userId（addUserId）
2. 查询是否已存在有效收藏：
   eq(indexId) AND eq(userId) AND eq(delFlag, false)
3. 若已存在 → 直接返回，不重复插入
4. 若不存在 → 构建 Entity，设置 indexId、userId，调用 setAddUser()，save()
```

### 2. 取消收藏（幂等）

```
1. 从 ServletRequestContext 获取当前用户 userId
2. 查询是否存在有效收藏：
   eq(indexId) AND eq(userId) AND eq(delFlag, false)
3. 若不存在 → 直接返回（幂等）
4. 若存在 → lambdaUpdate 逻辑删除：set(delFlag, true)，setUpdateUser()
```

### 3. 查询我的收藏列表

```
1. 从 ServletRequestContext 获取当前用户 userId
2. 查询该用户所有有效收藏：
   eq(userId) AND eq(delFlag, false)
3. 提取 indexId 列表
4. 若列表为空 → 返回空列表
5. 批量查询 com_di_index：in(id, indexIdList) AND eq(delFlag, false)
6. 构建 Map<indexId, indexName>
7. 组装 DiIndexFavoriteResp 列表（过滤 indexId 在 Map 中不存在的记录）
8. 内存中按 indexName 升序排序后返回
```

---

## 关键代码结构

### ComDiIndexFavoriteEntity

```java
@TableName("com_di_index_favorite")
public class ComDiIndexFavoriteEntity extends BaseEntity {
    private Long indexId;
    private String userId;  // 冗余存储 addUserId，便于查询
}
```

### ComDiIndexFavoriteAggregate（核心逻辑）

```java
// 收藏
public void add(Long indexId) {
    String userId = ServletRequestContext.getAddingUser().getAddUserId();
    boolean exists = favoriteService.lambdaQuery()
        .eq(ComDiIndexFavoriteEntity::getIndexId, indexId)
        .eq(ComDiIndexFavoriteEntity::getUserId, userId)
        .eq(ComDiIndexFavoriteEntity::getDelFlag, false)
        .exists();
    if (exists) return;  // 幂等
    ComDiIndexFavoriteEntity entity = new ComDiIndexFavoriteEntity();
    entity.setId(SnowFlakeUtils.nextId());
    entity.setIndexId(indexId);
    entity.setUserId(userId);
    entity.setDelFlag(false);
    entity.setAddUser();
    favoriteService.save(entity);
}

// 取消收藏
public void cancel(Long indexId) {
    String userId = ServletRequestContext.getAddingUser().getAddUserId();
    ComDiIndexFavoriteEntity record = favoriteService.lambdaQuery()
        .eq(ComDiIndexFavoriteEntity::getIndexId, indexId)
        .eq(ComDiIndexFavoriteEntity::getUserId, userId)
        .eq(ComDiIndexFavoriteEntity::getDelFlag, false)
        .one();
    if (record == null) return;  // 幂等
    record.setUpdateUser();
    favoriteService.lambdaUpdate()
        .eq(ComDiIndexFavoriteEntity::getId, record.getId())
        .set(ComDiIndexFavoriteEntity::getDelFlag, true)
        .update();
}

// 查询我的收藏列表
public List<DiIndexFavoriteResp> myList() {
    String userId = ServletRequestContext.getAddingUser().getAddUserId();
    List<ComDiIndexFavoriteEntity> favorites = favoriteService.lambdaQuery()
        .eq(ComDiIndexFavoriteEntity::getUserId, userId)
        .eq(ComDiIndexFavoriteEntity::getDelFlag, false)
        .list();
    if (CollUtil.isEmpty(favorites)) return Collections.emptyList();

    List<Long> indexIds = favorites.stream()
        .map(ComDiIndexFavoriteEntity::getIndexId).collect(Collectors.toList());

    Map<Long, String> indexNameMap = indexService.lambdaQuery()
        .in(ComDiIndexEntity::getId, indexIds)
        .eq(ComDiIndexEntity::getDelFlag, false)
        .list()
        .stream()
        .collect(Collectors.toMap(ComDiIndexEntity::getId, ComDiIndexEntity::getIndexName));

    return favorites.stream()
        .filter(f -> indexNameMap.containsKey(f.getIndexId()))
        .map(f -> {
            DiIndexFavoriteResp resp = new DiIndexFavoriteResp();
            resp.setIndexId(f.getIndexId());
            resp.setIndexName(indexNameMap.get(f.getIndexId()));
            resp.setAddTime(f.getAddTime());
            return resp;
        })
        .sorted(Comparator.comparing(DiIndexFavoriteResp::getIndexName))
        .collect(Collectors.toList());
}
```

---

## 数据库变更

```sql
CREATE TABLE `com_di_index_favorite`
(
    `id`               BIGINT       NOT NULL COMMENT '主键',
    `index_id`         BIGINT       NOT NULL COMMENT '指标ID（关联 com_di_index.id）',
    `user_id`          VARCHAR(50)  NOT NULL COMMENT '用户账号',
    `del_flag`         TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '删除标识（0-正常，1-已删除）',
    `add_user_id`      VARCHAR(50)           COMMENT '创建人账号',
    `add_user_name`    VARCHAR(100)          COMMENT '创建人姓名',
    `add_time`         DATETIME              COMMENT '创建时间',
    `update_user_id`   VARCHAR(50)           COMMENT '更新人账号',
    `update_user_name` VARCHAR(100)          COMMENT '更新人姓名',
    `update_time`      DATETIME              COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_user_id_index_id` (`user_id`, `index_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '数据资讯指标收藏表';
```

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 重复收藏 | 幂等返回成功，不插入 |
| 取消未收藏的指标 | 幂等返回成功，不操作 |
| 收藏列表中指标已删除 | filter 过滤，不返回该条 |

---

## 影响范围

### 新增文件（共 8 个）
- `entity/di/ComDiIndexFavoriteEntity.java`
- `mapper/di/ComDiIndexFavoriteMapper.java`
- `service/di/IComDiIndexFavoriteService.java`
- `service/di/impl/ComDiIndexFavoriteServiceImpl.java`
- `model/di/resp/DiIndexFavoriteResp.java`
- `aggregate/di/ComDiIndexFavoriteAggregate.java`
- `controller/di/ComDiIndexFavoriteController.java`
- `scripts/V0008__create_com_di_index_favorite.sql`

### 无需修改的文件
- 现有 di 域所有文件均不受影响（只读 `IComDiIndexService`）

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| userId 冗余字段与 addUserId 不一致 | 查询结果错误 | save 前显式赋值 `entity.setUserId(userId)` |
| 收藏列表指标量大时内存排序性能 | 响应慢 | 当前场景收藏量有限，内存排序可接受 |

---

**状态**：草稿

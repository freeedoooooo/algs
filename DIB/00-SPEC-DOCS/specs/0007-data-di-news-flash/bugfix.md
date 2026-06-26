# Bugfix 需求文档：ComDiNewsFlashAggregate 缺少 enable/disable 方法

> 编号：`0007-bugfix` | 模块：`data` | 服务：`dib-agent-service-data` | 创建时间：2026-03-26
> 关联 spec：`0007-data-di-news-flash`

---

## Introduction

`ComDiNewsFlashAggregate` 已实现 page / add / edit / delete / carousel / listByTopic 六个方法，`ComDiNewsFlashEntity` 中存在 `enableFlag`（Boolean）字段表示激活状态，`carousel()` 和 `listByTopic()` 查询时均已过滤 `enableFlag = true`。

然而，目前没有任何接口可以修改 `enableFlag` 的值，导致后台管理员无法对快讯进行激活或禁用操作。新增的快讯默认 `enableFlag = true`，一旦需要临时下线某条快讯，只能通过删除来实现，无法恢复，造成数据丢失风险。

本 bugfix 补充 `enable(Long id)` 和 `disable(Long id)` 两个方法，以及对应的 Controller 接口。

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 后台管理员需要禁用某条快讯（将 `enableFlag` 设为 `false`）THEN 系统不存在对应接口，操作无法完成

1.2 WHEN 后台管理员需要重新激活某条已禁用的快讯（将 `enableFlag` 设为 `true`）THEN 系统不存在对应接口，操作无法完成

1.3 WHEN 调用 `POST /di/news-flash/disable/{id}` THEN 系统返回 404，接口不存在

1.4 WHEN 调用 `POST /di/news-flash/enable/{id}` THEN 系统返回 404，接口不存在

### Expected Behavior (Correct)

2.1 WHEN 后台管理员调用 `POST /di/news-flash/disable/{id}` 且记录存在且未删除 THEN 系统 SHALL 将该记录的 `enableFlag` 更新为 `false` 并返回成功

2.2 WHEN 后台管理员调用 `POST /di/news-flash/enable/{id}` 且记录存在且未删除 THEN 系统 SHALL 将该记录的 `enableFlag` 更新为 `true` 并返回成功

2.3 WHEN 调用 enable/disable 接口时 id 对应记录不存在或已逻辑删除 THEN 系统 SHALL 抛出业务异常，提示"快讯记录不存在"

2.4 WHEN enable/disable 操作成功 THEN 系统 SHALL 同步更新 `updateUserId`、`updateUserName`、`updateTime` 字段

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 调用 `POST /di/news-flash/page` THEN 系统 SHALL CONTINUE TO 按原有条件分页查询，不受 enable/disable 影响

3.2 WHEN 调用 `POST /di/news-flash/add` THEN 系统 SHALL CONTINUE TO 新增快讯并默认设置 `enableFlag = true`

3.3 WHEN 调用 `POST /di/news-flash/edit` THEN 系统 SHALL CONTINUE TO 编辑快讯内容，不修改 `enableFlag`

3.4 WHEN 调用 `POST /di/news-flash/delete/{id}` THEN 系统 SHALL CONTINUE TO 执行逻辑删除，设置 `delFlag = true`

3.5 WHEN 调用 `GET /di/news-flash/carousel` THEN 系统 SHALL CONTINUE TO 仅返回 `enableFlag = true` 且在有效日期范围内的记录

3.6 WHEN 调用 `GET /di/news-flash/list-by-topic/{newsTopicType}` THEN 系统 SHALL CONTINUE TO 仅返回 `enableFlag = true` 的记录

---

## Bug Condition

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type NewsFlashOperation
  OUTPUT: boolean

  // 当操作类型为 enable 或 disable 时触发缺陷
  RETURN X.operationType = ENABLE OR X.operationType = DISABLE
END FUNCTION
```

```pascal
// Property: Fix Checking - enable/disable 接口可用
FOR ALL X WHERE isBugCondition(X) DO
  result ← callApi'(X)
  ASSERT result.httpStatus = 200
    AND result.body.code = SUCCESS
    AND enableFlag_in_db(X.id) = expectedFlag(X.operationType)
END FOR
```

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

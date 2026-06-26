# 字典模块代码重构 技术设计

> 编号：`0005` | 模块：`mdm` | 服务：`data-cloud-mdm` | 创建时间：2026-03-18
> 关联需求：`requirements.md`

---

## 概述

在不改变任何 API 行为和数据库结构的前提下，对字典模块代码进行规范化重构：统一使用 MapStruct Converter 替代 `BeanUtils.copyProperties`，使用 `lambdaQuery()` 链式写法替代手动 `LambdaQueryWrapper`，修正 Converter 命名和注解，补充 `del_flag` 过滤条件。

---

## 架构设计

### 整体架构（不变）

```
DictController
    ├── DictDefAggregate  →  IDictDefService / IDictItemService  →  Mapper  →  DB
    └── DictItemAggregate →  IDictItemService                   →  Mapper  →  DB
```

### 涉及文件

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 修改 | `aggregate/DictDefAggregate.java` | 替换 BeanUtils、LambdaQueryWrapper，补充 del_flag 过滤 |
| 修改 | `aggregate/DictItemAggregate.java` | 替换 BeanUtils，修正入参修改问题 |
| 修改 | `converter/DictDefConverter.java` | 添加 `componentModel = "spring"`，补充转换方法，改为 Spring 注入 |
| 修改 | `converter/DictItemConverter.java` | 重命名方法，补充转换方法，添加 `componentModel = "spring"` |
| 修改 | `controller/dict/DictController.java` | 改为注入 Converter（如需），补全 Swagger 注解 |

---

## 数据模型

### 涉及数据库表

| 表名 | 操作 | 说明 |
|------|------|------|
| `p_mdm_dict_def` | SELECT / INSERT / UPDATE / DELETE | 字典定义表，无结构变更 |
| `p_mdm_dict_item` | SELECT / INSERT / UPDATE / DELETE | 字典项表，无结构变更 |

---

## 核心逻辑设计

### 重构点 1：DictDefConverter — 添加 Spring 注入 + 补充方法

**现状：**
```java
@Mapper
public interface DictDefConverter {
    DictDefConverter INSTANCE = Mappers.getMapper(DictDefConverter.class);
    DictDefInfoResp fromEntityToResp(DictDefEntity defEntity);
    List<DictDefInfoResp> fromEntityListToResp(List<DictDefEntity> defList);
}
```

**重构后：**
```java
@Mapper(componentModel = "spring")
public interface DictDefConverter {
    DictDefConverter INSTANCE = Mappers.getMapper(DictDefConverter.class);

    DictDefInfoResp fromEntityToResp(DictDefEntity entity);
    List<DictDefInfoResp> fromEntityListToResp(List<DictDefEntity> list);

    // 新增：用于 addDictDef / updateDictDef 中替换 BeanUtils
    DictDefEntity fromSaveReqToEntity(DictDefSaveReq req);
}
```

> 注意：保留 `INSTANCE` 静态引用以兼容现有调用，同时支持 Spring 注入（两种方式均可用）。

---

### 重构点 2：DictItemConverter — 重命名 + 补充方法

**现状：**
```java
@Mapper
public interface DictItemConverter {
    DictItemConverter INSTANCE = Mappers.getMapper(DictItemConverter.class);
    List<DictItemBO> fromEntityListToReq(List<DictItemEntity> defList);  // 命名错误
}
```

**重构后：**
```java
@Mapper(componentModel = "spring")
public interface DictItemConverter {
    DictItemConverter INSTANCE = Mappers.getMapper(DictItemConverter.class);

    // 重命名（原 fromEntityListToReq）
    List<DictItemBO> fromEntityListToBO(List<DictItemEntity> list);

    // 新增：用于 getDictItem 中替换 BeanUtils
    DictItemResp fromEntityToResp(DictItemEntity entity);

    // 新增：用于 addDictItem / updateDictItem 中替换 BeanUtils
    DictItemEntity fromSaveReqToEntity(DictItemSaveReq req);

    // 新增：用于 DictDefAggregate.addDictDef / updateDictDef 中替换 BeanUtils
    DictItemEntity fromBOToEntity(DictItemBO bo);
}
```

---

### 重构点 3：DictDefAggregate — 全面重构

#### 3.1 listDictDef — 补充 del_flag 过滤 + 改用 lambdaQuery

**现状问题：**
- 使用 `Wrappers.lambdaQuery()` 手动构建，未过滤 `del_flag`
- 字典项查询也未过滤 `del_flag`

**重构后：**
```java
public List<DictDefDetailResp> listDictDef(DictDefQuery definitionQuery) {
    List<DictDefEntity> definitionList = dictDefServicePlus.lambdaQuery()
        .in(CollUtil.isNotEmpty(definitionQuery.getDictCodeList()),
            DictDefEntity::getDictCode, definitionQuery.getDictCodeList())
        .eq(DictDefEntity::getDelFlag, false)
        .list();

    // ... 构建 dictMap（逻辑不变）

    List<DictItemEntity> itemList = dictItemServicePlus.lambdaQuery()
        .in(CollUtil.isNotEmpty(definitionQuery.getDictCodeList()),
            DictItemEntity::getDictCode, definitionQuery.getDictCodeList())
        .eq(DictItemEntity::getActiveFlag, 1)
        .eq(DictItemEntity::getDelFlag, false)
        .orderByAsc(DictItemEntity::getOrderNum)
        .list();

    // ... 封装逻辑不变
}
```

#### 3.2 pageDictDef — 改用 lambdaQuery

**重构后：**
```java
public PageResp<DictDefInfoResp> pageDictDef(DictDefQuery definitionQuery) {
    Page<DictDefEntity> page = dictDefServicePlus.lambdaQuery()
        .in(CollUtil.isNotEmpty(definitionQuery.getDictCodeList()),
            DictDefEntity::getDictCode, definitionQuery.getDictCodeList())
        .and(StrUtil.isNotBlank(definitionQuery.getDictCodeOrName()),
            qw -> qw.like(DictDefEntity::getDictName, definitionQuery.getDictCodeOrName())
                    .or()
                    .like(DictDefEntity::getDictCode, definitionQuery.getDictCodeOrName()))
        .eq(StrUtil.isNotBlank(definitionQuery.getDictType()),
            DictDefEntity::getDictType, definitionQuery.getDictType())
        .orderByDesc(DictDefEntity::getUpdateTime)
        .page(Page.of(definitionQuery.getPageNum(), definitionQuery.getPageSize()));

    List<DictDefInfoResp> respList = DictDefConverter.INSTANCE.fromEntityListToResp(page.getRecords());
    return PageResp.of(page.getTotal(), respList);
}
```

#### 3.3 getDefById — 替换 BeanUtils

**重构后：**
```java
public DictDefInfoResp getDefById(Integer id) {
    DictDefEntity entity = dictDefServicePlus.getById(id);
    return DictDefConverter.INSTANCE.fromEntityToResp(entity);
}
```

#### 3.4 addDictDef — 替换 BeanUtils

**重构后：**
```java
@Transactional(rollbackFor = Exception.class)
public Integer addDictDef(DictDefSaveReq dictDefSaveReq) {
    Date now = new Date();
    DictDefEntity dictDefEntity = DictDefConverter.INSTANCE.fromSaveReqToEntity(dictDefSaveReq);
    dictDefEntity.setId(SnowFlakeUtils.nextId());
    dictDefEntity.setUpdateUserId(dictDefSaveReq.getAccount());
    dictDefEntity.setUpdateTime(now);
    dictDefServicePlus.save(dictDefEntity);

    List<DictItemBO> dictItemList = dictDefSaveReq.getDictItemList();
    if (CollUtil.isNotEmpty(dictItemList)) {
        List<DictItemEntity> itemEntities = new ArrayList<>();
        for (DictItemBO bo : dictItemList) {
            DictItemEntity itemEntity = DictItemConverter.INSTANCE.fromBOToEntity(bo);
            itemEntity.setId(SnowFlakeUtils.nextId());
            itemEntity.setUpdateTime(now);
            itemEntity.setDictCode(dictDefEntity.getDictCode());
            itemEntities.add(itemEntity);
        }
        dictItemServicePlus.saveBatch(itemEntities);
    }
    return dictDefEntity.getId().intValue();
}
```

#### 3.5 updateDictDef — 替换 BeanUtils

**重构后：**
```java
@Transactional(rollbackFor = Exception.class)
public Integer updateDictDef(DictDefSaveReq dictDefSaveReq) {
    Date now = new Date();
    DictDefEntity dictDefEntity = DictDefConverter.INSTANCE.fromSaveReqToEntity(dictDefSaveReq);
    dictDefEntity.setUpdateUserId(dictDefSaveReq.getAccount());
    dictDefEntity.setUpdateTime(now);
    dictDefServicePlus.updateById(dictDefEntity);

    // 先删除（保持原逻辑：物理删除）
    dictItemServicePlus.lambdaUpdate()
        .eq(DictItemEntity::getDictCode, dictDefSaveReq.getDictCode())
        .remove();

    List<DictItemBO> dictItemList = dictDefSaveReq.getDictItemList();
    if (CollUtil.isNotEmpty(dictItemList)) {
        List<DictItemEntity> itemEntities = new ArrayList<>();
        for (DictItemBO bo : dictItemList) {
            DictItemEntity itemEntity = DictItemConverter.INSTANCE.fromBOToEntity(bo);
            itemEntity.setId(SnowFlakeUtils.nextId());
            itemEntity.setUpdateTime(now);
            itemEntity.setDictCode(dictDefSaveReq.getDictCode());
            itemEntities.add(itemEntity);
        }
        dictItemServicePlus.saveBatch(itemEntities);
    }
    return dictDefEntity.getId().intValue();
}
```

#### 3.6 deleteDictDef — 改用 lambdaUpdate().remove()

**重构后：**
```java
@Transactional(rollbackFor = Exception.class)
public Integer deleteDictDef(List<String> dictCodeList) {
    for (String dictCode : dictCodeList) {
        dictDefServicePlus.lambdaUpdate()
            .eq(DictDefEntity::getDictCode, dictCode)
            .remove();
        dictItemServicePlus.lambdaUpdate()
            .eq(DictItemEntity::getDictCode, dictCode)
            .remove();
    }
    return 0;
}
```

---

### 重构点 4：DictItemAggregate — 全面重构

#### 4.1 listDictItem — 替换 Converter 方法名

```java
public List<DictItemBO> listDictItem(DictItemQuery query) {
    List<DictItemEntity> list = dictItemServicePlus.lambdaQuery()
        // 条件不变
        .list();
    return DictItemConverter.INSTANCE.fromEntityListToBO(list);  // 方法名更新
}
```

#### 4.2 addDictItem — 不再修改入参，替换 BeanUtils

**现状问题：** `saveReq.setId(SnowFlakeUtils.nextId())` 直接修改了入参对象

**重构后：**
```java
public void addDictItem(DictItemSaveReq saveReq) {
    DictItemEntity entity = DictItemConverter.INSTANCE.fromSaveReqToEntity(saveReq);
    entity.setId(SnowFlakeUtils.nextId());
    dictItemServicePlus.save(entity);
}
```

> 注意：Controller 层 `return GeneralResult.success(saveReq.getId())` 依赖入参的 id，重构后需改为 `return GeneralResult.success(entity.getId())`。但这会改变 Controller 代码。评估：Controller 返回的是 entity 的 id（雪花 ID），行为一致，可以接受。

**Controller 对应调整：**
```java
@PostMapping(value = "/item/add")
public GeneralResult<Long> addDictItem(@RequestBody DictItemSaveReq saveReq) {
    Long id = dictItemAggregate.addDictItem(saveReq);  // 改为返回 Long
    return GeneralResult.success(id);
}
```

因此 `DictItemAggregate.addDictItem` 改为返回 `Long`：
```java
public Long addDictItem(DictItemSaveReq saveReq) {
    DictItemEntity entity = DictItemConverter.INSTANCE.fromSaveReqToEntity(saveReq);
    entity.setId(SnowFlakeUtils.nextId());
    dictItemServicePlus.save(entity);
    return entity.getId();
}
```

#### 4.3 updateDictItem — 替换 BeanUtils

```java
public void updateDictItem(DictItemSaveReq saveReq) {
    DictItemEntity entity = DictItemConverter.INSTANCE.fromSaveReqToEntity(saveReq);
    dictItemServicePlus.updateById(entity);
}
```

#### 4.4 getDictItem — 替换 BeanUtils

```java
public DictItemResp getDictItem(Integer id) {
    DictItemEntity entity = dictItemServicePlus.getById(id);
    return DictItemConverter.INSTANCE.fromEntityToResp(entity);
}
```

#### 4.5 mapItemCodeToName — 改用 lambdaQuery

```java
public Map<String, String> mapItemCodeToName(String dictCode) {
    if (StrUtil.isBlank(dictCode)) {
        throw BizValidateException.of("字典编码不能为空");
    }
    List<DictItemEntity> list = dictItemServicePlus.lambdaQuery()
        .eq(DictItemEntity::getDictCode, dictCode)
        .list();
    Map<String, String> codeNameMap = new HashMap<>();
    for (DictItemEntity item : list) {
        codeNameMap.put(item.getItemCode(), item.getItemName());
    }
    return codeNameMap;
}
```

---

## 接口设计

所有接口路径、HTTP 方法、请求/响应结构保持不变，详见 `requirements.md`。

唯一行为变化：
- `POST /dict/list`：新增对已删除字典定义（`del_flag=true`）的过滤，不再返回已删除数据（已确认接受）

---

## 数据库变更

无。

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| `mapItemCodeToName` 传入空 dictCode | 抛出 `BizValidateException` | "字典编码不能为空" |

---

## 影响范围

### 修改文件
- `aggregate/DictDefAggregate.java` — 全面重构（BeanUtils → Converter，LambdaQueryWrapper → lambdaQuery，补充 del_flag）
- `aggregate/DictItemAggregate.java` — 全面重构（BeanUtils → Converter，addDictItem 返回值改为 Long）
- `converter/DictDefConverter.java` — 添加 `componentModel = "spring"`，新增 `fromSaveReqToEntity`
- `converter/DictItemConverter.java` — 添加 `componentModel = "spring"`，重命名 `fromEntityListToBO`，新增 3 个方法
- `controller/dict/DictController.java` — `addDictItem` 方法调整（接收 Aggregate 返回的 Long id）

### 无需修改
- `entity/dict/DictDefEntity.java`
- `entity/dict/DictItemEntity.java`
- `mapper/dict/DictDefMapper.java`
- `mapper/dict/DictItemMapper.java`
- `service/dict/IDictDefService.java`
- `service/dict/IDictItemService.java`
- `service/dict/impl/DictDefServiceImpl.java`
- `service/dict/impl/DictItemServiceImpl.java`
- `model/dict/DictItemBO.java`
- `model/dict/req/DictDefQuery.java`
- `model/dict/req/DictDefSaveReq.java`
- `model/dict/req/DictItemQuery.java`
- `model/dict/req/DictItemSaveReq.java`
- `model/dict/resp/DictDefDetailResp.java`
- `model/dict/resp/DictDefInfoResp.java`
- `model/dict/resp/DictItemResp.java`

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| MapStruct `fromSaveReqToEntity` 字段映射不完整 | 部分字段丢失 | 重构后逐接口验证字段映射，必要时添加 `@Mapping` 注解 |
| `DictDefConverter` 同时保留 `INSTANCE` 和 Spring 注入 | 两套实例共存 | Aggregate 统一使用 `INSTANCE` 静态调用，保持一致性 |
| `addDictItem` 返回值从 void 改为 Long | Controller 需同步修改 | 已在设计中明确 Controller 调整方式 |

---

**状态**：已确认

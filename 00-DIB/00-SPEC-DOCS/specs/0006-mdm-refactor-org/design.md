# 组织模块代码重构 技术设计文档

> 编号：`0006` | 模块：`mdm` | 服务：`data-cloud-mdm` | 创建时间：2026-03-18

---

## 一、设计目标

在不改变任何 API 行为的前提下：
1. 消除 Controller 层直接操作数据库的问题
2. 统一使用 `lambdaQuery()` / `lambdaUpdate()` 链式写法替换手动 `LambdaQueryWrapper`
3. 统一使用 MapStruct Converter 替换 `BeanUtils.copy` / `BeanUtils.copyProperties`
4. 修复 `findByTreeCode` 永远返回空列表的 bug

---

## 二、架构分层设计

```
OrgController          OrgUserController
     ↓ 仅调用 Aggregate       ↓ 仅调用 Aggregate
OrgAggregate           OrgUserAggregate
     ↓                        ↓
IOrgService            IOrgService + IOrgUserService
     ↓                        ↓
  Mapper                   Mapper
```

**重构后 Controller 职责**：仅做参数校验 + 调用 Aggregate + 返回 `GeneralResult<T>`，不注入任何 Service。

---

## 三、Converter 设计

### 3.1 OrgConverter

```java
@Mapper(componentModel = "spring")
public interface OrgConverter {
    OrgConverter INSTANCE = Mappers.getMapper(OrgConverter.class);

    // 已有
    OrgResp fromEntityToResp(OrgEntity entity);
    List<OrgResp> fromEntityToResp(List<OrgEntity> entityList);

    // 新增
    /** OrgAddReq → OrgEntity */
    OrgEntity fromAddReqToEntity(OrgAddReq req);

    /** OrgEntity → OrgTreeNode */
    OrgTreeNode fromEntityToTreeNode(OrgEntity entity);
    List<OrgTreeNode> fromEntityToTreeNode(List<OrgEntity> entityList);
}
```

> 注意：`OrgEntity` 主键为 `orgId`（`@TableId`），MapStruct 按字段名匹配，`req.orgId` 会正确映射到 `entity.orgId`。

### 3.2 OrgUserConverter

```java
@Mapper(componentModel = "spring")
public interface OrgUserConverter {
    OrgUserConverter INSTANCE = Mappers.getMapper(OrgUserConverter.class);

    // 已有
    OrgUserResp fromEntityToResp(OrgUserEntity entity);
    List<OrgUserResp> fromEntityToResp(List<OrgUserEntity> entityList);

    // 新增
    /** OrgUserSaveReq → OrgUserEntity */
    OrgUserEntity fromSaveReqToEntity(OrgUserSaveReq req);

    /** OrgUserResp → OrgUserEntity */
    OrgUserEntity fromRespToEntity(OrgUserResp resp);
}
```

---

## 四、OrgAggregate 重构设计

### 4.1 新增方法

| 方法签名 | 来源 | 说明 |
|---------|------|------|
| `updateOrg(OrgEditReq req)` | OrgController.updateOrg | 校验存在 + Converter 转换 + updateById |
| `deleteOrg(String orgId)` | OrgController.deleteOrg | 校验存在 + 校验子节点 + 校验用户 + removeById |
| `getOrgById(String orgId)` | OrgController.getOrgUnitInfoById | getById + Converter |

### 4.2 现有方法改造

| 方法 | 改造内容 |
|------|---------|
| `addOrg` | `BeanUtils.copy(orgAddReq, orgUnit)` → `OrgConverter.INSTANCE.fromAddReqToEntity(orgAddReq)` |
| `findDirChd` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `findAllChd` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `hasChildren` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `selectMaxTreeCode` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `getOrgListByOrgName` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `getOrgUnitAndChildrenById` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `getOrgUnitListByIds` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `listOrgByTreeCodes` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `findByOrgTypes` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `getAllEnableOrgNode` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；`stream().map(convertToMdmOrgUnitTreeNode)` → `OrgConverter.INSTANCE.fromEntityToTreeNode(orgList)` |
| `convertToMdmOrgUnitTreeNode` | 删除（由 Converter 替代） |

### 4.3 deleteOrg 依赖 OrgUserAggregate

`deleteOrg` 需要调用 `orgUserAggregate.hasUser(orgId)` 进行校验，因此 `OrgAggregate` 需注入 `OrgUserAggregate`。

> 注意循环依赖：`OrgAggregate` → `OrgUserAggregate`，`OrgUserAggregate` → `OrgAggregate`（无）。单向依赖，无循环问题。

---

## 五、OrgUserAggregate 重构设计

### 5.1 新增方法

| 方法签名 | 来源 | 说明 |
|---------|------|------|
| `findOrgByAccount(String account)` | OrgUserController.findByAccount | 查 OrgUser + 查 Org + Converter |
| `findChildren(String orgId)` | OrgUserController.findChildren | lambdaQuery + Converter |
| `findRoot()` | OrgUserController.findRoot | lambdaQuery + Converter |
| `findByType(String orgType)` | OrgUserController.findByType | lambdaQuery + Converter |
| `findByTreeCode(String treeCode)` | OrgUserController.findByTreeCode | 查 Org + 查 OrgUser + Converter（含 bug 修复） |
| `listOrgUnitByUser(String account)` | OrgUserController.listOrgUnitByUser | lambdaQuery + Converter |
| `addUserOrgUnit(OrgUserResp req)` | OrgUserController.addUserOrgUnit | Converter + setId + save |
| `updateUserOrgUnit(OrgUserResp req)` | OrgUserController.updateUserOrgUnit | Converter + updateById |

### 5.2 现有方法改造

| 方法 | 改造内容 |
|------|---------|
| `saveAuthOrgByUser` | 签名改为 `saveAuthOrgByUser(List<OrgUserSaveReq> reqList)`，内部用 Converter 构建 entity 并设置 id |
| `selectBelongOrgByUser` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `saveBelongOrgByUser` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `selectAuthOrgByUser` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `hasUser` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `selectBelongUserByOrg` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；stream 手动构建 → `OrgUserConverter.INSTANCE.fromEntityToResp` |
| `getUserByOrgId` | 手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式 |
| `updateUserName` | 手动 `LambdaQueryWrapper` → `lambdaUpdate()` 链式 |

### 5.3 findByTreeCode bug 修复

原代码：
```java
for (OrgUserEntity orgUnit : userOrgUnitList) {
    OrgUserResp orgUserResp = new OrgUserResp();
    BeanUtils.copyProperties(orgUnit, orgUserResp);
    // ❌ 缺少 orgUserRespList.add(orgUserResp)
}
```

修复后（迁移至 Aggregate，使用 Converter）：
```java
return OrgUserConverter.INSTANCE.fromEntityToResp(userOrgUnitList);
```

---

## 六、OrgController 重构设计

### 6.1 移除注入

- 移除 `@Autowired IOrgService orgServicePlus`
- 保留 `OrgAggregate orgAggregate`、`OrgUserAggregate orgUserAggregate`

### 6.2 方法改造

| 方法 | 改造前 | 改造后 |
|------|--------|--------|
| `findAllChd` | Controller 内 `orgServicePlus.getById` + 设置 treeCode | 迁移至 `OrgAggregate.findAllChd`（内部处理 orgId→treeCode 转换） |
| `updateOrg` | Controller 内校验 + BeanUtils + updateById | `orgAggregate.updateOrg(orgEditReq)` |
| `deleteOrg` | Controller 内校验 + hasChildren + hasUser + removeById | `orgAggregate.deleteOrg(orgId)` |
| `getOrgUnitInfoById` | Controller 内 getById + Converter | `orgAggregate.getOrgById(orgId)` |
| `getOrgUnitListByIds` | Controller 内调用 Aggregate + Converter | `orgAggregate.getOrgUnitListByIds` 返回 `List<OrgResp>`（Aggregate 内转换） |
| `listOrgByTreeCodes` | Controller 内调用 Aggregate + Converter | 同上 |
| `getOrgListByOrgName` | Controller 内调用 Aggregate + Converter | 同上 |
| `getOrgUnitAndChildrenById` | Controller 内调用 Aggregate + Converter | 同上 |
| `findByOrgId` | Controller 内调用 Aggregate + Converter | 同上 |
| `findByOrgTypes` | Controller 内调用 Aggregate + Converter | 同上 |

> `findAllChd` 的 orgId→treeCode 查询逻辑迁移至 `OrgAggregate.findAllChd(OrgQuery)`，Aggregate 内部先 getById 获取 treeCode 再查询。

---

## 七、OrgUserController 重构设计

### 7.1 移除注入

- 移除 `@Autowired IOrgUserService orgUserServicePlus`
- 移除 `@Autowired IOrgService orgServicePlus`
- 移除私有方法 `parseOrgUnit`
- 保留 `OrgUserAggregate orgUserAggregate`

### 7.2 方法改造

| 方法 | 改造后 |
|------|--------|
| `findByAccount` | `orgUserAggregate.findOrgByAccount(account)` |
| `findChildren` | `orgUserAggregate.findChildren(orgId)` |
| `findRoot` | `orgUserAggregate.findRoot()` |
| `findByType` | `orgUserAggregate.findByType(orgType)` |
| `findByTreeCode` | `orgUserAggregate.findByTreeCode(treeCode)` |
| `listOrgUnitByUser` | `orgUserAggregate.listOrgUnitByUser(userOrgUnit.getAccount())`（校验逻辑保留在 Controller） |
| `addUserOrgUnit` | `orgUserAggregate.addUserOrgUnit(userOrgUnit)` |
| `updateUserOrgUnit` | `orgUserAggregate.updateUserOrgUnit(userOrgUnit)` |
| `saveAuthOrgByUser` | `orgUserAggregate.saveAuthOrgByUser(orgUserSaveReqList)`（直接传 req 列表） |
| `saveBelongOrgByUser` | 保持现有调用，但移除 Controller 内手动构建 entity 逻辑，改为传 `OrgUserSaveReq` |

> `saveBelongOrgByUser`：Controller 内手动构建 `OrgUserEntity` 的逻辑迁移至 Aggregate，Aggregate 方法签名改为接收 `OrgUserSaveReq`。

---

## 八、影响范围

| 文件 | 变更类型 |
|------|---------|
| `OrgConverter.java` | 新增 `componentModel`、`fromAddReqToEntity`、`fromEntityToTreeNode` |
| `OrgUserConverter.java` | 新增 `componentModel`、`fromSaveReqToEntity`、`fromRespToEntity` |
| `OrgAggregate.java` | 新增 3 个方法，改造 10+ 个方法，注入 `OrgUserAggregate` |
| `OrgUserAggregate.java` | 新增 8 个方法，改造 8 个方法，`saveAuthOrgByUser` 签名变更 |
| `OrgController.java` | 移除 `IOrgService` 注入，简化 5 个方法 |
| `OrgUserController.java` | 移除 `IOrgService`/`IOrgUserService` 注入，简化 9 个方法，移除 `parseOrgUnit` |

**不涉及变更**：Entity、Mapper、Service、XML、feign 模块、数据库表结构、API 路径/请求/响应结构。

---

## 九、关键设计决策

1. **`OrgAggregate` 返回类型统一**：`getOrgUnitListByIds`、`listOrgByTreeCodes`、`getOrgListByOrgName`、`getOrgUnitAndChildrenById`、`findByOrgTypes` 原来返回 `List<OrgEntity>`，Controller 再调用 Converter。重构后 Aggregate 直接返回 `List<OrgResp>`，Controller 无需再转换。

2. **`INSTANCE` 保留**：Converter 添加 `componentModel = "spring"` 的同时保留 `INSTANCE` 静态引用，Aggregate 统一使用 `INSTANCE` 调用，无需 `@Autowired` 注入 Converter。

3. **`listOrgUnitByUser` 账号校验位置**：账号非空校验（`StrUtil.isBlank`）保留在 Controller 层（属于参数校验），Aggregate 只负责查询逻辑。

4. **`saveBelongOrgByUser` 签名**：Controller 内手动构建 entity 的逻辑迁移至 Aggregate，Aggregate 方法改为接收 `OrgUserSaveReq`，内部用 Converter 转换并设置 `belongFlag = true`。

---

**状态**：草稿

# 组织模块代码重构 需求文档

> 编号：`0006` | 模块：`mdm` | 服务：`data-cloud-mdm` | 创建时间：2026-03-18

---

## 背景

组织模块（Org + OrgUser）现有代码存在多处严重违反公共宪法分层规范的问题：
- `OrgController` 和 `OrgUserController` 直接注入 Service 并在 Controller 层操作数据库
- 大量业务逻辑散落在 Controller 层，未经过 Aggregate 编排
- Aggregate 层大量使用手动 `LambdaQueryWrapper` 而非 `lambdaQuery()` 链式写法
- `OrgConverter`、`OrgUserConverter` 缺少 `componentModel = "spring"` 及必要转换方法
- `OrgAggregate.convertToMdmOrgUnitTreeNode` 手动逐字段赋值，应改用 Converter
- `OrgUserAggregate` 中手动构建响应对象，应改用 Converter
- `OrgUserController.findByTreeCode` 存在 bug：`BeanUtils.copyProperties` 后未将对象加入列表，导致永远返回空列表

本次重构目标：在**不改变任何 API 行为**的前提下，将所有业务逻辑归位到正确的层，消除 Controller 层直接操作数据库的问题，统一使用 Converter 和 `lambdaQuery()` 规范写法，并修复已知 bug。

---

## 目标用户

开发团队（内部代码质量改善，不影响前端/调用方）

---

## 功能描述

对组织模块以下文件进行代码规范重构，不新增功能，不修改 API 路径、请求/响应结构、数据库表结构：

- `OrgController.java` — 移除直接 Service 注入，业务逻辑迁移至 Aggregate
- `OrgUserController.java` — 移除直接 Service 注入，业务逻辑迁移至 Aggregate，修复 bug
- `OrgAggregate.java` — 手动 QueryWrapper 改为 `lambdaQuery()`，BeanUtils 改为 Converter
- `OrgUserAggregate.java` — 手动 QueryWrapper 改为 `lambdaQuery()`，手动构建响应改为 Converter
- `OrgConverter.java` — 添加 `componentModel = "spring"`，补充转换方法
- `OrgUserConverter.java` — 添加 `componentModel = "spring"`，补充转换方法

---

## 所属模块

- 服务：`data-cloud-mdm`（端口 `20002`）
- 模块：`data-cloud-mdm-web`
- 业务域：组织管理（Org + OrgUser）
- 涉及文件/目录：
  - `controller/org/OrgController.java`
  - `controller/org/OrgUserController.java`
  - `aggregate/OrgAggregate.java`
  - `aggregate/OrgUserAggregate.java`
  - `converter/OrgConverter.java`
  - `converter/OrgUserConverter.java`

---

## 核心业务规则

### 约束（不可变更）
1. **API 兼容性**：所有接口路径、HTTP 方法、请求参数结构、响应结构保持不变
2. **数据库兼容性**：表名 `p_mdm_org` / `p_mdm_org_user` 保持不变
3. **删除逻辑**：保持现有删除行为不变（`deleteOrg` 使用 `removeById`）
4. **feign 模块**：不在本次重构范围内

### 重构规则

| 问题 | 重构方式 |
|------|---------|
| Controller 直接注入 Service 操作数据库 | 移除 Controller 中的 Service 注入，相关逻辑迁移至对应 Aggregate |
| Controller 层手动构建 entity / 业务校验 | 迁移至 Aggregate |
| 手动 `LambdaQueryWrapper` | 替换为 `lambdaQuery()` / `lambdaUpdate()` 链式写法 |
| `BeanUtils.copy` / `BeanUtils.copyProperties` | 替换为 MapStruct Converter 方法 |
| `convertToMdmOrgUnitTreeNode` 手动赋值 | 替换为 `OrgConverter.fromEntityToTreeNode` |
| `selectBelongUserByOrg` stream 手动构建 | 替换为 `OrgUserConverter.fromEntityToResp` |
| `OrgConverter` / `OrgUserConverter` 缺少 `componentModel` | 添加 `componentModel = "spring"` |
| `findByTreeCode` bug（未 add 到列表） | 修复：补充 `orgUserRespList.add(orgUserResp)` |

### 迁移清单（Controller → Aggregate）

**OrgController → OrgAggregate：**
- `updateOrg`：校验组织存在 + BeanUtils.copy + updateById → 迁移为 `OrgAggregate.updateOrg(OrgEditReq)`
- `deleteOrg`：校验存在 + 校验子节点 + 校验用户 + removeById → 迁移为 `OrgAggregate.deleteOrg(String orgId)`
- `getOrgUnitInfoById`：getById + Converter → 迁移为 `OrgAggregate.getOrgById(String orgId)`

**OrgUserController → OrgUserAggregate：**
- `findByAccount`：查 OrgUser + 查 Org + BeanUtils → 迁移为 `OrgUserAggregate.findOrgByAccount(String account)`
- `findChildren`：lambdaQuery + BeanUtils → 迁移为 `OrgUserAggregate.findChildren(String orgId)`
- `findRoot`：lambdaQuery + BeanUtils → 迁移为 `OrgUserAggregate.findRoot()`
- `findByType`：lambdaQuery + BeanUtils → 迁移为 `OrgUserAggregate.findByType(String orgType)`
- `findByTreeCode`：查 Org + 查 OrgUser + BeanUtils（含 bug 修复）→ 迁移为 `OrgUserAggregate.findByTreeCode(String treeCode)`
- `listOrgUnitByUser`：校验 + lambdaQuery → 迁移为 `OrgUserAggregate.listOrgUnitByUser(String account)`
- `addUserOrgUnit`：BeanUtils + setId + save → 迁移为 `OrgUserAggregate.addUserOrgUnit(OrgUserResp req)`
- `updateUserOrgUnit`：BeanUtils + updateById → 迁移为 `OrgUserAggregate.updateUserOrgUnit(OrgUserResp req)`
- `saveAuthOrgByUser`：手动构建 entity 列表 → 迁移为 `OrgUserAggregate.saveAuthOrgByUser(List<OrgUserSaveReq>)`（原 Aggregate 方法接收 entity 列表，改为接收 req 列表）

---

## 输入参数

> 本次为重构，不新增接口，输入参数结构保持不变。

---

## 输出结果

> 保持不变，所有接口响应结构不变。

---

## 用户故事

- 作为开发者，我希望组织模块代码符合分层规范，Controller 不直接操作数据库，以便后续维护
- 作为开发者，我希望修复 `findByTreeCode` 的 bug，以便该接口能正确返回数据

---

## 验收标准

- [ ] `OrgController` 中不再直接注入 `IOrgService`，所有数据库操作通过 Aggregate
- [ ] `OrgUserController` 中不再直接注入 `IOrgService` / `IOrgUserService`，所有数据库操作通过 Aggregate
- [ ] `OrgAggregate` 中所有手动 `LambdaQueryWrapper` 替换为 `lambdaQuery()` 链式写法
- [ ] `OrgUserAggregate` 中所有手动 `LambdaQueryWrapper` 替换为 `lambdaQuery()` 链式写法
- [ ] `OrgAggregate.convertToMdmOrgUnitTreeNode` 替换为 Converter 方法
- [ ] `OrgUserAggregate.selectBelongUserByOrg` stream 手动构建替换为 Converter
- [ ] `OrgConverter` 添加 `componentModel = "spring"`，补充 `fromAddReqToEntity`、`fromEntityToTreeNode` 方法
- [ ] `OrgUserConverter` 添加 `componentModel = "spring"`，补充 `fromSaveReqToEntity`、`fromRespToEntity` 方法
- [ ] `findByTreeCode` bug 修复：`orgUserRespList.add(orgUserResp)` 补充
- [ ] 所有现有接口行为（路径、请求结构、响应结构）保持不变
- [ ] 编译通过，无新增警告

---

## 边界条件

| 场景 | 处理方式 |
|------|---------|
| `OrgUserController.saveAuthOrgByUser` 迁移后 | Aggregate 方法签名改为接收 `List<OrgUserSaveReq>`，内部构建 entity，Controller 直接传 req 列表 |
| `OrgConverter` 改为 Spring 注入后 | 保留 `INSTANCE` 静态引用，Aggregate 统一使用 `INSTANCE` 调用 |
| `OrgEntity` 主键为 `orgId`（非标准 `id`） | Converter 映射时注意 `@TableId` 字段为 `orgId`，`fromAddReqToEntity` 不映射 `id` 字段 |

---

## 非功能需求

- **可维护性**：重构后代码必须符合公共宪法第五、七、九、十条规范
- **安全性**：不引入任何行为变更，不影响现有数据

---

**状态**：草稿

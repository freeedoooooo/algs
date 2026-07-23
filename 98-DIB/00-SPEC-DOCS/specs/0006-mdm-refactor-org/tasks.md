# 组织模块代码重构 任务清单

> 编号：`0006` | 模块：`mdm` | 服务：`data-cloud-mdm` | 创建时间：2026-03-18

---

## 任务列表

- [x] 1. 重构 OrgConverter
  - [x] 1.1 添加 `componentModel = "spring"`
  - [x] 1.2 新增 `fromAddReqToEntity(OrgAddReq req)` 方法
  - [x] 1.3 新增 `fromEntityToTreeNode(OrgEntity entity)` 方法
  - [x] 1.4 新增 `fromEntityToTreeNode(List<OrgEntity> entityList)` 方法

- [x] 2. 重构 OrgUserConverter
  - [x] 2.1 添加 `componentModel = "spring"`
  - [x] 2.2 新增 `fromSaveReqToEntity(OrgUserSaveReq req)` 方法
  - [x] 2.3 新增 `fromRespToEntity(OrgUserResp resp)` 方法

- [x] 3. 重构 OrgAggregate（新增方法 + 改造现有方法）
  - [x] 3.1 注入 `OrgUserAggregate`
  - [x] 3.2 新增 `updateOrg(OrgEditReq req)`：校验存在 + Converter 转换 + updateById
  - [x] 3.3 新增 `deleteOrg(String orgId)`：校验存在 + hasChildren + hasUser + removeById
  - [x] 3.4 新增 `getOrgById(String orgId)`：getById + Converter 返回 `OrgResp`
  - [x] 3.5 `addOrg`：`BeanUtils.copy` 替换为 `OrgConverter.INSTANCE.fromAddReqToEntity`
  - [x] 3.6 `findDirChd`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式
  - [x] 3.7 `findAllChd`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；内部增加 orgId→treeCode 查询逻辑（从 Controller 迁移）
  - [x] 3.8 `hasChildren`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式
  - [x] 3.9 `selectMaxTreeCode`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式
  - [x] 3.10 `getOrgListByOrgName`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；返回类型改为 `List<OrgResp>`
  - [x] 3.11 `getOrgUnitAndChildrenById`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；返回类型改为 `List<OrgResp>`
  - [x] 3.12 `getOrgUnitListByIds`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；返回类型改为 `List<OrgResp>`
  - [x] 3.13 `listOrgByTreeCodes`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；返回类型改为 `List<OrgResp>`
  - [x] 3.14 `findByOrgTypes`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；返回类型改为 `List<OrgResp>`
  - [x] 3.15 `getAllEnableOrgNode`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；`stream().map(convertToMdmOrgUnitTreeNode)` → `OrgConverter.INSTANCE.fromEntityToTreeNode`
  - [x] 3.16 删除 `convertToMdmOrgUnitTreeNode` 私有方法

- [x] 4. 重构 OrgUserAggregate（新增方法 + 改造现有方法）
  - [x] 4.1 新增 `findOrgByAccount(String account)`：查 OrgUser + 查 Org + OrgConverter 返回 `OrgResp`
  - [x] 4.2 新增 `findChildren(String orgId)`：lambdaQuery + OrgConverter 返回 `List<OrgResp>`
  - [x] 4.3 新增 `findRoot()`：lambdaQuery + OrgConverter 返回 `List<OrgResp>`
  - [x] 4.4 新增 `findByType(String orgType)`：lambdaQuery + OrgConverter 返回 `List<OrgResp>`
  - [x] 4.5 新增 `findByTreeCode(String treeCode)`：查 Org + 查 OrgUser + OrgUserConverter（含 bug 修复）返回 `List<OrgUserResp>`
  - [x] 4.6 新增 `listOrgUnitByUser(String account)`：lambdaQuery + OrgUserConverter 返回 `List<OrgUserResp>`
  - [x] 4.7 新增 `addUserOrgUnit(OrgUserResp req)`：OrgUserConverter + setId + save
  - [x] 4.8 新增 `updateUserOrgUnit(OrgUserResp req)`：OrgUserConverter + updateById
  - [x] 4.9 `saveAuthOrgByUser`：签名改为接收 `List<OrgUserSaveReq>`，内部用 OrgUserConverter 构建 entity 并设置 id
  - [x] 4.10 `saveBelongOrgByUser`：签名改为接收 `OrgUserSaveReq`，内部用 OrgUserConverter 构建 entity 并设置 `belongFlag = true`
  - [x] 4.11 `selectBelongOrgByUser`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式
  - [x] 4.12 `selectAuthOrgByUser`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式
  - [x] 4.13 `hasUser`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式
  - [x] 4.14 `selectBelongUserByOrg`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式；stream 手动构建 → `OrgUserConverter.INSTANCE.fromEntityToResp`
  - [x] 4.15 `getUserByOrgId`：手动 `LambdaQueryWrapper` → `lambdaQuery()` 链式
  - [x] 4.16 `updateUserName`：手动 `LambdaQueryWrapper` → `lambdaUpdate()` 链式

- [x] 5. 重构 OrgController
  - [x] 5.1 移除 `IOrgService orgServicePlus` 注入及相关 import
  - [x] 5.2 `findAllChd`：移除内部 getById 逻辑，直接调用 `orgAggregate.findAllChd(orgQuery)`
  - [x] 5.3 `updateOrg`：替换为 `orgAggregate.updateOrg(orgEditReq)`
  - [x] 5.4 `deleteOrg`：替换为 `orgAggregate.deleteOrg(orgId)`
  - [x] 5.5 `getOrgUnitInfoById`：替换为 `orgAggregate.getOrgById(orgId)`
  - [x] 5.6 `getOrgUnitListByIds`、`listOrgByTreeCodes`、`getOrgListByOrgName`、`getOrgUnitAndChildrenById`、`findByOrgId`、`findByOrgTypes`：移除 Controller 内 Converter 调用（Aggregate 已直接返回 Resp）

- [x] 6. 重构 OrgUserController
  - [x] 6.1 移除 `IOrgUserService orgUserServicePlus`、`IOrgService orgServicePlus` 注入及相关 import
  - [x] 6.2 移除私有方法 `parseOrgUnit`
  - [x] 6.3 `findByAccount`：替换为 `orgUserAggregate.findOrgByAccount(account)`
  - [x] 6.4 `findChildren`：替换为 `orgUserAggregate.findChildren(orgId)`
  - [x] 6.5 `findRoot`：替换为 `orgUserAggregate.findRoot()`
  - [x] 6.6 `findByType`：替换为 `orgUserAggregate.findByType(orgType)`
  - [x] 6.7 `findByTreeCode`：替换为 `orgUserAggregate.findByTreeCode(treeCode)`
  - [x] 6.8 `listOrgUnitByUser`：保留账号非空校验，查询逻辑替换为 `orgUserAggregate.listOrgUnitByUser(account)`
  - [x] 6.9 `addUserOrgUnit`：替换为 `orgUserAggregate.addUserOrgUnit(userOrgUnit)`
  - [x] 6.10 `updateUserOrgUnit`：替换为 `orgUserAggregate.updateUserOrgUnit(userOrgUnit)`
  - [x] 6.11 `saveAuthOrgByUser`：移除手动构建 entity 逻辑，直接调用 `orgUserAggregate.saveAuthOrgByUser(orgUserSaveReqList)`
  - [x] 6.12 `saveBelongOrgByUser`：移除手动构建 entity 逻辑，直接调用 `orgUserAggregate.saveBelongOrgByUser(orgUserSaveReq)`

- [x] 7. 编译验证
  - [x] 7.1 运行 getDiagnostics 检查所有修改文件，确认无编译错误

---

## 验收对照

| 验收标准 | 对应任务 |
|---------|---------|
| OrgController 不再注入 IOrgService | 5.1 |
| OrgUserController 不再注入 IOrgService / IOrgUserService | 6.1 |
| OrgAggregate 所有手动 QueryWrapper 替换为 lambdaQuery() | 3.6~3.15 |
| OrgUserAggregate 所有手动 QueryWrapper 替换为 lambdaQuery() | 4.11~4.16 |
| convertToMdmOrgUnitTreeNode 替换为 Converter | 3.15、3.16 |
| selectBelongUserByOrg stream 手动构建替换为 Converter | 4.14 |
| OrgConverter 添加 componentModel + 新方法 | 1.1~1.4 |
| OrgUserConverter 添加 componentModel + 新方法 | 2.1~2.3 |
| findByTreeCode bug 修复 | 4.5 |
| 所有接口行为不变 | 全部 |
| 编译通过无新增警告 | 7.1 |

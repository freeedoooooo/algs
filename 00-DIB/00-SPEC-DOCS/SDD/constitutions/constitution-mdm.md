# Data Cloud MDM 项目宪法

> 本文档是 data-cloud-mdm（主数据管理服务）的开发规范。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录专属规范。

---

## 一、项目概述

data-cloud-mdm 是 DIB 平台的主数据管理服务，负责组织架构、项目管理、数据字典、附件存储等基础主数据的管理，是平台其他服务的数据基础。

### 项目结构
- **data-cloud-mdm-core**: 核心模块
- **data-cloud-mdm-web**: Web 服务模块（主要实现）
- **data-cloud-mdm-feign**: Feign 客户端模块（SDK）

### 端口号
- **20002** - 主数据服务端口（固定，禁止修改）

### context-path
- `/api/mdm`

---

## 二、技术栈（专属部分）

在公共技术栈基础上，mdm 服务额外使用：

- **文件存储**: 本地存储 / MinIO / FTP（通过配置切换）
- **文件上传**: 支持大文件（最大 300MB，`spring.servlet.multipart.max-file-size`）
- **文件加密**: 可选（`dib.file.enable-encrypt`，默认 false）

---

## 三、包结构规范

### 基础包路径
```
com.dib.data.cloud.mdm
```

### 标准包结构
```
com.dib.data.cloud.mdm/
├── aggregate/
│   ├── OrgAggregate                # 组织管理（树形结构）
│   ├── OrgUserAggregate            # 组织用户关系
│   ├── ProjectAggregate            # 项目管理
│   ├── ProjectDirAggregate         # 项目目录（树形）
│   ├── ProjectExtValueAggregate    # 项目扩展属性
│   ├── ProjectExtWarehouseAggregate
│   ├── DictDefAggregate            # 字典定义
│   ├── DictItemAggregate           # 字典项
│   ├── AttachmentRecordAggregate   # 附件记录
│   └── AttachmentStorageAggregate  # 附件存储
├── config/
│   ├── constant/
│   └── enums/
├── controller/
├── converter/
├── entity/
│   ├── OrgEntity                   # 组织表
│   ├── ProjectEntity               # 项目表
│   ├── DictDefEntity               # 字典定义表
│   ├── DictItemEntity              # 字典项表
│   ├── AttachmentEntity            # 附件表
│   └── ProjectExtValueEntity       # 项目扩展值表
├── mapper/
├── model/
│   ├── req/
│   └── resp/
├── service/
└── util/
```

---

## 四、业务域规范

### 核心业务域

| 业务域 | 说明 | 特点 |
|--------|------|------|
| 组织管理 | 组织架构树形结构 | 树形，支持多级 |
| 项目管理 | 项目及目录管理 | 树形目录，扩展属性 |
| 字典管理 | 数据字典定义和字典项 | 两级结构（定义+项） |
| 附件管理 | 文件上传、下载、存储 | 支持多种存储后端 |

### 表命名前缀
- 组织相关：`mdm_org_`
- 项目相关：`mdm_project_`
- 字典相关：`mdm_dict_`
- 附件相关：`mdm_attachment_`

---

## 五、树形结构规范

组织和项目目录均为树形结构，遵循以下规范：

- 树形节点必须包含 `parentId` 字段（根节点 `parentId = 0` 或 `null`）
- 查询树形数据使用递归或 CTE，禁止在 Java 层循环查询
- 删除节点前必须校验是否有子节点，有子节点时禁止删除
- 移动节点时必须校验不能移动到自身的子节点下（防止循环）
- 树形查询接口返回 `List<TreeNode>` 结构，包含 `children` 字段

```java
// 树形节点响应示例
public class OrgTreeResp {
    private Long id;
    private String orgName;
    private Long parentId;
    private List<OrgTreeResp> children;
}
```

---

## 六、字典管理规范

- 字典定义（DictDef）和字典项（DictItem）是两级结构
- 字典项通过 `dictCode` 关联字典定义
- 字典项有 `sortOrder` 字段，查询时按 `sortOrder` 升序排列
- 禁用字典定义时，其下所有字典项同步禁用
- 字典数据变更后，通知依赖方（通过 Feign 或事件）

---

## 七、附件管理规范

### 存储后端配置
通过配置文件切换存储方式：
```yaml
dib.file.enable-encrypt: false   # 是否加密
dib.file.minio.enable: false     # 是否使用 MinIO
dib.file.ftp.enable: false       # 是否使用 FTP
# 均为 false 时使用本地存储
```

### 文件操作规范
- 文件上传接口必须校验文件类型和大小
- 文件下载必须校验权限（文件归属）
- 支持 ZIP 打包下载多个附件
- 删除附件时同步删除物理文件（逻辑删除记录 + 物理删除文件）
- 大文件上传（>10MB）建议使用分片上传

### 文件大小限制
- 单文件最大 300MB（`spring.servlet.multipart.max-file-size: 300MB`）
- 超出限制时返回明确的错误信息

---

## 八、扩展属性规范

项目支持扩展属性（ProjectExtValue），用于存储动态字段：

- 扩展属性定义在 `ProjectExtWarehouse` 中
- 扩展属性值存储在 `ProjectExtValue` 中（EAV 模式）
- 查询项目时，扩展属性随主数据一起返回
- 扩展属性的增删改必须在事务中执行

---

## 九、AI 特别约束（专属）

- 修改树形结构相关逻辑时，必须确认循环引用检测
- 新增附件相关接口时，必须确认存储后端配置的兼容性
- 字典数据变更时，确认是否需要通知下游服务
- 扩展属性操作必须在事务中执行
- 文件操作必须有异常处理，避免物理文件和数据库记录不一致

---

**本宪法最终解释权归 DIB 项目团队所有。**

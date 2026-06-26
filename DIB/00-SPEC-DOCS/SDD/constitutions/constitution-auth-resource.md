# Data Cloud Auth Resource 项目宪法

> 本文档是 data-cloud-auth-resource（权限资源管理服务）的开发规范。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录专属规范。

---

## 一、项目概述

data-cloud-auth-resource 是 DIB 平台的权限资源管理服务，负责用户、角色、模块、接口权限、密级配置等核心权限数据的管理。

### 项目结构
- **data-cloud-auth-resource-core**: 核心模块
- **data-cloud-auth-resource-web**: Web 服务模块（主要实现）
- **data-cloud-auth-resource-feign**: Feign 客户端模块（SDK）

### 端口号
- **20001** - 权限资源服务端口（固定，禁止修改）

### context-path
- `/api/auth`

---

## 二、技术栈（专属部分）

在公共技术栈基础上，auth-resource 服务额外使用：

- **缓存**: Redis（权限数据缓存，通过 `dib.cache` 配置）
- **三员管理**: sysadmin（系统管理员）、safeadmin（安全管理员）、auditadmin（审计管理员）
- **超级管理员**: admin

---

## 三、包结构规范

### 基础包路径
```
com.dib.data.cloud.auth.resource
```

### 标准包结构
```
com.dib.data.cloud.auth.resource/
├── aggregate/
│   ├── UserInfoAggregate       # 用户业务编排
│   ├── RoleAggregate           # 角色业务编排
│   ├── UrlAggregate            # 接口权限业务编排
│   └── ...
├── config/
│   ├── constant/
│   └── enums/
├── controller/
│   ├── UserInfoController      # 用户管理
│   ├── RoleController          # 角色管理
│   ├── ModuleController        # 模块管理
│   ├── UrlController           # 接口权限管理
│   ├── CustomerController      # 客户管理
│   ├── PasswordStrategyController
│   ├── SecurityLevelConfigController
│   ├── UserPasswordController
│   ├── UserLoginInfoController
│   ├── UserLoginLogController
│   ├── UserSessionController
│   ├── UserIpLimitController
│   └── UserUnlockApplyController
├── converter/
├── entity/
│   ├── UserEntity              # 表：p_auth_user
│   ├── RoleEntity
│   ├── ModuleEntity
│   ├── UrlEntity
│   ├── CustomerEntity
│   ├── PasswordStrategyEntity
│   └── SecurityLevelConfigEntity
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

| 业务域 | 说明 | 主要实体 |
|--------|------|---------|
| 用户管理 | 用户 CRUD、角色分配、密码管理 | UserEntity |
| 角色管理 | 角色 CRUD、权限分配 | RoleEntity |
| 模块管理 | 系统模块树形结构 | ModuleEntity |
| 接口权限 | URL 级别权限控制 | UrlEntity |
| 客户管理 | 多客户隔离 | CustomerEntity |
| 密码策略 | 密码复杂度、有效期、历史记录 | PasswordStrategyEntity |
| 密级配置 | 用户密级、表单密级管理 | SecurityLevelConfigEntity |
| 登录管理 | 登录日志、会话管理、IP 限制 | - |
| 解锁申请 | 用户锁定后的解锁流程 | UserUnlockApplyEntity |

### 表命名前缀
- 权限相关表统一使用 `p_auth_` 前缀

---

## 五、权限缓存规范

- 权限数据通过 Redis 缓存，配置项 `dib.cache: redis`
- 修改用户权限、角色权限后，必须同步清除相关缓存
- 缓存 key 命名规范：`auth:{业务域}:{标识}`
- 禁止在循环中频繁读写缓存

---

## 六、多客户隔离规范

- 系统支持多客户（Customer）隔离
- 查询时必须带入 `customerId` 条件（除超级管理员外）
- 新增数据时必须关联 `customerId`
- 禁止跨客户查询数据

---

## 七、三员管理规范

系统内置三类特殊管理员角色，权限互相制约：

| 角色 | 账号 | 职责 |
|------|------|------|
| 系统管理员 | sysadmin | 用户和角色管理 |
| 安全管理员 | safeadmin | 安全策略配置 |
| 审计管理员 | auditadmin | 日志审计查询 |

- 三员账号禁止被普通接口删除或修改角色
- 超级管理员（admin）可管理三员

---

## 八、密码策略规范

- 密码修改必须校验密码策略（复杂度、长度、历史记录）
- 密码错误超过阈值后自动锁定账号
- 密码历史记录不得重复使用（策略配置的历史条数内）
- 密码存储必须加密，禁止明文

---

## 九、AI 特别约束（专属）

- 修改用户权限相关逻辑时，必须确认缓存清除逻辑
- 新增接口时，确认是否需要在 UrlEntity 中注册权限
- 涉及三员账号的逻辑，必须有特殊保护判断
- 多客户隔离查询条件不得遗漏

---

**本宪法最终解释权归 DIB 项目团队所有。**

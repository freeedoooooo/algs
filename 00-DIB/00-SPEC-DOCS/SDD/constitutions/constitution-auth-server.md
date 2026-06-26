# Data Cloud Auth Server 项目宪法

> 本文档是 data-cloud-auth-server（OAuth2 认证服务器）的开发规范。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录专属规范。

---

## 一、项目概述

data-cloud-auth-server 是 DIB 平台的统一认证服务，基于 Spring Security OAuth2 实现，负责用户登录认证、令牌签发与验证、密码策略执行、登录日志审计等功能。

### 项目结构
- 单模块项目（无子模块）

### 端口号
- **9090** - 认证服务端口（固定，禁止修改）

### context-path
- 无（根路径）

---

## 二、技术栈（专属部分）

在公共技术栈基础上，auth-server 额外使用：

- **认证框架**: Spring Security OAuth2
- **令牌存储**: Redis（JWT + Redis 双重存储）
- **数据库**: 支持 MySQL 8.0 和 DM8（达梦数据库）
- **密钥**: JKS 格式密钥库（`datacloud.jks`、`dibKey.keystore`）

---

## 三、包结构规范

### 基础包路径
```
com.dib.data.cloud.auth.server
```

### 标准包结构
```
com.dib.data.cloud.auth.server/
├── aggregate/
│   ├── UserAggregate                       # 用户认证业务编排
│   ├── OauthAggregate                      # OAuth2 流程编排
│   ├── PasswordStrategyAggregate           # 密码策略验证
│   ├── LoginLogAggregate                   # 登录日志记录
│   └── SecurityLevelConfigAggregate        # 密级配置
├── component/
│   └── CustomerAuthenticationFailureHandler  # 认证失败处理器
├── config/
│   ├── AuthorizationServerConfig           # OAuth2 授权服务器配置
│   ├── SecurityConfig                      # Spring Security 配置
│   └── constant/
├── controller/
├── converter/
├── entity/
├── mapper/
├── model/
├── service/
└── util/
```

---

## 四、OAuth2 规范

### 令牌端点
- 授权端点：`/oauth/authorize`
- 令牌端点：`/oauth/token`
- 令牌校验：`/oauth/check_token`
- 令牌刷新：通过 `/oauth/token` 使用 refresh_token

### 令牌配置
- 访问令牌有效期：通过配置文件管理，禁止硬编码
- 刷新令牌有效期：通过配置文件管理
- 令牌签名：使用 JKS 密钥库，禁止使用对称密钥

### 客户端配置
- 客户端信息存储在数据库中，禁止硬编码在代码里
- 新增客户端通过数据库脚本添加，不通过代码

---

## 五、认证流程规范

```
用户提交凭证
    ↓
密码策略校验（复杂度、有效期）
    ↓
用户状态校验（是否锁定、是否启用）
    ↓
认证成功 → 记录登录日志 → 签发令牌
    ↓
认证失败 → 记录失败日志 → 累计失败次数 → 超阈值则锁定账号
```

### 密码锁定规范
- 锁定时间通过配置 `dib.pwd.lock-time` 控制（单位：分钟）
- 锁定状态存储在 Redis 中，支持自动解锁
- 锁定期间的登录尝试必须记录日志

---

## 六、登录日志规范

- 每次登录（成功/失败）必须记录日志
- 日志字段：用户名、IP、时间、结果、失败原因
- 禁止在日志中记录密码明文
- 日志查询接口需要审计管理员权限

---

## 七、数据库兼容规范

auth-server 需同时支持 MySQL 和 DM8（达梦数据库）：

- SQL 语句禁止使用 MySQL 专有函数（如 `GROUP_CONCAT`、`IFNULL` 等）
- 使用 MyBatis-Plus 的数据库类型配置切换
- 新增 SQL 时必须在两种数据库下验证
- 日期函数使用 `DATE_FORMAT` 的替代写法或在 Java 层处理

---

## 八、安全规范

- 密钥文件（`.jks`、`.keystore`）禁止提交到代码仓库（已在 .gitignore 中）
- 敏感配置（数据库密码、Redis 密码）通过环境变量注入
- 令牌中禁止包含敏感用户信息（密码、密钥等）
- HTTPS 配置通过 `dib.auth.isHttps` 控制

---

## 九、AI 特别约束（专属）

- 修改认证流程时，必须确认登录日志记录逻辑完整
- 修改密码策略时，必须同步更新 auth-resource 侧的策略配置
- 禁止修改令牌端点路径（`/oauth/*`）
- 涉及密钥操作的代码，修改前必须说明影响范围
- 新增 SQL 时必须考虑 MySQL 和 DM8 的兼容性

---

**本宪法最终解释权归 DIB 项目团队所有。**

# DIB Agent Parent 项目宪法

> 本文档是 dib-agent-parent（父 POM 和基础设施）的开发规范。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录专属规范。

---

## 一、项目概述

dib-agent-parent 是 DIB Agent 微服务体系的父 POM 项目，负责统一管理所有子服务的依赖版本、构建配置和公共基础库。所有 DIB Agent 微服务均以此为父 POM。

### 项目结构（子模块）

| 模块 | 说明 |
|------|------|
| `data-cloud-dependencies` | 依赖版本 BOM 管理 |
| `data-cloud-ai-starter` | AI 集成 Starter |
| `data-cloud-cache-starter` | 缓存框架 Starter（Redis） |
| `data-cloud-datasource-starter` | 多数据源管理 Starter |
| `data-cloud-utils` | 公共工具库 |
| `data-cloud-job-starter` | 定时任务 Starter |
| `data-cloud-web` | Web 基础模块（BaseEntity、GeneralResult 等） |
| `data-cloud-web-starter` | Web 启动器（统一异常处理、响应封装） |
| `data-cloud-office` | Office 文档处理（Word、Excel） |
| `data-cloud-file-starter` | 文件管理 Starter（本地/MinIO/FTP） |
| `dib-agent-check-starter` | 数据 Starter |
| `dib-agent-data-starter` | 数据处理 Starter |
| `dib-agent-data-web-starter` | 数据 Web Starter |
| `dib-agent-standardization-starter` | 数据标准化 Starter |
| `dib-agent-task-starter` | 任务管理 Starter |
| `dib-agent-converter-starter` | 文件格式转换（word、excel、pdf、ppt转换为txt） Starter |
| `d2-dgb-extract-core` | 数据提取核心库 |
| `dib-agent-sample` | 示例项目（参考用） |

---

## 二、版本管理规范

### 核心依赖版本（通过 data-cloud-dependencies 管理）

| 依赖 | 版本 |
|------|------|
| Spring Boot | 2.5.15 |
| Spring Cloud | 2020.0.x |
| MyBatis-Plus | 3.x |
| MapStruct | 1.5.2 |
| Lombok | 1.18.26 |
| Knife4j | 最新兼容版 |
| Druid | 最新兼容版 |
| Hutool | 最新兼容版 |

### 版本变更规范
- **所有依赖版本必须在 `data-cloud-dependencies` 的 `dependencyManagement` 中统一声明**
- 子模块禁止自行声明依赖版本号（直接引用父 BOM 中的版本）
- 升级依赖版本必须在 `data-cloud-dependencies` 中修改，并通知所有子服务验证
- 禁止在子模块中使用 `<version>` 标签覆盖父 BOM 版本（紧急情况除外，需注释说明原因）

---

## 三、父 POM 版本号规范

- 父 POM 版本格式：`{主版本}.{次版本}.{修订版本}-SNAPSHOT`（开发中）或 `{主版本}.{次版本}.{修订版本}`（发布版）
- 当前版本：`2.7.1-SNAPSHOT`
- 子服务引用父 POM 时，版本号必须与父 POM 保持一致

---

## 四、公共基础类规范

以下基础类由 `data-cloud-web` 模块提供，所有服务必须使用，禁止自行实现：

### BaseEntity
所有业务实体必须继承 `BaseEntity`，包含：
```java
Long id;                // 主键
Boolean delFlag;        // 删除标识（逻辑删除）
String addUserId;       // 创建人账号
String addUserName;     // 创建人姓名
Date addTime;           // 创建时间
String updateUserId;    // 更新人账号
String updateUserName;  // 更新人姓名
Date updateTime;        // 更新时间
```

### GeneralResult
所有 API 响应必须使用 `GeneralResult<T>` 包装：
```java
GeneralResult.success(data);       // 成功
GeneralResult.fail("错误信息");    // 失败
```

### PageResp
分页响应使用 `PageResp<T>`：
```java
PageResp.of(total, records);
```

### BizValidateException
业务异常统一使用：
```java
throw BizValidateException.of("错误信息");
```

---

## 五、Starter 使用规范

### data-cloud-cache-starter
- 引入后自动配置 Redis 连接
- 使用 `@Cacheable`、`@CacheEvict` 等注解时，key 命名规范：`{服务名}:{业务域}:{标识}`

### data-cloud-datasource-starter
- 多数据源场景使用此 Starter
- 数据源切换通过 `@DS("数据源名称")` 注解

### data-cloud-file-starter
- 文件操作统一通过此 Starter 提供的接口
- 存储后端（本地/MinIO/FTP）通过配置切换，业务代码无需感知

### dib-agent-task-starter
- 异步任务和定时任务通过此 Starter 管理
- 任务状态持久化由 Starter 负责

---

## 六、新增子模块规范

在 dib-agent-parent 下新增子模块时：

1. 在父 `pom.xml` 的 `<modules>` 中注册新模块
2. 子模块 `pom.xml` 的 `<parent>` 指向 `dib-agent-parent`
3. 依赖版本在 `data-cloud-dependencies` 中声明
4. 新模块必须有 `README.md` 说明用途和使用方式
5. 公共工具类优先放入 `data-cloud-utils`，避免重复实现

---

## 七、AI 特别约束（专属）

- 修改父 POM 依赖版本前，必须评估对所有子服务的影响
- 禁止在子模块中覆盖父 BOM 的依赖版本（除非有充分理由并注释说明）
- 新增公共基础类时，放入对应的 Starter 模块，不要放在业务服务中
- 修改 `BaseEntity`、`GeneralResult` 等基础类时，必须评估全量影响
- `dib-agent-sample` 仅作参考，禁止在生产代码中引用

---

**本宪法最终解释权归 DIB 项目团队所有。**

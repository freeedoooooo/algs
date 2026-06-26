# Data Cloud Gateway 项目宪法

> 本文档是 data-cloud-gateway（API 网关）的开发规范。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录专属规范。

---

## 一、项目概述

data-cloud-gateway 是 DIB 平台的统一 API 网关，基于 Spring Cloud Gateway 实现，负责请求路由、统一认证、限流、Swagger 文档聚合等功能。

### 项目结构
- 单模块项目（无子模块）

### 端口号
- **20000** - 网关端口（固定，禁止修改）

### context-path
- 无（根路径，路由转发到各下游服务）

---

## 二、技术栈（专属部分）

在公共技术栈基础上，gateway 额外使用：

- **框架**: Spring Cloud Gateway（WebFlux，非阻塞响应式）
- **服务发现**: Nacos
- **负载均衡**: Spring Cloud LoadBalancer（`CustomBlockingLoadBalancerClient`）
- **认证**: JWT 令牌验证（对接 auth-server）
- **文档聚合**: Knife4j Gateway 聚合（`SwaggerProvider`）

> ⚠️ Gateway 使用 WebFlux，禁止引入任何 Spring MVC 依赖，禁止使用阻塞 API（如 `RestTemplate`）。

---

## 三、包结构规范

### 基础包路径
```
com.dib.data.cloud.gateway
```

### 标准包结构
```
com.dib.data.cloud.gateway/
├── authorization/
│   ├── AbstractAuthorization       # 认证抽象基类
│   └── DibAuthorization            # DIB 认证实现
├── config/
│   ├── SwaggerConfig               # Swagger 聚合配置
│   ├── GatewayConfig               # 网关配置
│   └── constant/
├── filter/                         # 全局过滤器
├── handler/                        # 异常处理器
├── loadbalancer/
│   └── CustomBlockingLoadBalancerClient
└── swagger/
    └── SwaggerProvider             # Swagger 文档提供者
```

---

## 四、路由配置规范

### 当前路由表

| 路由 ID | 目标服务 | 路径前缀 |
|---------|---------|---------|
| `auth-resource` | `lb://auth-resource` | `/api/auth/**` |
| `mdm` | `lb://mdm` | `/api/mdm/**` |
| `service-extract` | `lb://service-extract` | `/api/extract/**` |
| `service-report` | `lb://service-report` | `/api/report/**` |
| `service-data` | `lb://service-data` | `/api/data/**` |
| `service-rule` | `lb://service-rule` | `/api/rule/**` |
| `service-data-dg` | `lb://service-data-dg` | `/api/dg/**` |

### 路由变更规范
- 新增服务路由必须在 `application.yml` 中配置，禁止硬编码
- 路由 ID 与服务名保持一致
- 新增路由后必须同步更新 `SwaggerProvider` 的文档聚合列表

---

## 五、认证过滤规范

### 认证方式
网关支持三种认证方式，通过 `dib.oauth.filter` 配置：
- `token` - Bearer Token（Authorization Header）
- `session` - Session 认证
- `cookie` - Cookie 认证

### 白名单配置
- 不需要认证的路径在配置文件中维护白名单
- 白名单路径变更必须经过安全评审
- 禁止在代码中硬编码白名单路径

### 认证失败处理
- 认证失败统一返回 401，响应格式与业务接口保持一致
- 禁止在认证失败时暴露内部错误信息

---

## 六、WebFlux 编码规范

由于 Gateway 基于 WebFlux，编码规范与普通 Spring MVC 服务不同：

- 使用 `Mono<T>` / `Flux<T>` 处理异步响应
- 禁止使用 `RestTemplate`，使用 `WebClient`
- 禁止使用阻塞操作（`Thread.sleep`、同步 IO 等）
- 过滤器实现 `GlobalFilter` 接口，不使用 `HandlerInterceptor`
- 异常处理实现 `ErrorWebExceptionHandler`，不使用 `@ControllerAdvice`

---

## 七、Swagger 聚合规范

- 每个下游服务的 Swagger 文档通过 `SwaggerProvider` 聚合到网关
- 新增服务时，必须在 `SwaggerProvider` 中注册文档路径
- 文档路径格式：`/{服务路径前缀}/v2/api-docs`

---

## 八、AI 特别约束（专属）

- Gateway 无数据库操作，禁止引入 MyBatis-Plus 相关依赖
- 修改认证逻辑时，必须确认白名单配置完整
- 新增路由时，必须同步更新 Swagger 聚合配置
- 所有代码必须使用响应式风格，禁止阻塞调用
- 禁止在 Gateway 层实现业务逻辑，业务逻辑下沉到各服务

---

**本宪法最终解释权归 DIB 项目团队所有。**

# 框架准备-可视化 设计文档

> 编号：`0010` | 模块：`rule` | 服务：`dib-agent-service-rule` | 创建时间：`2026-04-14`

---

## 一、整体设计思路

本功能在 `dib-agent-service-rule` 服务的 `frame` 业务域下，新增一套独立的"可视化配置"能力。

核心设计原则：
- **与计算解耦**：不触碰现有框架计算链路，仅新增配置表和配置接口
- **遵循现有分层**：Controller → Aggregate → Service → Mapper，与现有 frame 模块保持一致

---

## 二、数据库设计

### 2.1 可视化配置主表：`com_frame_visualization`

```sql
CREATE TABLE `com_frame_visualization` (
  `id`                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  `frame_id`          BIGINT       NOT NULL                COMMENT '绑定的已发布框架ID',
  `stat_level`        VARCHAR(100) DEFAULT NULL            COMMENT '统计层级',
  `del_flag`          TINYINT(1)   NOT NULL DEFAULT 0      COMMENT '删除标识',
  `add_user_id`       VARCHAR(50)  DEFAULT NULL            COMMENT '创建人账号',
  `add_user_name`     VARCHAR(100) DEFAULT NULL            COMMENT '创建人姓名',
  `add_time`          DATETIME     DEFAULT NULL            COMMENT '创建时间',
  `update_user_id`    VARCHAR(50)  DEFAULT NULL            COMMENT '更新人账号',
  `update_user_name`  VARCHAR(100) DEFAULT NULL            COMMENT '更新人姓名',
  `update_time`       DATETIME     DEFAULT NULL            COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_frame_id` (`frame_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='框架可视化配置主表';
```

> 一个已发布框架对应一条主配置记录（`frame_id` 业务唯一，逻辑删除后可重建）。

### 2.2 风险等级配置子表：`com_frame_visualization_level`

```sql
CREATE TABLE `com_frame_visualization_level` (
  `id`               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  `visualization_id` BIGINT       NOT NULL                COMMENT '关联可视化配置ID',
  `level_name`       VARCHAR(100) NOT NULL                COMMENT '风险等级名称（中文）',
  `score_range`      VARCHAR(100) NOT NULL                COMMENT '分值区间，格式如 (1,199) / [0,100) / [100,200]，括号表示开区间，方括号表示闭区间',
  `level_color`      VARCHAR(50)  DEFAULT NULL            COMMENT '展示颜色（十六进制或颜色名），为空时前端默认黑色',
  `order_num`        INT          NOT NULL DEFAULT 0      COMMENT '排序序号',
  `del_flag`         TINYINT(1)   NOT NULL DEFAULT 0      COMMENT '删除标识',
  `add_user_id`      VARCHAR(50)  DEFAULT NULL            COMMENT '创建人账号',
  `add_user_name`    VARCHAR(100) DEFAULT NULL            COMMENT '创建人姓名',
  `add_time`         DATETIME     DEFAULT NULL            COMMENT '创建时间',
  `update_user_id`   VARCHAR(50)  DEFAULT NULL            COMMENT '更新人账号',
  `update_user_name` VARCHAR(100) DEFAULT NULL            COMMENT '更新人姓名',
  `update_time`      DATETIME     DEFAULT NULL            COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_visualization_id` (`visualization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='框架可视化风险等级配置子表';
```

#### 分值区间格式说明

`score_range` 字段采用数学区间字符串表示，支持开/闭区间组合，以及正负无穷：

| 示例 | 含义 |
|------|------|
| `[0,60)` | 0 ≤ x < 60（左闭右开） |
| `[60,80)` | 60 ≤ x < 80 |
| `[80,100]` | 80 ≤ x ≤ 100（左闭右闭） |
| `(0,100)` | 0 < x < 100（全开区间） |
| `(-inf,0)` | x < 0（负无穷到 0，左端开区间） |
| `[0,+inf)` | x ≥ 0（0 到正无穷，右端开区间） |
| `(-inf,+inf)` | 全域（无限制） |

> 无穷端固定使用开区间：`-inf` 对应 `(`，`+inf` 对应 `)`，不允许写成 `[-inf,...]` 或 `[...,+inf]`。

后端在保存时需解析该字符串进行格式校验和互斥性校验，解析规则：
- 首字符 `[` 为左闭，`(` 为左开
- 末字符 `]` 为右闭，`)` 为右开
- 中间以英文逗号分隔两个数值

---

## 三、包结构与新增文件清单

所有新增文件均在 `dib-agent-service-rule-web` 模块下，遵循现有 `frame` 子域规范。

```
com.dib.agent.rule.web/
├── controller/
│   └── ComFrameVisualizationController.java           # 新增
├── aggregate/
│   └── ComFrameVisualizationAggregate.java            # 新增
├── service/frame/
│   ├── IComFrameVisualizationService.java             # 新增
│   ├── IComFrameVisualizationLevelService.java        # 新增
│   └── impl/
│       ├── ComFrameVisualizationServiceImpl.java      # 新增
│       └── ComFrameVisualizationLevelServiceImpl.java # 新增
├── entity/frame/
│   ├── ComFrameVisualizationEntity.java               # 新增
│   └── ComFrameVisualizationLevelEntity.java          # 新增
├── mapper/frame/
│   ├── ComFrameVisualizationMapper.java               # 新增
│   └── ComFrameVisualizationLevelMapper.java          # 新增
├── model/frame/
│   ├── req/
│   │   └── FrameVisualizationSaveReq.java             # 新增（保存配置）
│   └── resp/
│       └── FrameVisualizationResp.java                # 新增（查询响应）
└── converter/frame/
    └── FrameVisualizationConverter.java               # 新增
```

resources/mapper 下新增：
```
ComFrameVisualizationMapper.xml
ComFrameVisualizationLevelMapper.xml
```

---

## 四、接口设计

Controller 路径前缀：`/comFrameVisualization`，Swagger Tag：`框架准备-可视化`

### 4.1 查询可视化配置

```
GET /comFrameVisualization/getVisualization/{frameId}
```

- 入参：`frameId`（路径参数，已发布框架ID）
- 出参：`GeneralResult<FrameVisualizationResp>`
- 逻辑：按 `frame_id` 查主表 + 子表，组装完整配置返回；若尚未创建配置则返回空对象（不报错）

### 4.2 保存可视化配置（草稿）

```
POST /comFrameVisualization/saveVisualization
Body: FrameVisualizationSaveReq
```

- 出参：`GeneralResult<Void>`
- 逻辑：
  1. 校验 `frameId` 对应框架状态为 `RELEASE`，否则抛 `BizValidateException`
  2. 校验风险等级：名称非空、名称不重复、`score_range` 格式合法、区间不重叠
  3. 若主表记录不存在则 insert，否则 update
  4. 子表先逻辑删除旧记录，再批量 insert 新记录（事务保证）

### 4.3 查询已发布框架列表（供前端选框架用）

```
GET /comFrameVisualization/listReleaseFrame
```

- 出参：`GeneralResult<List<FrameInfoResp>>`（复用现有 `FrameInfoResp`）
- 逻辑：查询 `frame_status = RELEASE` 且 `del_flag = 0` 且 `enable_flag = true` 的框架列表

---

## 五、核心模型设计

### 5.1 FrameVisualizationSaveReq

```java
public class FrameVisualizationSaveReq {
    @NotNull
    private Long frameId;                              // 已发布框架ID
    private String statLevel;                          // 统计层级
    @NotEmpty
    private List<LevelConfigItem> levelConfigs;        // 风险等级配置列表

    @Data
    public static class LevelConfigItem {
        @NotBlank
        private String levelName;                      // 等级名称（中文）
        @NotBlank
        private String scoreRange;                     // 分值区间，如 [0,60) / [60,100]
        private String levelColor;                     // 可为空，前端默认黑色
        private Integer orderNum;                      // 排序序号
    }
}
```

### 5.2 FrameVisualizationResp

```java
public class FrameVisualizationResp {
    private Long visualizationId;
    private Long frameId;
    private String frameName;                          // 从 ComFrameInfoEntity 取
    private String statLevel;
    private List<LevelConfigItem> levelConfigs;
    private Date updateTime;
}
```

---

## 六、业务校验逻辑（Aggregate 层）

### 6.1 框架状态校验

```java
ComFrameInfoEntity frame = frameInfoService.getById(frameId);
if (frame == null || frame.getDelFlag()) {
    throw new BizValidateException("框架不存在");
}
if (frame.getFrameStatus() != FrameStatusEnum.RELEASE) {
    throw new BizValidateException("只能为已发布框架配置可视化");
}
```

### 6.2 分值区间解析与校验

`score_range` 字符串解析为 `ScoreRangeBO`（内部对象，不持久化）：

```java
// 解析示例：[60,100)
// leftOpen=false, leftVal=60, rightVal=100, rightOpen=true
public class ScoreRangeBO {
    boolean leftOpen;    // true=(, false=[
    BigDecimal leftVal;
    BigDecimal rightVal;
    boolean rightOpen;   // true=), false=]
}
```

校验规则：
1. 格式合法：首字符为 `[` 或 `(`，末字符为 `]` 或 `)`，中间逗号分隔两个合法数值
2. `leftVal < rightVal`（不允许空区间）
3. 任意两个等级区间不重叠：解析后做数值比较，考虑开闭区间边界

### 6.3 区间互斥判断逻辑

```java
// 两个区间 A、B 重叠的充要条件：A.max > B.min 且 B.max > A.min（考虑开闭边界）
// 边界相切（如 [0,60) 和 [60,100]）不算重叠
private boolean isOverlap(ScoreRangeBO a, ScoreRangeBO b) {
    // a.right 与 b.left 比较
    int cmp1 = a.getRightVal().compareTo(b.getLeftVal());
    boolean aRightGtBLeft = a.isRightOpen() || b.isLeftOpen()
        ? cmp1 > 0 : cmp1 >= 0;  // 至少一端开区间时，相等不算重叠
    // b.right 与 a.left 比较
    int cmp2 = b.getRightVal().compareTo(a.getLeftVal());
    boolean bRightGtALeft = b.isRightOpen() || a.isLeftOpen()
        ? cmp2 > 0 : cmp2 >= 0;
    return aRightGtBLeft && bRightGtALeft;
}
```

### 6.4 保存事务

```java
@Transactional(rollbackFor = Exception.class)
public void saveVisualization(FrameVisualizationSaveReq req) {
    // 1. 校验框架状态
    // 2. 校验等级配置（格式 + 互斥）
    // 3. upsert 主表
    // 4. 逻辑删除旧子表记录（lambdaUpdate set del_flag=1 where visualization_id=?）
    // 5. 批量插入新子表记录
}
```

## 七、分层调用关系

```
ComFrameVisualizationController
    └── ComFrameVisualizationAggregate
            ├── IComFrameInfoService           (复用现有，校验框架状态)
            ├── IComFrameVisualizationService  (主表 CRUD)
            └── IComFrameVisualizationLevelService (子表 CRUD)
```

---

## 八、待确认问题

| # | 问题 | 影响范围 | 当前默认处理 |
|---|------|---------|------------|
| 1 | 分值区间是否必须覆盖全部分数空间 | 保存校验逻辑 | 本期不强制，仅校验格式合法性和互斥性 |
| 2 | 统计层级数据来源（枚举/框架字段/动态） | statLevel 字段类型 | 本期存 VARCHAR，不做枚举约束 |
| 3 | 一个框架是否允许多套并行可视化配置 | 主表唯一性约束 | 本期一个框架一套配置（frame_id 业务唯一） |

---

**状态**：草稿

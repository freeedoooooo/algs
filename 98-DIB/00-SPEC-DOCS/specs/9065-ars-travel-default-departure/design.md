# 9065 事前申请-出差默认出发地点 技术设计

## 概述

在差旅费申请表单中，通过系统参数服务获取默认出发地点配置，新建行程时自动填充出发地点字段。

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      a-front (前端)                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              TravelForm.vue                          │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  use-travel.ts (hooks)                       │    │   │
│  │  │  - getDefaultTravelData() 获取默认行程数据   │    │   │
│  │  │  - addTravel() 新增行程                      │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              BaseListApi.getByKey()                  │   │
│  │              获取 ft_travel_default_departure 参数   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    common-ms (后端)                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              /api/v1/base-data/getByKey              │   │
│  │              返回参数值                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 前端架构

- 所属应用：a-front
- 涉及页面：`ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/TravelForm.vue`
- 涉及 hooks：`ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/hooks/use-travel.ts`

## 数据模型

### 系统参数配置

| 参数 Key | 参数名称 | 值类型 | 值格式 | 示例 |
|---------|---------|-------|-------|------|
| ft_travel_default_departure | 差旅默认出发地点 | string | 逗号分隔的地区代码 | `110000,110100,110101` |

### 前端数据格式

```typescript
// 地区代码数组格式（el-cascader 使用）
type RegionCodeArray = string[]  // 如 ['110000', '110100', '110101']

// 参数值格式（系统参数存储）
type ParamValue = string  // 如 '110000,110100,110101'
```

## 技术方案

### 1. 获取默认出发地点参数

在 `TravelForm.vue` 组件初始化时，调用 `BaseListApi.getByKey()` 获取默认出发地点参数：

```typescript
import { BaseListApi } from '@public/api/common/baseData'

// 默认出发地点
const defaultDeparture = ref<string[]>([])

// 获取默认出发地点配置
const getDefaultDeparture = async () => {
  try {
    const res = await BaseListApi.getByKey('ft_travel_default_departure')
    if (res && typeof res === 'string' && res.trim()) {
      // 将逗号分隔的字符串转换为数组
      defaultDeparture.value = res.split(',').filter(Boolean)
    }
  } catch (error) {
    console.warn('获取默认出发地点配置失败', error)
  }
}

// 组件初始化时获取
onMounted(() => {
  getDefaultDeparture()
})
```

### 2. 修改 use-travel.ts hooks

修改 `useTravel` hooks，支持传入默认出发地点：

```typescript
export const useTravel = ({
  emptyTravelData,
  getLocationDisplayText,
  defaultDeparture  // 新增参数
}: {
  emptyTravelData: TravelItemInterface
  getLocationDisplayText?: (location: any[]) => string
  defaultDeparture?: Ref<string[]>  // 新增参数类型
}) => {
  const getDefaultTravelData = () => {
    const data = JSON.parse(JSON.stringify(emptyTravelData))
    // 如果有默认出发地点配置，则填充
    if (defaultDeparture?.value && defaultDeparture.value.length > 0) {
      data.from = [...defaultDeparture.value]
    }
    return data
  }
  // ... 其他代码不变
}
```

### 3. 修改 TravelForm.vue

在 `TravelForm.vue` 中传入默认出发地点：

```typescript
const {
  travelList,
  addTravel,
  // ... 其他
} = useTravel({
  emptyTravelData,
  getLocationDisplayText,
  defaultDeparture  // 传入默认出发地点
})
```

### 4. 处理编辑场景

编辑已有行程时，不覆盖已保存的出发地点值。这通过 `watch` 监听 `initData` 实现，已有逻辑会使用后端返回的数据覆盖默认值。

## 影响范围

### 前端

- 需要修改的现有文件：
  - `ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/TravelForm.vue`
  - `ars-front-2/apps/a-front/src/views/fin-track/expendManagement/advanceApply/form/hooks/use-travel.ts`

- 需要新增的文件：无

### 后端

- 无需修改，使用现有的 `base-data` 参数服务
- 需要在系统参数管理中新增 `ft_travel_default_departure` 参数配置

## 风险点

- 风险1：配置的地区代码无效或不存在
  - 应对：前端获取参数后不做校验，直接使用。如果代码无效，el-cascader 会显示为空或显示代码值，用户可手动修改
  
- 风险2：参数服务接口异常
  - 应对：使用 try-catch 捕获异常，失败时不影响正常功能，出发地点保持为空

## 测试要点

1. 配置参数后，新建行程出发地点自动填充
2. 未配置参数时，新建行程出发地点为空
3. 配置无效地区代码时，不影响页面正常使用
4. 编辑已有行程时，不覆盖已保存的出发地点
5. 自动填充的出发地点可以手动修改

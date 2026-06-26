# 9063 单位收款方启用状态优化 技术设计

## 概述
修改单位收款方管理功能，实现保存时自动启用，并在列表页根据启用状态控制删除按钮显示。

## 架构设计

### 整体架构
本次修改涉及前后端两部分：
- 后端：修改 Service 层保存逻辑，强制设置启用状态
- 前端：修改列表页模板，根据启用状态条件渲染删除按钮

### 前端架构
- 所属应用：a-front
- 涉及页面：`views/fin-track/spendAllocation/payeeManagement/index.vue`
- 修改内容：删除按钮添加 `v-if` 条件判断

### 后端架构
- 所属微服务：fin-track-ms (18615)
- 涉及模块：Service 层
- 修改文件：`PayeeManagementServiceImpl.java`

## 数据模型

### 数据库字段（无变更）
- 表名：`t_payee_management`
- 启用字段：`c_is_enabled` (VARCHAR)
  - "0" = 未启用
  - "1" = 已启用

## 代码修改设计

### 后端修改

#### PayeeManagementServiceImpl.java - saveData 方法

**修改位置**：`saveData` 方法，在保存前强制设置 `isEnabled = "1"`

**修改前**：
```java
@Override
public PayeeManagementRespVO saveData(PayeeManagementReqVO reqVO) {
    PayeeManagementEntity entity = PayeeManagementEntityConvert.INSTANCE.vo2Entity(reqVO);
    if (ObjectUtil.isEmpty(entity.getId())){
        int insert = baseMapper.insert(entity);
        // ...
    }else {
        int i = baseMapper.updateById(entity);
        // ...
    }
    return PayeeManagementEntityConvert.INSTANCE.entity2VO(entity);
}
```

**修改后**：
```java
@Override
public PayeeManagementRespVO saveData(PayeeManagementReqVO reqVO) {
    PayeeManagementEntity entity = PayeeManagementEntityConvert.INSTANCE.vo2Entity(reqVO);
    // 新增或编辑保存后，自动设置为启用状态
    entity.setIsEnabled("1");
    if (ObjectUtil.isEmpty(entity.getId())){
        int insert = baseMapper.insert(entity);
        // ...
    }else {
        int i = baseMapper.updateById(entity);
        // ...
    }
    return PayeeManagementEntityConvert.INSTANCE.entity2VO(entity);
}
```

### 前端修改

#### index.vue - 境内收款方删除按钮

**修改位置**：境内收款方 Tab 的操作列模板

**修改前**：
```vue
<template #opera="scope">
  <el-button link @click="handleEdit(scope.row)" type="primary" v-hasPermi="['fico:basic-config:payee:domestic-edit']"> 编辑 </el-button>
  <el-button link @click="handleDelete(scope.row)" type="primary" v-hasPermi="['fico:basic-config:payee:domestic-del']"> 删除 </el-button>
</template>
```

**修改后**：
```vue
<template #opera="scope">
  <el-button link @click="handleEdit(scope.row)" type="primary" v-hasPermi="['fico:basic-config:payee:domestic-edit']"> 编辑 </el-button>
  <el-button v-if="scope.row.isEnabled !== '1'" link @click="handleDelete(scope.row)" type="primary" v-hasPermi="['fico:basic-config:payee:domestic-del']"> 删除 </el-button>
</template>
```

#### index.vue - 境外收款方删除按钮

**修改位置**：境外收款方 Tab 的操作列模板

**修改前**：
```vue
<template #opera="scope">
  <el-button link @click="handleEdit(scope.row)" type="primary" v-hasPermi="['fico:basic-config:payee:overseas-edit']"> 编辑 </el-button>
  <el-button link @click="handleDelete(scope.row)" type="primary" v-hasPermi="['fico:basic-config:payee:overseas-del']"> 删除 </el-button>
</template>
```

**修改后**：
```vue
<template #opera="scope">
  <el-button link @click="handleEdit(scope.row)" type="primary" v-hasPermi="['fico:basic-config:payee:overseas-edit']"> 编辑 </el-button>
  <el-button v-if="scope.row.isEnabled !== '1'" link @click="handleDelete(scope.row)" type="primary" v-hasPermi="['fico:basic-config:payee:overseas-del']"> 删除 </el-button>
</template>
```

## 影响范围

### 前端
- 需要修改的现有文件：
  - `ars-front-2/apps/a-front/src/views/fin-track/spendAllocation/payeeManagement/index.vue`
- 需要新增的文件：无
- 需要更新的环境变量：无

### 后端
- 需要修改的现有文件：
  - `ars-fin-track/fin-track-ms/src/main/java/com/dibcn/ars/finTrack/service/spendAllocation/impl/PayeeManagementServiceImpl.java`
- 需要新增的文件：无
- 需要更新的配置：无

## 风险点
- 风险1：已有未启用的收款方数据不受影响，只有新保存的数据会自动启用
  - 应对：这是预期行为，无需处理历史数据

# 备菜不慌 · MVP 工程说明

> AI 驱动的家庭高效烹饪助手 —— 极简核心闭环版本
> 技术栈：微信原生小程序 + 微信云开发（CloudBase）+ 通义千问（DashScope）

本目录是可直接导入微信开发者工具运行的完整工程。MVP 聚焦核心闭环：

1. AI 一键推荐菜单（1 荤 1 素 1 汤），支持「清库存优先」
2. 烹饪前备菜 Checklist（建议备齐再开火，不强制阻断）
3. 多线程时间轴烹饪导航（节点倒计时 + 到点震动/提示音提醒）
4. 轻量手动库存（录入/编辑/删除、临期与过期分组、做菜后自动扣减）

暂不包含（留待 V2）：AI 拍照入库、订阅消息临期推送、家庭共享、偏好忌口设置页。

## 零、本地 Mock 模式（无需云服务，离线体验）

工程默认开启 **Mock 模式**（`miniprogram/config.js` 中 `USE_MOCK: true`），此时：

- 不调用任何云函数、不连接云开发，全部使用前端内置假数据（`miniprogram/mock/`）。
- 可在微信开发者工具中用**测试号**直接完整跑通：
  今日推荐 → 选菜 → 备菜清单勾选解锁 → 时间轴倒计时与到点提醒。
- 推荐为「场景 + 时令筛选后组合」，不含大模型（`source` 显示为 `mock`）；开启「清库存优先」时会按库存加权。
- 库存数据通过 `wx.setStorageSync`（key: `mock_inventory`）本地持久化，首次运行自动写入几条演示食材，重编不丢失。

切换到真实云开发：把 `config.js` 的 `USE_MOCK` 改为 `false`，再按下方「二、三」部署即可。
该开关是唯一改动点，页面、组件、utils、云函数代码均无需改动。

> 注意：`miniprogram/mock/recipes.js` 是 `cloudfunctions/seed/recipes.js` 的前端副本，
> 因为 cloudfunctions 目录不在小程序打包范围内。若更新种子菜谱，请同步这两份文件。

## 一、目录结构

```
60-mvp/
├── project.config.json          # 项目配置（miniprogramRoot / cloudfunctionRoot）
├── miniprogram/                 # 小程序前端
│   ├── app.js                   # 云开发初始化 + 静默登录
│   ├── app.json                 # 页面路由与全局窗口配置
│   ├── app.wxss                 # 全局样式与设计变量
│   ├── sitemap.json
│   ├── config.js                # 全局开关（USE_MOCK 本地离线模式）
│   ├── mock/                    # 本地 Mock（离线体验用）
│   │   ├── recipes.js           # 内置种子菜谱副本
│   │   └── index.js             # 假云函数 login/recommendMenu/getRecipeDetail/inventory
│   ├── utils/
│   │   ├── request.js           # 云函数调用封装（loading / 错误处理）
│   │   ├── timer.js             # 多路倒计时管理器
│   │   └── format.js            # 场景/类型/库存常量、日期与状态、提醒（震动+提示音）
│   ├── components/
│   │   ├── recipe-card/         # 菜谱卡片
│   │   ├── checklist-item/      # 备菜清单项
│   │   ├── timeline-step/       # 时间轴步骤节点
│   │   └── float-timer/         # 悬浮倒计时
│   └── pages/
│       ├── index/               # 首页：场景筛选 + 今日推荐
│       ├── menu/                # 菜单确认：换一换 + 选菜
│       ├── prep/                # 备菜清单：建议备齐（不强制阻断）
│       ├── cook/                # 烹饪导航：时间轴 + 倒计时提醒
│       └── inventory/           # 我的库存：分组列表 + 新增/编辑/删除
└── cloudfunctions/              # 云函数
    ├── login/                   # 静默登录，初始化 users
    ├── seed/                    # 一次性写入种子菜谱到 recipes
    ├── recommendMenu/           # AI 组合推荐 + 清库存优先 + 兜底
    ├── getRecipeDetail/         # 获取菜谱详情
    └── inventory/               # 库存增删改查 + 做菜扣减（action 分发）
```

## 二、前置准备（阶段 0）

1. 注册微信小程序，拿到 AppID，填入 `project.config.json` 的 `appid`。
2. 在微信开发者工具中开通「云开发」，选择按量付费，记录环境 ID（env）。
3. 申请通义千问 DashScope API Key（阿里云百炼平台，有免费额度）。

## 三、部署步骤

1. 导入项目
   - 微信开发者工具 → 导入项目 → 选择 `60-mvp` 目录 → 填入你的 AppID。

2. 配置云环境 ID
   - 编辑 `miniprogram/app.js`，将 `globalData.env` 填为你的云开发环境 ID（留空则用默认环境）。

3. 上传并部署云函数（对 `login`、`seed`、`recommendMenu`、`getRecipeDetail`、`inventory` 逐个操作）
   - 右键云函数目录 → 「上传并部署：云端安装依赖」。

4. 配置 AI 密钥（recommendMenu）
   - 云开发控制台 → 云函数 → `recommendMenu` → 配置 → 环境变量，新增：
     - `DASHSCOPE_API_KEY` = 你的通义千问 Key（必填，否则自动走随机兜底）
     - `QWEN_MODEL` = `qwen-turbo`（可选，默认即此值）
     - `AI_TIMEOUT` = `8000`（可选，单位 ms）

5. 初始化菜谱库
   - 云开发控制台 → 云函数 → `seed` → 云端测试，传入 `{}` 执行（幂等，可重复）。
   - 如需清空重写，传入 `{ "mode": "clear" }`。
   - 执行后会自动创建 `recipes` 集合并写入 17 道种子菜谱（覆盖快手/简单/周末大菜）。

6. 数据库集合与权限
   - `users`：首次登录时由 `login` 自动创建。
   - `recipes`：由 `seed` 自动创建。
   - `ingredients`：首次调用 `inventory` 时自动创建。
   - 建议在云开发控制台将集合权限设为「仅创建者可读写」或「所有用户可读，仅管理端可写」。

7. 真机预览
   - 首页选场景 → 今日推荐 → 选一道菜 → 备菜清单全勾 → 开始烹饪 → 时间轴节点开启倒计时。

## 四、核心流程

```
index（场景筛选 + 清库存优先开关 + 库存入口 + 今日推荐）
  → recommendMenu 云函数（scene 标签 + 时令筛选 →〔可选〕库存加权 → 通义千问组合 → 兜底）
  → menu（展示 1荤1素1汤 + 换一换）
  → 点选某道菜 → prep（getRecipeDetail 拉取清单，建议备齐）
  → cook（timelineSteps 时间轴，含 timer 的节点可启动倒计时，到点提醒）
  → 全部完成 → inventory(deduct) 按 BOM 自动扣减库存

inventory 页（我的库存）：list 分组展示 → save 新增/编辑 → delete 删除
```

## 五、数据模型（recipes 集合）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `_id` | string | 菜谱 ID（如 `recipe_tomato_egg`）|
| `name` | string | 菜名 |
| `type` | string | `meat` 荤 / `vegetable` 素 / `soup` 汤 |
| `tags` | array | 场景标签 `quick`/`easy`/`feast` |
| `season` | array | 时令月份，`[]` 表示全年 |
| `estimatedTime` | number | 预计总时长（分钟）|
| `servings` | number | 人份 |
| `ingredientsNeeded` | array | BOM 食材清单 |
| `checklist` | object | `mainIngredients` / `seasonings` / `tools` 三类 |
| `timelineSteps` | array | `{ time, action, type, timer? }`，`type` 为 `prep`/`cook`/`wait` |
| `tip` | string | 小贴士 |

## 五之二、数据模型（ingredients 集合）

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `_id` | string | 库存记录 ID |
| `openid` | string | 所属用户（按 openid 隔离）|
| `name` | string | 食材名称（与菜谱 BOM 同名才能自动扣减）|
| `category` | string | `vegetable`/`meat`/`seafood`/`fruit`/`other` |
| `quantity` | number | 数量 |
| `unit` | string | 单位（个/份/g）|
| `expiryDate` | string | 保质期 `YYYY-MM-DD`，空表示无 |
| `_status` | string | 读取时附加计算：`expired`/`expiring`/`normal`（临期阈值 ≤2 天）|
| `_daysLeft` | number | 读取时附加计算：距过期天数 |

## 六、注意事项

- 提示音：`utils/format.js` 的 `remind()` 会尝试播放 `/assets/notify.mp3`，该文件可选；
  若不存在则仅有震动 + Toast 提醒，不影响功能。如需声音，放置一个 `notify.mp3` 到
  `miniprogram/assets/` 即可。
- AI 兜底：未配置 `DASHSCOPE_API_KEY`、超时或返回不合法时，`recommendMenu` 会自动从候选池
  随机组合一套合规菜单，保证功能永远可用。
- 切换 AI 厂商：只需替换 `cloudfunctions/recommendMenu/ai.js` 中 `chatJSON` 的实现，
  保持入参/出参不变，其余代码无需改动。
- 倒计时基于前端定时器，页面卸载（`onUnload`）会统一清理，避免泄漏。

## 七、后续 V2 规划

AI 拍照入库、临期预警订阅消息推送、家庭共享、偏好忌口设置页、时令优先推荐（模式B）。

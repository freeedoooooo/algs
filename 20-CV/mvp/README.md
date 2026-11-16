# CV 提取 MVP

把 week-02 验证过的提取能力封装成一个**本地 Web 工具**：浏览器上传文件 → 后端提取 → 生成单页对照报告。
`weekly/week-02/` 的代码与产物**完全不改动**，本目录自包含。

## 启动

```bash
D:\miniforge3\envs\paddle\python.exe mvp/app.py
# 浏览器打开 http://127.0.0.1:8765
```

服务栈是 **FastAPI + uvicorn**（本机已装）。生产式启动：

```bash
cd mvp && uvicorn app:app --host 0.0.0.0 --port 8765 --workers 1
```

- 加载大模型的服务建议 **workers=1**：多 worker 会各自加载一份模型，内存翻倍；要扩容应横向起多实例，前面挂 Nginx 反代，进程用 systemd / Docker 托管。
- 内置 `GET /healthz` 健康检查；配置（端口、模型、阈值、路径）集中在 `config.py`。

## 目录结构（模块化）

```
mvp/
├── config.py                  唯一配置源：模型名 / DPI / 阈值 / 路径 / 端口
├── app.py                     FastAPI 路由 + 后台任务编排（约 180 行）
├── pipeline/                  提取层
│   ├── engines.py             模型单例（懒加载，全进程复用）
│   ├── ocr.py                 逐行文字 / 置信度 / 四点框 + 带框 PNG
│   ├── pdf.py                 首页渲染 / 文本层 / pdfplumber 表格 + bbox
│   ├── plain.py               CSV / TXT 直读
│   ├── table_model.py         网格预筛 / PPStructureV3 / HTML 解析 / 矫正图
│   ├── structure.py           表头分离 / cells 网格 / CSV 导出
│   └── runner.py              extract_one() 统一入口
├── report/                    报告层
│   ├── cards.py               各区块 HTML（图片 / 文字 / 表格 / JSON）
│   ├── builder.py             组装 index.html
│   └── assets/                前端资源，独立文件可单独编辑
│       ├── report.css / report.js / lightbox.html
│       └── upload.html / upload.css / upload.js
├── input/                     上传文件落盘（运行时生成）
└── output/                    产物（运行时生成）
    ├── index.html             汇总报告
    └── <序号_文件名>/        每个文件一个自包含目录
```

**源码模块化，产物自包含**：`builder.py` 生成报告时会把 `report.css` / `report.js` / `lightbox.html`
内联进 HTML，所以 `output/index.html` 单独拷走、用 `file://` 打开也能正常显示与交互。
上传页是线上页面，走 `/static/` 外链资源。

单个 Python 文件最大约 290 行，CSS / JS / HTML 各在独立文件里，IDE 高亮、改样式不必碰 Python。

## 支持格式与产物

| 输入 | 路线 | 主要产物 |
|---|---|---|
| png / jpg / bmp / webp / tif | OCR + 长直线预筛 → PPStructureV3 | `source.<ext>`、`boxes.png`、`pages/rectified.png`、`table_N.csv` |
| PDF 有文本层 | pymupdf 渲染首页 + OCR + pdfplumber 直读表格 | 同上，`pages/p1.png`；表格带单元格 bbox |
| PDF 无文本层 | 同图片路线 | 同上 |
| CSV / TXT / MD | 纯文本直读，不跑 OCR | `source.<ext>`、`table_N.csv`（CSV） |

每个 case 目录还固定有一份 `result.json`（OCR 行、表格、单元格坐标、诊断）。
`rectified.png` 只在真正抽到表的图片 / 扫描件里生成。

## 报告包含什么

- **原图 / 矫正图**切换（有矫正图时才出现切换条），点击图片全屏放大：滚轮以光标为中心缩放、拖拽平移、1:1 原像素、双击切换、Esc 关闭、叠加框开关、新窗口打开原图。
- **提取内容**：逐行 OCR 文字 + 置信度条，与左图识别框双向高亮；有文本层 / 纯文本另给全文折叠区。
- **表格内容**：带表头的 HTML 表格、CSV 下载（自包含 data URI + 真实文件链接）、多表 tab 切换。
- **单元格坐标回溯**：默认一个框都不画，悬停只高亮那一格、点击钉住（再点取消），并自动切到该表的坐标宿主视图；「显示整表网格」是默认关闭的调试开关。
- **完整 JSON**：折叠查看、下载 `result.json`、一键复制。

两套坐标空间严格互斥：文本层 / OCR 框基于 `source.<ext>`；表格模型单元格框基于 `pages/rectified.png`（转正 + 去扭曲，1:1 无需逆变换）。纯文本标注「无图像载体」。

## 与 week-02 的关系（重要）

- **算法自包含复制**，没有 import week-02，满足「week 目录不动」。代价是存在**逻辑漂移风险**：以后改了 week-02 的提取逻辑，mvp 不会自动同步。稳定后建议把公共部分抽成单一真相源供两边复用（那一步需要动 week 目录，需另行确认）。
- **定位不同**：week-02 是 25 个 case 的批量回归 + 汇总指标 + 标准答案对照 + bad case 库；mvp 是单文件即时预览。新来一张图先看效果用 mvp，改完算法验证没跑偏仍要跑 `weekly/week-02/a_batch_ocr.py`。
- 有文本层 PDF 的人工列边界模板放在 `config.TABLE_COLUMN_LINES`，按去掉数字编号后的语义名匹配（换编号仍命中）；未登记文件走 `auto_column_lines()` 自动推断。

## 已知限制 / 下一步

- 单任务串行、无鉴权、仅监听 `127.0.0.1`；上传用 base64 JSON，单文件上限 20MB。
- 多页 PDF 目前只处理**首页**。
- 无模型参数面板。调试效率最明显的下一步是把 `PDF_DPI`、`LOW_SCORE`、是否开文档预处理、表格策略做成页面开关，并保留历史任务的参数快照以便对比。
- 自动列边界对未登记的复杂版式仍是尽力而为；遇到新固定版式，往 `config.TABLE_COLUMN_LINES` 加一行即可。

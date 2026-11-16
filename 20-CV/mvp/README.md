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

## 独立部署

整个 `mvp/` 目录拷到目标机器即可运行：不依赖仓库其它目录、不 import week-02、路径全部由 `config.ROOT` 推导。

```bash
# 1) Python 3.10（3.9~3.12 均可），建议独立虚拟环境
python -m venv .venv && .venv\Scripts\activate     # Linux: source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt

# 2) 装完自检（只读、不加载模型，秒级）
python check_env.py

# 3) 启动
python app.py                                     # http://127.0.0.1:8765
uvicorn app:app --host 0.0.0.0 --port 8765 --workers 1    # 生产式
```

`requirements.txt` 锁的是本机实测版本，几个容易踩的点：

- `paddleocr 3.7.0` **不声明 paddlepaddle**，必须单独安装；GPU 机器把 `paddlepaddle==3.2.0` 换成对应 CUDA 版 `paddlepaddle-gpu`。
- `cv2` 来自 `opencv-contrib-python==4.10.0.84`（paddlex 的 `ocr-core` extra 指定），**不是** `opencv-python`，两个都装会冲突。
- 上传走 base64 JSON，所以不需要 `python-multipart`；Starlette 1.x 的静态文件也不需要 `aiofiles`。
- `pdfplumber` / `PyMuPDF` 是本项目自己用的，paddle 不带，别漏。

**离线 / 内网部署**：PaddleX 官方模型在首次推理时联网下载到 `${PADDLE_PDX_CACHE_HOME:-~/.paddlex}/official_models`（数百 MB）。先在联网机器跑一次把模型下全，再把该目录一起拷贝，并设置 `PADDLE_PDX_CACHE_HOME` 指向其**上级**目录。`check_env.py` 会检查缓存是否就绪。

**环境变量**（全部可选，默认值见 `config.py`）：

| 变量 | 默认 | 用途 |
|---|---|---|
| `CV_MVP_HOST` | `127.0.0.1` | 监听地址，服务器设 `0.0.0.0` |
| `CV_MVP_PORT` | `8765` | 端口 |
| `CV_MVP_MAX_FILE_MB` | `20` | 单文件上限（改它时同步改 `upload.js` 的前端 20MB 校验） |
| `CV_MVP_WARMUP` | `0` | 设 `1` 则启动时预加载模型 |
| `PADDLE_PDX_CACHE_HOME` | `~/.paddlex` | 模型缓存根目录，离线部署必设 |

容器化时把 `official_models` 缓存打进镜像，`CMD python app.py`、`HEALTHCHECK curl -f http://127.0.0.1:8765/healthz`，并保持 `--workers 1`。

## 模型加载时机（默认全程懒加载）

| 阶段 | 发生了什么 | 耗时 |
|---|---|---|
| 服务启动 `import app` | 只有 FastAPI + config，**连 paddleocr 库都不 import**（实测 0.53s） | ~0.5s |
| 首次上传 → 后台线程动态加载 `pipeline` 包 | 才 import cv2 / pdfplumber / pymupdf / PIL，仍不碰模型权重 | 1~3s |
| 首次 OCR `engines.ocr()` | 构造 PaddleOCR，加载检测 / 识别 / 方向分类模型 | 20~40s |
| 首次表格 `engines.structure()` | **先跑 `grid_score()` 长直线预筛**，命中网格才构造 PPStructureV3 | 20~40s |
| 后续文件 | `_OCR` / `_STRUCT` 模块级单例复用 | 每张几秒 |

- 两级懒加载：包级 import 在后台线程，权重只在第一次真正用到时实例化。上传页、`/healthz`、`/report` 都不会触发模型。
- **纯文字图 / 证件扫描 / CSV / 有文本层 PDF 完全不加载表格结构模型**（预筛不命中，或走 pdfplumber 直读）。
- 单例按**进程**缓存，重启会重新加载；`--workers 1` 保证只有一份。
- 想改成「启动即加载、首个请求不等」：设 `CV_MVP_WARMUP=1`，在 FastAPI lifespan 里同步预热，`python app.py` 与 `uvicorn app:app` 都生效。默认关闭。

## 目录结构（模块化）

```
mvp/
├── requirements.txt           独立部署依赖（实测版本锁定）
├── check_env.py               部署自检：缺包 / 目录 / 模型缓存
├── config.py                  唯一配置源：模型 / DPI / 阈值 / 路径 / 环境变量
├── app.py                     FastAPI 路由 + 后台任务编排 + 包自举（约 240 行）
├── __init__.py                支持 uvicorn mvp.app:app 包方式启动
├── .gitignore                 input/output/__pycache__ 不入库
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
├── input/                     上传文件落盘（运行时生成，带批次时间戳前缀）
└── output/                    产物（运行时生成，与 input 同名去后缀）
    ├── index.html             汇总报告
    └── <时间戳_文件名>/       每个文件一个自包含目录
```

### 命名规则：一次上传 = 一个批次戳

上传时按当前时间生成 `YYYYMMDDHHmmss`（年月日时分秒）前缀，`input/` 与 `output/` 共用它，目录按字典序排就是按时间排：

```
input/20261116160231_103_real_bank_statement_textlayer.pdf
output/20261116160231_103_real_bank_statement_textlayer/
       ├── result.json  boxes.png  source.png  table_1.csv
       └── pages/p1.png
```

- **只加前缀，不改原文件名**：源文件自带的 `103_` 这类数字编号完整保留，`output` 目录名就是「带戳输入名去掉后缀」。
- 重复上传同一个文件**不会覆盖**上一次：新批次有新前缀，历史产物全部保留，方便对比两次调试结果。
- 同一秒内再次上传加 `-2` / `-3`；同一批里出现重名文件也加 `-2` 区分。
- 批次号可在 `GET /api/status` 的 `batch` 字段看到，上传接口也直接返回。
- 注意 `output/index.html` 是**最近一次上传**的汇总报告，不是全历史索引。

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
- 有文本层 PDF 的人工列边界模板放在 `config.TABLE_COLUMN_LINES`，键是「剥掉批次时间戳后的原文件名」（**保留 `103_` 这类数字编号**）；查表时还会兜底试一次去掉编号的语义名，所以换编号仍命中。剥前缀只发生在查模板键时，不影响任何落盘文件名。未登记文件走 `auto_column_lines()` 自动推断。

## FAQ：IDE 报 `No module named 'config'`（已解决，零 IDE 配置）

早期版本内部用**顶层绝对导入**（`import config` / `pipeline` / `report`）。运行时靠
`sys.path` 兜底没问题，但 PyCharm / Pylance 的静态分析**不会执行** `sys.path.insert(...)`，
它默认把工作区根（`algs/`）当模块搜索起点，那里没有 `config.py`，于是 9 个文件一起标红。

**现在改成代码自洽的方案，不需要改任何 IDE 配置**（`.idea` / `.vscode` / `pyrightconfig` 都不用动）：

| 位置 | 写法 | 作用 |
|---|---|---|
| `pipeline/*.py`、`report/*.py` | `from .. import config` | 包内相对导入，静态分析器按目录层级就能解析 |
| `app.py`、`check_env.py` | `importlib.import_module(PKG + '.config')` 等动态加载 | 入口文件不再有静态的顶层绝对导入；`PKG` 取 `os.path.basename(ROOT)` |

关键是让所有内部模块**始终以「包」方式加载**：相对导入才成立，静态分析器也无需把 `mvp/`
标成 Sources Root / extraPaths。下面四种启动方式都实测通过：

```bash
python mvp/app.py                                # 从 20-CV/，脚本方式
cd mvp && python app.py                          # 从 mvp/，脚本方式
cd mvp  && uvicorn app:app --workers 1
cd 20-CV && uvicorn mvp.app:app --workers 1
```

整个 `mvp/` 拷走、甚至改目录名也能跑（包名动态取）。**模型仍然懒加载**：`pipeline` / `report`
只在后台处理线程里动态导入，`import app` 依旧 0.5s、连 paddleocr 库都不碰。

如果 IDE 还显示旧报错，刷新一下语言服务缓存（PyCharm: File → Reload All from Disk；
VS Code: Reload Window）即可 —— 代码里已经没有任何顶层绝对导入了。

## 已知限制 / 下一步

- 单任务串行、无鉴权、默认仅监听 `127.0.0.1`（可用 `CV_MVP_HOST=0.0.0.0` 放开）；上传用 base64 JSON，单文件上限 20MB。
- 首次运行需联网下载 PaddleX 官方模型（数百 MB）；离线部署要预置缓存，见「独立部署」。
- 多页 PDF 目前只处理**首页**。
- 无模型参数面板。调试效率最明显的下一步是把 `PDF_DPI`、`LOW_SCORE`、是否开文档预处理、表格策略做成页面开关，并保留历史任务的参数快照以便对比。
- 自动列边界对未登记的复杂版式仍是尽力而为；遇到新固定版式，往 `config.TABLE_COLUMN_LINES` 加一行即可。

# 项目长期约定

## 代码改动审阅方式（2026-11-09 更新，取代 2026-11-02 的旧约定）
- 用户**不需要**额外的交互式 diff 查看器 / 自绘 UI 组件，也不需要贴大段纯文本 diff。
- 代码改动直接落在工作区；用户通过编辑器 / IDE 自带的源代码管理面板（git diff）查看。
- 助手改完代码后只需简要说明：改了哪些文件、每处做了什么、验证结果。
- 助手侧可用 `git diff` 命令做核对，但不要为此生成可视化组件。

## 其他既有约定
- 本机 miniforge 环境名：`paddle`（`conda activate paddle`），路径 `D:\miniforge3\envs\paddle`，Python 3.10.9；需要实跑验证时用该环境的 `python.exe`。
- 脚本默认输入/输出路径统一放在文件顶部【配置区】，方便调试时一眼找到。
- 产物统一写 `output/`，输入统一放 `input/`。
- **输出隔离规则（2026-11-13 下午定稿，取代上午的单层版本）**：统一 `output/<脚本名>/<输入文件名去后缀>/` 两层隔离 —— 每个脚本占一个专属目录，脚本内每个输入再单独一个子目录；跨 case 的汇总表放该脚本目录的根。中间产物（转出的页图、OCR 临时页图）再单独一层子目录（`pages/`、`_tmp_pages/`），不与正式结果混放，**跑完保留供核对，重跑该 case 时先清空旧图再生成新图**（2026-11-13 晚定稿，取代原先「用完自动清理」；用户明确说检查时要能看到临时产物长什么样）。脚本的输出配置项只写「文件名」，由 case 目录拼接。用户明确要求「每个脚本产物隔离、脚本中不同输入的产物也隔离，一眼看清哪个输入对应哪个输出」。
- 批量 / 流水线类脚本：一次跑完 `input/` 下所有 case，不要让用户每次手改输入路径（2026-11-13）。
- **页码基准统一 1 起（2026-11-13 晚定稿）**：所有可见页码都与 PDF 阅读器一致 —— 页图 `_tmp_page_N.png` / `c_page_N.png`、表格 HTML `pipeline_table_pN.html` / `d_table_out_N.html`、`output.json` 的 `page`、日志「第 N 页」，N 从 1 起。代码统一 `enumerate(..., 1)`，**禁止再出现 `i + 1` 换算或 0 起编号**；`b_ocr_image.py` 的 OCR 文字行索引除外（内部要用 `polys[i]`，展示行号本来就是 `i + 1`）。重跑时脚本先清掉旧编号的表格 HTML / 旧页图，避免新旧两套编号并存。用户原话「统一从1开始，页面与输出保持一致」。
- 周笔记收敛为**单文件 `notes.md`**：散落的问答全稿、外部机器手册等，提炼结论后即可清理原文，避免同一知识维护两份（2026-11-13）。清理前提：确认文件已被 git 跟踪可恢复、把主笔记改成自包含（清掉所有指向被删文件的链接/章节引用）、全仓确认无其它引用。
- 用户偏好自己手动执行安装/运行命令；助手只在需要验证时跑轻量检查，不代替用户做环境操作。**例外**：用户明确说「重跑一下结果」时，助手直接代跑完整批量流水线。
- **week-02 输入 case 命名约定（2026-11-13 晚定稿，取代上午的 real_ 无编号版本）**：合成样本 `01~18`（编号 < 101）；**用户真实 case 从 101 起编号，格式 `101_real_xxx`**（数字前缀好找 + `real_` 语义标记 + 一眼看懂的名字）。新增 case 从 108 接着编，直接丢进 `input/` 重跑 `a_batch_ocr.py` 即生效，不用改脚本 / 清单。**唯一真相源是 `week-02/case_naming.py`**（`REAL_START_NO`、`strip_no()`、`is_real_case()`、`case_sort_key()`、`next_real_no()`、`pick_real_image()`），所有脚本都 import 它；禁止再在别处写死 case 文件名或靠 `name[:2].isdigit()` 猜分组。**排序必须用 `case_sort_key()`**：字典序下 `101_` 会插到 `10_` 前面，纯 `sorted()` 会让真实 case 跑到合成样本中间。必须去重（MD5，删字节级相同副本）。manifest 加 `group: synthetic/real` 与 `real_start_no`，但 manifest 不是白名单。
- **week-02 产物隔离（2026-11-13 晚）**：与 week-01 同规则 —— `output/a_batch_ocr/<输入名>/` 放 `result.json` / `result.txt` / `source.<ext>` / `boxes.png` / `pages/p1.png`，脚本目录根只放 `index.html` + `batch_summary.json/.txt`；`c_try_params.py` 产物放 `output/c_try_params/`。报告引用各 case 目录里的图片副本，整目录可搬走；卡片带「本 case 的 result.json」链接。用户原话「一整个输出的 json 都在一起看着不方便」。三类输入统一留 `source.<ext>` 副本（CSV 也复制 `source.csv`、不生成 `boxes.png`），保证每个 case 目录自包含；旧结构 `output/vis/`、`batch_ocr_results.json` 已清理，文档路径一律指向 `output/a_batch_ocr/`。
- **week-02 表格提取 = 对所有 case 全量检测、命中才提取（2026-11-13 晚二次纠正）**：`a_batch_ocr.finish()` 现对**每个 case** 调 `enrich_case()` 做表格检测；`TABLE_EXTRACT`（默认 True）是总开关，已删除 `TABLE_EXTRACT_CASES` 白名单。检测不到表格的 case 自动 `skipped`，**不产生任何表格文件**（`export_case_tables` 对空表跳过写盘）。103 = 文本层 pdfplumber 直读（24×8）；105 = CSV 也按文本层读成 1 张表（8 列）；107 = PPStructureV3 表格模型（自动转正 5×8）；104/106 扫描件预筛命中网格但模型没还原出表 → 仍 skipped。文本（`texts`/OCR）与表格（`structured_tables`）在 result.json 里**同时保留**；报告 `index.html` 每张卡片都带「表格提取」区块，命中表格显示表 + CSV 下载，未命中显示诊断。
- **重跑清理防沙箱拦截（2026-11-13 晚）**：`a_batch_ocr.prepare_case_dir()` 旧版把 `result.json`/`boxes.png`/`source.*` 也一起删，25 个 case 累计删 50+ 触发沙箱「安全删除」保护（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`）中断整批，导致部分 case 文本产物被清空。改为**只删表格类旧产物**（`tables.json`/`table_*.csv`/`pages/*.png`）—— 其余 `result.json` 等落盘时以「w」覆盖重写，删不删结果一样新，且一次全量删除数降到个位数，不再触发拦截。同理 `grid_score()` 直线预筛加 `try/except`，单图异常只当无网格跳过。
- **有文本层 PDF 的表格不要转图走 OCR 模型**（2026-11-13 定稿）：字符精确、带坐标/字体/矢量线，直读快两个数量级。方案分层：判载体 → lattice/stream 策略解析（pdfplumber `TABLE_STRATEGIES`，无竖线的 stream 型必须回退 `text`）→ 人工列边界模板（固定版式最稳，自动 words 聚类实测会混进页眉）→ 仅失败页转图走表格模型 → 业务校验。week-01 `weekend_pipeline.py` 与 week-02 `text_layer_extract.py` 各维护一份，不互相 import。
- **pymupdf 渲染被裁剪的 PDF**：默认按 CropBox，只出顶部一条；要 `page.set_cropbox(page.mediabox)` 才渲染整页（test3.pdf 910×218 → 910×1287）。

## PaddleOCR 3.7.0 坐标基准（2026-11-12 实测，涉及画识别框时必须遵守）
- 默认 `use_doc_preprocessor=True`（整页方向分类 + UVDoc 去扭曲）会让 `rec_polys` / `dt_polys` 基于**矫正后图像**，直接画回原图整体错位。
- 凡要把框叠到原图上，构造时加 `use_doc_orientation_classify=False, use_doc_unwarping=False`；week-02 已做成配置区开关 `USE_DOC_PREPROCESS`（默认 False）。
- 只取文字、不需要坐标时可保留默认：实测 UVDoc 会让亮字暗底终端截图识别更好（6 行/0.90 vs 关闭后 4 行/0.17），属质量与坐标的权衡。
- week-02 已做成配置区开关 `USE_DOC_PREPROCESS`（默认 False）。week-01（2026-11-12 优化后）：`b_ocr_image.py` 要画框，同样默认关闭并产出带框 PNG + 自包含 HTML；`weekend_pipeline.py` 只取文字不画框，**刻意保留默认开启**，两者不要统一。
- 用户不接受只看 JSON 的结果呈现；OCR 结果一律配「带框 PNG + 离线 HTML 对照报告」。
- **HTML 报告里叠加识别框的框必须 1:1 贴合（2026-11-13 晚定稿）**：`<img>` 与 `<svg>` 必须一起包进 `position:relative` 的 wrapper（`line-height:0`），svg 用 `left:0;top:0;width:100%;height:100%` 铺满，`viewBox` 用原图像素尺寸。**禁止**让 svg 相对被 grid stretch 的 `.stage` 用 `calc(100% - 28px)` 定位 —— 右栏内容高时会把框非等比纵向拉长（实测扁图 102 达 3.10×）。带框 PNG 用 `width=2` 去掉 `joint='curve'` 圆角，与 HTML `<polygon>` + `stroke-width:2` 对齐。
- **报告里的表格必须整行宽度（2026-11-13 晚），11-16 改为默认收起、按需展开**：不要把表格塞进有 `max-height:620px;overflow:auto` 的右侧 pane（前面还有几百行 OCR 文字，用户滚不到、会以为没有表格）。检测到的表格放在 `.grid` 之后的整宽区块，直接渲染带表头的 HTML 表格 + 跳转徽标 + 诊断折叠区；未检测到的只留一行说明。11-16 用户要求「按需展示」，故 `.tblbody` 默认 `hidden`、由 `.tbltoggle` 展开，跳转徽标点击时 JS 先展开再滚动（不能跳到空区）。**「下载 CSV」用 base64 data URI 自包含**（预览面板/沙箱 iframe 相对路径取不到本地文件时会失效），另保留指向真实 `table_N.csv` 的链接。改报告样式只需 `python vis_ocr_result.py`（秒级读回 result.json），不必重跑 OCR 全量。

## PaddleX 3.7.0 表格 HTML 导出坑（2026-11-13 实测）
- `result.save_to_html(文件路径)` 内部是 `html[list(html.keys())[0]]`；`res.html` 为空字典（这一页没表格）时抛 `IndexError`。多页 PDF 里证书扫描页必踩，不是识别失败。
- 同一方法遇「一页多张表」只写第一张并打 warning，会悄悄丢数据。
- 统一做法：先判 `res.html` → 空则从 `parsing_res_list` 的 `[table]` 块 `block_content` 兜底 → 仍空就跳过该页并打印序号；多表按 key 拆文件。week-01 `d_table_ocr.py` 的 `export_html()` 已实现，`weekend_pipeline.table_ocr_page()` 已加判空守卫。

## week-02 表格专项 case 20~28（2026-11-16）
- 用户要求从 20 起编号补充表格类 case。新增唯一脚本 `week-02/make_table_cases.py`（**只写 `input/` 与 manifest，不改任何提取脚本**），生成 9 个：20 跨 3 页、21 一页双表、22 合并单元格、23 跨页+多表、24 无线框 stream、25 无文本层扫描 2 页、26 一页三表+噪声、27 旋转双表图、28 空页混合（4 页）。19 留空。
- **生成技巧**：pymupdf 内置 CJK 字体 `fontname='china-s'` 能写真实中文文本层（零字体依赖，实测 pdfplumber 可直读）；合并单元格必须把内线**分段画**（跳过某行段的内竖线 = 横向合并，跳过某列段的内横线 = 纵向合并），`find_tables()` 才会把被吞格返回 `None`。
- **合成样本命名扩充为 `01~18` + `20~28`（编号 < 101）**，`case_sort_key()` 自动处理、真实 case 恒排最后。manifest 由脚本 upsert（只增删 category 以「表格专项」开头的条目）；重跑 `make_samples.py` 会整体重写 manifest，需再跑一次本脚本补登记。
- **实测暴露的两个现状限制（未改代码，留作练习）**：① `render_first_page()` 只出 `p1.png`，多页 PDF 第 2 页起的表虽有 `cell_grid` 坐标但报告无对应页图可叠；② 纯文字页被 `text` 策略误抽成伪表（28 的 p1 成 3×1）。逐 case 基线见 `week-02/notes.md`。

## mvp 独立部署与模型加载（2026-11-16 实测）
- **模型默认全程懒加载**：`import app` 实测 0.53s，连 `paddleocr` 库都不 import（只 FastAPI+config）；`import pipeline` 在后台处理线程里才发生；`pipeline/engines.py` 的 `_OCR/_STRUCT` 单例在首次 `ocr()`/`structure()` 才构造；表格模型更懒 —— `grid_score()` 长直线预筛命中才加载 PPStructureV3，纯文字图/CSV/文本层 PDF 完全不加载。按进程缓存，重启即失效，故 `--workers 1`。`CV_MVP_WARMUP=1` 可改成启动时经 FastAPI lifespan 同步预热（默认关）。
- **依赖坑（写 requirements.txt 必须记住）**：① `paddleocr 3.7.0` 只声明 `paddlex[ocr-core]>=3.7.0,<3.8.0`，**不装 paddlepaddle**，必须单列 `paddlepaddle==3.2.0`（GPU 换 paddlepaddle-gpu）；② `cv2` 来自 `opencv-contrib-python==4.10.0.84`（paddlex ocr-core extra 指定），**不是 opencv-python**，两个都装会冲突；③ `pdfplumber` / `PyMuPDF` 是本项目自己用的，paddle 不带；④ 上传走 base64 JSON，不需要 `python-multipart`；Starlette 1.x 静态文件不需要 `aiofiles`。
- `PADDLE_PDX_CACHE_HOME` 控制官方模型缓存根（默认 `~/.paddlex`，模型在 `official_models/`），离线部署要预置并指向其上级目录。`config.py` 用 `os.environ.setdefault` 不覆盖外部设置。
- `app.py` / `config.py` 顶部都把 `ROOT` 插入 `sys.path`，否则 `uvicorn mvp.app:app` 从仓库根启动会因顶层 `import config` 失败；已加 `mvp/__init__.py`。配置可用 `CV_MVP_HOST/PORT/MAX_FILE_MB/WARMUP` 覆盖。
- 新增 `requirements.txt`（10 条实测锁定版本）、`check_env.py`（依赖/目录/模型缓存自检，退出码可当 CI 门禁）、`.gitignore`（input/output/__pycache__ 不入库；已跟踪过的文件需 `git rm -r --cached` 才生效）。
- **IDE 报 `No module named 'config'` 已用「零 IDE 配置」方案根治（2026-11-16 定稿，用户明确不要改 .idea）**：根因是顶层绝对导入 + 静态分析器不执行 `sys.path.insert`。最终方案 = **内部模块一律以包方式加载**：`pipeline/*.py` / `report/*.py` 用 `from .. import config`；`app.py` / `check_env.py` 用 `importlib.import_module(PKG + '.xxx')` 动态加载（`PKG = os.path.basename(ROOT)`，父目录插入 sys.path）。代码里 **0 处**顶层绝对导入，IDE 无需 Sources Root / extraPaths / 任何配置；四种启动方式实测通过（`python mvp/app.py`、`cd mvp && python app.py`、`uvicorn app:app`、`uvicorn mvp.app:app`），目录改名也能跑，懒加载不变。**曾临时改过 `algs/algs.iml` 与两处 `pyrightconfig.json`，已全部回退；不要再动 IDE 配置**。

## week-02 表格单元格坐标回溯（2026-11-16 定稿，用户选「矫正图视图」）
- **不要为了拿坐标而关 UVDoc**：实测 107 关闭后 50 个单元格有 12 个内容退化（序号列塌成空值、0/O 混淆、数字错），换 `PP-OCRv4_server_rec` / `PP-OCRv5_server_rec` 也补不回来（差异 13 / 10 个）。UVDoc 无条件执行、只输出 `doctr_img` 不暴露变换场，其非线性形变无法精确逆变换。
- **正确做法 = 换坐标宿主，不做逆变换**：`cell_box_list` 本就基于 `doc_preprocessor_res["output_img"]`（转正 + 去扭曲图），把它另存 `<case>/pages/rectified.png`，框 1:1 叠上去；报告提供「原图 / 矫正图」切换。文本链路完全不动、零额外推理。
- 103 有文本层 PDF 走另一套空间：`page.find_tables()`（**不要用 `extract_tables()`，它丢坐标**）→ `Table.rows[i].cells` → 乘 `PDF_RENDER_DPI/72` 换到预览图像素；`clean_table()` 删空行空列时必须**同步删/补 bbox 网格**，否则从第 2 行起整体错位。
- 结构化表的 `cells[r][c]` 必须与「表头 1 行 + 数据 n 行」严格同形状，报告 `<td data-cell="r_c">` 才能直接索引。`split_header()` 多返回 `header_idx` 用于同步切网格；`colspan` 展开格共享同一个框序号（`_TableParser.box_tables` 记原始 `<td>` 序号）。CSV 无图 → `coord.space='none'`。
## mvp/ 命名约定（2026-11-16 用户定稿）
- 上传批次前缀 = `YYYYMMDDHHmmss`（**含时分秒**，14 位），`input/` 与 `output/` 共用；例 `20261116160643_103_real_bank_statement_textlayer.pdf` → `output/20261116160643_103_real_bank_statement_textlayer/`。输出目录 = 带戳输入名去掉后缀，一一对应、字典序即时间序。
- **只加前缀，不改原文件名**：源文件自带的 `103_` 这类数字编号必须完整保留（用户明确「不需要去掉」）。剥前缀只发生在 `pipeline/pdf.py::template_lines()` 查 `config.TABLE_COLUMN_LINES` 时，且只剥时间戳那一段（`^\d{12,14}_`），再依次试「带编号原名 / 去编号语义名」两个键，后者兼容 week-02 旧写法与换编号。
- 重复上传不覆盖：同一秒内再次上传加 `-2/-3`；同批内重名文件也加 `-2`。批次号在 `/api/status` 的 `batch` 与上传响应里。`output/index.html` 只是最近一次批次的汇总，历史批次目录保留供对比。
- 报告交互定稿（11-16 二次精进）：**单格定位** —— 所有 `.cellbox` 默认 `display:none`，悬停表格格只给该格加 `.hv`、点击加 `.pin`（再点取消），点击时 `ensureView()` 自动切到坐标宿主视图；「一次铺满整表网格」被用户否定（看不出定位到哪一格），降级为默认关闭的调试开关 `.all`。表格预览**默认收起**、多表 tab 只激活当前表的框（用 `.off` class，**禁止 inline style**，否则压住 `.hv`/`.pin`）、两套高亮 class 分开（OCR `.hl` / 单元格 `.hv`+`.pin`）、每个 `.view` 各自一个 `.imgwrap` 保 1:1。**点击图片全屏放大**（11-16）：`LIGHTBOX_HTML` 克隆整个 `.imgwrap`（含 svg 框），滚轮以光标为中心缩放 + 拖拽平移 + 1:1 原像素 + 适应窗口 + Esc 关闭 + 叠加框开关 + 「新窗口打开原图」绕过 iframe；缩放统一用 wrapper 的 `translate() scale()`，img 设原始像素宽高、svg 100%/100% 才不会错位。

# 项目长期约定（week-01/02 + mvp，CV 表格提取）

## 协作与环境
- 审阅方式：用户**不要**自绘 diff/UI 组件，也不要大段纯文本 diff；改动直接落工作区，用户用 IDE 的 git diff 看。助手只需简述改了哪些文件、做什么、验证结果。
- 环境：`paddle`（`D:\miniforge3\envs\paddle`，Python 3.10.9）；实跑用该环境 python.exe。用户偏好自己执行安装/运行命令，助手只做轻量验证；**例外**：用户明确说「重跑一下」时代跑完整流水线。
- 输入统一 `input/`，产物统一 `output/`；脚本配置区放文件顶部。
- 输出隔离：`output/<脚本名>/<输入名去后缀>/` 两层；中间页图放 `pages/`、`_tmp_pages/` 子目录，跑完保留供核对，重跑该 case 先清旧图再生成。每个 case 目录自包含（留 `source.<ext>` 副本）。
- 批量脚本一次跑完 `input/` 全部 case，不让用户改输入路径。
- 页码基准 **1 起**，与 PDF 阅读器一致：`enumerate(...,1)`，禁止 `i+1` 换算；重跑先清旧编号文件。
- 周笔记收敛单文件 `notes.md`，清理原文前确认已被 git 跟踪、主笔记自包含、全仓无其它引用。

## week-02 case / 表格规则
- 命名唯一真相源 `case_naming.py`（`case_sort_key()` 等），禁止别处写死 case 名或靠 `name[:2].isdigit()` 猜分组。合成样本 `01~18`+`20~28`（编号<101），真实 case 从 101 起 `101_real_xxx`；真实组恒排最后，必须 MD5 去重。
- 表格提取 = **对所有 case 全量检测、命中才提取**，无白名单；`TABLE_EXTRACT` 总开关。检测不到就 skipped、不写表格文件。文本（`texts`/OCR）与表格（`structured_tables`）在 result.json **同时保留**。
- 103（文本层 PDF）用 pdfplumber 直读 24×8 真表，按页面真实横线 `lines` 切行（不是按文字行，否则成 105×8 碎表）；105（CSV）读成 1 张表；107（扫描图）PPStructureV3 表格模型自动转正 5×8。
- 有文本层 PDF **不要转图走 OCR 模型**：判载体 → lattice/stream → 人工列边界模板 → 失败页转图 → 业务校验。无竖线 stream 型必须回退 `text`。week-01 `weekend_pipeline.py` 与 week-02 `text_layer_extract.py` 各维护一份，不互相 import。
- 表格专项 case 20~28 由 `make_table_cases.py` 生成（只写 input/+manifest，不动提取脚本）：20 跨3页、21 一页双表、22 合并单元格、23 跨页+多表、24 无线框、25 扫描2页、26 三表+噪声、27 旋转双表图、28 空页混合。生成技巧：pymupdf `fontname='china-s'` 写真实中文文本层；合并单元格把内线**分段画**，find_tables 才返回 None。重跑 `make_samples.py` 会重写 manifest，需再跑本脚本补登记。
- 已知限制（未改）：`render_first_page()` 只出 p1.png，多页第2页起的表无图可叠；纯文字页被 `text` 策略误抽成伪表（28 p1 成 3×1）。
- 重跑清理只删表格类旧产物（`tables.json`/`table_*.csv`/`pages/*.png`），别删 result.json/boxes.png/source.* —— 批量删 >50 触发沙箱 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 中断。`grid_score()` 加 try/except 保护。

## PaddleOCR 3.7.0 / PaddleX 3.7.0 坑
- 要画框叠原图：构造加 `use_doc_orientation_classify=False, use_doc_unwarping=False`（否则坐标基于矫正图、整体错位）。只取文字不画框可保留默认（UVDoc 让亮字暗底截图识别更好）。用户不接受只看 JSON，一律配「带框 PNG + 离线 HTML 报告」。
- HTML 框必须 1:1：`<img>`+`<svg>` 一起包进 `position:relative;line-height:0` 的 `.imgwrap`，svg `left/top:0;width/height:100%`，viewBox 用原图像素。禁止相对被 grid stretch 的 `.stage` 用 `calc(100%-28px)`（扁图 102 曾纵向拉 3.10×）。带框 PNG 用 `width=2` 去圆角。
- 表格表格区块整行宽度、默认收起（`.tblbody` hidden + `.tbltoggle` 展开，跳转徽标先展开再滚动）；CSV 下载用 base64 data URI 自包含。改报告只跑 `python vis_ocr_result.py`（秒级，不重跑 OCR）。
- PaddleX `result.save_to_html()`：`res.html` 空会抛 IndexError、多表只写第一张。统一先判空、从 `parsing_res_list` 的 `[table]` block 兜底、多表按 key 拆。
- pymupdf 渲染被裁剪的 PDF 要 `page.set_cropbox(page.mediabox)` 才出整页。

## 表格单元格坐标回溯（11-16 定稿，用户选「矫正图视图」）
- **不要为拿坐标关 UVDoc**：实测 107 关掉后 50 格有 12 格退化，换 server 模型也补不回。UVDoc 只输出 `doctr_img`、不暴露变换场，非线性形变无法精确逆变换。
- 正确做法：把 `doc_preprocessor_res["output_img"]` 另存 `<case>/pages/rectified.png`，`cell_box_list` 1:1 叠上去，报告提供「原图/矫正图」切换。文本链路不动、零额外推理。
- 103 走文本层空间：`find_tables()`（不用 `extract_tables()`，丢坐标）→ `Table.rows[i].cells` × DPI/72；`clean_table()` 删空行空列须同步删/补 bbox。`cells[r][c]` 与「表头1行+数据n行」严格同形；colspan 展开格共享同一框序号。CSV `coord.space='none'`。

## mvp/ 独立 Web 工具（11-16）
- 模块化：`config.py`（唯一配置源）、`app.py`（FastAPI 路由+后台任务）、`pipeline/`（engines/ocr/pdf/plain/table_model/structure/runner）、`report/`（cards/builder + assets 独立 css/js/html）、`check_env.py`、`requirements.txt`、`.gitignore`。源码模块化，但 builder 生成报告时内联 CSS/JS → `output/index.html` 自包含可拷走。
- 懒加载彻底：`import app` 0.5s，只 FastAPI；后台线程才 import pipeline；单例 `_OCR/_STRUCT` 首次调用才构造；表格模型 `grid_score()` 预筛命中才加载。故 `--workers 1`。`CV_MVP_WARMUP=1` 可 lifespan 预热（默认关）。
- 依赖坑：`paddleocr 3.7.0` 不带 paddlepaddle，须单列 `paddlepaddle==3.2.0`；cv2 来自 `opencv-contrib-python==4.10.0.84`（别装 opencv-python）；pdfplumber/PyMuPDF 自备；base64 JSON 上传不需 python-multipart；Starlette 1.x 静态文件不需 aiofiles。`PADDLE_PDX_CACHE_HOME` 指向 `official_models` 上级可离线部署。`CV_MVP_HOST/PORT/MAX_FILE_MB/WARMUP` 环境变量覆盖。
- **零 IDE 配置方案（用户明确不要改 .idea）**：内部模块一律包方式加载 —— `pipeline/*.py`/`report/*.py` 用 `from .. import config`；`app.py`/`check_env.py` 用 `importlib.import_module(PKG+'.xxx')`（`PKG=basename(ROOT)`）。0 处顶层绝对导入，四种启动方式（python mvp/app.py、cd mvp&&python app.py、uvicorn app:app、uvicorn mvp.app:app）实测通过、改名也能跑。**曾改 `algs/algs.iml` 和 pyrightconfig.json 已全部回退，不要再动 IDE 配置**。
- 命名：批次前缀 `YYYYMMDDHHmmss`（14 位含秒），input/output 共用；例 `20261116160643_103_real_xxx.pdf` → `output/20261116160643_103_real_xxx/`。**只加前缀不改原名**（源文件 `103_` 保留）；剥前缀只在 `pdf.py::template_lines()` 查模板时剥时间戳段 `^\d{12,14}_`，再试「带编号原名/去编号语义名」两键。同秒重复加 `-2/-3`。`output/index.html` 只是最近批次汇总。
- **调试参数面板（11-16 定稿）**：`mvp/params.py` 是参数唯一真相源（`SCHEMA` 的 order=页面优先级，`normalize()` 校验钳制+警告，`describe()` 出报告快照）；前端从 `GET /api/params` 动态渲染、后端同 schema 校验，无漂移。8 项按优先级：① `page`（只跑指定页、超页夹末页）② `table_strategy` ② `column_lines`（特殊版式临时覆盖自动推断）③ `grid_min_h/v` ④ `det/box_thresh`（predict 按次覆盖不重建单例）⑤ `dpi`（坐标同步缩放）。全 predict 级/纯参数，每批可不同。透传 app.upload→run_batch→extract_one→各模块；`result.json` 带 `params_snapshot`/`page`，报告页头 `.paramsnap` 折叠区、`/api/status` 带 params。引擎构造级（模型/文档预处理/UVDoc）刻意不放。**仍未做**：跨页全页+报告页签+拼接（结构性）、对照模式。
- **列边界不再写死任何 case（11-16 用户问「固定版式代码还有用吗」后清理）**：config 的 `TABLE_COLUMN_LINES`/`_BANK_LINES` 与 `pdf.py::template_lines()` 已删。`pipeline/pdf.py::_lines_from_edges()` 从 PDF 横线端点聚类还原列边界（实测 103 与人工模板逐字一致 25×8），`auto_column_lines()` 判据「端点数==文字数+1」才用端点法、否则回退 `_lines_from_words()`（多表混叠时端点法会把列虚高）：全 case 回归 103 25×8 / 20 7×5 / 21 11×5 / 22 6×4 / 23 6×5 / 24 6×4 / 26 11×2 / 28 3×1 全 OK。特殊版式用页面 `column_lines` 参数覆盖，不写死文件名。
- 报告交互：单格定位（cellbox 默认 display:none，hover 加 `.hv`、点击 `.pin`，点击 `ensureView()` 自动切宿主视图；整表网格 `.all` 默认关）、表格默认收起、多表 tab 只激活当前表框（`.off` class 不用 inline style）、两套高亮分开（OCR `.hl` / 单元格 `.hv`+`.pin`）、每 view 各自 `.imgwrap` 保 1:1、点击图片 lightbox 全屏（滚轮缩放+拖拽+1:1+适应窗口，`translate() scale()` 作用于 wrapper）。
- **运行日志（11-17）**：新增 `mvp/runlog.py`，`RunLog` 一批次一实例，同时写 `STATE['logs']`（结构化 {t,ms,level,stage,msg}，页面 `/api/status` 轮询）与 `output/<批次戳>/run.log`（`GET /api/logs` 下载）。pipeline 只认注入的 `emit(level,stage,msg)` 回调，不反向依赖 Web 层。上传页加进度条 + 分级配色日志面板（info/ok/stage/warn/error）。内部决策（预筛数值、策略、模型加载、坐标空间、耗时）全可见。
- **doc_unwarp 参数（11-17，用户指出 108 电子版截图不该矫正）**：`params.SCHEMA` 第 9 项，on/off，默认 on。实测 108（103 的电子版平整截图）开 UVDoc 时框被撑到 x=0.1~910 贴满整页、多 25 个空 td；关掉后 `angle=-1`、`output_img` 与原图**逐像素差 0**、框 x=23.5~882 贴合真实表格。故关矫正时 `coord.space='source'`、不落 rectified.png、框直接叠原图 1:1。`engines.structure(use_unwarp)` 按 bool 分两槽缓存单例，两种配置各加载一次、互不污染。**按载体选：平整电子版→off，旋转/弯曲扫描件→on（与 week-02「不要为拿坐标关 UVDoc」不矛盾，那条针对 107）**。107/108 是现成 A/B 对照。

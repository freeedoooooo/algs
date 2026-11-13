# 第 1 周笔记（P0 · 环境 + PaddleOCR）

> 边学边记。卡住的点、试出来的经验、对 OCR 的新认识，都写这里。
> **本周只保留这一份笔记**：11-02 的问答全稿与无影云工作站手册已于 2026-11-13 归并进来后清理，
> 两者都被 git 跟踪，需要原文可用 `git checkout -- <文件路径>` 恢复。
>
> 📌 2026-11-09 补：`weekend_pipeline.py` 三个 TODO 已完成，并补了面向初学者的详细注释。
> 📌 2026-11-12 补：四个脚本做了一轮工程优化，见文末「2026-11-12 优化记录」。
> 📌 2026-11-13 补：流水线改成**批量扫 `input/` + 每个 case 独立输出目录**，
> 并新增图片 / CSV 两条分支，见文末「2026-11-13 优化记录」。
> 📌 2026-11-13 再补：全仓输出统一为 **`output/<脚本名>/<输入名>/` 两层隔离**，
> 中间产物再单独一层子目录；`output/` 根目录旧产物已清理，见文末「全仓两层输出隔离」。
> 📌 2026-11-13 补：两份旧文档的结论已提炼进下方「本周结论速查」（A = 11-02 实测知识，
> B = 无影云工作站手册摘要与过期项）。本文件已自包含，不再依赖任何外部 md。

## 本周结论速查（先看这里）

> 归并自 11-02 的 11 节问答全稿 + 无影云工作站手册（两份原文已清理）。
> 这里保留**可复用的结论与关键实测数据**，过程性问答、完整命令清单不再重复；
> 具体排错过程仍看后文「卡住的点 & 怎么解决的」。

### A. 11-02 实测结论速查

**环境与包管理**
- 本机：miniforge 环境 `paddle` / `D:\miniforge3\envs\paddle` / Python 3.10.9；
  `requirements.txt` 锁 `paddlepaddle==3.2.0`(CPU)、`paddlex==3.7.2`、`paddleocr==3.7.0`、
  `pdfplumber==0.11.10`、`pymupdf==1.28.2`、`matplotlib==3.10.9`。
- 三条规矩：不带版本号的 `pip install` **会升级**；conda 环境里继续用 pip
  （`conda install` 的求解器可能顺手升降 numpy，把 paddle 弄坏）；统一 `python -m pip`
  保证装进当前解释器（本机存在 `python` 3.13 / `pip` 3.12 不一致的情况）。
- 版本方向是「先定 Python → 包必须有对应轮子」：`matplotlib==3.11.2` 装不上是因为它要求
  Python ≥3.11，与 paddle 无关；paddlepaddle 3.2.0 其实有 cp313 轮子（支持 3.9~3.13）。
- CPU / GPU 包互斥，换 GPU 要**同版本** `paddlepaddle-gpu==3.2.0`；
  `3.2.0 outdated (latest 3.3.1)` 只是提醒、不是错误，已验证组合别动。

**三层架构（本周最重要的概念）**
- `paddlepaddle 3.2.0` 框架（发动机）→ `paddlex 3.7.2` 产线编排 + 模型下载缓存 + 统一结果
  （变速箱 + 零件库）→ `paddleocr 3.7.0` 开箱即用的类（整车）。
- paddlex 具体管 5 件事：产线编排（版面检测 → 表格分类 → 结构识别 → 单元格检测 → OCR）、
  单模型的加载/预处理/推理/后处理封装、模型下载与缓存（`~/.paddlex/official_models/`）、
  YAML 默认配置、统一结果对象（`save_to_html` / `save_to_json` / `save_to_img`）。
- **排错归属**：换模型、调阈值、模型下载、导出 HTML，90% 是 paddlex 的事，不是 paddleocr。
- 模型不是「自动追新」：3.7.0 把默认映射改成 `PP-OCRv6_medium`，本地缓存没命中才去下载；
  惰性按需、下过一次就复用。`PADDLE_PDX_MODEL_SOURCE=BOS` 走国内源，但大文件断连仍会
  回退 HuggingFace（365MB `SLANeXt_wired` 就是这样，靠 curl 断点续传解决）。

**性能**：加分段耗时日志后立刻定位到「CPU 上跑 server 大模型」，换小模型即可：

| 模型 | 加载 | 单张推理 | 总计 |
|---|---|---|---|
| `PP-OCRv5_server` | 17.3s | 103.8s | 121s ❌ |
| `PP-OCRv4_mobile` | 3~7s | 3~5s | 5.8~12.4s ✅ |

精度几乎无损（照样认出"招商银行"），快 10~27 倍。根因不是加载慢，是 **CPU 跑 server 大模型**。

**3.x API 四个坑**：`use_angle_cls`→`use_textline_orientation`、
`.ocr(cls=True)`→`.predict()` + `rec_texts/scores/polys`、`PPStructure`→`PPStructureV3`、
`import fitz`→`import pymupdf`；结果多一层 `res.json['res']`；
`save_to_html()` 缺 `<meta charset>` → 中文按 GBK 解码变乱码（和 11-13 的 GBK CSV 同源）。

**PDF 专题（本周重头戏）**
- `pdfplumber` 读文本层（底层 pdfminer），`pymupdf` 渲染成图（MuPDF 绑定）；
  PaddleOCR **直喂 PDF 一律经 paddlex/pypdfium2 转图**（`PDFReaderBackend` → 逐页 `read()`），
  `paddleocr` 包里一行 PDF 代码都没有，也**不会先判断有没有文本层**。
- **MediaBox = 纸张尺寸 + 坐标系基准；CropBox = 显示 / 打印视口**（缺省时 = MediaBox）。
  页面字典里还有 BleedBox / TrimBox / ArtBox，5 个 Box 全是元数据，改哪个都不动内容流。
  `test3.pdf` 是 `/MediaBox [0 0 595 842]` 配 `/CropBox [0 699.482 595 842]`，
  只露出顶部 142.518pt（约 A4 的 1/6），下方 30+ 行流水仍完整留在文件里。
- **裁剪 = 隐藏，不等于删除**。查字节结构后判断是「程序化裁剪」而非人工裁坏：
  `%%EOF` / `startxref` 各 1 次（无增量更新）、仅 17 个 xref 对象且无 Producer/Creator
  （脚本产物）、`699.482` 是非整数（程序算的，不是鼠标拖的）。
- 同一份 PDF 四种读法，差别不在工具好坏，而在「读可见区」还是「读全部内容流」：

| 方式 | 读的范围 | 结果 |
|---|---|---|
| pdfplumber `extract_text()` | 全部内容流 | **2054 字符**（0.17s） |
| pdfplumber `page.crop(cropbox)` | 仅可见区 | 143 字符 |
| pymupdf 默认 `get_text()` | 可见区 | 144 字符 |
| PaddleOCR 直喂 PDF | 可见区 | 145 字符 / 19 行 / 2.5s |
| CropBox 改整页后渲染 → OCR | 整页 | 1802 字符 / 226 行 / 14.1s |

- 涉密内容必须真删，设 CropBox 无效。三种做法：设 CropBox → 文字还在、`extract_text()` 抽得到；
  **redaction 擦除** → 真删、抽不到；渲染成图再生成 PDF → 文字变像素、只能靠 OCR。
  擦除代码（PyMuPDF）：

```python
page.add_redact_annot(pymupdf.Rect(0, 0, 595, 699.482))
page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_REMOVE)
doc.save('out.pdf', garbage=4, deflate=True)
```

- 工程原则：**先分流，能用文本层就绝不用 OCR**（OCR 是像素→文字的有损重建）。
  判断方式：抽前几页看字符数（`MIN_CHARS=50`）；有则直接抽字（毫秒级、100% 准确、可复制、带坐标），
  无（扫描件）才转图 OCR。例外：文本层损坏缺 ToUnicode、需要版面/表格结构、印章/手写/公式。

**Python 基础与工程习惯**
- `if __name__ == '__main__':` 主程序守卫：直接运行才执行 `main()`，被 `import` 不执行。
  现在 `b` / `d` / `weekend_pipeline` 都加了守卫（11-12 优化），可以安全复用。
- 输入 / 输出路径 + 常用参数统一放文件顶部【配置区】，命令行参数优先级更高；
  流水线 11-13 起改为不带参数就批量扫 `INPUT_DIR`。

### B. 无影云工作站说明（外部机器专用，原文已清理）

原《无影环境搭建说明.md》是**早期写给另一台机器**（阿里云无影云工作站，Windows + GPU）的
手动安装手册，目标是一次性装好 GPU 版 Paddle、让 P1 训练阶段直接复用、不再重装。
本机实际用的是 miniforge `paddle` **CPU** 环境，两者不是同一套配置；这份手册内容已过期，
所以 11-13 归并时只保留「流程 + 冲突清单」，不搬运那些有误的 PowerShell 命令全文。

七步流程：仓库同步到无影 → `nvidia-smi` 查 CUDA → 装 Miniconda → 建 Python 3.10 环境
→ 按 CUDA 版本装 GPU 版 paddle（失败回退 CPU）→ 装其余依赖 → 冒烟测试 + 跑 `b_ocr_image.py`。

⚠️ **与本机 11-02 实测冲突的地方，照抄前必须先改**：

| 文档写法 | 实测 / 现行结论 |
|---|---|
| 环境名 `ocr` | 本机是 miniforge 环境 `paddle` |
| 「PaddlePaddle 只支持到 3.11，3.13 装不上」 | paddlepaddle 3.2.0 有 cp313 轮子、支持 3.9~3.13；装不上的是 `matplotlib==3.11.2`（要求 Python ≥3.11） |
| GPU 版 `2.6.2` / `3.0.0` | 锁的是 3.2.0，换 GPU 应同版本 `paddlepaddle-gpu==3.2.0` |
| `pip install paddleocr pdfplumber ...` 不带版本 | 会升级已装包，应用 `python -m pip install -r requirements.txt` |
| 裸 `pip install ...` | 统一 `python -m pip`，避免装进别的解释器 |
| 步骤 7「图片命名 `test.png` 放在 week-01/ 下」 | 输入统一放 `input/`，`b` 的配置区 `INPUT_IMAGE` 默认 `test2.jpg`；产物已是带框 PNG + HTML 报告 |
| 「首次下载模型慢，等一次即可」 | 默认 v6 模型会卡 HuggingFace，需 `PADDLE_PDX_MODEL_SOURCE=BOS` + 显式指定已缓存的 v4 mobile |
| 「`.ocr()` 不存在就改调用方式」 | 四个脚本早已全部改成 3.x API，无需再改 |

> 原手册已清理（被 git 跟踪，可恢复）。若以后真要在无影上执行，先按上表修订，
> 并以上面 A 节的实测结论为准。

## 我跑通了什么
- ✅ 环境：miniforge 环境名 `paddle`（`conda activate paddle`），Python 3.10.9，`requirements.txt` 全锁版本
- ✅ `b_ocr_image.py`：test2.jpg 识别 20 行，置信度 0.88~1.00（换 mobile 模型后 5.8~12.4s）；2026-11-12 起额外产出带框 PNG + 离线 HTML 对照报告
- ✅ `c_pdf_text_layer.py`：test3.pdf 0.34s 抽出 2054 字符；转图分支可用；新增逐页字符数概览
- ✅ `d_table_ocr.py`：test2.jpg → 4 个内容块 + 表格 HTML（乱码已修）
- ✅ `weekend_pipeline.py`：三个 TODO 补全；**2026-11-13 起改为批量跑 `input/` 全部 case**，
  不再手改输入路径。每个输入单独输出到 `output/weekend_pipeline/<文件名>/`，总览写在
  `output/weekend_pipeline/batch_summary.json` / `.txt`。实跑 5/5 成功（2 图片 + 2 PDF + 1 CSV）
- ✅ `weekend_pipeline.py` 的 OCR 分支首次实跑通过：`test3_image.pdf` 5 页 → 197 行 / 1750 字符 / 35.48s（关闭表格开关），中间页图 5/5 自动清理；批量模式下默认开表格重跑为 60.11s，产物仍落在自己的目录里
- ✅ `b`、`d` 已改成 `main()` + 主程序守卫（2026-11-12 优化）；`import` 三个模块仅 0.38s，不再加载模型
- ⬜ 3B1B 第 1 集：笔记里没记录，需自评

## bad case 观察（同步记到 ../week-02/bad_cases/notes.md）
- `test1.jpg`：深色背景终端截图（亮字暗底）→ 第1周当时用默认模型实测识别全乱码、置信度约 0.2。猜测：训练数据几乎都是暗字亮底。可试反色预处理。
  - 2026-11-12 复测（week-02 `a_batch_ocr.py`，v4 mobile + 文本行方向分类）：识别出 6 行、平均置信度 0.90。与第1周结论不同，说明**模型与预处理开关会显著改变结果**；这条样本仍值得收进 bad case 库，但归因笔记要写成两次实测的对比，而不是「必然失败」。
- `test3.pdf` 的 CropBox 裁剪：同一文件 4 种工具读出 143 / 144 / 145 / 2054 四种结果，差异来自「读内容流」还是「读可见区」。
- 有文本层却走 OCR：只拿到约 8% 内容，且 `15:47` 被认成 `15：47`（半角→全角）；密集小字整行漏检。

## 卡住的点 & 怎么解决的
- **首次跑 b 像卡死**：3.7.0 默认模型变成 `PP-OCRv6_medium`，本地缓存没命中 → 从 HuggingFace 下载卡住。改为显式指定已缓存的 `PP-OCRv4_mobile_*`，并设 `PADDLE_PDX_MODEL_SOURCE=BOS`。
- **一张图要 121s**：加分段耗时日志后定位到「CPU 上跑 server 大模型」（加载 17.3s + 推理 103.8s）。换 mobile 后 5.8~12.4s。
- **API 全报错**：3.x 把 `use_angle_cls` / `.ocr(cls=True)` / `PPStructure` / `import fitz` 全换了，逐项改成 `use_textline_orientation` / `.predict()` / `PPStructureV3` / `import pymupdf`。
- **表格模型下载断线**：365MB 的 `SLANeXt_wired` 从 BOS 断线后回退 HF；用 curl 断点续传下 tar，解压到 `~/.paddlex/official_models/`。
- **HTML 打开是中文乱码**：paddlex `save_to_html()` 输出 UTF-8 但没有 `<meta charset>`，浏览器按 GBK 解码 → 补完整 HTML 骨架 + charset。
- **结果取不到**：`PPStructureV3` 的结果多一层，要 `res.json['res']['parsing_res_list']`。

## 对"OCR = 检测 + 识别"的初步理解
- 检测（det）回答「字在哪」→ `rec_polys` 四点框；识别（rec）回答「是什么字」→ `rec_texts` + `rec_scores`。两步是两个独立模型，串起来才是一行结果，所以「漏检」和「认错」是两类不同的失败。
- 表格不是普通 OCR 能做的：还要版面检测 + 表格分类 + 结构识别 + 单元格检测，所以走 `PPStructureV3` 多模型产线，慢得多。
- OCR 是「像素 → 文字」的有损重建；PDF 有文本层时直接抽字又快又准，所以工程上先分流再决定要不要动用模型。

## 2026-11-12 优化记录（四个脚本）

- **可复用性**：`b_ocr_image.py`、`d_table_ocr.py` 原来是「脚本式写法」，所有代码在模块顶层，
  一 `import` 就会立刻跑一遍识别。现在都收进 `main()` + `if __name__ == '__main__':` 守卫，
  并把 `paddleocr` 的 import 挪进构造函数里做懒加载 —— 被 import 时不再加载几秒的模型。
- **消除警告**：显式指定 `*_model_name` 时 3.7.0 会忽略 `lang` 并打印警告，
  三个用到 PaddleOCR 的脚本都删掉了 `lang='ch'`。
- **统一模型源**：`b` 补上了 `PADDLE_PDX_MODEL_SOURCE=BOS` 等两行环境变量
  （必须在 import 前设置），换模型时不会再卡 HuggingFace。
- **坐标基准（重要）**：`b` 默认关闭 `use_doc_orientation_classify` / `use_doc_unwarping`，
  因为要把 `rec_polys` 画回原图；`weekend_pipeline.py` **保留默认开启**，
  它只取文字不画框，UVDoc 对亮字暗底的图识别更好。这是两种场景的不同取舍，别统一。
- **结果呈现**：`b` 原先取了 `boxes` 却从未使用（死代码）。现在用它生成
  `output/b_ocr_image/<输入名>/b_ocr_boxes.png` + 自包含的 `b_ocr_report.html`（图片 base64 内嵌，
  单独拷走 HTML 也能显示）；低置信度行标橙红。
- **真 bug**：`d` 用 `os.makedirs('output')` 写死目录，把 `OUT_HTML` 改到别处会报错；
  多结果时 `save_to_html` 还会互相覆盖；静默把缺失输入换成 `test2.jpg` 也容易误导。三处都已修。
- **文档一致性**：`c` 的 `has_text_layer()` 实际返回 3 个值，docstring 却写 2 个；
  新增逐页字符数概览，能看出混合型 PDF。README 里 `conda activate ocr`、
  2.x 的 `.ocr(cls=True)` 示例、默认 PDF 与产物文件名也都同步成本机实际值。
- **流水线收尾**：`weekend_pipeline.py` 的 OCR 分支当时跑完会自动删掉中间页图
  （配置区 `KEEP_TEMP_IMAGES` 可关；该开关和自动删图已在 11-13 晚移除，见下节），
  `cropbox_is_limited()` 遇到损坏 PDF 不再让主流程崩掉。
  另修了 `pdf_pages_to_images(pdf_path, dpi=DPI, out_dir=OUT_DIR)` 的**默认参数快照**问题：
  Python 在定义函数时就把默认值算好固定了，之后改 OUT_DIR 不生效；改成 `None` 再在函数体内读配置。
- **验证**：四个脚本 `py_compile` 通过；`import` 三模块 0.38s 不加载模型；
  b 产出 21 行 + 带框图（目视确认框精确套字）+ 自包含 HTML（charset / base64 / 21 行表格齐备）；
  c 两条分支正常（扫描件转 5 张图 0.72s；文本层 2054 字符 0.34s，逐页字符数 `[2054]`）；
  d 4 个内容块 + HTML 无嵌套无乱码；weekend 文本层 0.48s / 2054 字符，OCR 分支首次跑通。

## 2026-11-13 优化记录（流水线批量化 + 输出隔离）

**要解决的问题**：流水线的定位是「把 b/c/d 串起来」，但原来每次跑都要手改配置区
`INPUT_PDF`；而且所有结果都写 `output/output.json`，换一个输入就把上一个覆盖掉了，
不同 case 的产物混在一起没法对照。

- **批量入口**：配置区 `INPUT_PDF` → `INPUT_DIR='input'`。`collect_cases()` 扫描目录、
  按文件名排序、只保留 `SUPPORTED_EXTS` 里的类型；`run_batch()` 循环调用 `run()`，
  单个 case 出错只记一笔失败、继续跑下一个（和 week-02 `a_batch_ocr.py` 同款写法）。
  新增 case 只要丢进 `input/`，下次运行自动被扫到。
- **每个 case 独立目录**：`case_out_dir()` 按文件名（去后缀）生成
  `output/weekend_pipeline/<stem>/`（上午是 `output/<stem>/`，下午再加一层脚本名）。
  用一个 `set` 记录已用过的名字，处理 `a.pdf` 与 `a.jpg` 这种重名撞车。
  `OUT_JSON` / `OUT_TXT` 从「完整路径」改成「文件名」，由 `save_result()` 拼到各自目录里。
  中间页图、表格 HTML 也全部跟着传 `out_dir`，不再堆在 `output/` 根目录互相覆盖。
  顺带解决了一个历史隐患：根目录 `_tmp_page_0~4.png` 已被 git 跟踪，
  以前跑默认 OCR 分支会覆盖并删除它们；现在中间图在子目录里，不会碰那 5 张
  （下午统一清理旧产物时这 5 张一并删除了，均可从 git 恢复）。
- **补齐两条分支**（否则「所有 case」会漏掉 3 个）：图片直接 `ocr_image()`（没有文本层概念，
  也绝不清理输入原图）；`.csv/.txt/.md` 直接读文本、完全不加载模型。
  `input/test4.csv` 是 Excel 另存的 **GBK** 中文，直接按 utf-8 读会报错/乱码，
  所以 `read_plain_text()` 按 `utf-8-sig → gbk → latin-1` 逐个试编码，
  并把实际用的编码记进结果字典 —— 和 d 的 HTML 乱码是同一类「字节没错、解码规则没说清」问题。
  CSV 另用 `csv.reader` + `io.StringIO` 解析成表格，三条分支的 `tables` 就都有产出了。
- **汇总表**：`output/weekend_pipeline/batch_summary.json` / `.txt` 列出每个 case 的
  类型 / 识别方式 / 页数 / 字符数 / 表格数 / 耗时 / 输出目录。
  统计表格数时踩了一个口径坑：OCR 分支的 `tables` 里是「**每页一条检查记录**」
  （哪怕该页 0 个表格），文本层/CSV 分支则是「一个元素 = 一张表」，
  所以加了 `count_tables()` 区分，否则 `test3_image` 会被虚报成 5 个表格（实际 1 个）。
- **向后兼容**：`main()` 不带参数 = 跑全目录；带一个文件 = 只跑它（仍单独建目录）；
  带一个目录 = 跑指定目录。`run(input_path, out_dir=None)` 也保留默认参数，
  别的文件 `import` 后直接 `run('a.pdf')` 仍然可用。
- **验证**：`py_compile` 通过；默认配置（表格开启）完整批量 5/5 成功、94.33s；
  `test1.jpg` 254 字 / `test2.jpg` 169 字 / `test3.pdf` 2054 字 /
  `test3_image.pdf` 1750 字 / `test4.csv` 79 字（gbk）；中间图 5/5 自动清理；
  两个表格 HTML 均带 `charset="utf-8"`、无嵌套；单文件模式、空目录提示、
  不支持类型提示均正常（当时 `output/` 根目录的历史文件未动，下午已统一清理，见下节）。

### 同日追加：全仓两层输出隔离（2026-11-13 下午）

**要解决的问题**：上午只给流水线做了「按输入分目录」，但 b / c / d 三个脚本仍把产物
直接写在 `output/` 根目录；四个脚本的产物和 5 个 case 目录混在一起，分不清哪个文件
是谁生成的。`output/` 根还堆着 34 个历史文件。

- **统一规则 `output/<脚本名>/<输入文件名>/`**：四个脚本各有自己的 `OUT_DIR`
  （`b_ocr_image` / `c_pdf_text_layer` / `d_table_ocr` / `weekend_pipeline`），
  再各加一个 `case_dir()` 按输入文件名（去后缀）建第二层。`b` / `d` 的输出配置项
  从「完整路径」改成「文件名」，由 `os.path.join` 拼到 case 目录；
  `c` 顺带修了 `pdf_to_images(dpi=DPI, out_dir=OUT_DIR)` 的**默认参数快照**坑。
- **中间产物再单独一层**：`c` 转出的页图放 `<case>/pages/`；
  `weekend_pipeline` 的 OCR 临时页图放 `<case>/_tmp_pages/`，**跑完保留**供逐页核对。
  每次生成新页图前，`prepare_temp_dir()` 只删除该目录里 `_tmp_page_*.png` 旧图
  （不递归、不删子目录、不碰其它文件），避免新旧页图混在一起。
  正式结果（`output.json` / 表格 HTML）和中间图始终不在同一层。
- **汇总表归位**：`batch_summary.json` / `.txt` 放在 `output/weekend_pipeline/` 根，
  属于所有 case 共有，不属于任何单个输入。
- **日志可读性**：四个脚本各加 `show()`，只在打印和写汇总表时把 Windows 的 `\`
  显示成 `/`，实际读写路径一个都不改 —— 避免 `output/weekend_pipeline\test1` 这种斜杠混用。
- **清理旧产物**：`output/` 根目录下 21 个散文件 + 5 个旧 case 目录（共 34 个文件）全部删除。
  删前逐个 `git cat-file -e HEAD:<path>` 确认都在 git 里，
  恢复用 `git checkout -- "20-CV/weekly/week-01/output"`。
- **验证**：四脚本 `py_compile` 通过；`import` 四模块 0.29s 不加载模型；
  b / c / d 实跑确认各自落到 `output/b_ocr_image/test2/`、
  `output/c_pdf_text_layer/test3_image/pages/`、`output/d_table_ocr/test2/`；
  `weekend_pipeline` 批量 5/5 成功、104.29s；单独验证 `_tmp_pages/` 生成 5 张图、
  清理后目录自动消失、case 目录只剩 3 个正式产物（**这是当时的「跑完自动删」策略，
  当晚已改成跑完保留，见下节**）；4 个 HTML 均带 charset；
  汇总表与各 case 的 `output.json` 数据对齐。

### 同日再追加：临时产物跑完保留（2026-11-13 晚）

**要解决的问题**：跑完就删，检查时看不到 `_tmp_pages/`，想核对「OCR 到底看的是哪张
渲染图」只能把 `KEEP_TEMP_IMAGES` 改成 `True` 再重跑一遍；但直接改成永不清理，
又会有新旧页图混在一起、分不清哪张是本轮的风险。

- **策略改为「跑完保留 + 重跑前清空」**：移除 `KEEP_TEMP_IMAGES` 开关与
  `cleanup_temp_images()`（原来挂在 `try/finally` 里删图、再 `os.rmdir` 删空目录），
  换成 `prepare_temp_dir(temp_dir)`，在 `pdf_pages_to_images()` **之前**调用：
  先清掉该 case 的 `_tmp_pages/` 里上一次的 `_tmp_page_*.png`，再生成新图，跑完不删。
  OCR 中途报错时页图也会留下，正好用来排查。
- **安全边界**：清理只认配置区 `TEMP_FILE_PREFIX` 前缀的 `.png` 普通文件，
  `os.listdir` 只看这一层、`os.remove` 只删文件；不递归、不删子目录、
  不碰 `input/` 原图和其它 case 的正式产物。
- **可追溯**：OCR 分支往 `output.json` 写了 `temp_dir` / `temp_pages` 两个字段，
  日志也会打印页图目录，事后翻结果能直接找到。
- **验证**（轻量，不加载模型）：`py_compile` 通过；首次生成 5 张图 →
  `prepare_temp_dir()` 清掉 5 张旧图，同目录里的 `_keep_me.txt` 和子目录均未被误删 →
  再生成 5 张并保留；用 stub OCR 在临时目录跑 `run()` 两遍，
  第二次先清旧图、页图仍是 5 张，`output.json` 的 `temp_dir` / `temp_pages` 正确。

### 同日再追加：d 脚本输入多页 PDF 报 IndexError（2026-11-13 晚）

**现象**：`python d_table_ocr.py`（输入改成 `input/test3_image.pdf`）日志里内容块打印正常，
但 `res.save_to_html(path)` 抛 `IndexError: list index out of range`，
`output/d_table_ocr/test3_image/` 一个 HTML 都没生成。

**根因（paddlex 3.7.0 的库 bug，不是识别失败）**：
`HtmlMixin.save_to_html()`（`paddlex/inference/common/result/mixin.py:555`）写的是
`html[list(html.keys())[0]]`；而 `PPStructureV3Result._to_html()` 只在
`table_res_list` 非空时才往字典里放表格（`layout_parsing/result_v2.py:313`），
**这一页没表格就返回 `{}`** → 取 `[0]` 越界。
`predict(5 页 PDF)` 一页一个结果，第 3~5 页是证书扫描图（只有 `[image]` /
`[header]` / `[figure_title]`），必然命中；第 1 页也没有表格，所以循环第一个就崩了。
另一个隐患：一页多张表时 `save_to_html(文件路径)` 只写第一张并打 warning，会丢数据。

**修法（`weekly/week-01/d_table_ocr.py`）**
- 新增 `export_html(res, path)`，**不再调 `save_to_html()`**：先读公开的 `res.html`
  （dict：表名 → HTML 片段）；为空则从 `parse_blocks()` 的 `[table]` 块
  `block_content` 兜底（3.7.0 有些结果 `table_res_list` 空但内容块里已有还原好的表格）；
  两者都空返回 `[]`，由调用方跳过该页并打印序号。
- 多张表按 `key` 拆成多个文件（`<stem>_<key>.html`），用 `open(..., encoding='utf-8')`
  自己写，和 `HtmlWriter` 行为一致；每个文件照样过 `ensure_readable_html()` 补 charset。
- `main()` 汇总打印：实际写出的文件数、无表格页序号；全部无表格时给出明确提示，不再抛异常。
- `weekend_pipeline.py` 的 `table_ocr_page()` 同源风险也加了 `result[0].html` 判空守卫；
  两个脚本的示例代码 / README / 目录树同步更新。

**结论**：`save_to_html()` 只能在**确认这一页有表格**时用；多页 PDF 必须先判空。
「没识别出表格」是正常业务结果，不该让导出方法把整个流程打断。

### 同日再追加：全仓页码统一从 1 起（2026-11-13 晚）

**要解决的问题**：`test3_image.pdf` 的表格肉眼在**第 2 页**，但 `output.json` 写 `"page": 1`、
表格叫 `pipeline_table_p1.html`。查下来不是识别错位，而是同一个脚本里混了两套基准：
`enumerate(images)` 的 `i` 从 0 起，日志却用 `i + 1` 显示「第 N 页」，
文件名和 JSON 又直接用了 0 起的 `i`。页图 `_tmp_page_0.png` 对应第 1 页也一样容易误读。

**定稿**：所有**可见页码一律从 1 起，和 PDF 阅读器一致**，不再有 `+1` 换算：

| 第 2 页 | 新命名 / 新值 |
|---|---|
| 中间页图 | `_tmp_page_2.png`、`c_page_2.png` |
| 表格 HTML | `pipeline_table_p2.html`、`d_table_out_2.html` |
| 结构化结果 | `output.json` 里 `"page": 2` |
| 文本 / 日志 | `--- 第 2 页 ---`、「第 2/5 页 OCR 完成」 |

**改动清单**
- `weekend_pipeline.py`：`pdf_pages_to_images()` / `extract_tables_text_layer()` /
  OCR 主循环全部改 `enumerate(..., 1)`；`table_ocr_page(image_path, page_no, ...)`
  参数名从 `page_index` 改成 `page_no`（语义更明确），`p{page_no}.html` / `'page': page_no`；
  图片分支传 1、CSV 分支 `page=1`；分页标记与进度日志去掉 `+1`。
- `d_table_ocr.py`：`main()` 两处 `enumerate(result, 1)`，`d_table_out_<页码>.html`、
  日志「第 N 个输入」、跳过序号全部 1 起。
- `c_pdf_text_layer.py`：`enumerate(doc, 1)` → `c_page_1~5.png`。
- **配套清理**（避免新旧两套编号并存）：`weekend_pipeline.clear_old_table_html()`、
  `d_table_ocr.clear_old_html()`、`c_pdf_text_layer.prepare_pages_dir()`，
  在各自重跑前按精确正则只删本脚本生成的页级文件；页图沿用「跑完保留、重跑前清旧」。
- `b_ocr_image.py` 不动：它的 `enumerate` 是 OCR **文字行**索引（内部用 `polys[i]`），
  展示给人的行号本来就是 `i + 1`，和页码无关。

**验证**（轻量，不加载模型）：三脚本 `py_compile` 通过；真实 PDF 转图得到
`_tmp_page_1~5.png` / `c_page_1~5.png` 并清掉旧 0 起文件；
清旧编号函数只删目标文件、`keep.txt` 保留；`table_ocr_page(2)` → `page=2` /
`pipeline_table_p2.html`，CSV → `page=1`；`run()` 分页标记为 1~5；
stub 引擎跑 `d.main()` 两次 → 只生成 `d_table_out_2.html`，第二次正确清旧再重建。
完整模型推理未代跑，用户自行执行。

## 11-13 晚 · 有文本层 PDF 里的表格该怎么解析（TODO 3 进阶）

**问题**：`test3.pdf` 有文本层、内容明明是一张银行流水表，但
`output/weekend_pipeline/test3/output.json` 里 `tables: []`、`batch_summary.txt` 表格数 0。
有文本层的 PDF 要不要解析表格？要不要转图走模型？

**结论**：**要解析，但不要整页转图走 OCR 模型**。文本层里的字符是精确的
（金额 `26,608,757.65`、`记录数: 1160`），还带坐标、字体、矢量线；
转图等于把结构化信息降成像素再猜回来，既慢又引入识别误差。
汇总表实测 `test3.pdf` 0.9s vs `test3_image.pdf`（OCR 分支）63.11s，差两个数量级。
模型只该用在「前几层都失败的那几页」或纯扫描件上。

**实测诊断**（pdfplumber 0.11.10 / pymupdf 1.28.2，不加载模型）

| 检查项 | 结果 |
|---|---|
| 页面线型 | 208 条边，**全是横线、0 条竖线** |
| `extract_tables()` 默认 | 0 张表 |
| `lines` 策略 | 0 张表 |
| `text` 策略 | 1 张 151 行 × 7 列（清洗前），「借 贷」被合并、大量空单元格 |
| `PyMuPDF find_tables()` | 0 张表 |
| CropBox / MediaBox | 142.5pt / 842pt；1830 个字符里 1706 个在裁剪区外 |

根因：默认与 `lines` 策略靠闭合网格（尤其竖线）切列，这文件只有行分隔线，切不出列；
`text` 策略靠文字 x 坐标猜列，但列间距不均、单元格内换行，结果列错位。
CropBox 那条再次印证「看到的 ≠ 抽到的」：阅读器只显示顶部一小条，内容流里是整张表
（`pg.bbox` 仍是全页 842pt，所以裁剪**不是**表格抽取失败的直接原因）。

**自动坐标聚类的尝试（失败，记录以免重踩）**：按 `page.extract_words()` 的
`x0` 做频率聚类推断列边界，阈值 10% / 15% / 25% 分别得到 9 / 7 / 6 条线，
抽出 8 / 6 / 5 列，但会把页眉「用户所属公司 / 打印时间」混进表头，填充率 0.28~0.39，
并不比 `text` 策略好。**手工标定** 9 条竖线
`[17, 112, 175, 265, 326, 393, 463, 532, 578]` 反而一次拆对 8 列表头：
`['交易日期','借','贷','余额','摘要','收(付)方名称','收(付)方账号','交易类型']`。
→ 固定版式（流水 / 对账单 / 发票）用「模板 + 人工坐标」最稳，别指望自动聚类。

**分层方案（通用）**
1. 判断载体：表格是字符还是贴图？贴图 → 直接第 4 步。
2. 文本层解析（首选）：lattice 型（有横竖网格）用 `lines` / camelot lattice /
   PyMuPDF `find_tables()`；stream 型（无竖线）用 `text` / camelot stream。
3. 坐标级兜底：`chars` / `words` 的 `x0`、`top` 聚类，或人工标定列边界。
4. 仅失败页转图 → PPStructureV3 / Table Transformer，不整份转。
5. 业务校验：行数、列数、金额能否 `float()`、余额连续性、跨页表头；
   由这一步算置信度，低分才触发下一层。

**本次改动**
- `weekend_pipeline.py` 配置区新增 `TABLE_STRATEGIES`、`TABLE_MIN_FILL_RATIO`、
  `TABLE_COLUMN_LINES`（按文件名映射的人工列边界，默认给 `test3.pdf` 配好）。
- 新增 `build_table_settings()` / `clean_table()` / `table_strategies_for()`；
  重写 `extract_tables_text_layer()`：诊断线型 → 策略回退（命中模板时 explicit 优先）
  → 清洗空行空列 + 填充率打分 → 全失败时明确打印排查建议。
- 表格记录新增 `strategy` / `n_rows` / `n_cols` / `fill_ratio` / `low_confidence`
  （**故意不含 `table_count`**，否则 `count_tables()` 会误判成 OCR 的一页记录）。
- `run()` 日志打印策略与质量，`text` 策略额外提示「可能合并/错列，建议人工核对」。
- `README.md` 补「有文本层 PDF 的表格解析」小节。

**验证**（轻量，未加载模型）：`py_compile` 通过；真实 `test3.pdf` 命中模板 →
explicit 策略抽出 105×8、表头 8 列正确、`count_tables()==1`；
清空模板 → default 0 → lines 0 → text 102×7（表头「借 贷」合并）；
`run()` 单 case 端到端跑进临时目录，`output.json` 字段齐全、汇总统计仍为 1，临时目录已清理；
`clean_table()` 的空表 / 全空行 / 长短不齐三种边界均正常；无表格页会打印排查建议。
完整批量流水线未代跑，用户自行执行。

**遗留局限**：`explicit` 把结构拆对了，但 PDF 文字流里单元格内换行仍会把一条记录切成
2~3 行，需要按业务规则合并，属数据清洗而非结构识别；`fill_ratio` 只是粗粒度质量信号。

## 疑问（留着后面阶段解答）
- 为什么亮字暗底会几乎全军覆没？检测阶段到底在看什么特征？（week-02 反色实验 / P4）
- 调低 `text_det_thresh` 为什么能救漏检，又为什么会带来误检？DBNet 的概率图是什么？（week-02 Day3 感受，P4 深入）
- 同一个 PDF 的「全部内容流」和「肉眼可见区」，业务上该取哪个？`weekend_pipeline` 目前取前者并打了 `cropbox_limited` 标记。

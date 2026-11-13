# 第 1 周 · 环境搭建 + PaddleOCR 跑通

> **阶段**：P0 起步　|　**参考投入**：10-15h　|　**前置**：会 Python 基础（你已具备）
> **本周不需要懂深度学习**，目标是把工具跑起来、建立"OCR 原来这么用"的第一直觉。

---

## 本周定位

这是整条路线的"开机周"。你先用**最省力的方式**把 PaddleOCR 跑通，顺便判断工作里的 PDF 到底需不需要 OCR（很多 PDF 有文本层，能直接抽字，省一大半事）。同时把 Python/GPU 环境搭好，为下周和 P1 打地基。**边用边学，不要等学完原理才开始用工具。**

## 本周目标

一句话：**装好环境和 PaddleOCR，跑通"图片→文字"和"PDF→结构化文本"，看 1 集神经网络科普建立兴趣。**

硬指标：
1. Python 环境（conda 或 venv）可用，GPU 或云端算力就位
2. PaddleOCR 对一张印刷体图片输出正确文字
3. 会判断一个 PDF 有没有文本层（有→直接抽；无→走 OCR）
4. 表格图片能识别成结构化结果（HTML/Excel）
5. 看完 3Blue1Brown《神经网络》第 1 集

---

## 逐日安排

| 天 | 时长 | 任务 |
|---|---|---|
| Day 1（周一晚） | 1.5h | 搭 Python 环境（conda）+ 确认 GPU 或注册云算力 |
| Day 2（周二晚） | 1.5h | 装 PaddleOCR，跑通第一张图片识别 |
| Day 3（周三晚） | 1h | PDF 文本层判断（pdfplumber / PyMuPDF） |
| Day 4（周四晚） | 1h | 表格识别 PP-Structure，输出结构化结果 |
| Day 5（周五晚） | 1h | 看 3B1B《神经网络》第 1 集 |
| 周末（选一天） | 4-6h | 把"输入 PDF/图 → 输出结构化文本"串成一个小脚本；建 bad case 库雏形 |

---

## 学什么 & 怎么学

### 模块 A · Python 环境（Day 1）

**概念清单**：conda/venv 虚拟环境的作用（隔离依赖）、Python 版本、GPU 与 CUDA 的关系（本周只需知道"有没有 GPU"）。

**怎么学 / 动手**：
1. 装 Miniforge（比 Anaconda 轻，自带 conda）：官网 https://docs.conda.io/en/latest/miniconda.html
2. 建环境（**本机环境名就是 `paddle`，已装好，直接激活即可**）：
   ```bash
   conda create -n paddle python=3.10 -y   # 已经建过就跳过这行
   conda activate paddle
   python --version   # 3.10.9
   ```
3. **算力二选一**：
   - **有本地 NVIDIA 显卡**：本周先只用 CPU 也能跑 PaddleOCR，GPU 留到 P1 装 PyTorch 时再配。
   - **没有显卡**：注册云算力——AutoDL（https://www.autodl.com ，国内快、按小时租 GPU）或 Google Colab（https://colab.research.google.com ，免费 T4）。本周 CPU 足够，云 GPU 主要为 P1 之后准备。

**产出**：`conda activate paddle` 能进环境，`python` 能跑。

---

### 模块 B · PaddleOCR 跑通图片识别（Day 2）⭐本周核心

**概念清单**：OCR = 文字检测（找文字在哪）+ 文字识别（把文字读出来）；PaddleOCR 是百度开源的工业级 OCR，开箱即用。本周**当黑盒 API 用即可**，原理留到 P4。

**怎么学 / 动手**：
1. 安装（**用锁好版本的 `requirements.txt`**，别直接 `pip install paddleocr`——不带版本会顺手升级，破坏本机已验证的 `paddlepaddle 3.2.0 / paddlex 3.7.2 / paddleocr 3.7.0` 配套）：
   ```bash
   conda activate paddle
   python -m pip install -r requirements.txt
   ```
2. 跑通第一张图（直接运行目录里已备好的 `b_ocr_image.py`，本周脚手架，无需自建）：
   ```bash
   python b_ocr_image.py                      # 默认识别 input/test2.jpg
   python b_ocr_image.py input/你的图片.png     # 临时换一张图
   ```
   脚本里的核心写法（已按本机 3.7.0 实跑校正）：
   ```python
   from paddleocr import PaddleOCR

   ocr = PaddleOCR(
       text_detection_model_name='PP-OCRv4_mobile_det',   # 本地已缓存，免下载
       text_recognition_model_name='PP-OCRv4_mobile_rec',
       use_textline_orientation=True,   # 3.x 名称，替代已废弃的 use_angle_cls
       # 显式指定模型名时不要传 lang，否则 3.7.0 会打印「will be ignored」警告
       use_doc_orientation_classify=False,   # 关掉文档预处理，识别框坐标才对齐原图
       use_doc_unwarping=False,
   )
   for res in ocr.predict('input/test2.jpg'):   # 3.x 用 predict()
       for text, conf in zip(res['rec_texts'], res['rec_scores']):
           print(f'{text}  置信度={conf:.2f}')
   ```
3. 找一张含中文的截图/照片放进 `input/`，改脚本顶部的 `INPUT_IMAGE` 或用命令行传路径，看到文字被读出来即成功。

> ⚠️ **版本提示**：3.x 把 `.ocr(cls=True)` 改成 `.predict()`，结果从「三层嵌套列表」变成 dict 风格的 `rec_texts / rec_scores / rec_polys`；`use_angle_cls`、`PPStructure`、`import fitz` 也都换了名字。另外**默认开启的 UVDoc 去扭曲会让坐标基于矫正后图像**，要把识别框画回原图必须关掉上面那两项。换版本仍以官方 Quickstart 为准：https://github.com/PaddlePaddle/PaddleOCR

**产出**：产物按「脚本名 / 输入名」分目录。例如识别 `input/test2.jpg` → `output/b_ocr_image/test2/`，里面是 `b_ocr_result.txt`（文字 + 置信度）、`b_ocr_boxes.png`（原图叠加识别框）、`b_ocr_report.html`（左图右文字的离线对照报告，浏览器直接打开）。换一张图会自动进另一个目录，不会覆盖上一次的结果。**原图有字却没框的地方就是漏检**，比只看文本直观得多；不想要可视化就把配置区 `MAKE_VIS` 改成 `False`。

---

### 模块 C · PDF 文本层判断（Day 3）—— 最省力的一步

**为什么要学**：**能直接抽文字的 PDF 根本不用 OCR**。先判断，能省一大半事，这是工程思维（你的强项）。

**怎么学 / 动手**：装库 `python -m pip install pdfplumber pymupdf`，跑这段判断逻辑（已备好为 `c_pdf_text_layer.py`）。配置区 `INPUT_PDF` 默认是 `input/test3_image.pdf`（扫描件，会走"转图"分支）；**想看"直接抽字"有多快，把它改成 `input/test3.pdf`**，或用命令行临时指定：`python c_pdf_text_layer.py input/test3.pdf`。
```python
import pdfplumber

def has_text_layer(pdf_path, sample_pages=3):
    """前几页能抽到足够文字 = 有文本层，不用 OCR"""
    with pdfplumber.open(pdf_path) as pdf:
        text = "".join((p.extract_text() or "") for p in pdf.pages[:sample_pages])
    return len(text.strip()) > 50, text[:200]

ok, preview = has_text_layer("work.pdf")
print("有文本层，直接抽字即可" if ok else "扫描件/图片型，需要 OCR")
print("预览：", preview)
```
- **有文本层** → 直接 `extract_text()` 拿结果，本周任务对它已完成。
- **无文本层（扫描件）** → 用 PyMuPDF 把每页转成图片，再喂给模块 B 的 PaddleOCR：
  ```python
  import pymupdf                       # PyMuPDF：新导入名（`import fitz` 已弃用）
  doc = pymupdf.open("scan.pdf")
  for i, page in enumerate(doc):
      pix = page.get_pixmap(dpi=200)      # dpi 越高越清晰但越慢
      # 页图是中间产物，脚本会单独放到该输入目录下的 pages/ 子目录
      pix.save(f"output/c_pdf_text_layer/scan/pages/page_{i}.png")
  doc.close()
  ```

**产出**：一个能判断"该不该 OCR"的函数，并把一个扫描 PDF 转成图片。脚本还会打印**逐页字符数**，让判断依据看得见；若各页字数差异极大，会提示这可能是「部分页有文本层、部分页是扫描图」的混合型 PDF（整份文件只给一个结论会漏字，这个坑留到以后逐页分流解决）。

---

### 模块 D · 表格识别 PP-Structure（Day 4）

**概念清单**：普通 OCR 只给"一行行文字"，表格需要**结构识别**（还原行列关系），PaddleOCR 的 PP-Structure / PP-StructureV3 干这个，输出 HTML 或 Excel 结构。

**怎么学 / 动手**：
```python
from paddleocr import PPStructureV3          # 3.x 已移除旧的 PPStructure，改用 PPStructureV3

engine = PPStructureV3(
    use_formula_recognition=False, use_chart_recognition=False,
    use_seal_recognition=False, use_region_detection=False,
    use_table_recognition=True,              # 只保留表格识别
)
result = engine.predict('input/test2.jpg')   # 3.x 用 predict()，返回 list[结果对象]
res = result[0]
if res.html:    # 先判空！这页没表格时是 {}，直接 save_to_html 会 IndexError
    res.save_to_html('output/d_table_ocr/test2/d_table_out.html')
for b in res.json['res']['parsing_res_list']:
    print(b['block_label'], str(b['block_content'])[:50])   # header / text / table ...
```
> 表格识别是**多模型流水线**（版面检测 + 表格分类 + 结构识别 + 单元格检测），首次运行要下模型；脚本里已切到百度云 BOS 源，避免卡 HuggingFace。本周**跑通一个表格→HTML**即可，不追求完美。

**产出**：把一张表格图片转成 HTML，用浏览器打开看到还原的表格。（代码已备好为 `d_table_ocr.py`，`python d_table_ocr.py` 直接跑，输出 `output/d_table_ocr/test2/d_table_out.html`。脚本会自动补 `<meta charset="utf-8">`，中文不会乱码。）

> **输入换成多页 PDF 时**：`predict()` 一页返回一个结果，但很多页根本没有表格（`test3_image.pdf` 第 3~5 页是证书扫描图）。paddlex 3.7.0 的 `save_to_html()` 遇到空结果会抛 `IndexError`，所以脚本改为先读 `res.html` 判空、空则从 `[table]` 内容块兜底、仍为空就跳过该页并在日志里列出序号；一页多张表会按表名拆成多个文件，不会只写第一张。

---

### 模块 E · 神经网络第一直觉（Day 5，轻松）

**怎么学**：看 3Blue1Brown《神经网络》系列**第 1 集**（讲"神经网络是什么"，纯直觉无公式）。
- 官方站（英文，有字幕）：https://www.3blue1brown.com/topics/neural-networks
- B 站：搜索「**3Blue1Brown 神经网络**」，有官方中文字幕版。

**产出**：能用自己的话说"神经网络大概是在干嘛"（一句话即可）。这周不深挖，下周和第 3 周看完整 4 集。

---

### 周末 · 串成 pipeline + bad case 库雏形（4-6h）

1. **串脚本**：把模块 B/C/D 合起来——`输入文件 → 判断该走哪条路 → 输出结构化 txt/json`。这是你**第一个能拿出手的小工具**。（`weekend_pipeline.py` 三个 TODO 已补全，并补了面向初学者的逐行注释。）

   **现在直接 `python weekend_pipeline.py` 就会批量跑 `input/` 下所有 case**，不用再手改输入路径。它按后缀分三条路：PDF 判断文本层（有则 `pdfplumber` 抽字、无则转图逐页 OCR）、图片直接 OCR、CSV/TXT 直接读（连模型都不用加载）。

   **产物全部隔离**：全周统一规则是 **`output/<脚本名>/<输入文件名>/`** —— 脚本之间互不干扰，同一脚本换一个输入也不会覆盖上一次的结果。中间产物（转出的页图、OCR 临时页图）再单独放一层子目录，不和正式结果混在一起。

   ```text
   output/
     b_ocr_image/
       test2/             b_ocr_result.txt + b_ocr_boxes.png + b_ocr_report.html
     c_pdf_text_layer/
       test3/             test3_text.txt（抽出的全文）
       test3_image/
         pages/           c_page_0~4.png（转出的页图，中间产物）
     d_table_ocr/
       test2/             d_table_out.html
     weekend_pipeline/
       batch_summary.json / batch_summary.txt   ← 所有 case 的总览表
       test1/             output.json + pipeline_result.txt
       test2/             output.json + pipeline_result.txt + pipeline_table_p0.html
       test3/             output.json + pipeline_result.txt
       test3_image/       output.json + pipeline_result.txt + pipeline_table_p1.html
                          + _tmp_pages/（OCR 页图，跑完保留供逐页核对）
       test4/             output.json + pipeline_result.txt
   ```

   只跑一个文件：`python weekend_pipeline.py input/test3.pdf`；跑别的目录：`python weekend_pipeline.py ../week-02/input`。新增 case 只要丢进 `input/` 就会自动被扫到（支持 `.pdf` / 常见图片 / `.csv .txt .md`，见配置区 `SUPPORTED_EXTS`）。OCR 分支的中间页图放在 `<case>/_tmp_pages/`，**跑完保留**方便逐页核对「OCR 看的是哪张图」，下次重跑该 case 时会先清空旧图再生成新图（不用改任何开关，出错时页图也会留着排查）；`output.json` 里的 `temp_dir` / `temp_pages` 会记下页图位置和张数；表格识别每页约 +20s，只想快速看文字把 `ENABLE_TABLE` 改成 `False`。输入统一放 `input/`，产物按上面两层规则自动建目录。
2. **bad case 库雏形**：建一个文件夹 `bad_cases/`，把你跑的过程中**识别错、识别不全、模糊/倾斜/反光**的样本图存进去，附一个 `notes.md` 记"这张为什么失败"。**这是第 2 周和 P4 的宝贵素材，现在就开始攒。**

---

## 本周资源清单（点开即用）

| 用途 | 链接 |
|---|---|
| Miniforge 安装 | https://docs.conda.io/en/latest/miniconda.html |
| PaddleOCR 仓库（含 Quickstart） | https://github.com/PaddlePaddle/PaddleOCR |
| pdfplumber | https://github.com/jsvine/pdfplumber |
| PyMuPDF 文档 | https://pymupdf.readthedocs.io/ |
| AutoDL 云 GPU | https://www.autodl.com |
| Google Colab | https://colab.research.google.com |
| 3B1B 神经网络（官方站） | https://www.3blue1brown.com/topics/neural-networks |

---

## 验收清单（周末打勾）

- [ ] `conda activate paddle` 能进环境
- [ ] PaddleOCR 对一张中文图片输出正确文字 + 置信度
- [ ] 能判断一个 PDF 有没有文本层，并对扫描件转图
- [ ] 一张表格图片 → HTML，浏览器打开看到还原表格
- [ ] 看完 3B1B 第 1 集，能一句话说"神经网络在干嘛"
- [ ] 有一个把 PDF→结构化文本的小脚本
- [ ] `bad_cases/` 文件夹建好，存了 ≥3 个失败样本

---

## 常见坑 & 卡住怎么办

- **装 PaddleOCR 报错/依赖冲突**：确认用的是干净的 conda 环境（Python 3.10 较稳）；还报错就贴报错信息问 AI，或去仓库 Issues 搜。**卡超 2h 先用 CPU 版跑通再说。**
- **`.ocr()` 方法不存在**：你装的是 3.x，改用 `.predict()`；`use_angle_cls` → `use_textline_orientation`、`PPStructure` → `PPStructureV3`、`import fitz` → `import pymupdf`。
- **首次运行自动下载模型很慢/失败**：默认 PP-OCRv6 会从 HuggingFace 拉，国内常卡住。脚本已显式指定本地缓存的 `PP-OCRv4_mobile_*`，并在 import 前设好 `PADDLE_PDX_MODEL_SOURCE=BOS`；换模型时记得这两行不能删。
- **识别框没套住文字（整体错位）**：3.7.0 默认做整页方向分类 + UVDoc 去扭曲，`rec_polys` 是**矫正后图像**的坐标。要画回原图必须构造时加 `use_doc_orientation_classify=False, use_doc_unwarping=False`；只取文字、不画框时可以保留默认（部分图反而更准）。
- **日志里出现 `lang / ocr_version will be ignored` 警告**：显式指定 `*_model_name` 时不要再传 `lang`，语言能力由所选识别模型决定。
- **HTML 打开中文乱码**：paddlex `save_to_html()` 写的是 UTF-8 但没有 `<meta charset>`，浏览器按 GBK 解码。脚本里的 `ensure_readable_html()` 会补完整 HTML 骨架，别删。
- **PDF 抽字是乱码/空**：说明是扫描件（无文本层），走模块 C 的转图 OCR 分支。
- **没有 GPU 焦虑**：本周 CPU 完全够用，GPU 是 P1 装 PyTorch 时才必需，届时用云算力也行。

---

## 进度日志（本周日填）

```
第 1 周（日期 ____）｜阶段 P0
· 本周跑通了什么：____________________
· 肉眼看到了什么：____________________（识别出的文字 / 还原的表格 / bad case）
· 卡在哪、怎么解决的：________________
· bad case 库攒了几个：______________
· 下周第一件要动手的事：______________
```

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
1. 装 Miniconda（比 Anaconda 轻）：官网 https://docs.conda.io/en/latest/miniconda.html
2. 建环境：
   ```bash
   conda create -n ocr python=3.10 -y
   conda activate ocr
   python --version   # 确认
   ```
3. **算力二选一**：
   - **有本地 NVIDIA 显卡**：本周先只用 CPU 也能跑 PaddleOCR，GPU 留到 P1 装 PyTorch 时再配。
   - **没有显卡**：注册云算力——AutoDL（https://www.autodl.com ，国内快、按小时租 GPU）或 Google Colab（https://colab.research.google.com ，免费 T4）。本周 CPU 足够，云 GPU 主要为 P1 之后准备。

**产出**：`conda activate ocr` 能进环境，`python` 能跑。

---

### 模块 B · PaddleOCR 跑通图片识别（Day 2）⭐本周核心

**概念清单**：OCR = 文字检测（找文字在哪）+ 文字识别（把文字读出来）；PaddleOCR 是百度开源的工业级 OCR，开箱即用。本周**当黑盒 API 用即可**，原理留到 P4。

**怎么学 / 动手**：
1. 安装：
   ```bash
   pip install paddlepaddle        # CPU 版；有 GPU 后续再换 paddlepaddle-gpu
   pip install paddleocr
   ```
2. 跑通第一张图（新建 `week1_ocr.py`）：
   ```python
   from paddleocr import PaddleOCR

   # lang='ch' 中英混合；use_angle_cls=True 自动摆正倾斜文字
   ocr = PaddleOCR(use_angle_cls=True, lang='ch')
   result = ocr.ocr('test.png', cls=True)

   for line in result[0]:
       box, (text, conf) = line      # box=四点坐标, text=识别文字, conf=置信度
       print(f'{text}  置信度={conf:.2f}')
   ```
3. 找一张含中文的截图/照片当 `test.png`，运行，看到文字被读出来即成功。

> ⚠️ **版本提示**：PaddleOCR 3.x 把 `.ocr()` 改成了 `.predict()`，返回结构也略有不同。若上面代码报错，去官方仓库看当前版本的 Quickstart：https://github.com/PaddlePaddle/PaddleOCR （README 顶部有最新用法）。**以官方 README 为准。**

**产出**：命令行打印出图片里的文字 + 置信度。

---

### 模块 C · PDF 文本层判断（Day 3）—— 最省力的一步

**为什么要学**：**能直接抽文字的 PDF 根本不用 OCR**。先判断，能省一大半事，这是工程思维（你的强项）。

**怎么学 / 动手**：装库 `pip install pdfplumber pymupdf`，跑这段判断逻辑：
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
  import fitz  # PyMuPDF
  doc = fitz.open("scan.pdf")
  for i, page in enumerate(doc):
      pix = page.get_pixmap(dpi=200)      # dpi 越高越清晰但越慢
      pix.save(f"page_{i}.png")           # 存成图片，再走 PaddleOCR
  ```

**产出**：一个能判断"该不该 OCR"的函数，并把一个扫描 PDF 转成图片。

---

### 模块 D · 表格识别 PP-Structure（Day 4）

**概念清单**：普通 OCR 只给"一行行文字"，表格需要**结构识别**（还原行列关系），PaddleOCR 的 PP-Structure / PP-StructureV3 干这个，输出 HTML 或 Excel 结构。

**怎么学 / 动手**：
```python
from paddleocr import PPStructure

engine = PPStructure(table=True, ocr=True, lang='ch')
result = engine('table.png')          # 一张含表格的图片
for item in result:
    print(item['type'])                # table / text
    if item['type'] == 'table':
        print(item['res']['html'])     # 表格的 HTML 结构，可直接存 .html 用浏览器打开
```
> PP-StructureV3 是更新版本，用法以官方仓库"表格识别"章节为准：https://github.com/PaddlePaddle/PaddleOCR 。本周**跑通一个表格→HTML**即可，不追求完美。

**产出**：把一张表格图片转成 HTML，用浏览器打开看到还原的表格。

---

### 模块 E · 神经网络第一直觉（Day 5，轻松）

**怎么学**：看 3Blue1Brown《神经网络》系列**第 1 集**（讲"神经网络是什么"，纯直觉无公式）。
- 官方站（英文，有字幕）：https://www.3blue1brown.com/topics/neural-networks
- B 站：搜索「**3Blue1Brown 神经网络**」，有官方中文字幕版。

**产出**：能用自己的话说"神经网络大概是在干嘛"（一句话即可）。这周不深挖，下周和第 3 周看完整 4 集。

---

### 周末 · 串成 pipeline + bad case 库雏形（4-6h）

1. **串脚本**：把模块 B/C/D 合起来——`输入一个 PDF → 判断有无文本层 → 有则抽字/无则转图 OCR → 表格走 PP-Structure → 输出一个结构化 txt/json`。这是你**第一个能拿出手的小工具**。
2. **bad case 库雏形**：建一个文件夹 `bad_cases/`，把你跑的过程中**识别错、识别不全、模糊/倾斜/反光**的样本图存进去，附一个 `notes.md` 记"这张为什么失败"。**这是第 2 周和 P4 的宝贵素材，现在就开始攒。**

---

## 本周资源清单（点开即用）

| 用途 | 链接 |
|---|---|
| Miniconda 安装 | https://docs.conda.io/en/latest/miniconda.html |
| PaddleOCR 仓库（含 Quickstart） | https://github.com/PaddlePaddle/PaddleOCR |
| pdfplumber | https://github.com/jsvine/pdfplumber |
| PyMuPDF 文档 | https://pymupdf.readthedocs.io/ |
| AutoDL 云 GPU | https://www.autodl.com |
| Google Colab | https://colab.research.google.com |
| 3B1B 神经网络（官方站） | https://www.3blue1brown.com/topics/neural-networks |

---

## 验收清单（周末打勾）

- [ ] `conda activate ocr` 能进环境
- [ ] PaddleOCR 对一张中文图片输出正确文字 + 置信度
- [ ] 能判断一个 PDF 有没有文本层，并对扫描件转图
- [ ] 一张表格图片 → HTML，浏览器打开看到还原表格
- [ ] 看完 3B1B 第 1 集，能一句话说"神经网络在干嘛"
- [ ] 有一个把 PDF→结构化文本的小脚本
- [ ] `bad_cases/` 文件夹建好，存了 ≥3 个失败样本

---

## 常见坑 & 卡住怎么办

- **装 PaddleOCR 报错/依赖冲突**：确认用的是干净的 conda 环境（Python 3.10 较稳）；还报错就贴报错信息问 AI，或去仓库 Issues 搜。**卡超 2h 先用 CPU 版跑通再说。**
- **`.ocr()` 方法不存在**：你装的是 3.x，改用 `.predict()`，以官方 README 为准。
- **首次运行自动下载模型很慢/失败**：多试一次，或看仓库文档手动指定模型路径。
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

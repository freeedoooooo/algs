# 第 2 周 · 真实图片实战 + bad case 库

> **阶段**：P0 起步（收尾）　|　**参考投入**：10-15h　|　**前置**：第 1 周（PaddleOCR 已跑通）
> 本周仍**不需要深度学习**，目标是把 OCR 用"熟"，并攒下贯穿整个计划的 bad case 素材库。

---

## 本周定位

第 1 周你跑通了 demo，本周要拿**真实图片**（工作文档、生活照片、网上找的复杂场景）去压测 PaddleOCR，建立"**什么场景效果好、什么场景效果差**"的直觉——这个直觉是 P4 学检测/识别原理时"回看 bad case"的锚点。同时把 bad case 库正式建起来。**这是 P0 的收尾周，结束时你应达到 PaddleOCR 的 L1（会用）。**

## 本周目标

一句话：**用真实图片把 PaddleOCR 用到熟，系统化建立 bad case 素材库，看完 3B1B 神经网络系列，正式起步深度学习。**

硬指标：
1. 对 ≥10 张真实/复杂图片跑过 OCR，记录效果
2. bad case 库成型：按"失败类型"分类，每类有样本 + 归因笔记
3. 看完 3B1B《神经网络》全 4 集（第 1 集上周已看，本周补 2-4）
4. 达成 **L1 会用**：能独立装、跑、拿到结果
5. （涉密提醒）确认工作敏感文档只走本地，不上云

---

## 逐日安排

| 天 | 时长 | 任务 |
|---|---|---|
| Day 1（周一晚） | 1h | 收集 10+ 张真实/复杂图片，批量跑 OCR |
| Day 2（周二晚） | 1.5h | 分析结果，把失败样本按类型归类 |
| Day 3（周三晚） | 1h | 学 PaddleOCR 常用参数（角度分类/语言/检测阈值），试着救几个 bad case |
| Day 4（周四晚） | 1h | 看 3B1B《神经网络》第 2 集（梯度下降） |
| Day 5（周五晚） | 1h | 看 3B1B 第 3 集（反向传播） |
| 周末（选一天） | 4-6h | 建正式 bad case 库（目录+笔记）；看 3B1B 第 4 集；装好 PyTorch 环境（CPU 即可）为 P1 铺路 |

---

## 脚本地图：谁调用谁

**一句话**：`a_batch_ocr.py` 是本周唯一的主入口，你只需要运行它；
`case_naming.py`、`text_layer_extract.py`、`vis_ocr_result.py` 都是被它调用的模块。

```
a_batch_ocr.py   ← 你只运行这一个（主入口 / 编排）
    ├── case_naming.py         ① 文件顶部 import，全程用：命名 / 分组 / 排序
    ├── text_layer_extract.py ② 文件顶部 import，只在 PDF / CSV 分支直读表格
    └── vis_ocr_result.py     ③ main() 里「用到才 import」：画对照报告
```

| 文件 | 角色 | 被谁调用 | 加载时机 | 能单独运行吗 |
|---|---|---|---|---|
| `a_batch_ocr.py` | 主入口：遍历 case、跑 OCR、落盘 | 你（命令行） | — | 是，`python a_batch_ocr.py` |
| `case_naming.py` | 命名 / 分组 / 排序的唯一真相源 | **5 个脚本**（见下） | 各脚本 import 时 | 否，纯函数模块、无 main |
| `text_layer_extract.py` | PDF 文本层 / CSV 直读，不加载模型 | 仅 `a_batch_ocr.py` | a 的文件顶部 | 否，纯模块、无 main |
| `vis_ocr_result.py` | 画原图 + 识别框 + 直读结果的 HTML | `a_batch_ocr.py`，也可直接运行 | **懒加载**，画报告时才 import | 是，`python vis_ocr_result.py` |

`case_naming.py` 是公共底座，除 a 外还有 4 个调用方：
`c_try_params.py`（自动挑默认图）、`make_samples.py`（生成 / 补登记样本）、
`text_layer_extract.py`（`strip_no()` 匹配列边界模板）、
`vis_ocr_result.py`（卡片分组与统计）。

**为什么 ③ 是懒加载**：画图属于附加功能。放在 `main()` 里、并裹在 `try` 中，
即使报告生成失败，已经落盘的 `result.json` / `result.txt` 也不会白跑。
跑 `a_batch_ocr.py` 时日志开头会打印「本次运行会用到的模块」，
想让日志安静就把配置区 `SHOW_DEPS` 改成 `False`。

> 想知道某个文件被谁调用，最快的办法：在 week-02 目录搜它的文件名，
> 或看该文件顶部 docstring 里的「谁在调用我」小节。

## 学什么 & 怎么学

### 模块 A · 真实图片压测（Day 1）

> 本机 miniforge 环境名是 `paddle`，跑任何脚本前先 `conda activate paddle`
> （依赖是第1周锁定的 paddleocr 3.7.0，别在别的环境里跑）。

#### 素材：已备好，不用自己找

`input/` 里已放好 **25 个 case**（18 张合成 + 7 个真实），由 `make_samples.py` 一次性生成：

| 编号 | 内容 | 归类 |
|---|---|---|
| `01` | 清晰印刷体底稿（对照组） | 对照组 |
| `02~03`、`11`、`15` | 轻度模糊 / 降采样 / 噪声 / 重度模糊 | 01_模糊低质 |
| `04~05`、`13` | 倾斜 8° / 梯形透视 / 倒置 180° | 02_倾斜透视 |
| `06~08`、`16~18` | 反光、阴影、低对比，以及三种重度版本 | 03_反光光照 |
| `09`、`12` | 双栏 16px 密集小字、行楷手写 | 04_密集小字 |
| `10`、`14` | 亮字暗底、模糊+倾斜+阴影混合退化 | 06_漏检 |
| `101~107` | 7 个用户真实 case（101 起编号，全部排在最后） | 见下表 |

真实 case（11-13 定稿，编号 101 起）：

| 文件名 | 内容 |
|---|---|
| `101_real_terminal_screenshot.jpg` | 第1周真实终端截图（亮字暗底） |
| `102_real_clear_doc.jpg` | 第1周真实清晰文档 |
| `103_real_bank_statement_textlayer.pdf` | 有文本层的银行流水 PDF（含 8 列表格） |
| `104_real_certificates_scan.pdf` | 5 页证书 / 备案表扫描件 PDF |
| `105_real_transactions_gbk.csv` | GBK 编码的 CSV 交易流水 |
| `106_real_scan_page1.jpg` / `107_real_scan_page2.jpg` | 第1周渲染出的真实扫描页（带噪点、印章） |

> **命名约定（11-13 定稿）**：合成样本 `01~18`（编号 < 101）；自己的真实 case
> **从 101 起编号**，格式 `101_real_xxx`，数字前缀好找、`real_` 一眼看出是自己的素材。
> 新增 case 从 108 接着编，直接丢进 `input/` 再跑 `a_batch_ocr.py` 就生效 ——
> 不用改脚本、不用改清单，日志还会提示「未登记的新 case」和下一个建议编号。
> 分组 / 排序规则集中在 **`case_naming.py`**（唯一真相源）：真实 case 恒排最后，
> 组内按编号升序。注意不能靠纯 `sorted()`：字典序里 `101_` 会插到 `10_` 前面。
> 原先 `test1/test2` 各存了两份字节级相同的副本，已去重删掉，只留正本。

设计要点：**01~14 共用同一份干净底稿，每张只施加一种退化**，所以结果差异能归因到单一因素；
`input/samples_manifest.json` 记着每类的退化参数、分组与「标准答案文字」，报告会自动算出
「命中 / 未命中」行。想加自己的素材，按 `108_real_xxx` 丢进 `input/` 再跑一遍即可 ——
manifest 不是白名单，没登记照样跑（分组由 `case_naming.py` 按编号推断）。
重新生成全套样本用 `python make_samples.py`（只覆盖同名文件，不删你自己的图；
顺带把新增 case 补登记进说明书，不会把它们冲掉）。

> ⚠️ 合成图是教学用的对照实验，不等于真实分布。第 1 周那两张真实图和两张扫描页
> 就是用来补这一课的：真实文档的噪点、印章、版式复杂度是画不出来的。

**怎么学 / 动手**：
1. 确认 `input/` 覆盖了多种场景（已备好，也可换成自己拍的照片，注意脱敏）：
   - 清晰的印刷体（对照组，应该效果好）
   - 模糊 / 低分辨率
   - 倾斜 / 透视变形（拍照角度歪）
   - 反光 / 光照不均 / 阴影
   - 密集小字 / 复杂版面 / 多栏
   - 手写体（**只观察效果，不深究**——这是兔子洞，本计划不攻手写）
2. 用 `a_batch_ocr.py` 批量跑，把每张的**识别结果和原图对应存好**。
3. **打开 `output/a_batch_ocr/index.html`** —— 这是本周最该花时间看的地方：
   - 左边原图上叠着识别框，右边是逐行文字 + 置信度条；
   - 鼠标移到右侧任意一行，左图对应的框会高亮；
   - 橙红框 = 置信度 < 0.8 的可疑行；
   - **原图上有字、却没被框住的地方，就是漏检**；
   - 顶部可一键「只看有问题的图」，折叠区能对照标准答案看哪几行没认出来；
   - 每张卡片上有「本 case 的 result.json」链接，配合
     `output/a_batch_ocr/<输入名>/boxes.png` 单张带框图，排查时只看这一个目录；
   - 只重画报告、不重跑 OCR：`python vis_ocr_result.py`。

**脚本产物**：

| 路径 | 内容 |
|---|---|
| `output/a_batch_ocr/index.html` | ★ 可视化对照报告，浏览器直接打开，不用起服务 |
| `output/a_batch_ocr/batch_summary.json` / `.txt` | 跨 case 汇总表（只有关键指标，一眼看全） |
| `output/a_batch_ocr/<输入名>/result.json` | 该 case 的完整结果：文字 / 置信度 / 坐标 / 直读表格与诊断 |
| `output/a_batch_ocr/<输入名>/result.txt` | 该 case 的纯文本结果 |
| `output/a_batch_ocr/<输入名>/source.<ext>` | 输入副本：图片=原图 / PDF=首页渲染图 / CSV=原始文本，给 HTML 引用，也让目录自包含 |
| `output/a_batch_ocr/<输入名>/boxes.png` | 原图 + 识别框，单张可贴笔记（CSV 等纯文本不生成） |
| `output/a_batch_ocr/<输入名>/pages/p1.png` | PDF 首页渲染图（中间产物，跑完保留供核对） |
| `output/c_try_params/param_compare.txt` | 模块 C 的调参对比结果 |

> **产物隔离（与第1周同一套规矩）**：脚本一层 `output/a_batch_ocr/`，每个输入再一层
> `<输入名>/`，中间产物再单独一层 `pages/`。排查某个 case 只看它自己的目录，
> 不用在一整个大 JSON 里翻。报告放根、图片引用各 case 目录里的副本，
> 所以移动时把**整个 `a_batch_ocr/` 目录**一起带走，别只拷 HTML。
> 重跑会先清掉每个 case 目录里本脚本自己生成的旧文件（只删固定名单，不碰你的文件），
> 已废弃的旧 case 目录只打印提示、不自动删除。

**PDF / CSV 也能进对比预览（11-13 新增）**：`a_batch_ocr.py` 按后缀分三条路 ——
图片直接 OCR；PDF 首页渲染成图给 OCR，**有文本层时额外用 pdfplumber 直读表格**；
CSV 直接按文本解析、完全不跑模型。报告里同一个 PDF 卡片会同时显示
「上面的 OCR 文字 + 识别框」和「下面的直读表格 + 抽取诊断」，一眼看出
像素识别的误差与文本层直读的无损差别。文本层策略与第1周 `weekend_pipeline.py`
一致（诊断线型 → `TABLE_STRATEGIES` 回退 → 人工列边界模板 → 填充率打分），
实现放在 `text_layer_extract.py`；`103_real_bank_statement_textlayer.pdf` 已配好
9 条竖线模板，能拆出正确的 8 列表头。模板按「去掉数字编号后的语义名」登记，
所以以后把 103 改成 108、或复制出新 case，模板照样命中，不用跟着改字典。

**批量跑参考代码**（`python a_batch_ocr.py` 直接跑 `input/` 下所有 case；也可
`python a_batch_ocr.py ../week-01/input` 临时换目录。脚手架已按本机
**paddleocr 3.7.0** 校准，下面是它内部的核心写法）：
```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    text_detection_model_name='PP-OCRv4_mobile_det',   # 第1周已缓存，免下载
    text_recognition_model_name='PP-OCRv4_mobile_rec',
    use_textline_orientation=True,   # 3.x 名称，替代已废弃的 use_angle_cls
    # 不传 lang：显式指定模型名时 lang 会被忽略并报警告
    # ↓ 关闭文档预处理，保证 rec_polys 是「原图像素坐标」，画框才对得齐
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
)

results = ocr.predict(path)          # 3.x 用 predict()
for res in results:
    texts  = res['rec_texts']        # 每行文字
    scores = res['rec_scores']       # 对应置信度
    boxes  = res['rec_polys']        # 每行文字的四点坐标
```
> ⚠️ 旧教程里的 `use_angle_cls`、`ocr.ocr(path, cls=True)`、`result[0][1][0]` 解包
> 都是 **2.x** 写法，在 3.7.0 上会报错或报警告。取数一律走
> `rec_texts` / `rec_scores` / `rec_polys`。

**产出**：≥10 张图片的识别结果 + 一份可视化对照报告，心里有数"哪些好、哪些差"。

> ⚠️ **识别框坐标的坑（本机 3.7.0 实测）**：默认开启的「整页方向分类 + UVDoc 去扭曲」
> 会先把图矫正一遍，返回的 `rec_polys` 是矫正后图像的坐标，直接画回原图会整体错位
> （实测标题框 y=27~66，而标题墨迹实际在 y=66~98）。关闭这两项后框与墨迹完全吻合。
> 代价是某些图识别质量会下降：`101_real_terminal_screenshot.jpg`（原 `real_terminal_screenshot.jpg`）从 6 行 / 0.90 变成 4 行 / 0.17。
> 顶部配置区 `USE_DOC_PREPROCESS` 可切换；只取文字、不需要坐标时可以试 True。

---

### 模块 B · bad case 归类分析（Day 2）⭐本周核心

**为什么要做**：bad case 是你后面所有阶段的**真实问题锚点**。P4 学到"倾斜文本检测不敏感"时，回来翻这些样本，理解会最深刻。**现在只归类和记录，不急着解决**（你还没学原理）。

**怎么归类**——建这样的目录：
```
bad_cases/
├── 01_模糊低质/        # 模糊、低分辨率
├── 02_倾斜透视/        # 拍照歪、透视变形
├── 03_反光光照/        # 反光、阴影、光照不均
├── 04_密集小字/        # 小字、多栏、复杂版面
├── 05_识别错误/        # 检测对了但字认错（形近字等）
├── 06_漏检/            # 整块文字没被检测到
└── notes.md            # 每个样本一行：文件名 | 类型 | 现象 | 我的猜测
```

**notes.md 记法示例**：
```
| 文件 | 类型 | 现象 | 我的猜测（现在猜错没关系）|
|---|---|---|---|
| img_07.jpg | 03_反光光照 | 反光区域整行漏检 | 反光让文字和背景对比度消失？ |
| img_12.png | 05_识别错误 | "未"识别成"末" | 形近字，识别头分不清 |
```

**产出**：分类目录 + notes.md，每类至少 1-2 个样本。

---

### 模块 C · PaddleOCR 参数调优初体验（Day 3）

**概念清单**：PaddleOCR 不是只能一键跑，有几个能"救场"的参数。本周**只需知道有这些旋钮**，深入调优是 P4 的事。

**动手试**（以下均为 3.7.0 的参数名，旧教程写的 2.x 名称已标注）：
- `use_textline_orientation`：文本行方向分类（2.x 叫 `use_angle_cls`），倾斜/倒置样本试试开/关
- `lang`：`ch`（中英）/ `en` / 其他；选错语言识别率会掉（**仅在不显式指定模型名时生效**；本周脚手架指定了模型名，故不传 `lang`）
- `text_det_thresh` / `text_det_box_thresh`：检测阈值，默认 **0.3 / 0.6**；**漏检时调低、误检时调高**（2.x 叫 `det_db_thresh` / `det_db_box_thresh`；原理 P4 讲 DBNet 时深入）
- `text_det_limit_side_len`：检测时图像边长限制，大图 / 密集小字漏检时可调大，代价是变慢

```python
# 3.x：阈值可在 predict() 时「按次覆盖」，一个引擎就能对比两组参数
ocr = PaddleOCR(
    text_detection_model_name='PP-OCRv4_mobile_det',
    text_recognition_model_name='PP-OCRv4_mobile_rec',
    use_textline_orientation=True,   # 显式模型名时不要再传 lang，会被忽略并报警告
    use_doc_orientation_classify=False,   # 与 a_batch_ocr.py 保持一致，见下方坐标坑
    use_doc_unwarping=False,
)
img = 'bad_cases/06_漏检/xxx.png'

default_res   = ocr.predict(img)          # 默认 0.3 / 0.6
sensitive_res = ocr.predict(              # 调低 → 更敏感
    img,
    text_det_thresh=0.2,
    text_det_box_thresh=0.4,
)
texts = sensitive_res[0]['rec_texts']     # 3.x 取数方式
```
（已备好 `c_try_params.py`：把顶部配置区的 `IMG` 改成你的漏检样本，或用命令行
`python c_try_params.py 图片路径`；脚本会打印 B 组「新增 / 丢掉」的行，
并把完整对比存到 `output/c_try_params/param_compare.txt`。）

> 参数名/默认值可能随版本变化，以官方文档为准：https://github.com/PaddlePaddle/PaddleOCR
> 本机可用 `python -c "import inspect; from paddleocr import PaddleOCR; print(inspect.signature(PaddleOCR.predict))"` 直接查当前版本支持哪些参数。

**产出**：把 notes.md 里 1-2 个 bad case 通过调参数"救"回来一点，记录"调了什么、结果怎么变"。

---

### 模块 D · 3B1B 神经网络系列（Day 4/5 + 周末）

**怎么学**：看完《神经网络》**第 2、3、4 集**（第 1 集上周已看）。
- 第 2 集：梯度下降（网络怎么"学"）
- 第 3 集：反向传播（梯度怎么算）
- 第 4 集：反向传播微积分（直觉，看不懂公式没关系，第 3 周会 just-in-time 补）
- 链接：https://www.3blue1brown.com/topics/neural-networks ；B 站搜「3Blue1Brown 神经网络」

**心态**：**这周只求"直觉"，不求会推公式。** 真正动手写神经网络是第 3-4 周（P1-A）。看完能回答"网络靠什么变聪明"（答：靠梯度下降不断调参数）就够了。

**产出**：看完 4 集，能口头说清"前向传播→算误差→反向传播→梯度下降更新"这个大循环。

---

### 模块 E · 涉密与合规（贯穿本周）

- [ ] **工作敏感文档只用本地 PaddleOCR，绝不上传云端 LLM/在线 OCR。**
- [ ] 如果 bad case 库要放进将来的 GitHub 作品集，**务必用脱敏数据**（打码/替换敏感信息），别把公司机密传上去。

---

### 周末 · bad case 库成型 + PyTorch 环境预备（4-6h）

1. 把本周散落的 bad case 正式归入模块 B 的目录结构，补全 notes.md。
2. 看 3B1B 第 4 集。
3. **为 P1 铺路**：装好 PyTorch（CPU 版即可，GPU 版第 3 周再按需配）：
   ```bash
   # CPU 版（先能跑就行）。统一用 python -m pip，保证装进当前 conda 解释器
   python -m pip install torch torchvision
   ```
   ```python
   import torch
   print(torch.__version__)              # 打印版本号即成功
   print(torch.cuda.is_available())      # 有没有 GPU（False 也没关系）
   ```
4. 打开 d2l 教材首页浏览目录，混个眼熟：https://zh.d2l.ai/

**产出**：bad case 库成型；PyTorch 能 import 并打印版本；对 d2l 结构有印象。

---

## 本周资源清单

| 用途 | 链接 |
|---|---|
| PaddleOCR 仓库（参数/文档） | https://github.com/PaddlePaddle/PaddleOCR |
| 3B1B 神经网络系列 | https://www.3blue1brown.com/topics/neural-networks |
| d2l《动手学深度学习》教材 | https://zh.d2l.ai/ |
| PyTorch 安装指引 | https://pytorch.org/get-started/locally/ |

---

## 验收清单（周末打勾）

- [ ] 对 ≥10 张真实/复杂图片跑过 OCR
- [ ] bad case 库按 6 类建好，每类有样本，notes.md 填了归因
- [ ] 试过调 PaddleOCR 参数（角度/阈值），救回 1-2 个 bad case
- [ ] 看完 3B1B 神经网络全 4 集，能说清"前向→误差→反向→更新"循环
- [ ] 确认涉密文档只走本地
- [ ] PyTorch 装好，能 import 并打印版本
- [ ] **自评达成 L1 会用**：能独立装、跑、拿结果

---

## 常见坑 & 卡住怎么办

- **照抄旧教程报 `use_angle_cls` / `.ocr()` 的错**：那是 2.x 写法。本机 paddleocr 3.7.0 用 `use_textline_orientation` + `.predict()`，取 `rec_texts` / `rec_scores` / `rec_polys`。本周两个脚手架已按 3.x 校准，报错时先对照它们。
- **找不到合适的复杂图片**：`input/` 已备好 25 个 case（`python make_samples.py` 可重新生成；18 张合成 + 7 个 `101~107_real_*` 真实 case）。想加自己的图就按 `108_real_xxx.jpg` 命名丢进去，重跑 `a_batch_ocr.py` 直接生效；素材可以拍生活里的招牌/票据/说明书（注意脱敏），或网上搜"场景文字识别数据集样本图"。
- **报告里的识别框没套住文字**：多半是 `USE_DOC_PREPROCESS` 被改成了 True。见模块 A 末尾的「识别框坐标的坑」。文字内容没错、只是框错位，就查这一项。
- **报告打开是乱码 / 图片不显示**：`index.html` 已带 `<meta charset="utf-8">`；原图副本在每个 case 自己的目录里（`output/a_batch_ocr/<输入名>/source.<ext>`），所以要把**整个 `a_batch_ocr/` 目录**一起移动，别只单独拷走 HTML（早期版本用 `../../input/` 跳出目录，静态服务下会 404，已修）。
- **调阈值两组结果一模一样 / 反而更差**：正常。清晰印刷体本来就没有漏检，看不出差异；换 `bad_cases/06_漏检/` 里的样本再试。本周只是"感受旋钮存在"，真正会调是 P4。别卡这。
- **报警告 `lang and ocr_version will be ignored`**：显式指定模型名时 `lang` 会被忽略（语言能力由所选模型决定）。照脚手架删掉 `lang` 即可，不影响识别结果。
- **3B1B 第 4 集公式看不懂**：**完全没关系**，这集就是劝退向的直觉铺垫，第 3 周会 just-in-time 补数学。跳过继续。
- **PyTorch 装不上**：CPU 版一般 `python -m pip install torch torchvision` 即可；报错就去 https://pytorch.org/get-started/locally/ 选对应命令。GPU 版留到第 3 周需要时再配。

---

## 进度日志（本周日填）

```
第 2 周（日期 ____）｜阶段 P0
· 本周跑通了什么：____________________
· bad case 库共攒了 ____ 个，最典型的一个是：____________
· 肉眼看 3B1B 后，我对"神经网络怎么学"的理解：____________
· 卡在哪、怎么解决的：________________
· P0 是否收尾（L1 达成）：____________
· 下周（P1-A）第一件要动手的事：____________
```

# 第 2 周笔记（P0 收尾 · 真实图片 + bad case 库）

## 我压测了哪些场景，效果如何

> 首轮基线（11-12 历史记录）由 `a_batch_ocr.py` 代跑：22 张样本，`PP-OCRv4_mobile_det/rec`，
> 关闭文档预处理，总 37.16s（含模型加载 2.62s）。
> 格式：`检出行数 / 平均置信度`。
> 当时的产物是 `output/batch_ocr_results.json` + `output/vis/`，11-13 已清理并改成
> 按 case 隔离的 `output/a_batch_ocr/`。**现在看图对照请打开
> `output/a_batch_ocr/index.html`**，跨 case 汇总看 `output/a_batch_ocr/batch_summary.txt`。

> ⚠️ **下面这张表是 11-12 首轮基线的历史记录，用的是当时的旧编号**，数据如实保留、没有改写。
> 11-13 把输入重排成「01~18 合成样本 + `real_*` 真实 case」，旧名 → 新名对照：
>
> | 旧名 | 新名 |
> |---|---|
> | `17_heavy_blur.png` | `15_heavy_blur.png` |
> | `18_glare_wipe.png` | `16_glare_wipe.png` |
> | `19_dark_shadow.png` | `17_dark_shadow.png` |
> | `20_faint.png` | `18_faint.png` |
> | `15_real_terminal.jpg` | `real_terminal_screenshot.jpg` |
> | `16_real_doc.jpg` | `real_clear_doc.jpg` |
> | `21_real_scan_p1.jpg` | `real_scan_page1.jpg` |
> | `22_real_scan_p2.jpg` | `real_scan_page2.jpg` |
>
> 重跑后的新结果一律以 `output/a_batch_ocr/batch_summary.txt` /
> `output/a_batch_ocr/index.html` 为准；逐行文字与坐标在
> `output/a_batch_ocr/<输入名>/result.json`。

| 场景 | 代表样本 | 效果 | 备注 |
|---|---|---|---|
| 清晰印刷体（对照） | `01_clear.png` 12 / 0.99、`16_real_doc.jpg` 21 / 0.94 | 好 | 识别框与文字完全对齐，作为基准 |
| 模糊 / 低质 | `02_blur` 12 / 0.96、`03_lowres` 13 / **0.38**、`11_noise` 13 / 0.64、`17_heavy_blur` **4 / 0.07** | 轻度几乎无影响，降采样与重度模糊才崩 | `17` 应有 12 行只检出 4 行，是典型漏检 |
| 倾斜 / 透视 | `04_skew` 12 / 0.99、`05_perspective` 12 / 0.99、`13_rot180` 12 / 0.98 | 好 | 8° 倾斜、梯形透视、整页倒置都正常；`use_textline_orientation` 起作用了 |
| 反光 / 光照 | `06~08` 12 / 0.99、`18_glare_wipe` **8** / 0.95、`19_dark_shadow` 12 / 0.99、`20_faint` 12 / 0.99 | 全局变暗变淡不影响；局部过曝漏 4 行 | `19` / `20` 压到 10% 亮度、13% 对比度仍全对 |
| 密集小字 / 多栏 | `09_dense_small` 35 / 0.96（标准答案 28 行）、`22_real_scan_p2` 58 / 0.85 | 行数膨胀、部分低置信 | 疑似一行被拆成多块，需看带框图确认 |
| 手写（只观察） | `12_handwriting` 4 / 0.99 | 基本能认 | ⚠️ 用的是**行楷印刷字体，不是真手写**，样本不具代表性；建议自己手写一张拍照替换，本计划仍不攻手写 |
| 真实复杂文档 | `21_real_scan_p1` 76 / 0.60（35 行低置信）、`15_real_terminal` 4 / **0.17** | 最差 | 真实扫描件的噪点 + 印章 + 版面是复合退化，比任何单因素合成图都难 |

## 本次实测的三个关键观察

1. **模型对"全局"退化异常鲁棒，怕的是"信息被物理抹除"。**
   模糊 2.4、倾斜 8°、透视、倒置 180°、亮度压到 10%、对比度压到 13%，
   全都稳定在 0.96~0.99；真正让它崩的是降采样（细节永久丢失）、
   强反光过曝（文字像素洗成纯白）、重度模糊（笔画糊成色块）。
2. **置信度筛不出漏检。** `18_glare_wipe.png` 漏了 4 行，但留下的 8 行平均 0.95，
   只看 JSON 的 `avg_score` 会完全错过它。必须看带框图：**原图有字、没有框**才是漏检。
3. **坐标基准有个 3.7.0 的坑。** 默认的「整页方向分类 + UVDoc 去扭曲」会让
   `rec_polys` 基于矫正后的图像，画回原图整体错位（实测标题框 y=27~66，
   墨迹实际 y=66~98）。关闭后完全吻合。代价是 `15_real_terminal.jpg` 从
   6 行 / 0.90 掉到 4 行 / 0.17 —— 预处理对某些图确实有用。
   配置区 `USE_DOC_PREPROCESS` 可切换，取文字与取坐标是两种取舍。

## 调参数救回了哪个 bad case，调了什么
- （Day 3 自己填。建议拿 `18_glare_wipe.png` 或 `03_lowres.jpg` 跑 `c_try_params.py`，
  对比默认阈值 0.3/0.6 与调低后的 0.2/0.4，看是"救回漏检"还是"多了误检"。）
- 已知结果：`18_glare_wipe.png` 两组都是 8 行 / 0.95、**0 差异**。
  这不代表"没有漏检"，而是过曝区的文字像素已不存在，调阈值无能为力。
  这正是「参数不是万能的」的第一个实例，值得记下来。

## 看完 3B1B 4 集，我对"神经网络怎么学"的理解
- 

## P0 收尾自评（L1 会用达成了吗）
- 

## 11-13 · 输入重排 + 让文本层 PDF 进对比预览

**需求**：把 week-01 的样例搬进 week-02/input 并排在最后；所有真实 case 也排最后；
真实 case 统一 `real_` 前缀、名字一眼看懂、去掉重复；重跑结果；
再把第1周「有文本层 PDF 的表格直读」搬到第2周，好用对比预览看提取效果。

**输入整理**
- 18 张合成样本改成连续编号 `01~18`（原 17~20 → 15~18）。
- 真实 case 统一 `real_` 前缀：`real_terminal_screenshot.jpg`、`real_clear_doc.jpg`、
  `real_bank_statement_textlayer.pdf`、`real_certificates_scan.pdf`、
  `real_transactions_gbk.csv`、`real_scan_page1.jpg`、`real_scan_page2.jpg`。
  字母 r 的字典序在数字之后，`sorted()` 时天然全部排在最后。
- **去重**：MD5 核对发现两对字节级相同的副本（`test1.jpg` / `test2.jpg` 各存了两份），
  删掉副本只留正本（旧名都在 git 里，可恢复）。`real_scan_page1/2` 是 PDF 渲染页
  缩放出来的 JPEG，与 PDF 原件内容不同，保留为独立的扫描 bad case。
- `make_samples.py` 把原来三段清单合并成一张 `REAL_CASES`（copy / scan 两种来源），
  重跑不会再生成重复文件；manifest 新增 `group` 字段区分合成 / 真实。

**文本层 PDF 接入**（新模块 `text_layer_extract.py`）
- 移植第1周的策略回退：线型诊断 → `TABLE_STRATEGIES` → 人工列边界模板 → 清洗 + 填充率。
  `real_bank_statement_textlayer.pdf` 配 9 条竖线，抽出 105×8、8 列表头正确。
- `a_batch_ocr.py` 按后缀分三路：图片 OCR / PDF 首页渲染成图后 OCR + 文本层直读 /
  CSV 纯文本解析（不跑模型）。PDF 渲染必须 `set_cropbox(mediabox)`，否则只出
  910×218 的顶部一条（整页 910×1287）—— 第1周裁剪陷阱的又一次体现。
- `vis_ocr_result.py` 每张 PDF/CSV 卡片下方新增「直读结果」区：抽出的表格、
  策略 / 行列数 / 填充率、抽取诊断、CSV 原文；顶部汇总加「直读表格」「真实 case」统计。
  表格按原始抽取顺序平铺，**不假设第 1 行是表头**（这文件第 1 行其实是页眉）。

**验证**（不加载模型）：5 个脚本 `py_compile` 通过；`extract_case()` 对两个 PDF + 一个
CSV 结果正确；构造 3 类 record 生成报告，10 项 HTML 检查全通过。
（当时产物路径是 `output/batch_ocr_results.json` + `output/vis/`，
11-13 晚已改成两层隔离的 `output/a_batch_ocr/`，见下一节。）

## 11-13 晚 · 101 起编号 + 新增 case 自动生效 + 产物按 case 隔离

**需求**：真实 case 改成 `101_real_xxx` 这种数字前缀（从 101 起）方便查找；
希望以后新增 case 只要丢进 `input/` 重跑就直接生效；
输出不要全挤在一个大 JSON 里，改成和第 1 周一样按输入隔离，方便排查。

**为什么「只改文件名 + 重跑」原本不生效**（实测 5 处耦合）：

| 位置 | 原来的写法 | 改名后的后果 |
|---|---|---|
| `vis_ocr_result.py` 卡片分组 | `info.get('group', 'synthetic' if name[:2].isdigit() else 'real')` | `101_` 前两位是数字 → 未登记的新 case 被误判成合成样本 |
| `vis_ocr_result.py` 顶部统计 | 只数 manifest 里 `group=='real'` | 改名后匹配不上，真实 case 数变 0 |
| `text_layer_extract.py` 列边界模板 | 字典键写死 `real_bank_statement_textlayer.pdf` | 模板失效，8 列表格退回 `text` 策略（7 列、借贷合并） |
| `c_try_params.py` 默认图 | 写死 `input/real_terminal_screenshot.jpg` | 直接 FileNotFoundError |
| `make_samples.py` / manifest | `REAL_CASES` 与 `file` 字段都是旧名 | 重跑生成旧名副本、卡片说明丢失 |

还有一个**隐蔽的排序坑**：字典序里 `'101_'` 比 `'10_'` 小（第二位 `'0'` < `'_'`），
`ls`/`sorted()` 实测把 `101~107` 插在 `09_` 和 `10_` 之间，反而没排到最后。
所以「靠字母 r 排在数字之后」的老办法在三位编号上彻底失效，必须显式分组排序。

**做法**
- 新建 **`case_naming.py`** 作为唯一真相源：`REAL_START_NO=101`、
  `parse_no()` / `strip_no()` / `case_dir_name()` / `is_real_case()` /
  `case_group()` / `case_sort_key()` / `next_real_no()` / `pick_real_image()`。
  分组优先级：manifest 明确登记 > 编号 ≥ 101 > 旧 `real_` 前缀；
  排序 `(分组, 编号, 文件名)`，真实 case 恒排最后、组内按编号升序。
- 输入重命名为 `101_real_terminal_screenshot.jpg` ~ `107_real_scan_page2.jpg`；
  manifest 的 `file`/`design`/`groups` 同步，`REAL_CASES` 同步；
  `make_samples.py` 重跑时会把**用户新增 case 补登记**进说明书，不会再冲掉。
- 新增 case 自动生效：`list_cases()` 只按后缀过滤、不查清单；分组靠命名规则推断；
  日志打印「未登记的新 case」与下一个建议编号（当前是 108）。
  `TABLE_COLUMN_LINES` 改按 `strip_no()` 的语义名匹配，换编号不失效；
  `c_try_params.py` 默认图改成 `pick_real_image()` 自动挑。
- **输出两层隔离**（与 week-01 一致）：
  `output/a_batch_ocr/<输入名>/` 放 `result.json`、`result.txt`、`source.<ext>`、
  `boxes.png`、`pages/p1.png`；根目录只放 `index.html` +
  `batch_summary.json/.txt`。报告用 `<case>/source.<ext>` 相对路径引用图片，
  整目录可搬走；卡片上有「本 case 的 result.json」直达链接。
  重跑前 `prepare_case_dir()` 只清固定名单的旧产物，废弃的旧 case 目录只提示不删。
  `vis_ocr_result.py` 独立运行时改成遍历各 case 目录读回 `result.json`。
  `c_try_params.py` 的产物也挪到 `output/c_try_params/`。

**验证**（不加载模型）：6 个脚本 `py_compile` 通过；命名规则（101 排最后、
旧名兼容、未登记 108 判真实、next=108、默认图自动挑）全通过；
`103_...pdf` 仍命中 explicit 模板抽出 105×8、8 列表头正确；
临时目录模拟新增 case，扫描顺序正确；报告的相对路径、单 case 链接、
真实 case 统计、独立读回顺序均正确；清单 / manifest / 磁盘三者 25 个一致。

**实跑收尾（11-13 晚，`paddle` 环境代跑）**：清掉旧结构 `output/vis/`（49 个旧命名
`real_*` 文件），重跑 `a_batch_ocr.py`（25 个 case，总 99.37s，含模型加载 7.49s）
和 `c_try_params.py`（默认图自动挑到 `101_real_terminal_screenshot.jpg`；
两组都是 4 行 / 0.17，说明**调低阈值救不回过曝已经消失的笔画**）。

- 25 个 case 目录各有 `result.json` / `result.txt` / `source.<ext>`；
  22 张图 + 2 个 PDF 另有 `boxes.png`，2 个 PDF 另有 `pages/p1.png`。
- 顺序 `01~18` → `101~107`，真实 case 恒排最后；汇总记 25 个 / 真实 7 个。
- `103_...pdf` 文本层 explicit 模板仍抽出 105×8（填充率 0.293，
  `cropbox_limited=True`）；`104` 扫描件无文本层、0 张表（符合预期）；
  `105` GBK CSV 直读 2×8、OCR 行数 0。`index.html` 74 个相对引用全部可达。
- 真实 case 值得留作 bad case 素材：`101` 终端亮字暗底 4 行 / 0.17，
  `106` 扫描页 76 行 / 0.60（35 行低置信），`104` 证书扫描 53 行 / 0.52；
  而 `103` 有文本层的流水 OCR 226 行 / 0.98，正好对照「像素路线 vs 直读路线」。

**顺手补的一个缺口**：CSV 分支原来不复制源文件，`105_.../` 目录搬走会丢原始输入。
`vis_ocr_result.py` 的 `prepare_image()` 改名 `copy_source()`，三类输入统一留副本，
CSV 卡片加「查看原始文件」链接；只重画报告就生效，不用重跑 OCR。
文档里残留的 `output/vis/index.html` / `batch_ocr_results.json` 指引已全部改成新路径。

## 11-13 晚 · 把「谁调用谁」写进代码和文档

**问题**：`case_naming.py` / `text_layer_extract.py` / `vis_ocr_result.py` 都被
`a_batch_ocr.py` 调用，但关系散落在注释和各处 import 里，单独打开某个模块
看不出「我是被谁用的、我能不能单独跑」。

**核实到的关系**（在 week-02 搜 import 得来，不是凭印象）：
- ①② `case_naming.py`、`text_layer_extract.py` 在 a 的文件顶部 import；
  前者全程用，后者只在 `build_case_record()` 的 PDF / CSV 分支。
- ③ `vis_ocr_result.py` 在 `main()` 里函数内 import（懒加载），`MAKE_VIS=True`
  时调 `build_report()`；画报告失败不影响已落盘的 JSON / TXT。
- `case_naming.py` 另被 `c_try_params.py` / `make_samples.py` /
  `text_layer_extract.py` / `vis_ocr_result.py` 引用，共 **5 个调用方**。
- 只有 `vis_ocr_result.py`、`c_try_params.py` 带 `main()` 能独立跑；另两个是纯模块。

**四层体现**（从「打开文件」到「跑一次」逐级可见）：
1. 三个模块各自 docstring 顶部加「谁在调用我」小节 —— 打开即见。
2. `a_batch_ocr.py` 文件头加 ASCII 调用关系图；import 区按 ①②③ 编号标注，
   ③ 的懒加载处也补对应编号注释。
3. 配置区 `SHOW_DEPS=True`，`main()` 开头用 `show_dependencies()` 打印依赖树，
   跑一次就能看见，不必只读注释；想安静就改 False。
4. README 新增「脚本地图：谁调用谁」章节（图 + 角色表 + 懒加载原因）。

**验证**：6 脚本 `py_compile` 通过；`import a_batch_ocr` 后单独调
`show_dependencies()` 输出正确；`python vis_ocr_result.py` 独立重画报告正常；
文档里 `text_layer_extract` 的调试命令实测输出 `pdf 1 105`。
**没有重跑 OCR** —— 这次只改注释 / 文档 / 日志打印，产物内容不变。

**顺手修掉一个隔离漏洞**：验证那条 `text_layer_extract` 调试命令时发现，
`PDF_PAGES_DIR` 默认值原是 `output/a_batch_ocr/pages` —— 单独调试（不传
`pages_dir`）会在正式产物根目录多出一个「不属于任何 case」的 `pages/`，
还会被 `report_stale_cases()` 当成废弃 case 误报。已改成
`output/text_layer_extract/pages`（按脚本名隔离），并让 `report_stale_cases()`
跳过 `pages` / `__pycache__` 这类非 case 目录。
复核：正式产物根 25 个目录、`多余 = []`、误报为空；调试页图按脚本隔离保留供核对。

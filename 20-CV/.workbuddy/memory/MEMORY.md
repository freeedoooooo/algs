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
- **week-02 产物隔离（2026-11-13 晚）**：与 week-01 同规则 —— `output/a_batch_ocr/<输入名>/` 放 `result.json` / `result.txt` / `source.<ext>` / `boxes.png` / `pages/p1.png`，脚本目录根只放 `index.html` + `batch_summary.json/.txt`；`c_try_params.py` 产物放 `output/c_try_params/`。报告引用各 case 目录里的图片副本，整目录可搬走；卡片带「本 case 的 result.json」链接。用户原话「一整个输出的 json 都在一起看着不方便」。重跑前 `prepare_case_dir()` 只清固定名单的旧产物，废弃的旧 case 目录只提示不删。
- **有文本层 PDF 的表格不要转图走 OCR 模型**（2026-11-13 定稿）：字符精确、带坐标/字体/矢量线，直读快两个数量级。方案分层：判载体 → lattice/stream 策略解析（pdfplumber `TABLE_STRATEGIES`，无竖线的 stream 型必须回退 `text`）→ 人工列边界模板（固定版式最稳，自动 words 聚类实测会混进页眉）→ 仅失败页转图走表格模型 → 业务校验。week-01 `weekend_pipeline.py` 与 week-02 `text_layer_extract.py` 各维护一份，不互相 import。
- **pymupdf 渲染被裁剪的 PDF**：默认按 CropBox，只出顶部一条；要 `page.set_cropbox(page.mediabox)` 才渲染整页（test3.pdf 910×218 → 910×1287）。

## PaddleOCR 3.7.0 坐标基准（2026-11-12 实测，涉及画识别框时必须遵守）
- 默认 `use_doc_preprocessor=True`（整页方向分类 + UVDoc 去扭曲）会让 `rec_polys` / `dt_polys` 基于**矫正后图像**，直接画回原图整体错位。
- 凡要把框叠到原图上，构造时加 `use_doc_orientation_classify=False, use_doc_unwarping=False`；week-02 已做成配置区开关 `USE_DOC_PREPROCESS`（默认 False）。
- 只取文字、不需要坐标时可保留默认：实测 UVDoc 会让亮字暗底终端截图识别更好（6 行/0.90 vs 关闭后 4 行/0.17），属质量与坐标的权衡。
- week-02 已做成配置区开关 `USE_DOC_PREPROCESS`（默认 False）。week-01（2026-11-12 优化后）：`b_ocr_image.py` 要画框，同样默认关闭并产出带框 PNG + 自包含 HTML；`weekend_pipeline.py` 只取文字不画框，**刻意保留默认开启**，两者不要统一。
- 用户不接受只看 JSON 的结果呈现；OCR 结果一律配「带框 PNG + 离线 HTML 对照报告」。

## PaddleX 3.7.0 表格 HTML 导出坑（2026-11-13 实测）
- `result.save_to_html(文件路径)` 内部是 `html[list(html.keys())[0]]`；`res.html` 为空字典（这一页没表格）时抛 `IndexError`。多页 PDF 里证书扫描页必踩，不是识别失败。
- 同一方法遇「一页多张表」只写第一张并打 warning，会悄悄丢数据。
- 统一做法：先判 `res.html` → 空则从 `parsing_res_list` 的 `[table]` 块 `block_content` 兜底 → 仍空就跳过该页并打印序号；多表按 key 拆文件。week-01 `d_table_ocr.py` 的 `export_html()` 已实现，`weekend_pipeline.table_ocr_page()` 已加判空守卫。

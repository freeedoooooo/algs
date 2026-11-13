"""
第2周 · 模块A：批量跑真实图片（PaddleOCR 3.7.0 版，可直接运行）

【这份脚本在做什么】
把 input/ 下的 case 逐个处理，把「每个 case 提取到什么」存成结构化结果，
用来建立 "什么场景效果好、什么场景效果差" 的直觉，并为 bad case 库挑素材。

11-13 起支持三类输入，按后缀自动分流：
    图片 (.png/.jpg/...)  → PaddleOCR 逐张识别（原有能力）
    PDF  (.pdf)           → 首页渲染成图给 OCR；**有文本层时额外直读表格**
                            （策略回退见 text_layer_extract.py，完全不加载表格模型）
    CSV/TXT (.csv/...)    → 直接按文本读，解析成表格，不跑 OCR
11-13 下午新增：表格不再只是「文字之外的补充」，而是一等公民。
三类输入都会再过一遍 table_extract.py：有文本层就直读、无文本层就先
长直线预筛再走表格结构模型，最终每个 case 目录里额外产出 tables.json +
table_N.csv（可直接用 Excel 打开）。典型例子：103 银行流水、107 备案名单。

【脚本之间怎么串起来】（11-13 补：想一眼看清「谁调用谁」就看这里）
本脚本是本周**唯一的主入口**，另外 4 个模块都是被它调用的：

    a_batch_ocr.py  ← 你只需要运行这一个
        ├── case_naming.py        ① 文件顶部 import，全程用
        │                          命名 / 分组 / 排序 / 输出目录名
        ├── text_layer_extract.py ② 文件顶部 import，只在 PDF / CSV 分支
        │                          build_case_record() 里调 extract_case()
        ├── table_extract.py      ④ 文件顶部 import，build_case_record() 末尾
        │                          调 enrich_case()：表格检测 + 结构化 + 导出 CSV
        └── vis_ocr_result.py     ③ main() 里「用到才 import」（懒加载）
                                  build_report() 生成对照报告

    另外 case_naming.py 是公共底座，还被 c_try_params.py / make_samples.py /
    text_layer_extract.py / vis_ocr_result.py 引用（一共 5 个调用方）。
    ④ 内部会复用 ② 的直读结果，并在确实需要时懒加载 PPStructureV3。

为什么 ③ 不写在文件顶部：画图是附加功能。放在 main() 里、并裹在 try 中，
即使报告生成失败，已经落盘的 result.json / result.txt 也不会白跑。
这种「用到才 import」叫懒加载，是 Python 很常见的写法。

单独运行：python vis_ocr_result.py（只重画报告）、
python text_layer_extract.py（只测文本层直读，默认 case 103）、
python table_extract.py（只测表格提取，默认 103 + 107 两条路线）、
python c_try_params.py（调参）；case_naming.py 是纯函数模块，没有 main()。
只想验证某个 case 的「直读」抽得对不对 → 跑 text_layer_extract.py 就够（不加载模型）；
只想验证「表格结构化 / CSV 导出」对不对 → 跑 table_extract.py（也不跑 a 的 OCR）；
想看它和 OCR 识别框并排的对比 → 仍要跑本脚本走完整流水线。

环境（本机 miniforge，环境名就是 paddle）：
    conda activate paddle

用法（在 week-02 目录下）：
    python a_batch_ocr.py                        # 用配置区 INPUT_DIR
    python a_batch_ocr.py ../week-01/input       # 命令行临时指定别的输入目录

产物（两层隔离，和第1周一致：脚本一层、每个输入一层）：
    output/a_batch_ocr/
        index.html                  ★ 跨 case 对比报告（可离线打开）
        batch_summary.json / .txt   ★ 跨 case 汇总表（只放关键指标，一眼看全）
        <输入文件名去后缀>/
            result.json             这个 case 的完整结果：文字 / 置信度 / 坐标 / 直读表格
            result.txt              这个 case 的纯文本结果
            tables.json             ★ 结构化表格（表头 + 数据行 + 提取路线 + 诊断）
            table_1.csv …           ★ 可直接用 Excel 打开的表头 + 数据行
            source.<ext>            输入副本（图片=原图 / PDF=首页渲染图 / CSV=原始文本）
            boxes.png               原图 + 识别框（纯文本没有像素，不生成）
            pages/p1.png            PDF 首页渲染图（中间产物，单独一层，跑完保留）
排查某个 case 时只看它自己的目录即可，不用再在一整个大 JSON 里翻找。
可视化由 vis_ocr_result.py 生成，跑完本脚本会自动调用；不想要可把 MAKE_VIS 改 False。

【新增 case 怎么用】
直接把文件丢进 input/，自己的素材从 101 起编号（101_real_xxx.jpg、108_real_xxx.pdf …）。
不用改任何脚本、不用改清单，重跑本脚本就自动扫到并按规则分组排序；
命名 / 分组 / 排序规则集中在 case_naming.py，是唯一真相源。
重跑时每个 case 目录里本脚本自己生成的旧文件会先清掉再重建。

【与第1周的关系】
第1周的 b_ocr_image.py 一次只跑一张图；这里复用同样的 3.x API，
只是外面套了一层「遍历目录 → 逐张记录 → 统一落盘」。
模型在进程里只加载一次，之后每张图只剩推理耗时。

【3.x 与 2.x 的三个区别（第1周踩过的坑）】
    use_angle_cls            → use_textline_orientation
    ocr.ocr(path, cls=True)  → ocr.predict(path)
    result[0] / line[1][0]   → res['rec_texts'] / res['rec_scores'] / res['rec_polys']
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_DIR = 'input'                              # 输入目录（相对当前工作目录）
OUT_ROOT = 'output/a_batch_ocr'                  # 本脚本专属产物根目录（第一层隔离）
# 下面这些只写「文件名」，实际路径由 OUT_ROOT/<case 目录>/ 拼出来（第二层隔离）。
RESULT_JSON = 'result.json'                      # 每个 case 的完整结构化结果
RESULT_TXT = 'result.txt'                        # 每个 case 的纯文本结果
SOURCE_BASENAME = 'source'                       # 原图副本的主文件名（扩展名沿用原图）
BOXES_NAME = 'boxes.png'                         # 带框 PNG
PAGES_SUBDIR = 'pages'                           # case 内的中间产物子目录
# 跨 case 的汇总表放 OUT_ROOT 根目录，不带 case 名。
SUMMARY_JSON = 'batch_summary.json'
SUMMARY_TXT = 'batch_summary.txt'
DET_MODEL = 'PP-OCRv4_mobile_det'                # 检测模型（找文字在哪）
REC_MODEL = 'PP-OCRv4_mobile_rec'                # 识别模型（读出来）
# 模型说明：无 GPU 时 server 大模型在 CPU 上极慢（第1周实测 104s vs mobile 3.8s），
#           这里沿用第1周已缓存的 mobile 模型，免下载、跑得快。
LOW_SCORE = 0.8                                 # 低于此置信度算「可疑行」，用于挑 bad case
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp')   # 图片：走 PaddleOCR
PDF_EXTS = ('.pdf',)                             # PDF：渲染首页走 OCR + 有文本层时直读表格
TEXT_EXTS = ('.csv', '.txt', '.md')              # 纯文本：直接读，不跑 OCR
SUPPORTED_EXTS = IMAGE_EXTS + PDF_EXTS + TEXT_EXTS
# 文档预处理开关（整页方向分类 + UVDoc 去扭曲）：
#   False（推荐）：坐标就是原图像素坐标，可视化报告里的框才套得准；少加载 2 个模型。
#   True         ：对弯曲/歪斜的真实拍照文档可能识别更好，但 rec_polys 会基于
#                  矫正后的图像，画回原图时框会整体错位。想试时改成 True 再跑一次。
USE_DOC_PREPROCESS = False
MAKE_VIS = True                                  # 跑完自动生成可视化对照报告（建议保持 True）
# 表格检测与结构化提取：只对明确含表格的真实 case 生效
# （用户 11-13 指定：103 文本层银行流水、107 扫描备案表）。
# 其它 22 个 case 一律只做原来的文本提取，不跑表格逻辑、不生成 tables.json / table_N.csv，
# 这样它们的产物和以往完全一致，也不会因为表格预筛 / 模型异常被连累。
# 想给更多 case 加表格提取，只往 TABLE_EXTRACT_CASES 里加「去后缀的输入文件名」即可
# （命名规则与输出目录名一致：文件名去掉扩展名，如 103_real_bank_statement_textlayer）。
TABLE_EXTRACT = True
TABLE_EXTRACT_CASES = ['103_real_bank_statement_textlayer', '107_real_scan_page2']
SHOW_DEPS = True                                 # 运行时打印「本次用到哪些模块」，想让日志安静改 False
MANIFEST_NAME = 'samples_manifest.json'          # 说明书文件名，脚本会在输入目录里找它
# ==========================================================================

import os       # 拼路径、列目录、建文件夹
import sys      # 读命令行参数 sys.argv
import json     # 把结果写成 .json 文件
import time     # 计时：perf_counter() 相减得到秒数

# 这两个环境变量必须在 import paddleocr 之前设置：paddlex 在被导入时会读一次并「快照」，
# 之后再改就无效了。BOS 是国内模型源，避免第1周遇到的 HuggingFace 下载卡住。
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

from paddleocr import PaddleOCR  # noqa: E402  （放在 env 设置之后是故意的）

# ---------- 本项目的依赖模块（对应关系见文件头「脚本之间怎么串起来」）----------
# ① case_naming.py —— 纯函数，全程用：list_cases() / case_rel_name() / save_results() / main()
import case_naming as naming                # noqa: E402
# ② text_layer_extract.py —— 只依赖 pdfplumber + pymupdf，不加载任何 OCR 模型。
#    单独成模块是为了让「哪些结果来自像素、哪些来自文字本身」在代码里就分得清；
#    只在 build_case_record() 的 PDF / CSV 分支调 extract_case()。
from text_layer_extract import extract_case  # noqa: E402
# ④ table_extract.py —— 表格检测 / 结构化 / 导出 CSV，在 build_case_record() 末尾
#    调 enrich_case()。它自己不 import paddleocr（模型在用到时才懒加载），
#    所以放文件顶部 import 很轻，不会拖慢启动。
from table_extract import enrich_case        # noqa: E402
# ③ vis_ocr_result.py 不在这里 import —— 它在 main() 里懒加载，见下方 MAKE_VIS 分支。


def show_dependencies():
    """
    运行时打印「本次会用到哪些模块」，让调用关系不只写在注释里，跑一次也能看见。
    由配置区 SHOW_DEPS 控制；这里只打印文本，不额外 import 任何东西
    （①②④ 已在文件顶部加载完，③ 要等画报告时才加载；④ 内部的表格模型
     更要等「预筛命中网格」才加载）。
    """
    print('>> 本次运行会用到的模块（主入口：a_batch_ocr.py）：')
    print('   ① case_naming.py         命名 / 分组 / 排序（已随本脚本加载）')
    print('   ② text_layer_extract.py  PDF / CSV 直读（已随本脚本加载）')
    print('   ④ table_extract.py       表格检测 + CSV 导出（已随本脚本加载）')
    print('   ③ vis_ocr_result.py      对照报告（画报告时才加载，懒加载）')
    print('      └ PPStructureV3       表格结构模型（仅网格命中的 case 才加载）')


def list_cases(src_dir):
    """
    列出目录里所有支持的 case，返回完整路径列表。

    只按后缀过滤，**不查任何清单**：新丢进来的文件立刻就能被扫到，
    这就是「新增 case 重跑直接生效」的关键。
    排序用 naming.case_sort_key：合成样本在前、真实 case 恒排最后，
    组内按数字编号升序。不能用纯 sorted() —— 字典序里 '101_' 会插到
    '10_' 前面，真实 case 反而跑到合成样本中间去了。
    """
    if not os.path.isdir(src_dir):
        sys.exit(
            f'找不到输入目录：{os.path.abspath(src_dir)}\n'
            f'改文件顶部的 INPUT_DIR，或命令行指定：python a_batch_ocr.py 输入目录'
        )
    # name.lower().endswith(...) 让 .JPG 这种大写后缀也能被认出来。
    names = [name for name in os.listdir(src_dir)
             if name.lower().endswith(SUPPORTED_EXTS)]
    names.sort(key=naming.case_sort_key)
    return [os.path.join(src_dir, name) for name in names]


def read_manifest(src_dir):
    """读样本说明书，返回 {文件名: 条目}；文件不存在就返回空字典（不影响跑批）。"""
    path = os.path.join(src_dir, MANIFEST_NAME)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return {item['file']: item for item in (data.get('samples') or [])
            if isinstance(item, dict) and item.get('file')}


def case_rel_name(name, used):
    """
    算出这个 case 的输出目录名 = 输入文件名去后缀。
    万一出现同名不同后缀（a.jpg / a.png），给后者加上后缀避免互相覆盖。
    """
    rel = naming.case_dir_name(name)
    if rel in used:
        rel = f'{rel}_{os.path.splitext(name)[1].lstrip(".").lower()}'
    used.add(rel)
    return rel


def prepare_case_dir(case_abs):
    """
    重跑前清掉这个 case 目录里的**表格类旧产物**，再确保目录存在。

    为什么只清表格文件、不清 result.json / boxes.png / source.* ：
        后面 save_results（写 result.json / result.txt）、copy_source（写 source.*）、
        draw_boxes_png（写 boxes.png）都是用「w」模式把同名文件**覆盖重写**，
        清不清理结果都一样新；
        而 tables.json / table_*.csv 只有 enrich_case() 给 103 / 107 写，
        其它 case 不会重写，留着就会变成「新旧混存」，所以只针对它们清理。
    好处：一次全量重跑最多删十来个文件，不会触发批量删除保护
    （之前把 result.json 等也一起删，25 个 case 累计删 50+ 被沙箱拦中断过）。
    安全边界：不递归、不删子目录、不碰你手工放进去的文件。
    """
    os.makedirs(case_abs, exist_ok=True)
    removed = 0
    for name in os.listdir(case_abs):
        path = os.path.join(case_abs, name)
        if not os.path.isfile(path):
            continue
        is_table = (name == 'tables.json'
                    or (name.startswith('table_') and name.lower().endswith('.csv')))
        if is_table:
            os.remove(path)
            removed += 1
    pages = os.path.join(case_abs, PAGES_SUBDIR)
    if os.path.isdir(pages):
        for name in os.listdir(pages):
            path = os.path.join(pages, name)
            if os.path.isfile(path) and name.lower().endswith('.png'):
                os.remove(path)
                removed += 1
    return removed


def report_stale_cases(current_rels):
    """
    旧编号残留的 case 目录只提示、不自动删，避免误删你放进去的东西。

    pages / __pycache__ 这类非 case 目录不算「废弃 case」，直接跳过 ——
    它们不是某个输入对应的输出，提示出来只会让人误会。
    """
    if not os.path.isdir(OUT_ROOT):
        return
    stale = sorted(name for name in os.listdir(OUT_ROOT)
                   if os.path.isdir(os.path.join(OUT_ROOT, name))
                   and name not in current_rels
                   and name not in (PAGES_SUBDIR, '__pycache__'))
    if stale:
        print(f'>> 提示：有 {len(stale)} 个旧 case 目录已不再对应输入（不会自动删除）：')
        for name in stale:
            print(f'   {name}/')


def build_ocr():
    """创建 OCR 引擎（这一步会加载模型，整个进程只做一次）。"""
    print(f'>> 初始化 PaddleOCR（det={DET_MODEL}, rec={REC_MODEL}），首次加载稍慢…')
    t0 = time.perf_counter()
    ocr = PaddleOCR(
        text_detection_model_name=DET_MODEL,
        text_recognition_model_name=REC_MODEL,
        use_textline_orientation=True,   # 3.x 名称，替代已废弃的 use_angle_cls
        # 不传 lang：显式指定模型名时 lang / ocr_version 会被忽略并报警告，
        # 语言能力已由所选模型决定（PP-OCRv4_mobile_rec 本身就是中英模型）。
        #
        # ↓ 由顶部 USE_DOC_PREPROCESS 控制，默认 False（关闭）。
        # 默认开启的「整页方向分类 + UVDoc 去扭曲」会先把图片矫正一遍，
        # 返回的 rec_polys 是矫正后图像的坐标，直接画回原图时框会整体偏移
        # （实测标题框 y=27~66，而标题墨迹实际在 y=66~98）。
        # 关闭后坐标就是原图像素坐标：标题框 [[74,67],[461,98]] 与墨迹
        # y66~98 / x71~462 完全吻合，可视化报告才准确；顺带少加载 2 个模型。
        # 识别出来的「文字内容」不受影响，受影响的只有坐标。
        # 以后若真要处理弯曲/拍照歪斜的文档可以再打开，但那时需自行做坐标反变换。
        use_doc_orientation_classify=USE_DOC_PREPROCESS,
        use_doc_unwarping=USE_DOC_PREPROCESS,
    )
    print(f'>> 模型加载耗时：{time.perf_counter() - t0:.2f}s')
    return ocr


def to_plain(value):
    """坐标是 numpy 数组，不能直接写进 JSON；.tolist() 转成普通 list。"""
    return value.tolist() if hasattr(value, 'tolist') else value


def recognize(ocr, path):
    """识别一张图，返回一条 dict 记录。"""
    t0 = time.perf_counter()
    results = ocr.predict(path)          # 3.x 用 predict，返回 list[结果对象]
    elapsed = time.perf_counter() - t0

    # predict 对单张图通常只返回 1 个结果；写成循环是为了兼容一次多图的情况。
    texts, scores, boxes = [], [], []
    for res in results:
        texts.extend(res['rec_texts'])                       # 每行文字
        scores.extend(float(s) for s in res['rec_scores'])   # 对应置信度
        polys = res.get('rec_polys') or res.get('dt_polys') or []
        boxes.extend(to_plain(b) for b in polys)             # 每行文字的四点坐标

    avg = sum(scores) / len(scores) if scores else 0.0
    return {
        'file': os.path.basename(path),
        'lines': len(texts),
        'avg_score': round(avg, 4),
        'low_score_lines': sum(1 for s in scores if s < LOW_SCORE),
        'elapsed': round(elapsed, 2),
        'texts': texts,
        'scores': [round(s, 4) for s in scores],
        'boxes': boxes,
    }


def build_case_record(ocr, path, case_abs):
    """
    按后缀分流处理一个 case，统一返回一条 dict 记录。
    case_abs 是这个 case 的专属输出目录，PDF 首页渲染图会落到它的 pages/ 里。

    三类输入共用同一套字段（file / lines / texts / scores / boxes ...），
    这样 vis_ocr_result.py 不用关心输入类型；多出来的字段：
        kind              'image' / 'pdf' / 'csv'
        preview_image     PDF 首页渲染图路径（图片用原图，CSV 没有图）
        pages / text_layer / cropbox_limited / tables / diagnostics
        plain_text / encoding   纯文本分支用
    """
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()

    def finish(rec):
        """
        所有分支的统一出口：只有「明确要表格提取的 case」才过 enrich_case()，
        把结构化表格写回 rec，并写出 tables.json / table_N.csv。
        其它 case 原样返回，保持原来的纯文本提取产物不变（不生成任何表格文件）；
        表格是增强功能，enrich_case 内部自己吞掉模型异常，OCR 结果永不被连累。
        """
        stem = naming.case_dir_name(name)
        if TABLE_EXTRACT and stem in TABLE_EXTRACT_CASES:
            return enrich_case(rec, path, case_abs)
        return rec

    # ---- 图片：先 OCR，再判有没有表格网格（107 这种扫描表格会命中）----
    if ext in IMAGE_EXTS:
        rec = recognize(ocr, path)
        rec['kind'] = 'image'
        rec['preview_image'] = None
        return finish(rec)

    # ---- PDF / CSV：先走「直读」，不加载任何模型 ----
    # PDF 首页渲染图放进 <case 目录>/pages/，每个输入各一份，互不干扰。
    extra = extract_case(path, pages_dir=os.path.join(case_abs, PAGES_SUBDIR))
    if extra['kind'] == 'csv':
        # 纯文本没有像素，也就没有识别框和置信度；给它一套空字段保持结构统一。
        rec = {
            'file': name, 'lines': 0, 'avg_score': 0.0,
            'low_score_lines': 0, 'elapsed': 0.0,
            'texts': [], 'scores': [], 'boxes': [],
            'plain_text': extra['plain_text'],
        }
    else:
        # PDF：把首页渲染成 PNG 再当普通图片喂给 OCR，
        # 这样 rec_boxes 的坐标正好对应预览里那张图，框不会错位。
        png = extra['preview_image']
        rec = recognize(ocr, png) if png and os.path.isfile(png) else {
            'file': name, 'lines': 0, 'avg_score': 0.0,
            'low_score_lines': 0, 'elapsed': 0.0,
            'texts': [], 'scores': [], 'boxes': [], 'error': 'PDF 首页渲染失败',
        }
        rec['plain_text'] = ''
        # ★ recognize() 内部用 os.path.basename(path) 当 file，这里 path 是
        #   PDF 首页渲染出的 PNG。必须改回 case 原名，否则 JSON 里会记成
        #   xxx_p1.png，manifest 匹配不上，预览卡片标题也会变成渲染图名。
        rec['file'] = name

    rec['kind'] = extra['kind']
    rec['preview_image'] = extra['preview_image']
    rec['pages'] = extra['pages']
    rec['text_layer'] = extra['text_layer']
    rec['cropbox_limited'] = extra['cropbox_limited']
    rec['tables'] = extra['tables']
    rec['diagnostics'] = extra['diagnostics']
    if extra['encoding']:
        rec['encoding'] = extra['encoding']
    return finish(rec)


def case_text_lines(rec):
    """把一条记录写成「这个 case 自己的纯文本结果」，方便直接打开看。"""
    kind = rec.get('kind', 'image')
    lines = [
        f'case：{rec["file"]}',
        f'分组：{rec.get("group", "?")}　类型：{kind}',
        f'模型：{DET_MODEL} + {REC_MODEL}',
        f'OCR 行数：{rec["lines"]}　平均置信度：{rec["avg_score"]:.2f}　'
        f'可疑行：{rec["low_score_lines"]}　耗时：{rec["elapsed"]}s',
    ]
    if rec.get('error'):
        lines.append(f'识别失败：{rec["error"]}')
    if kind != 'image':
        tables = rec.get('tables') or []
        tag = (f'共 {rec.get("pages", 1)} 页，text_layer={rec.get("text_layer")}'
               if kind == 'pdf' else f'编码 {rec.get("encoding", "?")}')
        lines.append(f'文本层 / 纯文本直读：{len(tables)} 张表（{tag}）')
        for t in tables:
            lines.append(f'  第 {t["page"]} 页 / {t["strategy"]} 策略 / '
                         f'{t["n_rows"]}×{t["n_cols"]} / 填充率 {t["fill_ratio"]}')
    # 结构化表格是所有 case 共有的增强结果：图片分支也可能有（107）。
    structured = rec.get('structured_tables') or []
    if structured:
        lines.append(f'--- 结构化表格（路线 {rec.get("table_route", "?")}）---')
        for t in structured:
            lines.append(f'  {t["csv_file"]}: {t["n_rows"]} 行 × {t["n_cols"]} 列'
                         f' / 填充率 {t["fill_ratio"]}'
                         + (f' / 标题 {t["title"]}' if t['title'] else ''))
            lines.append(f'    表头：{" | ".join(t["headers"])}')
            if t['rows']:
                lines.append(f'    首行：{" | ".join(t["rows"][0])}')
    for note in rec.get('table_notes') or []:
        lines.append(f'  · {note}')
    lines.append('--- 逐行 OCR 结果（文字<TAB>置信度）---')
    # zip() 把文字和置信度一一配对
    for text, score in zip(rec.get('texts') or [], rec.get('scores') or []):
        lines.append(f'{text}\t{score:.2f}')
    if rec.get('plain_text'):
        lines.append('--- 原文 ---')
        lines.append(rec['plain_text'].strip())
    return lines


def save_results(records):
    """
    两层隔离落盘（和第1周同一套规矩）：
        每个 case → <OUT_ROOT>/<case>/result.json + result.txt（完整结果）
        OUT_ROOT 根 → batch_summary.json + batch_summary.txt（跨 case 汇总）
    汇总表刻意只放关键指标；要看某个 case 的逐行文字 / 坐标，直接进它的
    result.json，不用再在一整个大 JSON 里翻找。
    """
    os.makedirs(OUT_ROOT, exist_ok=True)   # exist_ok=True：目录已存在也不报错
    for rec in records:
        case_abs = os.path.join(OUT_ROOT, rec['out_dir'])
        os.makedirs(case_abs, exist_ok=True)
        # ensure_ascii=False 保证中文原样写入，不变成 \uXXXX；indent=2 方便人看。
        with open(os.path.join(case_abs, RESULT_JSON), 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        with open(os.path.join(case_abs, RESULT_TXT), 'w', encoding='utf-8') as f:
            f.write('\n'.join(case_text_lines(rec)) + '\n')

    summary = {
        'model': {'det': DET_MODEL, 'rec': REC_MODEL},
        'case_count': len(records),
        'real_count': sum(1 for r in records if r.get('group') == 'real'),
        'real_start_no': naming.REAL_START_NO,
        'cases': [{
            'file': r['file'], 'out_dir': r['out_dir'], 'group': r.get('group'),
            'case_no': naming.parse_no(r['file']),
            'kind': r.get('kind', 'image'), 'lines': r.get('lines', 0),
            'avg_score': r.get('avg_score', 0),
            'low_score_lines': r.get('low_score_lines', 0),
            'tables': len(r.get('tables') or []),
            'structured_tables': len(r.get('structured_tables') or []),
            'table_route': r.get('table_route'),
            'elapsed': r.get('elapsed', 0),
            'error': r.get('error'),
        } for r in records],
    }
    with open(os.path.join(OUT_ROOT, SUMMARY_JSON), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    lines = [
        f'模型：{DET_MODEL} + {REC_MODEL}',
        f'case 数：{len(records)}（合成 {len(records) - summary["real_count"]} / '
        f'真实 {summary["real_count"]}；真实 case 从 {naming.REAL_START_NO} 起编号）',
        f'结构化表格：{sum(c["structured_tables"] for c in summary["cases"])} 张'
        f'（CSV 见各 case 目录的 table_N.csv）',
        f'每个 case 的完整结果在：{OUT_ROOT}/<输入名>/{RESULT_JSON}',
        '',
    ]
    for item in summary['cases']:
        lines.append(
            f'{item["file"]:42s} | {str(item["group"]):9s} | {item["kind"]:5s} | '
            f'OCR {item["lines"]:4d} 行 | 置信度 {item["avg_score"]:.2f} | '
            f'直读表格 {item["tables"]} | 结构化 {item["structured_tables"]}'
            f' | {item["elapsed"]}s'
            + (f' | 失败：{item["error"]}' if item['error'] else '')
        )
    with open(os.path.join(OUT_ROOT, SUMMARY_TXT), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print(f'>> 每个 case 的结果已写入 {OUT_ROOT}/<输入名>/{RESULT_JSON}')
    print(f'>> 跨 case 汇总：{os.path.join(OUT_ROOT, SUMMARY_JSON)} / {SUMMARY_TXT}')


def main():
    if SHOW_DEPS:
        show_dependencies()
    # 命令行第一个参数优先于配置区，方便临时指向别的输入目录。
    src_dir = sys.argv[1] if len(sys.argv) > 1 else INPUT_DIR
    cases = list_cases(src_dir)

    # 没有 case 就直接退出，不加载模型 —— 省得白等几秒。
    if not cases:
        print(f'>> {os.path.abspath(src_dir)} 里没有可处理的 case'
              f'（支持 {", ".join(SUPPORTED_EXTS)}）')
        print('>> 先把素材放进 input/，或用命令行指定别的目录。')
        return

    # ---- 新增 case 的可见反馈 ----
    # manifest 只是「说明书」，不是白名单：没登记照样跑，这里只提示一下。
    manifest_map = read_manifest(src_dir)
    case_names = [os.path.basename(p) for p in cases]
    unknown = [n for n in case_names if n not in manifest_map]
    if unknown:
        print(f'>> 发现 {len(unknown)} 个未登记到 {MANIFEST_NAME} 的新 case'
              f'（照常处理，不影响识别）：')
        for n in unknown:
            print(f'   {n}')
        print(f'>> 下一个建议编号：{naming.next_real_no(case_names)}'
              f'（自己的 case 从 {naming.REAL_START_NO} 起编号）')

    # 先算好每个 case 的专属目录名，重跑前清旧、并提示已废弃的旧目录。
    used = set()
    rels = [case_rel_name(name, used) for name in case_names]
    report_stale_cases(set(rels))

    print(f'>> 共 {len(cases)} 个 case，开始批量处理（图片 OCR / PDF 文本层直读 / CSV 纯文本）')
    ocr = build_ocr()                 # 只创建一次，后面循环复用
    t_all = time.perf_counter()

    records = []
    # zip() 把「输入路径」和「输出目录名」一一配对；enumerate 负责给进度序号。
    for i, (path, rel) in enumerate(zip(cases, rels), start=1):
        name = os.path.basename(path)
        case_abs = os.path.join(OUT_ROOT, rel)
        prepare_case_dir(case_abs)      # 重跑先清本脚本生成的旧产物
        try:
            rec = build_case_record(ocr, path, case_abs)
        except Exception as e:
            # 单个 case 失败不能让整批中断，记下来继续跑下一个。
            print(f'>> [{i}/{len(cases)}] {name} 处理失败：{e}')
            rec = {
                'file': name, 'error': str(e), 'lines': 0,
                'avg_score': 0.0, 'low_score_lines': 0, 'elapsed': 0.0,
                'texts': [], 'scores': [], 'boxes': [],
            }
        # 这几个字段写进 result.json，方便脱离 manifest 也能看懂这条结果。
        rec['out_dir'] = rel
        rec['group'] = naming.case_group(name, manifest_map.get(name, {}).get('group'))
        rec['case_no'] = naming.parse_no(name)
        records.append(rec)
        if not rec.get('error'):
            n_struct = len(rec.get('structured_tables') or [])
            # 只在该 case 真有表格时才打印，25 行日志里一眼能找到 103 / 107。
            table_note = (f', 结构化表格 {n_struct} 张'
                          f' [{rec.get("table_route", "?")}]' if n_struct else '')
            print(
                f'>> [{i}/{len(cases)}] {name}: OCR {rec["lines"]} 行, '
                f'平均置信度 {rec["avg_score"]:.2f}, '
                f'低置信 {rec["low_score_lines"]} 行{table_note}, {rec["elapsed"]}s'
            )

    save_results(records)
    # 先记下「纯识别」耗时，再画图；否则报告生成时间会混进这个数字里。
    elapsed_all = time.perf_counter() - t_all

    # ---- 自动生成可视化对照报告 ----
    # 放在 try 里：画图属于附加功能，万一某张图的坐标格式异常，也不能让已经
    # 落盘的 JSON / TXT 白跑。函数内 import 是懒加载（第1周 weekend_pipeline 用过）。
    if MAKE_VIS:
        try:
            from vis_ocr_result import build_report   # ③ 懒加载：用到才 import
            report = build_report(
                records,
                image_dir=src_dir,                                  # 原图要和跑 OCR 时同一个目录
                out_root=OUT_ROOT,
                manifest_path=os.path.join(src_dir, MANIFEST_NAME),
                summary_path=os.path.join(OUT_ROOT, SUMMARY_JSON),
            )
            print(f'>> 可视化对照报告（用浏览器打开）：{report}')
        except Exception as e:
            print(f'>> 可视化生成失败（识别结果不受影响）：{e}')

    print(f'>> 全部完成，总耗时 {elapsed_all:.2f}s（含模型加载）')
    print(f'>> 排查单个 case：打开 {OUT_ROOT}/<输入名>/{RESULT_JSON} 或 {RESULT_TXT}')
    print('>> 下一步：把有问题的 case 按类型放进 bad_cases/ 子目录，')
    print('           并在 bad_cases/notes.md 记一行「现象 + 我的猜测」。')


# 主程序守卫：直接运行才执行 main()；被别的文件 import 时不会自动跑。
if __name__ == '__main__':
    main()

"""
第1周 · 周末任务：把「输入文件 → 结构化文本」串成一个小 pipeline。

【这份脚本在做什么】
给一个文件，自动判断该怎么读，然后走三条不同的路：
    1) PDF 里能直接读出文字（叫「有文本层」）→ 用 pdfplumber 抽字，又快又准；
    2) PDF 读不出字（扫描件，页面其实是一张图）→ 渲染成 PNG，再用 PaddleOCR 逐页识别；
    3) 本来就是图片 → 直接 OCR；本来就是纯文本 / CSV → 直接读，连模型都不用加载；
    4) 顺带把表格单独抽出来（三条分支用的方法不一样）；
    5) 最后把结果写成一个 JSON 文件 + 一个纯文本文件。

【批量模式：现在不用再手动改输入路径了】
直接运行 `python weekend_pipeline.py`，脚本会扫描【配置区】INPUT_DIR 目录里
**所有支持的 case**，一个一个跑完，并给每个输入单独建一个输出目录：

    input/                       output/weekend_pipeline/
      test1.jpg        ───────→    test1/         output.json + pipeline_result.txt
      test2.jpg        ───────→    test2/         output.json + pipeline_result.txt
      test3.pdf        ───────→    test3/         output.json + pipeline_result.txt
      test3_image.pdf  ───────→    test3_image/   output.json + pipeline_result.txt
                                                   + pipeline_table_p*.html
                                                   + _tmp_pages/（OCR 页图，跑完保留供核对）
      test4.csv        ───────→    test4/         output.json + pipeline_result.txt
                                   batch_summary.json   ← 所有 case 的总览表
                                   batch_summary.txt    ← 人直接看的总览表

其它三个脚本也各有自己的目录，互不干扰：
    output/b_ocr_image/<输入名>/       文字 / 带框 PNG / HTML 报告
    output/c_pdf_text_layer/<输入名>/  抽取文本 + pages/ 页图
    output/d_table_ocr/<输入名>/       表格 HTML
全仓统一规则：**output/<脚本名>/<输入文件名>/**，中间产物再单独放一层子目录。
这样不同脚本、不同输入的结果都不会混在一起，一眼就知道哪个文件产出了什么。
新增 case 只要丢进 input/，下次运行自动被扫到，不用改任何代码。

【Python 初学者阅读提示】
- `#` 开头的行是注释，程序不会执行，纯粹写给人看。
- `def 名字(参数):` 是「定义函数」。冒号下面**缩进**的代码属于这个函数，
  缩进结束就表示函数结束。Python 用缩进代替其他语言的大括号 {}。
- 重点：`def` 只是「登记」这个函数，定义时函数体**并不会执行**；
  要等到后面有人写 `名字(...)` 去调用它，才会真正一行行跑。
- 函数里的 `return` 表示「把结果交回给调用它的地方」，同时结束函数。
- 用引号包起来的是字符串(str)，直接写的数字是整数(int)，
  True / False 是布尔值(bool)，`None` 表示「什么都没有」。

【代码从上到下的执行顺序（重要）】
    1. 执行配置区的赋值语句
    2. import 各工具箱 + 设置环境变量
    3. 定义下面一堆函数（只是登记，不执行函数体）
    4. 执行到文件最底下的 `if __name__ == '__main__':` → 调用 main()
    5. main() → run_batch() → 循环调用 run() → run() 再调用上面那些小函数
所以想读懂流程，建议**从文件最底下往上看**，而不是从第一行往下读。

【历史】三个 TODO 已补全（11-09）：
    TODO 1 判断有无文本层 → 有则 pdfplumber 直接抽字，无则转图逐页 OCR
    TODO 2 结果写成 JSON（另存一份纯文本方便看全文）
    TODO 3 进阶表格识别：文本层用 pdfplumber，扫描件用 PP-StructureV3
11-13 改进：改成批量扫描 input/、每个 case 独立输出目录、支持图片和 CSV/TXT；
      再把全仓输出统一为「output/<脚本名>/<输入名>/」两层隔离，中间页图单独一层。
11-13 再改：OCR 临时页图跑完保留供核对，重跑该 case 时先清空旧图再生成新图，
      避免新旧页图混在一起（去掉了「跑完自动删」和 KEEP_TEMP_IMAGES 开关）。

run(输入路径) 返回一个 dict（字典，含 mode / text / pages / elapsed / tables 等键），
同时把结果落盘；run_batch() 负责把它们串起来并写汇总表。

用法（在 week-01 目录下）：
    conda activate paddle
    python weekend_pipeline.py                       # ★ 批量跑 input/ 下所有 case
    python weekend_pipeline.py input/test3.pdf        # 只跑这一个文件（仍会单独建目录）
    python weekend_pipeline.py ../week-02/input       # 批量跑指定的别的目录

调试要改的路径都在文件顶部的【配置区】，不用往下翻代码。
"""

# =========================== 配置区：调试只改这里 ===========================
# 下面这些全大写的名字叫「常量」。Python 语法上并没有强制不能改，
# 全大写只是程序员之间的约定：这些是配置项，想调整就直接改这一行。
# 等号左边是变量名，右边是值；`变量 = 值` 叫「赋值语句」。
INPUT_DIR = 'input'                             # 输入目录（字符串）。默认批量扫描这里所有 case
# ↓ 产物总目录：本流水线单独占一个，和 b / c / d 三个脚本的产物互不干扰。
#   每个 case 会在它下面再建一个专属子目录，形成「脚本名 / 输入名」两层隔离。
OUT_DIR = 'output/weekend_pipeline'
TEMP_DIRNAME = '_tmp_pages'                     # OCR 中间页图的子目录名（在每个 case 目录里面）
TEMP_FILE_PREFIX = '_tmp_page_'                 # 页图文件名前缀；重跑时只清这个前缀的旧图
# ↓ 中间页图策略（固定行为，不再设开关）：跑完**保留**在 <case>/_tmp_pages/ 供逐页核对；
#   下次重跑该 case 时，先清空这个目录里上一次留下的旧图，再生成新图，避免新旧混淆。

# ↓ 注意：这两个现在是「文件名」，不再是完整路径！
#   脚本会把它们拼到每个 case 的目录里，
#   例如 output/weekend_pipeline/test3/output.json。
#   这样 5 个输入各写各的，不会互相覆盖。
OUT_JSON = 'output.json'                        # 结构化结果（含模式、页数、耗时、表格）
OUT_TXT = 'pipeline_result.txt'                 # 纯文本结果，方便直接打开看全文；改成 None 就不写

# ↓ 这两个是「批量总览表」，属于所有 case 共有，所以放在 OUT_DIR 根目录
SUMMARY_JSON = 'batch_summary.json'             # 机器可读的汇总
SUMMARY_TXT = 'batch_summary.txt'               # 人直接看的汇总

# ↓ 支持哪些文件类型（都是「元组」，用小括号包起来的一串值）。
#   元组之间可以用 + 拼接成一个新元组；不想让某类被扫到，直接从这里删掉即可。
#   .lower() 会让 '.JPG' 也能匹配，所以这里统一写小写。
PDF_EXTS = ('.pdf',)
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
TEXT_EXTS = ('.csv', '.txt', '.md')             # 纯文本类：直接读，不加载模型
SUPPORTED_EXTS = PDF_EXTS + IMAGE_EXTS + TEXT_EXTS

DPI = 200                                       # 转图清晰度（整数）。越高越清晰，但越慢、图越大
MIN_CHARS = 50                                  # 前几页抽到超过这么多字 → 判定「有文本层」
SAMPLE_PAGES = 3                                # 只检查前几页，避免大 PDF 判断太慢
ENABLE_TABLE = True                             # 表格识别开关（布尔值）。OCR 分支每页约 +20s，
                                                # 批量跑全部 case 会比较久，只想快速看文字就改 False
# ==========================================================================


# ---------- 导入（import）：把别人写好的工具箱拿进来用 ----------
# 前 7 个是 Python 自带的「标准库」，装好 Python 就有，不用额外 pip install。
import sys      # 读命令行参数：sys.argv 是一个列表(list)
import os       # 操作系统相关：拼路径、建文件夹、读写环境变量
import json     # 把 Python 字典写成 .json 文件（或反过来读）
import re       # 正则表达式：按规则查找/替换字符串。这里用来检查 HTML 里有没有 charset
import time     # 计时：perf_counter() 返回一个高精度时间点，两个时间点相减就是耗时秒数
import csv      # 读 CSV（逗号分隔的表格文本）：csv.reader 把每行拆成单元格列表
import io       # io.StringIO：把内存里的字符串「伪装」成一个文件对象给 csv.reader 读

# os.environ 是「当前进程的环境变量表」，行为像一个字典(dict)。
# setdefault(键, 值) 的意思是：这个键不存在才写入；已经存在就保持原值不动。
#   这样写是为了不覆盖你在终端里自己 set 过的配置；
#   如果写成 os.environ[键] = 值，就会强制覆盖。
# 注意 'True' 带了引号，是**字符串**不是布尔值 True —— 环境变量只能是字符串，
#   paddlex 读出来后会自己解析；写成不带引号的 True 会报 TypeError。
#
# 两行各自的作用：
#   PADDLE_PDX_MODEL_SOURCE=BOS  → 模型下载源选 BOS（百度对象存储，国内较快），
#                                  另一个常见值是 HuggingFace（国内常卡住）。
#   ...DISABLE_MODEL_SOURCE_CHECK='True' → 跳过 paddlex 启动时对各模型源的
#                                  连通性探测，避免网络不通时干等超时。
#
# 为什么必须放在任何 paddleocr / paddlex 的 import 之前：
#   那些库在「被导入的那一刻」就读走环境变量，存成模块级常量（相当于拍了张快照），
#   之后再改 os.environ 已经影响不到那个常量了。
#   注意：这不是「锁死只走 BOS」，下载大文件断开时 paddlex 仍可能自动回退 HuggingFace；
#   另外模型已在本地缓存命中时根本不下载，这两行也就用不上。
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

# 下面 2 个是「第三方库」，需要先 pip install 才能 import。
import pdfplumber  # 读 PDF 的文本层、按线条/对齐抽表格
import pymupdf     # PyMuPDF：把 PDF 页面渲染成图片；也能读 MediaBox / CropBox
                   # 说明：`import fitz` 是旧名字，1.24+ 起已弃用，现在官方推荐 `import pymupdf`。

# 变量名以下划线开头，是约定：「这是模块内部用的，外部不要直接碰」。
# 先设成 None（Python 里表示「空 / 还没有」），等真正需要时再装模型。
# 这叫「懒加载」：程序启动时不加载耗时几秒的模型，只有走到 OCR 分支才加载，
# 而且同一次运行里只加载一次（下面两个 get_ 开头的函数负责这件事）。
# 批量跑时这点尤其重要：5 个 case 共用同一个引擎，模型只加载一次。
# 这两个变量定义在函数外面，叫「全局变量」，所有函数都能读到。
_ocr = None
_table_engine = None


def show(path):
    """
    只用于「显示 / 写入汇总表」：把 Windows 的反斜杠统一成正斜杠。

    os.path.join 在 Windows 上会拼出 output/weekend_pipeline\\test1 这种
    斜杠混用的字符串 —— 功能完全正常，但读起来别扭。
    这里仅替换要打印或写进结果文件的字符串，真正传给 open()、
    os.makedirs() 的路径一个都不动，所以不会影响任何文件操作。
    """
    return str(path).replace(os.sep, '/') if path else path


def get_ocr():
    """
    取得 OCR 引擎：第一次调用时才创建，之后直接返回已经创建好的那个。

    返回：一个 PaddleOCR「对象」。对象 = 数据 + 可以调用的方法（这里是 .predict()）。
    """
    # global 声明：下面要给「函数外面」的 _ocr 赋值。
    # 少了这一行，Python 会认为 _ocr 是函数内部的局部变量，
    # 赋值就影响不到外面那个全局变量（读可以，写不行）。
    global _ocr

    if _ocr is None:   # 只有还没创建过，才执行下面这段
        # import 也可以写在函数里：执行到这一行才真正导入。
        # 好处：走「有文本层」/「纯文本」分支时，整个 paddle 都不会被加载，启动更快。
        from paddleocr import PaddleOCR

        t0 = time.perf_counter()   # 记下开始时间点
        # 括号里是「关键字参数」：参数名=值。顺序可以任意，比位置参数更好读。
        _ocr = PaddleOCR(
            # 检测模型：找出「字在图的哪个位置」
            text_detection_model_name='PP-OCRv4_mobile_det',
            # 识别模型：把框出来的字读成文本。mobile = 移动端小模型，CPU 上比 server 快约 27 倍
            text_recognition_model_name='PP-OCRv4_mobile_rec',
            use_textline_orientation=True,   # 是否判断文字方向；3.x 用它替代已废弃的 use_angle_cls
            # 不传 lang：显式指定模型名时 lang / ocr_version 会被忽略并打印警告。
            # 这里【刻意保留】默认的整页方向分类 + UVDoc 去扭曲：本流水线只取文字、
            # 不画识别框，坐标错位不影响它；实测 UVDoc 对亮字暗底的图反而识别更准。
            # 对比 b_ocr_image.py：那边要画框，所以必须关掉这两项（见它的配置区）。
        )
        # f'...' 叫 f-string：字符串里 {表达式} 会被替换成计算出来的值。
        # {xxx:.2f} 里的 :.2f 表示「按浮点数显示，保留 2 位小数」。
        print(f'>> OCR 模型加载耗时 {time.perf_counter() - t0:.2f}s')
    return _ocr


def get_table_engine():
    """取得 PP-StructureV3 表格识别流水线，同样只在第一次调用时创建。"""
    global _table_engine
    if _table_engine is None:
        from paddleocr import PPStructureV3
        t0 = time.perf_counter()
        _table_engine = PPStructureV3(
            # PP-StructureV3 是一条「多模型流水线」，下面 4 个 False 表示关掉用不到的子模型，
            # 少下载几个模型、也少花时间；只保留表格识别。
            use_formula_recognition=False,   # 公式识别
            use_chart_recognition=False,     # 图表识别
            use_seal_recognition=False,      # 印章识别
            use_region_detection=False,      # 区域检测
            use_table_recognition=True,      # 表格识别（唯一要开的）
            text_detection_model_name='PP-OCRv4_mobile_det',
            text_recognition_model_name='PP-OCRv4_mobile_rec',
        )
        print(f'>> 表格流水线加载耗时 {time.perf_counter() - t0:.2f}s')
    return _table_engine


def ocr_image(path):
    """
    对单张图片跑 OCR，返回识别到的文字列表（list[str]，即「由字符串组成的列表」）。

    PaddleOCR 3.x 用 .predict()，返回的是一个列表：每张输入图对应一个结果对象。
    结果对象的用法类似字典，用 ['rec_texts'] 取出识别出的每一行文字。
    """
    # 这一行等价于：engine = get_ocr() 然后 result = engine.predict(path)
    # Python 允许把「取对象」和「调用方法」连着写，中间用点号连接。
    result = get_ocr().predict(path)

    # 下面这一行是「列表推导式」，把两层 for 循环压缩成一行。展开写就是：
    #     texts = []
    #     for res in result:              # 外层：每张图一个结果对象
    #         for t in res['rec_texts']:  # 内层：这张图识别出的每一行文字
    #             texts.append(t)
    #     return texts
    # 初学时看不懂推导式很正常，按上面的展开版去理解即可，两者完全等价。
    return [t for res in result for t in res['rec_texts']]


def pdf_pages_to_images(pdf_path, dpi=None, out_dir=None):
    """
    把 PDF 每一页转成 PNG 图片，返回「图片路径组成的列表」。

    参数写成 `名字=值` 叫「默认参数」：调用时不传就用默认值；
    也可以临时指定，例如 pdf_pages_to_images('a.pdf', dpi=150)。
    这里不传时，函数体会去读配置区的 DPI / OUT_DIR。

    这里特意把默认值写成 None、进函数再读配置区，而不是直接写 `dpi=DPI, out_dir=OUT_DIR`：
    Python 的**默认参数值在函数定义那一刻就被算好并固定了**，之后就算改了配置区的
    OUT_DIR（或在别的文件里 import 后改），也不会生效。写成 None 才是「运行时读配置」。

    批量模式下 run() 会传入 <case 目录>/_tmp_pages/，所以每个 PDF 的页图
    各放各的，而且单独一层，不会和 output.json 这类正式结果混在一起，
    更不会像早期版本那样全堆在 output/ 根目录互相覆盖。

    这些 PNG 是「中间产物」，但**跑完会保留**：想逐页核对「OCR 到底看的是哪张图」
    时可以直接打开。为了避免新旧页图混在一起，run() 在调用本函数**之前**
    会先用 prepare_temp_dir() 清空该目录里上一次留下的旧图。
    """
    dpi = DPI if dpi is None else dpi
    out_dir = OUT_DIR if out_dir is None else out_dir
    os.makedirs(out_dir, exist_ok=True)  # 建文件夹；exist_ok=True 表示「已存在也别报错」
    doc = pymupdf.open(pdf_path)         # 打开 PDF，得到一个可以逐页遍历的文档对象
    paths = []                           # 创建一个空列表，用来收集生成的文件路径
    try:
        # enumerate(可迭代对象) 同时给出「序号」和「元素」，
        # 比写 for i in range(len(doc)) 更简洁，是 Python 惯用写法。
        for i, page in enumerate(doc):
            # f"{TEMP_FILE_PREFIX}{i}.png" 是 f-string，{i} 会被替换成 0、1、2……
            # 前缀写在配置区：重跑时 prepare_temp_dir() 靠它认出「哪些是本脚本生成的旧图」。
            # os.path.join 负责用当前系统的分隔符拼路径
            # （Windows 是反斜杠，不要自己手写字符串拼接）。
            out = os.path.join(out_dir, f"{TEMP_FILE_PREFIX}{i}.png")
            # get_pixmap() 把这一页渲染成位图，.save() 存成 PNG。
            page.get_pixmap(dpi=dpi).save(out)
            paths.append(out)   # list.append(x)：往列表末尾添加一个元素
    finally:
        # finally 里的代码「无论中间有没有报错」都一定会执行，
        # 用来释放文件句柄这类资源，是处理文件的标准写法。
        doc.close()
    return paths


def prepare_temp_dir(temp_dir):
    """
    生成**新**页图之前先准备好 <case 目录>/_tmp_pages/，返回这个目录路径。

    策略（11-13 晚按需求改的）：
      - 跑完**不删**临时目录和页图 —— 事后想核对「OCR 看的到底是哪张渲染图」
        可以直接打开，OCR 中途报错时页图也会留着，正好用来排查；
      - 但**重跑时先清空**上一次留下的旧图，否则新旧页图混在一起分不清哪张是本轮的。

    安全边界（很重要）：只在传进来的这一个 _tmp_pages/ 目录里操作，
    只删 TEMP_FILE_PREFIX 开头、.png 结尾的**普通文件**；不递归、不删子目录、
    不碰 input/ 原图、也不碰其它 case 的正式产物（output.json / 表格 HTML 等）。
    os.listdir 只列出这一层，os.remove 只删单个文件，不会误伤别处。
    """
    os.makedirs(temp_dir, exist_ok=True)   # 目录不存在就建；已存在也别报错
    removed = 0
    for name in os.listdir(temp_dir):
        # 只认「本脚本自己生成的临时页图」，其它文件一律不动
        if not (name.startswith(TEMP_FILE_PREFIX) and name.lower().endswith('.png')):
            continue
        path = os.path.join(temp_dir, name)
        if not os.path.isfile(path):       # 万一同名的是个文件夹，跳过
            continue
        try:
            os.remove(path)                # 删单个文件；os.rmdir 那种删目录的操作这里没有
            removed += 1
        except OSError:
            pass                           # 被占用 / 删不掉都不影响主流程
    if removed:
        print(f'>> 重跑前清掉 {removed} 张旧页图 → {show(temp_dir)}')
    return temp_dir


# ---------------------------------------------------------------- TODO 1 --
def has_text_layer(pdf_path):
    """
    判断 PDF 有没有文本层，返回 (是否有, 总页数)。

    一次 return 返回两个值，叫「元组」(tuple)；调用处写 `ok, pages = ...`
    就能把两个值分别装进两个变量，这叫「元组解包」，下面 run() 里就是这么用的。
    """
    # with 是「上下文管理器」：缩进块结束后自动关闭 PDF，即使中间出错也会关，
    # 所以这里不需要（也不能）再手动写 pdf.close()。
    with pdfplumber.open(pdf_path) as pdf:
        pages = len(pdf.pages)   # len() 求长度；pdf.pages 是所有页组成的列表
        # 拆解这一行（从内往外看）：
        #   pdf.pages[:SAMPLE_PAGES]  → 切片，只取前 3 页，避免几百页的 PDF 判断太慢
        #   p.extract_text() or ''   → 抽不到字时 extract_text() 返回 None，
        #                              `or ''` 表示「如果是空值就换成空字符串」，
        #                              否则后面拼接时会报错
        #   for p in ...             → 生成器表达式，逐页产生一段文本
        #   ''.join(...)             → 用空字符串把这些文本首尾相连，拼成一个大字符串
        sample = ''.join((p.extract_text() or '') for p in pdf.pages[:SAMPLE_PAGES])
    # .strip() 去掉首尾空白字符；再数一数字数是否超过阈值。
    # `>` 比较的结果本身就是 True / False，可以直接返回，不必写 if。
    return len(sample.strip()) > MIN_CHARS, pages


def extract_text_layer(pdf_path):
    """有文本层：逐页抽取全文，用换行符拼成一整篇文本。"""
    with pdfplumber.open(pdf_path) as pdf:
        # '\n' 是转义字符，代表换行（反斜杠 + n 这两个字符合起来表示「换行」）。
        # 这里读的是「全部内容流」，不受 CropBox 显示裁剪的影响 ——
        # 所以可能抽到打开 PDF 时肉眼看不见的字（test3.pdf 就是这种）。
        return '\n'.join((p.extract_text() or '') for p in pdf.pages)


def cropbox_is_limited(pdf_path):
    """检查 CropBox 是否比 MediaBox 小（学习记录 6.3 记录的「裁剪陷阱」）。"""
    # 有些 PDF 加密或损坏时打不开。这个标记只是「额外提示」，不该让整条流水线崩掉，
    # 所以失败时返回 False 继续跑主流程（try/except 与下面 open 后的 try/finally 是两件事）。
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        print(f'>> CropBox 检查失败，按「未裁剪」继续：{e}')
        return False
    try:
        # any(...) 里面是「生成器表达式」：逐页判断，只要有一页不相等就返回 True。
        # 等价于自己写 for 循环 + 一个标志变量，但这种写法更短。
        return any(page.cropbox != page.mediabox for page in doc)
    finally:
        doc.close()


# ---------------------------------------------------------------- TODO 3 --
def extract_tables_text_layer(pdf_path):
    """有文本层时直接用 pdfplumber 抽表格：快，且完全不需要加载模型。"""
    found = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                # extract_tables() 返回「表格的列表」，每个表格又是「行的列表」，
                # 每行还是「单元格的列表」，所以是嵌套了三层的列表结构。
                # 后面 `or []` 保证拿不到结果时至少是个空列表，可以安全地 for 遍历。
                tables = page.extract_tables() or []
            except Exception as e:
                # try / except：try 块里出错不会让整个程序崩溃，而是跳到这里处理。
                # Exception 是绝大多数常见异常的父类；`as e` 把错误对象存进变量 e。
                print(f'>> 第 {i + 1} 页表格抽取失败，已跳过：{e}')
                continue   # 跳过本页剩下的代码，直接进入下一轮 for 循环
            for table in tables:
                # {'键': 值} 是字典(dict)，以后用 `记录['page']` 按键取值。
                # 这里组装一条表格记录，再 append 进总列表。
                found.append({'page': i, 'source': 'pdfplumber', 'rows': table})
    return found


def ensure_readable_html(path):
    """
    给 paddlex save_to_html() 导出的 HTML 片段补上 <meta charset="utf-8">。

    坑点：paddlex 写文件用的确实是 utf-8（字节没错），但导出的只是
    `<html><body><table>...` 这种片段，没有 charset 声明；
    中文 Windows 的浏览器会按 GBK 去解码，于是中文全是乱码。
    """
    with open(path, encoding='utf-8') as f:  # encoding 明确按 utf-8 读，中文才不会乱
        frag = f.read()

    # re.search(正则, 字符串) 找不到时返回 None（在 if 里相当于 False）。
    # flags=re.I 表示忽略大小写。已有 charset 就直接结束，不做任何改动。
    if re.search(r'<meta[^>]+charset', frag, flags=re.I):
        return   # 单独一个 return 表示「返回 None 并结束函数」

    # 正则字符串前的 r 表示「原始字符串」：反斜杠按字面保留，不再当转义符处理。
    # 写正则表达式时几乎都会加 r，否则 \s 这类序列会先被 Python 当转义字符解释（新版本还会告警）。
    # re.sub(规则, 替换成什么, 原字符串)：把片段自带的 html/body 外层标签去掉，
    # 避免下面补骨架时出现 <html><html> 的嵌套。
    inner = re.sub(r'^\s*<html[^>]*>|</html>\s*$', '', frag, flags=re.I)
    inner = re.sub(r'^\s*<body[^>]*>|</body>\s*$', '', inner, flags=re.I)

    # 括号里是「字符串字面量隐式拼接」：相邻的几个字符串会自动连成一个，
    # 这样可以把一整段 HTML 按行写清楚，不用每行末尾都写 + 号。
    # 中间那个 `+ inner` 才是真的字符串相加，把原表格内容插进骨架里。
    doc = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '  <meta charset="utf-8">\n  <title>表格识别结果</title>\n'
        '  <style>body{font-family:"Microsoft YaHei",sans-serif;margin:24px}'
        'table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #999;padding:6px 10px}</style>\n'
        '</head>\n<body>\n' + inner + '\n</body>\n</html>\n'
    )
    # 'w' 是写模式：文件不存在就创建，已存在会整个覆盖。
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc)


def table_ocr_page(image_path, page_index, out_dir=None):
    """
    对一页图跑 PP-StructureV3，挑出表格内容块并导出 HTML。

    out_dir 是「这个 case 的专属目录」，导出的 HTML 会放在它里面，
    不会跟别的输入的表格混在一起（批量模式的关键）。

    现在 `d_table_ocr.py` 也改成了 main() + __main__ 守卫，可以被安全 import；
    这里仍在本地重写一份，好处是本文件单独读就能看懂整条流水线，
    不必跳到另一个文件查参数（两边参数保持一致即可）。
    """
    out_dir = OUT_DIR if out_dir is None else out_dir
    result = get_table_engine().predict(image_path)
    blocks = []
    for res in result:
        # hasattr(对象, '属性名') 判断有没有这个属性：有就取 .json，没有就直接用 res。
        # `A if 条件 else B` 叫三元表达式，条件成立取 A，否则取 B。
        # 这是为了兼容不同版本返回结构而做的兜底。
        data = res.json if hasattr(res, 'json') else res
        # isinstance(x, dict) 判断 x 是不是字典，避免对非字典调用 .get() 而报错。
        # 3.x 的 res.json 是 {'res': {...}} 这种嵌套结构，真正字段藏在里面一层。
        if isinstance(data, dict) and isinstance(data.get('res'), dict):
            data = data['res']
        if isinstance(data, dict):
            # .get('键', 默认值)：键不存在时返回默认值，不会抛 KeyError。
            for b in data.get('parsing_res_list', []):
                blocks.append({
                    'label': b.get('block_label', '?'),
                    'content': str(b.get('block_content', '')),  # str() 转成字符串
                })
    # 带 if 的列表推导式：只保留 label 里含 'table' 的块。
    # .lower() 先统一转小写，这样 'Table' / 'TABLE' 也能匹配上。
    tables = [b for b in blocks if 'table' in b['label'].lower()]
    html_path = None
    # 在 if 判断里，非空列表、非空字符串都视为 True，空列表 / None 视为 False。
    if tables and result:
        # 同 d 脚本踩过的坑（11-13）：paddlex 3.7.0 的 save_to_html() 内部是
        # html[list(html.keys())[0]]，结果里没有任何表格 HTML 时会 IndexError。
        # 先用公开的 res.html 判空，空就跳过导出 —— 这一页只是没表格，不是错误。
        html_map = result[0].html or {}
        if html_map:
            os.makedirs(out_dir, exist_ok=True)
            html_path = os.path.join(out_dir, f'pipeline_table_p{page_index}.html')
            result[0].save_to_html(html_path)   # [0] 表示取列表的第一个元素
            ensure_readable_html(html_path)     # 补 charset，修中文乱码
        else:
            print(f'>> 第 {page_index + 1} 页有表格块但没有可导出的表格 HTML，跳过')
    return {
        'page': page_index,
        'source': 'PPStructureV3',
        'table_count': len(tables),
        'blocks': tables,
        'html': html_path,
    }


# ------------------------------------------------- 新增：纯文本 / CSV 分支 --
def read_plain_text(path):
    """
    直接读 .csv / .txt / .md，返回 (文本内容, 实际用的编码)。

    为什么要「一个个编码试」：Windows 上用 Excel 另存的中文 CSV 常常是 GBK，
    直接用 utf-8 打开会抛 UnicodeDecodeError（或读出一堆乱码方块）。
    这和第 1 周 d_table_ocr.py 的 HTML 乱码是同一类问题 —— 字节没错，
    只是「用什么规则把字节翻译成字符」没说清楚。

    做法：先用 'rb'（二进制模式）读出原始 bytes，再按候选编码逐个 decode：
      utf-8-sig → 带 BOM 的 UTF-8（能自动去掉文件头的 BOM 标记）
      gbk       → 简体中文 Windows 常见编码（input/test4.csv 就是这种）
      latin-1   → 兜底，任何字节都能解，不会抛错（但中文会变成奇怪字符）
    """
    with open(path, 'rb') as f:     # 'rb' = read binary，读出来的是 bytes 不是 str
        raw = f.read()
    for enc in ('utf-8-sig', 'gbk', 'latin-1'):
        try:
            return raw.decode(enc), enc   # bytes.decode(编码) 把字节翻译成字符串
        except UnicodeDecodeError:
            continue                     # 这个编码解不了，换下一个再试
    # 理论上 latin-1 一定能成功，下面这行只是保险；errors='replace' 把解不了的字节换成符号
    return raw.decode('utf-8', errors='replace'), 'utf-8(replace)'


def csv_tables(text):
    """
    把 CSV 文本拆成「行的列表」，塞进和另外两条分支同结构的 tables 记录。

    csv.reader 需要的是「可逐行读的文件对象」，而我们手里已经是字符串了，
    io.StringIO(字符串) 就是把字符串伪装成文件对象，免得再打开一次磁盘文件。
    """
    if not text.strip():             # 空文件直接返回空列表
        return []
    rows = list(csv.reader(io.StringIO(text)))
    # any(...) 判断这一行里有没有任何一个非空单元格；全空行就丢掉。
    # 带 if 的列表推导式前面已经用过，这里再练一次。
    rows = [r for r in rows if any(c.strip() for c in r)]
    return [{'page': 0, 'source': 'csv', 'rows': rows}] if rows else []


# ---------------------------------------------------------------- TODO 2 --
def save_result(result, out_dir):
    """
    把结果字典写进「这个 case 自己的目录」：out_dir/OUT_JSON 和 out_dir/OUT_TXT。

    注意 OUT_JSON / OUT_TXT 在配置区里只是**文件名**，要靠 os.path.join
    拼上 out_dir 才是完整路径 —— 这就是「不同输入不混在一起」的实现点。
    """
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, OUT_JSON)
    with open(json_path, 'w', encoding='utf-8') as f:
        # json.dump(对象, 文件对象) = 把 Python 字典「序列化」成 JSON 文本写进文件。
        #   ensure_ascii=False → 中文原样写入，而不是变成 \u4e2d\u6587 这种转义；
        #   indent=2          → 每层缩进 2 个空格，方便人直接阅读。
        json.dump(result, f, ensure_ascii=False, indent=2)
    if OUT_TXT:   # 配置区把 OUT_TXT 改成 None，这段就会被跳过
        txt_path = os.path.join(out_dir, OUT_TXT)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(result['text'])   # 用键从字典里取出值
    return json_path


# ------------------------------------------------------ 新增：批量调度部分 --
def classify(path):
    """
    看文件后缀，判断该走哪条分支，返回字符串：'pdf' / 'image' / 'plain_text' / 'unknown'。

    os.path.splitext('input/test3.PDF') 返回 ('input/test3', '.PDF')，
    取 [1] 拿到后缀，再 .lower() 统一转小写，这样大写后缀也能认。
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXTS:
        return 'pdf'
    if ext in IMAGE_EXTS:
        return 'image'
    if ext in TEXT_EXTS:
        return 'plain_text'
    return 'unknown'


def case_out_dir(input_path, used_names):
    """
    给每个输入算一个专属输出目录：OUT_DIR/<文件名去掉后缀>/。

    used_names 是一个 set（集合）：里面装着本轮已经用过的目录名，
    用来处理「同名不同后缀」的输入，例如 a.pdf 和 a.jpg 都想叫 a/ 时会撞车，
    第二个就改叫 a_jpg/；再撞就 a_2/、a_3/…… 保证谁也不覆盖谁。
    set 的特点是元素不重复；`.add()` 往里加一个，下面 run_batch() 会全程传同一个 set。
    """
    base = os.path.basename(input_path)          # 只要文件名，去掉前面的 input/ 路径
    stem, ext = os.path.splitext(base)           # 元组解包：('test3', '.pdf')
    name = stem
    if name in used_names:
        # ext.lstrip('.') 去掉后缀前面的点：'.jpg' → 'jpg'
        name = f'{stem}_{ext.lstrip(".")}'
    n = 2
    while name in used_names:   # while = 「只要条件成立就一直重复」，这里用于继续避让
        name = f'{stem}_{n}'
        n += 1
    used_names.add(name)
    return os.path.join(OUT_DIR, name)


def collect_cases(input_dir):
    """
    扫描输入目录，把要跑的文件挑出来，按文件名排序后返回一个列表。

    sorted(...) 保证每次运行顺序一致（否则不同系统 listdir 的顺序可能不一样）；
    os.path.isfile 排除掉子目录；不在 SUPPORTED_EXTS 里的（比如 .gitkeep）直接跳过。
    所以「新增 case」只要把文件丢进 input/，不用改代码。
    """
    cases = []
    for name in sorted(os.listdir(input_dir)):
        path = os.path.join(input_dir, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() not in SUPPORTED_EXTS:
            continue
        cases.append(path)
    return cases


def run(input_path, out_dir=None):
    """
    跑一个 case（PDF / 图片 / 纯文本），返回结构化 dict，并把结果写进自己的目录。

    这是整条流水线的「串联」部分：上面那些函数都是零件，由这里按流程依次调用。
    out_dir 不传时会自动按文件名生成一个（方便单独 import 本文件后调用 run('a.pdf')）。
    返回 dict 后，调用方可以取 result['text']、result['mode'] 等。
    """
    if out_dir is None:
        out_dir = case_out_dir(input_path, set())
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.perf_counter()                  # 总耗时起点
    kind = classify(input_path)
    if kind == 'unknown':
        # raise 表示「主动抛出一个错误」。批量模式会接住它，只记一笔失败继续跑下一个。
        raise ValueError(f'不支持的文件类型：{input_path}')

    tables = []
    limited = False
    extra = {}       # 各分支特有的字段先收在这里，最后用 update() 合并进结果字典

    if kind == 'pdf':
        # -------------------------------- PDF 分支 --------------------------------
        limited = cropbox_is_limited(input_path)   # 是否命中 CropBox 裁剪陷阱
        ok, pages = has_text_layer(input_path)     # 元组解包：(是否有文本层, 总页数)

        if ok:
            # TODO 1：有文本层 → 直接抽字，不碰 OCR（又快又准）
            print('>> 有文本层 → 直接抽字（跳过 OCR）')
            text = extract_text_layer(input_path)
            # 一行给两个变量赋值，也是元组解包（等价于分两行写）。
            mode, scope = 'text_layer', 'all_content_stream'
            if limited:
                # 字符串可以分成两行写，Python 会自动拼接（相邻字面量拼接）。
                print('>> 注意：该 PDF 有 CropBox 裁剪，抽到的是全部内容流，'
                      '可能包含打开时看不到的文字')
            # TODO 3：文本层分支用 pdfplumber 抽表格，不需要模型
            if ENABLE_TABLE:
                tables = extract_tables_text_layer(input_path)
                print(f'>> 表格抽取：{len(tables)} 个表格（pdfplumber）')
        else:
            # TODO 1：无文本层 → 转图，逐页 OCR 后汇总
            print('>> 无文本层（扫描件）→ 转图后逐页 OCR')
            # ★ 中间页图单独放 <case 目录>/_tmp_pages/：
            #   既和别的 case 隔离，也不与 output.json / 表格 HTML 混在同一层。
            temp_dir = os.path.join(out_dir, TEMP_DIRNAME)
            # 重跑时先清掉上一次留下的旧图，再生成新图；跑完**保留**供核对。
            prepare_temp_dir(temp_dir)
            images = pdf_pages_to_images(input_path, out_dir=temp_dir)
            print(f'>> 中间页图 {len(images)} 张 → {show(temp_dir)}/'
                  f'（跑完保留，下次重跑该 case 时先清空）')
            chunks = []
            # 这里不再用 try/finally 做清理：页图是本轮要留着核对的产物，
            # 哪怕某一页 OCR 报错也留在目录里，正好用来排查。
            for i, img in enumerate(images):
                t1 = time.perf_counter()          # 单页耗时起点
                lines = ocr_image(img)
                chunks.append(f'--- 第 {i + 1} 页 ---')  # 加一个分页标记，方便看结果
                # extend 把另一个列表的元素「逐个」加进来；
                # append 则是把整个列表当成「一个」元素塞进去 —— 初学者很容易混。
                chunks.extend(lines)
                print(f'>> 第 {i + 1}/{len(images)} 页 OCR 完成：{len(lines)} 行，'
                      f'{time.perf_counter() - t1:.2f}s')
                # TODO 3：扫描件分支用 PP-StructureV3 还原表格结构
                if ENABLE_TABLE:
                    info = table_ocr_page(img, i, out_dir)
                    tables.append(info)
                    # 外层 f-string 用单引号，里面取字典键用双引号，两种引号不冲突。
                    print(f'   表格识别：{info["table_count"]} 个表格块'
                          + (f'，HTML → {show(info["html"])}' if info['html'] else ''))
            # 把页图位置记进 output.json，事后翻结果时能直接找到它
            extra['temp_dir'] = show(temp_dir)
            extra['temp_pages'] = len(images)
            text = '\n'.join(chunks)              # 把所有行用换行符连成一整篇文本
            mode, scope = 'ocr', 'visible_cropbox'

    elif kind == 'image':
        # -------------------------------- 图片分支 --------------------------------
        # 图片没有「文本层」这个说法，直接 OCR 就行；也不需要转图、更不需要清理
        # （input/ 里的原图是输入，绝不能删）。
        print('>> 图片输入 → 直接 OCR（无需判断文本层）')
        pages = 1
        lines = ocr_image(input_path)
        text = '\n'.join(lines)
        mode, scope = 'ocr', 'image'
        print(f'>> 识别到 {len(lines)} 行')
        if ENABLE_TABLE:
            info = table_ocr_page(input_path, 0, out_dir)
            tables.append(info)
            print(f'>> 表格识别：{info["table_count"]} 个表格块'
                  + (f'，HTML → {info["html"]}' if info['html'] else ''))

    else:
        # ---------------------------- 纯文本 / CSV 分支 ----------------------------
        # 这类文件本来就是文字，连模型都不用加载，是最快的一条路。
        text, enc = read_plain_text(input_path)
        pages = 1
        mode, scope = 'plain_text', 'file_content'
        extra['encoding'] = enc       # 记下用了哪种编码，方便追溯乱码问题
        print(f'>> 纯文本输入 → 直接读取（编码 {enc}），{len(text)} 字符')
        if ENABLE_TABLE and input_path.lower().endswith('.csv'):
            tables = csv_tables(text)
            print(f'>> CSV 表格解析：{len(tables)} 张表')

    # {'键': 值, ...} 定义字典；缩进只是为了让结构好看，不影响含义。
    result = {
        'source': input_path,                 # 输入文件路径
        'out_dir': show(out_dir),              # 本次产物目录（显示层统一用正斜杠）
        'kind': kind,                         # 'pdf' / 'image' / 'plain_text'
        'mode': mode,                         # 'text_layer' / 'ocr' / 'plain_text'
        'text': text,
        'chars': len(text),
        'pages': pages,
        'text_scope': scope,                 # 读的是全部内容流、可见区、图片还是原文件
        'cropbox_limited': limited,
        'elapsed': round(time.perf_counter() - t0, 2),  # round(x, 2) 保留 2 位小数
        'tables': tables,
    }
    # dict.update(另一个字典)：把 extra 里的键值合并进来。
    # 目前只有纯文本分支会用到（放进 'encoding' 字段）。
    result.update(extra)

    # TODO 2：落盘（ensure_ascii=False 保证中文不变成 \uXXXX）
    out_json = save_result(result, out_dir)
    print(f'>> 已保存 {show(out_json)}（mode={mode}, {pages} 页, {len(text)} 字符, '
          f'{result["elapsed"]}s）')
    return result


def count_tables(result):
    """
    数一数「真正识别出的表格有几个」，专门给汇总表用。

    这里有个容易踩的坑：三条分支往 result['tables'] 里放的东西语义不一样 ——
      文本层分支 / CSV 分支：一个元素 = 一张表格，直接 len() 就对；
      OCR 分支（扫描件 / 图片）：一个元素 = **一页的检查记录**，
          里面 'table_count' 才是该页识别出的表格块数，可能一页都没有。
    所以先看看第一个元素有没有 'table_count' 这个键，有就把各页加起来。
    """
    items = result['tables']
    if items and isinstance(items[0], dict) and 'table_count' in items[0]:
        return sum(t.get('table_count', 0) for t in items)
    return len(items)


def save_summary(summary, input_dir):
    """
    把所有 case 的结果写成 OUT_DIR/batch_summary.json 和 batch_summary.txt。

    汇总表不属于任何一个 case，所以放在本脚本的产物根目录
    output/weekend_pipeline/，而不是某个 case 子目录里。
    input_dir 传的是本轮实际扫描的目录（命令行可能指定别的目录，不能写死 INPUT_DIR）。
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    json_path = os.path.join(OUT_DIR, SUMMARY_JSON)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(OUT_DIR, SUMMARY_TXT)
    lines = [
        f'批量结果汇总  共 {len(summary)} 个 case',
        f'输入目录：{show(input_dir)}    产物目录：{show(OUT_DIR)}',
        '=' * 78,
        '序号 | 输入文件 | 类型 | 识别方式 | 页 | 字符数 | 表格数 | 耗时(s) | 输出目录',
        '-' * 78,
    ]
    for i, s in enumerate(summary, 1):
        if s['ok']:
            # 这里用 f-string 把每一项转成字符串再拼接，中文列宽不严格对齐也能看
            lines.append(
                f'{i:>2} | {os.path.basename(s["source"])} | {s["kind"]} | '
                f'{s["mode"]} | {s["pages"]} | {s["chars"]} | {s["tables"]} | '
                f'{s["elapsed"]} | {show(s["out_dir"])}'
            )
        else:
            # 失败的那一行也要留在表里，不能悄悄消失
            lines.append(f'{i:>2} | {os.path.basename(s["source"])} | 失败 | '
                         f'{s["error"]} | - | - | - | - | {show(s["out_dir"])}')
    lines.append('=' * 78)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return json_path, txt_path


def run_batch(input_dir=None):
    """
    批量模式：扫描目录 → 逐个跑 → 写汇总表。

    默认参数照旧写成 None、进函数再读配置区，避开「默认值在定义时就固定」的坑。
    单个 case 失败不会中断整批：try/except 接住错误、记一笔，继续跑下一个。
    """
    input_dir = INPUT_DIR if input_dir is None else input_dir
    if not os.path.isdir(input_dir):
        sys.exit(f'找不到输入目录：{os.path.abspath(input_dir)}\n'
                 f'改文件顶部的 INPUT_DIR，或用命令行指定一个目录')
    cases = collect_cases(input_dir)
    if not cases:
        sys.exit(f'{os.path.abspath(input_dir)} 里没有可处理的文件。\n'
                 f'支持的类型：{", ".join(SUPPORTED_EXTS)}')

    print(f'>> 批量模式：在 {input_dir}/ 找到 {len(cases)} 个 case，'
          f'每个会单独输出到 {OUT_DIR}/<文件名>/')
    if ENABLE_TABLE:
        print('>> 提示：表格识别已开启，OCR 分支每页约 +20s；'
              '只想快速看文字就把配置区 ENABLE_TABLE 改成 False')

    os.makedirs(OUT_DIR, exist_ok=True)
    used_names = set()      # 全程共用一个集合，负责给每个 case 分配不冲突的目录名
    summary = []
    t_all = time.perf_counter()

    # enumerate(cases, 1)：第二个参数是「序号从几开始」，写 1 就显示 [1/5] 而不是 [0/5]
    for i, path in enumerate(cases, 1):
        out_dir = case_out_dir(path, used_names)
        print(f'\n===== [{i}/{len(cases)}] {os.path.basename(path)}  →  {show(out_dir)} =====')
        try:
            r = run(path, out_dir)
            summary.append({
                'source': r['source'], 'out_dir': r['out_dir'], 'kind': r['kind'],
                'mode': r['mode'], 'pages': r['pages'], 'chars': r['chars'],
                'tables': count_tables(r), 'elapsed': r['elapsed'], 'ok': True,
            })
        except Exception as e:
            # type(e).__name__ 拿到错误的类型名（如 ValueError），比只打印消息更好排查。
            print(f'!! 这个 case 处理失败，继续跑下一个：{type(e).__name__}: {e}')
            summary.append({
                'source': path, 'out_dir': show(out_dir), 'ok': False,
                'error': f'{type(e).__name__}: {e}',
            })

    json_path, txt_path = save_summary(summary, input_dir)
    ok_count = sum(1 for s in summary if s['ok'])   # 生成器 + sum：数一数成功几个
    print(f'\n>> 全部完成：{ok_count}/{len(summary)} 个成功，'
          f'总耗时 {time.perf_counter() - t_all:.2f}s（含模型加载）')
    print(f'>> 汇总表：{show(json_path)}  /  {show(txt_path)}')
    return summary


def main():
    # sys.argv 是命令行参数组成的列表：argv[0] 是脚本名本身，argv[1] 才是第一个参数。
    # `A if 条件 else B` 是三元表达式：没带参数就用配置区的 INPUT_DIR（批量跑全部 case）。
    arg = sys.argv[1] if len(sys.argv) > 1 else INPUT_DIR

    if os.path.isdir(arg):
        # 目录 → 批量模式（不带参数时的默认行为）
        run_batch(arg)
        return   # 提前结束函数，不再往下走单文件逻辑

    if not os.path.isfile(arg):
        # sys.exit(字符串) 会打印这句话，并以非零退出码结束程序。
        # \n 是字符串里的换行转义，让提示分成两行显示。
        sys.exit(f"找不到输入：{os.path.abspath(arg)}\n"
                 f"不带参数 = 批量跑 {INPUT_DIR}/ 下所有 case；也可指定一个文件或目录")
    if classify(arg) == 'unknown':
        sys.exit(f'不支持的文件类型：{arg}\n当前支持：{", ".join(SUPPORTED_EXTS)}')

    # 单文件模式：仍然给它单独建一个目录，保持「结果不混在一起」的规则
    out_dir = case_out_dir(arg, set())
    print(f'>> 单文件模式：{show(arg)}  →  {show(out_dir)}')
    result = run(arg, out_dir)
    print('>> 前 300 字预览：')
    # [:300] 是切片，取前 300 个字符；`or '(空)'` 处理文本为空的情况。
    print(result['text'][:300] or '(空)')
    if OUT_TXT:
        print(f'>> 全文见 {show(os.path.join(out_dir, OUT_TXT))}')


# ---------------------------------------------------------------------------
# 程序入口（你之前专门问过这一句）：
#
# 每个 .py 文件被「运行」或被「导入」时，Python 都会给它一个内置变量 __name__：
#     直接运行：python weekend_pipeline.py  → __name__ 的值是 '__main__'
#     被别的文件 import 进来             → __name__ 的值是模块名 'weekend_pipeline'
#
# 所以 `if __name__ == '__main__':` 的意思是「只有直接运行本文件时才调用 main()」。
# 好处：别的文件可以安全地 import 本文件的函数复用，不会顺带把整条流水线跑一遍。
# week-01 的 b_ocr_image.py / d_table_ocr.py 现在也都加了这个守卫，
# 所以以后想复用 `from d_table_ocr import ensure_readable_html` 之类是安全的。
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    main()

"""
第2周 · case 命名 / 分组 / 排序的唯一真相源

【为什么单独一个文件】
11-13 之前，「哪些是用户自己的真实 case」这个判断散落在好几个地方：
    make_samples.py 的 REAL_CASES 清单、
    samples_manifest.json 的 group 字段、
    vis_ocr_result.py 里的 name[:2].isdigit() 猜测、
    text_layer_extract.py 里写死的 PDF 文件名。
结果就是：给真实 case 改个名字（或加个数字前缀），报告分组会错、
人工列边界模板会失效、默认图片会找不到 —— 重跑也说不清生没生效。
现在把规则集中到这个文件，其它脚本统一 import 它；以后要改编号规则，只改这里。

【谁在调用我】（11-13 补）
我是本周被复用最多的底层模块，一共 5 个脚本 import 我：
    a_batch_ocr.py        主入口：分组 / 排序 / 输出目录名 / 汇总
    vis_ocr_result.py     卡片分组、真实 case 统计、独立运行时的结果排序
    text_layer_extract.py 用 strip_no() 让列边界模板按语义名匹配
    c_try_params.py       用 pick_real_image() 自动挑默认图
    make_samples.py       生成 / 补登记真实 case
我没有 main()，不单独运行；要改命名规则只改这一个文件，其它脚本自动跟着变。
想自己核对调用方：在 week-02 目录下搜 `import case_naming`。

【命名约定（用户 11-13 定稿）】
    合成样本：01~18          两位数字前缀，编号 < 101
    真实 case：101_real_xxx.pdf / .jpg / .csv …
               编号从 101 起，后面跟 real_ 语义标记 + 一眼看懂内容的名字
    新增 case：直接丢进 input/，编号接着往下排（108、109…），
               不用改任何脚本、不用改清单，重跑 a_batch_ocr.py 就自动被扫到。

【为什么不能只靠 sorted()】
字典序里 '101_' 会排在 '10_' 前面（第二位 '0' 比 '_' 小），
所以 101 开头的真实 case 会插进合成样本中间，而不是排在最后。
因此提供 case_sort_key()：先按「合成 / 真实」分组，再在组内按编号升序，
真实 case 恒定排最后，跟前缀有几位数字无关。

【兼容旧名】
历史用过的 real_xxx（没有数字前缀）仍算真实 case，
方便从 git 恢复旧样本时不会突然被当成合成样本。

【Python 初学者提示】
本模块只做「根据文件名算结论」的纯函数，不读磁盘内容（pick_real_image 除外），
所以 import 它没有副作用，也不会触发模型加载。
"""

import os
import re

# =========================== 配置区：改命名规则只改这里 ======================
REAL_START_NO = 101            # 真实 case 的起始编号；小于它的编号都算合成样本
REAL_MARKER = 'real_'          # 真实 case 的语义标记（配合编号使用，也兼容旧名）
# ==========================================================================

# 正则：匹配文件名开头「一串数字 + 下划线或短横线」。
# ^ 表示从开头匹配，(\d+) 是「至少一位数字」并被括号捕获，[_-] 是分隔符。
_NO_PREFIX = re.compile(r'^(\d+)[_-]')


def parse_no(name):
    """取文件名开头的编号；没有数字前缀就返回 None。"""
    match = _NO_PREFIX.match(os.path.basename(name))
    return int(match.group(1)) if match else None


def strip_no(name):
    """
    去掉开头的数字编号，返回剩下的文件名（含扩展名）。

    用途：人工列边界模板按「语义名」登记，这样以后给 103_real_xxx.pdf
    换成 108_real_xxx.pdf，模板照样能命中，不必跟着改字典的键。
    例：'103_real_bank_statement_textlayer.pdf' → 'real_bank_statement_textlayer.pdf'
    """
    return _NO_PREFIX.sub('', os.path.basename(name))


def case_dir_name(name):
    """case 的输出目录名 = 输入文件名去掉扩展名（编号保留，方便一眼对上）。"""
    return os.path.splitext(os.path.basename(name))[0]


def is_real_case(name, manifest_group=None):
    """
    判断一个 case 是不是「用户自己的真实 case」。

    manifest_group 是 samples_manifest.json 里登记的 group；有值就优先信它
    （人工确认过的最准）。没登记 / 写错时按命名规则推断，所以新丢进来的
    case 即使还没写进 manifest，也能被正确分组。

    规则优先级：
        ① manifest 明确写了 real / synthetic
        ② 有数字前缀且编号 >= 101  → 真实 case
        ③ 无编号但以 real_ 开头    → 真实 case（兼容旧名）
        ④ 其它                     → 合成样本
    """
    if manifest_group in ('real', 'synthetic'):
        return manifest_group == 'real'
    no = parse_no(name)
    if no is not None:
        return no >= REAL_START_NO
    return os.path.basename(name).lower().startswith(REAL_MARKER)


def case_group(name, manifest_group=None):
    """返回 'real' / 'synthetic'，给 JSON 字段与报告标签用。"""
    return 'real' if is_real_case(name, manifest_group) else 'synthetic'


def case_sort_key(name):
    """
    sorted() 的 key：真实 case 恒排最后，组内按数字编号升序。

    返回的是一个元组 (分组, 编号, 文件名)，Python 比较元组时从第一项开始，
    第一项相同才比第二项 —— 这就是「先分组、再排序」的实现方式。
    """
    no = parse_no(name)
    rank = 1 if is_real_case(name) else 0
    return (rank, no if no is not None else 0, name)


def next_real_no(names):
    """算出下一个建议编号 = 当前最大真实编号 + 1（只用于日志提示，不改文件）。"""
    used = [parse_no(n) for n in names
            if parse_no(n) is not None and parse_no(n) >= REAL_START_NO]
    return max(used, default=REAL_START_NO - 1) + 1


def pick_real_image(src_dir, image_exts):
    """
    从目录里挑第一张真实 case 图片，给 c_try_params.py 当默认输入。

    这样以后把 101_real_terminal_screenshot.jpg 改成别的编号，
    调参脚本也不会因为写死文件名而报「找不到图片」。
    """
    if not os.path.isdir(src_dir):
        return None
    exts = tuple(e.lower() for e in image_exts)
    for name in sorted(os.listdir(src_dir), key=case_sort_key):
        if is_real_case(name) and name.lower().endswith(exts):
            return os.path.join(src_dir, name)
    return None

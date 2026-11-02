"""
第1周 · 模块D：表格识别 PP-Structure（可直接运行）

普通 OCR 只给"一行行文字"，表格需要结构识别（还原行列关系），输出 HTML。

用法：
    把含表格的图片命名为 table.png 放到本目录，然后：
    python table_ocr.py
    跑完会生成 table_out.html，用浏览器打开看还原效果。
"""
from paddleocr import PPStructure

engine = PPStructure(table=True, ocr=True, lang='ch')

IMAGE = 'table.png'
result = engine(IMAGE)

html_parts = []
for item in result:
    print('区域类型：', item['type'])          # table / text
    if item['type'] == 'table':
        html = item['res']['html']
        html_parts.append(html)
        print(html[:200], '...')

# 存成 HTML，用浏览器打开看表格
with open('table_out.html', 'w', encoding='utf-8') as f:
    f.write("\n".join(html_parts))
print("\n已保存 table_out.html，用浏览器打开查看")

# 注：PP-StructureV3 是更新版本，用法以官方仓库"表格识别"章节为准：
#     https://github.com/PaddlePaddle/PaddleOCR

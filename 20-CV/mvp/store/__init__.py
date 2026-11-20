"""store/ — 数据访问层（保存方式接缝）。

catalog.py  目录元数据 repo（MySQL：sources/templates/runs/quarantine/load_log）
content.py  内容 repo（当前=文件实现：extract.json / records.json 原子读写）
db.py       薄驱动接口 + PyMySQL 实现 + conn_ref 解析 + 迁移执行器

业务层只调 repo，不出现 SQL / 裸路径拼接；懒加载（import 不碰 DB）。
"""
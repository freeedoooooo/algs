"""store/ — 数据访问层（DB 唯一事实源）。

catalog/       目录元数据 repo，按域拆分：files / templates / tasks / load
               （__init__ 全量重导出，调用方 catalog.xxx() 不感知边界）
content.py     内容门面（extract 经 artifact BLOB；records 经 content_db 三表）
content_db.py  暂存三表（record/field/lineage）读写与跨任务查询
artifact.py    产物附件接缝（DB-only）
artifact_db.py 产物附件 repo（MySQL BLOB，task_file 粒度）
loader.py      目标业务库写入（连接/introspection/字段校验/写入/transform/门禁）
db.py          薄驱动接口 + PyMySQL 实现 + conn_ref 解析（建表人工跑 001）
errors.py      类型化业务错误（StoreError.code → HTTP；DB 故障原样上抛 503）

业务层只调 repo，不出现 SQL / 裸路径拼接；懒加载（import 不碰 DB）。
"""
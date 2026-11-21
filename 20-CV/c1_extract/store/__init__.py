"""store/ — 数据访问层（DB 唯一事实源）。

catalog.py  目录元数据 repo（MySQL：file/template/task/task_file/quarantine）
content.py  内容门面（extract 经 artifact BLOB；records 经 content_db 三表）
db.py       薄驱动接口 + PyMySQL 实现 + conn_ref 解析 + 迁移执行器
errors.py   类型化业务错误（StoreError.code → HTTP；DB 故障原样上抛 503）

业务层只调 repo，不出现 SQL / 裸路径拼接；懒加载（import 不碰 DB）。
"""
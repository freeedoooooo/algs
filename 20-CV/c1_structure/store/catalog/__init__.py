"""store/catalog — 目录元数据 repo（MySQL）。

按业务域拆分子模块，本 __init__ 全量重导出公共函数——调用方一律
`from . import catalog` 后 `catalog.xxx()`，不感知子模块边界：

    _common.py   行投影 / JSON 反序列化共享小工具
    files.py     源文件域（c1_doc_file ＋ content 原件字节）
    rules.py     抽取规则域（c1_extract_rule / c1_extract_rule_version）
    tasks.py     任务域（c1_task / c1_task_file / c1_load_quarantine）
    load.py      入库域（c1_load_datasource / load_table(_field) / load_log）

只经 db.connect 拿 DB-API 连接，SQL 全部收敛在本包；DB 必选，错误上抛。
JSON 列：写入 json.dumps，读出 json.loads（驱动无关，不依赖 MySQL JSON 函数）。
无外键约束：引用完整性归应用层（delete_file 引用守卫；级联删除见设计稿 §2）。
"""
from .files import (register_file, list_files, get_file, get_file_content,
                    delete_file, update_file_meta)
from .rules import (list_rules, get_rule_version, get_rule,
                        create_rule, create_version, update_rule,
                        delete_rule, list_versions)
from .tasks import (create_task, set_task_state, add_task_file,
                    set_task_file_state, rollup_task_state, get_task,
                    list_tasks, task_file_ids,
                    add_quarantine, list_quarantine)
from .load import (list_datasources, get_datasource, create_datasource,
                   update_datasource, delete_datasource,
                   ensure_default_datasource, list_load_tables, get_load_table,
                   create_load_table, update_load_table, delete_load_table,
                   set_task_load, add_load_log, list_load_logs)
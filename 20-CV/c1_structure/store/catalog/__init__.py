"""store/catalog — 目录元数据 repo（MySQL）。

按领域导出：文档 files、单行规则 rules、当前抽取结果 results、入库配置/
绑定/回执 load。所有 SQL 收敛在本包，引用完整性由应用层显式维护。
"""
from .files import (register_file, list_files, get_file, get_file_content,
                    delete_file, clear_document_results, update_file_meta,
                    set_state, set_params, add_quarantine, clear_quarantine,
                    list_quarantine)
from .rules import (list_rules, get_rule, create_rule, update_rule, delete_rule)
from .results import (list_extract_results, get_extract_result,
                      ensure_extract_result, finish_extract_result,
                      purge_extract_result)
from .load import (list_datasources, get_datasource, get_datasource_by_code,
                   create_datasource, update_datasource, delete_datasource,
                   ensure_default_datasource, list_load_tables, get_load_table,
                   get_load_table_by_code, create_load_table,
                   update_load_table, delete_load_table,
                   create_binding, update_binding, get_binding, list_bindings,
                   confirm_binding, start_binding, finish_binding, add_receipt,
                   list_receipts, purge_receipts, list_loaded_results)

"""c1_structure/accept_records_db.py — 当前解耦契约的静态/导入检查。

旧版七项手工验收依赖已废弃的 rule_version/file 级 records 契约，并会连接
平台库、启动临时服务、创建/删除合成表和写业务库，已不再适用。本脚本只检查
源码与模块接口，不连接任何数据库、不发 HTTP 请求、不启动服务、不写文件。

当前契约：
  * c1_extract_rule 一行一条完整规则，没有规则版本表；
  * 文档通过 c1_extract_result 关联多条规则结果；
  * c1_extract_record 以 extract_result_id 为记录边界；
  * c1_load_binding 按 extract_result_id 唯一绑定一个 c1_load_table；
  * 入库 API 以 extract_result_id 为键，确认绑定与执行入库分两步。

用法（从 20-CV）：
  D:/miniforge3/envs/paddle/python.exe -u c1_structure/accept_records_db.py

这不是数据库验收；需要功能验收时应使用当前 API，并另行取得写库授权。
"""
import ast
import importlib
import inspect
import os
import sys

# 手工运行时不产生项目模块的 __pycache__；导入期间的目录创建也被拦截。
sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _path in (PARENT, ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

FAILS = []
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _path in (PARENT, ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

FAILS = []


def check(name, ok, detail=''):
    print('  {}  {}{}'.format('PASS' if ok else 'FAIL', name,
                              (' · ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


def _parse(relative_path):
    path = os.path.join(ROOT, relative_path)
    with open(path, 'r', encoding='utf-8') as source:
        return ast.parse(source.read(), filename=path)


def _calls(tree):
    """返回被调用的属性/函数名，以及属性调用的完整点号名称。"""
    names, attributes = set(), set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
            parts = [func.attr]
            value = func.value
            while isinstance(value, ast.Attribute):
                parts.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                parts.append(value.id)
                attributes.add('.'.join(reversed(parts)))
    return names, attributes


def _imported_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.split('.')[0]
                         for alias in node.names)
    return names


def _routes(tree):
    routes = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute) or func.attr not in (
                    'get', 'post', 'patch', 'put', 'delete'):
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                routes.add((func.attr.upper(), decorator.args[0].value))
    return routes


def _has_params(module, function, required):
    try:
        params = inspect.signature(getattr(module, function)).parameters
    except (AttributeError, TypeError, ValueError):
        return False
    return all(name in params for name in required)


def main():
    print('== records 解耦契约静态/导入检查（无数据库、HTTP、写文件）==')
    try:
        app_tree = _parse('app.py')
        catalog_tree = _parse(os.path.join('store', 'catalog', '__init__.py'))
        content_tree = _parse(os.path.join('store', 'content_db.py'))
        self_tree = _parse(os.path.basename(__file__))
    except (OSError, SyntaxError) as exc:
        print('  FAIL  源码读取/语法检查 · {}: {}'.format(type(exc).__name__, exc))
        return 1

    calls, attributes = _calls(app_tree)
    check('应用代码已移除 get_rule_version 调用',
          'get_rule_version' not in calls)
    check('应用代码已移除 catalog.set_rule 调用',
          'catalog.set_rule' not in attributes)

    routes = _routes(app_tree)
    required_routes = {
        ('POST', '/api/sources/{file_id}/extract'),
        ('GET', '/api/extract-results/{extract_result_id}/staging'),
        ('PATCH', '/api/extract-results/{extract_result_id}/staging/{index}'),
        ('POST', '/api/extract-results/{extract_result_id}/load'),
        ('POST', '/api/load/bindings'),
    }
    check('抽取结果级 API 路由齐全', required_routes <= routes,
          '缺少 {}'.format(sorted(required_routes - routes)))
    check('旧 file 级 staging/load 路由已移除',
          not any(path in ('/api/sources/{file_id}/staging',
                           '/api/sources/{file_id}/load') for _, path in routes))

    catalog_imports = _imported_names(catalog_tree)
    content_calls, content_attributes = _calls(content_tree)
    self_calls, self_attributes = _calls(self_tree)
    check('catalog 导出单行规则/结果/绑定接口', {
        'get_rule', 'create_rule', 'get_extract_result', 'create_binding'
    } <= catalog_imports)
    check('content_db 不再调用 purge_records',
          'purge_records' not in content_calls)
    check('静态检查脚本无数据库/HTTP/服务调用', not (
        self_calls & {'connect', 'connect_direct', 'urlopen', 'Popen', 'execute',
                      'commit', 'rollback', 'drop', 'remove', 'unlink', 'rmtree'}
        or self_attributes & {'db.connect', 'loader.connect_datasource',
                              'urllib.request.urlopen', 'subprocess.Popen'}))

    original_makedirs = os.makedirs

    def forbidden_connect(*_args, **_kwargs):
        raise AssertionError('静态/导入检查禁止连接数据库')

    def skip_makedirs(*_args, **_kwargs):
        """config 导入会建运行目录；静态检查明确不落盘。"""
        return None

    os.makedirs = skip_makedirs
    try:
        db = importlib.import_module(PKG + '.store.db')
        loader = importlib.import_module(PKG + '.store.loader')
        original_connect = db.connect
        original_loader_connect = loader.connect_datasource
        db.connect = forbidden_connect
        loader.connect_datasource = forbidden_connect
        try:
            catalog = importlib.import_module(PKG + '.store.catalog')
            content_db = importlib.import_module(PKG + '.store.content_db')
            check('catalog/content_db 导入未连接数据库或创建目录', True)
        finally:
            db.connect = original_connect
            loader.connect_datasource = original_loader_connect
    except Exception as exc:
        check('catalog/content_db 导入未连接数据库或创建目录', False,
              '{}: {}'.format(type(exc).__name__, exc))
        return 1
    finally:
        os.makedirs = original_makedirs

    interfaces = (
        (catalog, 'get_rule', ('rule_id', 'name')),
        (catalog, 'create_rule', ('name', 'output_schema_json',
                                 'extraction_spec_json')),
        (catalog, 'get_extract_result', ('extract_result_id',)),
        (catalog, 'create_load_table', ('datasource_code', 'target_table', 'fields')),
        (catalog, 'create_binding', ('extract_result_id', 'load_table_id',
                                    'field_map', 'write_mode', 'business_keys')),
        (content_db, 'get_records', ('extract_result_id',)),
        (content_db, 'save_records', ('extract_result_id', 'records')),
        (content_db, 'patch_record', ('extract_result_id', 'index', 'values')),
        (content_db, 'set_review', ('extract_result_id', 'indexes', 'state')),
    )
    for module, function, required in interfaces:
        check('{}.{} 接口存在'.format(module.__name__.rsplit('.', 1)[-1], function),
              _has_params(module, function, required))

    check('已废弃规则版本接口不存在', not hasattr(catalog, 'get_rule_version'))
    print('\n结论：{}'.format('静态/导入检查全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())

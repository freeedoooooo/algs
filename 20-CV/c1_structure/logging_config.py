"""Python 标准控制台日志配置；任务文件与页面结构化日志保持独立。"""
import logging
import os

_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
_DATEFMT = '%Y-%m-%d %H:%M:%S'
_HANDLER_NAME = 'c1-structure-console'


def configure_logging():
    logger = logging.getLogger('c1_structure')
    logger.setLevel(os.getenv('C1_LOG_LEVEL', 'INFO').upper())
    logger.propagate = False
    if not any(h.name == _HANDLER_NAME for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.name = _HANDLER_NAME
        handler.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
        logger.addHandler(handler)
    return logger


def uvicorn_log_config():
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {'standard': {'format': _FORMAT, 'datefmt': _DATEFMT}},
        'handlers': {'default': {
            'class': 'logging.StreamHandler', 'formatter': 'standard',
            'stream': 'ext://sys.stdout'}},
        'loggers': {
            'uvicorn': {'handlers': ['default'], 'level': 'INFO',
                        'propagate': False},
            'uvicorn.error': {'handlers': ['default'], 'level': 'INFO',
                              'propagate': False},
            'uvicorn.access': {'handlers': ['default'], 'level': 'INFO',
                               'propagate': False},
        },
    }


def log_level(level):
    return {'ok': logging.INFO, 'stage': logging.INFO,
            'info': logging.INFO, 'warn': logging.WARNING,
            'error': logging.ERROR}.get(level, logging.INFO)

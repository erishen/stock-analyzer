"""
InvestKit 共享模块

提供各项目共享的配置、日志、缓存、工具、异常、类型定义和测试工具。

模块:
- config: 配置管理
- cache: 缓存抽象层
- logging: 统一日志
- api_docs: API 文档聚合
- utils: 通用工具函数
- exceptions: 统一异常处理
- types: 共享类型定义
- testing: 测试工具函数
- db: 数据库模型、连接管理、路径配置
"""

__version__ = "1.0.0"

__all__ = [
    "Config",
    "LoggerManager",
    "MemoryCache",
    "get_config",
    "get_logger",
    "setup_logging",
]

_lazy_imports = {
    "Config": "investkit_utils.config",
    "get_config": "investkit_utils.config",
    "LoggerManager": "investkit_utils.log_utils",
    "get_logger": "investkit_utils.log_utils",
    "setup_logging": "investkit_utils.log_utils",
    "MemoryCache": "investkit_utils.cache",
}


def __getattr__(name):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'investkit_utils' has no attribute {name!r}")

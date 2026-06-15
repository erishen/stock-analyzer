"""InvestKit 统一配置模块

提供配置加载、验证和管理功能。

使用示例:
    from investkit_utils.config import get_config, AppConfig

    # 加载配置
    config = get_config("asset-lens")

    # 访问配置
    print(config.app.name)
    print(config.database.sqlite.path)
    print(config.llm.default_provider)
"""

__all__ = [
    "Config",
    "ConfigLoader",
    "get_config",
]

_lazy_imports = {
    "Config": "investkit_utils.config.models",
    "get_config": "investkit_utils.config.loader",
    "ConfigLoader": "investkit_utils.config.loader",
    "reload_config": "investkit_utils.config.loader",
    "set_config_path": "investkit_utils.config.loader",
    "clear_config_cache": "investkit_utils.config.loader",
    "AppConfig": "investkit_utils.config.models",
    "LoggingConfig": "investkit_utils.config.models",
    "DatabaseConfig": "investkit_utils.config.models",
    "CacheConfig": "investkit_utils.config.models",
    "ApiConfig": "investkit_utils.config.models",
    "Environment": "investkit_utils.config.models",
}


def __getattr__(name):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'investkit_utils.config' has no attribute {name!r}")

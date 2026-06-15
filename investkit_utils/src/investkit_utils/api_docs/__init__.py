"""
InvestKit API 文档聚合模块

聚合各项目的 OpenAPI 文档，提供统一的 API 文档入口。

使用示例:
    from investkit_utils.api_docs import aggregate_openapi_docs, serve_aggregated_docs

    # 聚合文档
    app = serve_aggregated_docs()
"""

__all__ = [
    "aggregate_openapi_docs",
    "serve_aggregated_docs",
]

_lazy_imports = {
    "aggregate_openapi_docs": "investkit_utils.api_docs.openapi",
    "aggregate_from_files": "investkit_utils.api_docs.openapi",
    "serve_aggregated_docs": "investkit_utils.api_docs.server",
    "ServiceRegistry": "investkit_utils.api_docs.discovery",
    "ServiceInfo": "investkit_utils.api_docs.discovery",
    "ServiceStatus": "investkit_utils.api_docs.discovery",
    "HealthCheckResult": "investkit_utils.api_docs.discovery",
    "get_service_registry": "investkit_utils.api_docs.discovery",
    "register_service": "investkit_utils.api_docs.discovery",
    "get_service": "investkit_utils.api_docs.discovery",
    "get_all_services": "investkit_utils.api_docs.discovery",
    "APIService": "investkit_utils.api_docs.services",
    "INVESTKIT_SERVICES": "investkit_utils.api_docs.services",
    "fetch_openapi_spec": "investkit_utils.api_docs.openapi",
    "load_openapi_spec_from_file": "investkit_utils.api_docs.openapi",
    "merge_openapi_specs": "investkit_utils.api_docs.openapi",
}


def __getattr__(name):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'investkit_utils.api_docs' has no attribute {name!r}")

"""OpenAPI 规范处理

支持:
- 合并多个 OpenAPI 规范
- 从服务获取 OpenAPI 规范
- 从文件加载 OpenAPI 规范
- 缓存支持
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from investkit_utils.api_docs.services import APIService

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from investkit_utils.cache import CacheBackend

_cache: CacheBackend | None = None
_cache_ttl: int = 300
_DEFAULT_HTTP_TIMEOUT = 10.0


def set_cache(cache: CacheBackend | None, ttl: int = 300) -> None:
    """设置缓存

    Args:
        cache: 缓存实例
        ttl: 缓存过期时间 (秒)
    """
    global _cache, _cache_ttl
    _cache = cache
    _cache_ttl = ttl


def merge_openapi_specs(
    specs: list[dict],
    main_info: dict | None = None,
) -> dict:
    """合并多个 OpenAPI 规范

    Args:
        specs: OpenAPI 规范列表
        main_info: 主信息 (可选)

    Returns:
        合并后的 OpenAPI 规范
    """
    merged: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": main_info
        or {
            "title": "InvestKit API",
            "description": "InvestKit 统一 API 文档",
            "version": "1.0.0",
        },
        "paths": {},
        "components": {
            "schemas": {},
            "securitySchemes": {},
        },
        "tags": [],
    }

    existing_tags = set()

    for spec in specs:
        if not spec:
            continue

        prefix = spec.get("_prefix", "")
        service_name = spec.get("_service", "")

        if "paths" in spec:
            for path, methods in spec["paths"].items():
                new_path = f"{prefix}{path}" if prefix else path
                if service_name:
                    for method in methods.values():
                        if isinstance(method, dict):
                            tags = method.get("tags", [])
                            if service_name not in tags:
                                method["tags"] = [service_name, *tags]
                merged["paths"][new_path] = methods

        if "components" in spec:
            if "schemas" in spec["components"]:
                for schema_name, schema in spec["components"]["schemas"].items():
                    prefixed_name = f"{service_name}_{schema_name}" if service_name else schema_name
                    merged["components"]["schemas"][prefixed_name] = schema
            if "securitySchemes" in spec["components"]:
                merged["components"]["securitySchemes"].update(spec["components"]["securitySchemes"])

        if "tags" in spec:
            for tag in spec["tags"]:
                tag_name = tag.get("name")
                if tag_name and tag_name not in existing_tags:
                    existing_tags.add(tag_name)
                    merged["tags"].append(tag)

    for service_name in set(spec.get("_service") for spec in specs if spec and spec.get("_service")):
        if service_name not in existing_tags:
            merged["tags"].append({"name": service_name, "description": f"{service_name} API"})

    return merged


async def fetch_openapi_spec(service: APIService, use_cache: bool = True) -> dict | None:
    """获取服务的 OpenAPI 规范

    Args:
        service: API 服务定义
        use_cache: 是否使用缓存

    Returns:
        OpenAPI 规范字典
    """
    cache_key = f"openapi:{service.name}"

    if use_cache and _cache:
        cached_spec = _cache.get(cache_key)
        if cached_spec:
            return cached_spec

    try:
        import httpx

        async with httpx.AsyncClient(timeout=_DEFAULT_HTTP_TIMEOUT) as client:
            response = await client.get(f"{service.url}{service.openapi_url}")
            response.raise_for_status()
            spec = response.json()
            spec["_prefix"] = service.prefix
            spec["_service"] = service.name

            if use_cache and _cache:
                _cache.set(cache_key, spec, ttl=_cache_ttl)

            return spec
    except (httpx.HTTPError, httpx.InvalidURL) as e:
        logger.warning("Failed to fetch OpenAPI spec from %s: %s", service.name, e)
        return None


def load_openapi_spec_from_file(file_path: str) -> dict | None:
    """从文件加载 OpenAPI 规范

    Args:
        file_path: 文件路径

    Returns:
        OpenAPI 规范字典
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load OpenAPI spec from %s: %s", file_path, e)
        return None


async def aggregate_openapi_docs(
    services: list[APIService] | None = None,
    main_info: dict | None = None,
    use_cache: bool = True,
) -> dict:
    """聚合所有服务的 OpenAPI 文档

    Args:
        services: 服务列表 (默认使用 INVESTKIT_SERVICES)
        main_info: 主信息
        use_cache: 是否使用缓存

    Returns:
        聚合后的 OpenAPI 规范
    """
    from investkit_utils.api_docs.services import INVESTKIT_SERVICES

    services = services or INVESTKIT_SERVICES
    specs = []

    for service in services:
        if service.enabled:
            spec = await fetch_openapi_spec(service, use_cache=use_cache)
            if spec:
                specs.append(spec)

    return merge_openapi_specs(specs, main_info)


def aggregate_from_files(
    spec_files: list[tuple[str, str]],
    main_info: dict | None = None,
) -> dict:
    """从文件聚合 OpenAPI 文档

    Args:
        spec_files: [(文件路径, 路径前缀), ...]
        main_info: 主信息

    Returns:
        聚合后的 OpenAPI 规范
    """
    specs = []

    for file_path, prefix in spec_files:
        spec = load_openapi_spec_from_file(file_path)
        if spec:
            spec["_prefix"] = prefix
            specs.append(spec)

    return merge_openapi_specs(specs, main_info)


def clear_cache() -> None:
    """清除 OpenAPI 缓存"""
    global _cache
    if _cache:
        keys = _cache.keys("openapi:*")
        for key in keys:
            _cache.delete(key)

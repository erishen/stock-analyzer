"""InvestKit 缓存管理器

提供缓存实例的创建和管理。
"""

from __future__ import annotations

from investkit_utils.cache.base import CacheBackend
from investkit_utils.cache.memory import MemoryCache

_cache_instances: dict[str, CacheBackend] = {}
_default_cache: CacheBackend | None = None


def get_cache(name: str | None = None) -> CacheBackend:
    """获取缓存实例

    Args:
        name: 缓存名称 (可选)

    Returns:
        缓存实例
    """
    global _default_cache

    if name is None:
        if _default_cache is None:
            _default_cache = MemoryCache()
        return _default_cache

    if name not in _cache_instances:
        _cache_instances[name] = MemoryCache()

    return _cache_instances[name]


def get_memory_cache(
    name: str | None = None,
    default_ttl: int | None = None,
) -> MemoryCache:
    """获取内存缓存实例

    Args:
        name: 缓存名称 (可选)
        default_ttl: 默认过期时间

    Returns:
        内存缓存实例
    """
    cache = MemoryCache(default_ttl=default_ttl)

    if name:
        _cache_instances[name] = cache

    return cache


def get_redis_cache(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: str | None = None,
    prefix: str = "investkit:",
    name: str | None = None,
) -> CacheBackend:
    """获取 Redis 缓存实例

    Args:
        host: Redis 主机
        port: Redis 端口
        db: Redis 数据库
        password: Redis 密码
        prefix: 键前缀
        name: 缓存名称 (可选)

    Returns:
        Redis 缓存实例
    """
    from investkit_utils.cache.redis_cache import RedisCache

    cache = RedisCache(
        host=host,
        port=port,
        db=db,
        password=password,
        prefix=prefix,
    )

    if name:
        _cache_instances[name] = cache

    return cache


def clear_all_caches() -> None:
    """清空所有缓存实例"""
    global _default_cache

    for cache in _cache_instances.values():
        cache.clear()

    if _default_cache:
        _default_cache.clear()

    _cache_instances.clear()
    _default_cache = None


def set_default_cache(cache: CacheBackend) -> None:
    """设置默认缓存实例

    Args:
        cache: 缓存实例
    """
    global _default_cache
    _default_cache = cache

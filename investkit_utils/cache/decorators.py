"""InvestKit 缓存装饰器

提供函数结果缓存装饰器。
"""

from __future__ import annotations

import functools
import hashlib
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from investkit_utils.cache.base import CacheBackend
from investkit_utils.cache.manager import get_cache

_CACHE_MISS = object()

T = TypeVar("T")
F = Callable[..., T]


def _make_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    key_prefix: str | None = None,
) -> str:
    parts = [func.__module__, func.__qualname__]

    if args:
        parts.append(str(args))
    if kwargs:
        parts.append(str(sorted(kwargs.items())))

    key_content = ":".join(parts)
    key_hash = hashlib.md5(key_content.encode()).hexdigest()[:12]

    if key_prefix:
        return f"{key_prefix}:{func.__name__}:{key_hash}"
    return f"cached:{func.__name__}:{key_hash}"


def _resolve_cache(cache: CacheBackend | str | None) -> CacheBackend:
    if cache is None:
        return get_cache()
    if isinstance(cache, str):
        return get_cache(cache)
    return cache


def cached(
    ttl: int | None = None,
    key_prefix: str | None = None,
    cache: CacheBackend | str | None = None,
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_instance = _resolve_cache(cache)
            key = _make_cache_key(func, args, kwargs, key_prefix)

            cached_value = cache_instance.get(key, default=_CACHE_MISS)
            if cached_value is not _CACHE_MISS:
                return cached_value

            result = func(*args, **kwargs)
            cache_instance.set(key, result, ttl)

            return result

        wrapper._cache_info = {"ttl": ttl, "key_prefix": key_prefix}  # type: ignore

        return wrapper  # type: ignore

    return decorator


def cached_async(
    ttl: int | None = None,
    key_prefix: str | None = None,
    cache: CacheBackend | str | None = None,
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_instance = _resolve_cache(cache)
            key = _make_cache_key(func, args, kwargs, key_prefix)

            cached_value = cache_instance.get(key, default=_CACHE_MISS)
            if cached_value is not _CACHE_MISS:
                return cached_value

            result = await func(*args, **kwargs)
            cache_instance.set(key, result, ttl)

            return result

        wrapper._cache_info = {"ttl": ttl, "key_prefix": key_prefix}  # type: ignore

        return wrapper  # type: ignore

    return decorator


def cache_result(
    func: F | None = None,
    *,
    ttl: int | None = None,
    key_prefix: str | None = None,
) -> F | Callable[[F], F]:
    """智能缓存装饰器

    自动检测同步/异步函数并使用对应的装饰器。

    Args:
        func: 函数 (可选)
        ttl: 过期时间 (秒)
        key_prefix: 键前缀

    Returns:
        装饰器或装饰后的函数

    示例:
        @cache_result(ttl=300)
        def sync_func(arg):
            return compute(arg)

        @cache_result(ttl=300)
        async def async_func(arg):
            return await compute(arg)
    """

    def decorator(f: F) -> F:
        if inspect.iscoroutinefunction(f):
            return cached_async(ttl=ttl, key_prefix=key_prefix)(f)
        return cached(ttl=ttl, key_prefix=key_prefix)(f)

    if func is not None:
        return decorator(func)
    return decorator


def invalidate_cache(
    func: Callable,
    *args: Any,
    key_prefix: str | None = None,
    cache: CacheBackend | str | None = None,
    **kwargs: Any,
) -> bool:
    cache_instance = _resolve_cache(cache)
    key = _make_cache_key(func, args, kwargs, key_prefix)
    return cache_instance.delete(key)

"""InvestKit 内存缓存实现

基于字典的内存缓存，支持 TTL 过期。
"""

from __future__ import annotations

import fnmatch
import time
from threading import Lock
from typing import Any

from investkit_utils.cache.base import CacheBackend


class CacheEntry:
    """缓存条目"""

    __slots__ = ["expires_at", "value"]

    def __init__(self, value: Any, ttl: int | None = None):
        self.value = value
        self.expires_at = time.time() + ttl if ttl else None

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class MemoryCache(CacheBackend):
    """内存缓存实现

    特点:
    - 基于字典存储
    - 支持 TTL 过期
    - 线程安全
    - 支持模式匹配

    示例:
        cache = MemoryCache()
        cache.set("key", "value", ttl=60)
        value = cache.get("key")
    """

    def __init__(self, default_ttl: int | None = None):
        """初始化内存缓存

        Args:
            default_ttl: 默认过期时间 (秒)
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._default_ttl = default_ttl

    def get(self, key: str, default: Any | None = None) -> Any | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return default
            if entry.is_expired():
                del self._cache[key]
                return default
            return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if ttl is None:
            ttl = self._default_ttl
        with self._lock:
            self._cache[key] = CacheEntry(value, ttl)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                return False
            return True

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def keys(self, pattern: str | None = None) -> list[str]:
        with self._lock:
            self._cleanup_expired()
            if pattern is None:
                return list(self._cache.keys())
            return [key for key in self._cache if fnmatch.fnmatch(key, pattern)]

    def _cleanup_expired(self) -> int:
        """清理过期缓存

        Returns:
            清理的数量
        """
        count = 0
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items() if entry.expires_at and current_time > entry.expires_at
        ]
        for key in expired_keys:
            del self._cache[key]
            count += 1
        return count

    def __len__(self) -> int:
        """返回缓存数量"""
        with self._lock:
            self._cleanup_expired()
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """支持 `in` 操作符"""
        return self.exists(key)

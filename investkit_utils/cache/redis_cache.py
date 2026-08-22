"""InvestKit Redis 缓存实现

基于 Redis 的分布式缓存实现。
"""

from __future__ import annotations

import json
from typing import Any

from investkit_utils.cache.base import CacheBackend

try:
    import redis

    REDIS_AVAILABLE = True
    _RedisConnectionError = redis.ConnectionError
except ImportError:
    REDIS_AVAILABLE = False
    _RedisConnectionError = ConnectionError


class RedisCache(CacheBackend):
    """Redis 缓存实现

    特点:
    - 分布式缓存
    - 持久化支持
    - 高性能
    - 支持模式匹配

    示例:
        cache = RedisCache(host="localhost", port=6379)
        cache.set("key", "value", ttl=60)
        value = cache.get("key")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        prefix: str = "investkit:",
        **kwargs: Any,
    ):
        """初始化 Redis 缓存

        Args:
            host: Redis 主机
            port: Redis 端口
            db: Redis 数据库
            password: Redis 密码
            prefix: 键前缀
            **kwargs: 其他 Redis 参数
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not installed. Install it with: pip install redis")

        self._client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
            **kwargs,
        )
        self._prefix = prefix

    def _make_key(self, key: str) -> str:
        """添加前缀"""
        return f"{self._prefix}{key}"

    def _serialize(self, value: Any) -> str:
        """序列化值"""
        return json.dumps(value)

    def _deserialize(self, value: str | None) -> Any:
        """反序列化值"""
        if value is None:
            return None
        return json.loads(value)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        full_key = self._make_key(key)
        value = self._client.get(full_key)
        if value is None:
            return default
        return self._deserialize(value)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        full_key = self._make_key(key)
        serialized = self._serialize(value)
        if ttl:
            self._client.setex(full_key, ttl, serialized)
        else:
            self._client.set(full_key, serialized)

    def delete(self, key: str) -> bool:
        full_key = self._make_key(key)
        return bool(self._client.delete(full_key))

    def exists(self, key: str) -> bool:
        full_key = self._make_key(key)
        return bool(self._client.exists(full_key))

    def clear(self) -> None:
        """清空所有带前缀的缓存（使用 SCAN 替代 KEYS）"""
        pattern = f"{self._prefix}*"
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=pattern, count=100)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

    def keys(self, pattern: str | None = None) -> list[str]:
        full_pattern = self._make_key(pattern) if pattern else f"{self._prefix}*"

        result = []
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=full_pattern, count=100)
            result.extend(keys)
            if cursor == 0:
                break
        prefix_len = len(self._prefix)
        return [key[prefix_len:] for key in result]

    def incr(self, key: str, amount: int = 1) -> int:
        full_key = self._make_key(key)
        return self._client.incrby(full_key, amount)

    def decr(self, key: str, amount: int = 1) -> int:
        return self.incr(key, -amount)

    def ping(self) -> bool:
        """检查 Redis 连接"""
        try:
            return self._client.ping()
        except _RedisConnectionError:
            return False

    def close(self) -> None:
        """关闭连接"""
        self._client.close()

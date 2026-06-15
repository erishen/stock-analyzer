"""InvestKit 缓存抽象基类

定义缓存后端必须实现的接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):
    """缓存后端抽象基类

    所有缓存实现必须继承此类并实现所有抽象方法。

    方法:
        get: 获取缓存值
        set: 设置缓存值
        delete: 删除缓存值
        exists: 检查缓存是否存在
        clear: 清空缓存
        keys: 获取所有缓存键
    """

    @abstractmethod
    def get(self, key: str, default: Any | None = None) -> Any | None:
        """获取缓存值

        Args:
            key: 缓存键
            default: 缓存不存在时的默认值

        Returns:
            缓存值，不存在则返回 default
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间 (秒)，None 表示永不过期
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有缓存"""
        pass

    @abstractmethod
    def keys(self, pattern: str | None = None) -> list[str]:
        """获取所有缓存键

        Args:
            pattern: 键模式 (可选)

        Returns:
            键列表
        """
        pass

    _MISSING = object()

    def get_or_set(self, key: str, default: Any, ttl: int | None = None) -> Any:
        """获取缓存值，不存在则设置默认值

        Args:
            key: 缓存键
            default: 默认值或可调用对象
            ttl: 过期时间 (秒)

        Returns:
            缓存值或默认值
        """
        value = self.get(key, default=self._MISSING)
        if value is not self._MISSING:
            return value

        value = default() if callable(default) else default

        self.set(key, value, ttl)
        return value

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """批量获取缓存值

        Args:
            keys: 缓存键列表

        Returns:
            键值对字典
        """
        return {key: self.get(key) for key in keys}

    def set_many(self, mapping: dict[str, Any], ttl: int | None = None) -> None:
        """批量设置缓存值

        Args:
            mapping: 键值对字典
            ttl: 过期时间 (秒)
        """
        for key, value in mapping.items():
            self.set(key, value, ttl)

    def delete_many(self, keys: list[str]) -> int:
        """批量删除缓存值

        Args:
            keys: 缓存键列表

        Returns:
            删除的数量
        """
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count

    def incr(self, key: str, amount: int = 1) -> int:
        """递增缓存值

        Args:
            key: 缓存键
            amount: 递增量

        Returns:
            递增后的值
        """
        value = self.get(key, default=0)
        new_value = int(value) + amount
        self.set(key, new_value)
        return new_value

    def decr(self, key: str, amount: int = 1) -> int:
        """递减缓存值

        Args:
            key: 缓存键
            amount: 递减量

        Returns:
            递减后的值
        """
        return self.incr(key, -amount)

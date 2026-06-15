"""InvestKit 缓存模块测试"""

import asyncio
import time

from investkit_utils.cache import (
    MemoryCache,
    cached,
    cached_async,
    clear_all_caches,
    get_cache,
    get_memory_cache,
    invalidate_cache,
)


class TestMemoryCache:
    def setup_method(self):
        self.cache = MemoryCache()

    def test_set_and_get(self):
        self.cache.set("key", "value")
        assert self.cache.get("key") == "value"

    def test_get_nonexistent(self):
        assert self.cache.get("nonexistent") is None

    def test_delete(self):
        self.cache.set("key", "value")
        assert self.cache.delete("key") is True
        assert self.cache.get("key") is None

    def test_delete_nonexistent(self):
        assert self.cache.delete("nonexistent") is False

    def test_exists(self):
        self.cache.set("key", "value")
        assert self.cache.exists("key") is True
        assert self.cache.exists("nonexistent") is False

    def test_clear(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.clear()
        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is None

    def test_keys(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        keys = self.cache.keys()
        assert "key1" in keys
        assert "key2" in keys

    def test_keys_pattern(self):
        self.cache.set("user:1", "value1")
        self.cache.set("user:2", "value2")
        self.cache.set("item:1", "value3")
        keys = self.cache.keys("user:*")
        assert len(keys) == 2
        assert "user:1" in keys
        assert "user:2" in keys

    def test_ttl(self):
        self.cache.set("key", "value", ttl=1)
        assert self.cache.get("key") == "value"
        time.sleep(1.1)
        assert self.cache.get("key") is None

    def test_get_or_set(self):
        value = self.cache.get_or_set("key", "default")
        assert value == "default"
        assert self.cache.get("key") == "default"

    def test_get_or_set_callable(self):
        value = self.cache.get_or_set("key", lambda: "computed")
        assert value == "computed"

    def test_get_many(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        result = self.cache.get_many(["key1", "key2", "key3"])
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"
        assert result["key3"] is None

    def test_set_many(self):
        self.cache.set_many({"key1": "value1", "key2": "value2"})
        assert self.cache.get("key1") == "value1"
        assert self.cache.get("key2") == "value2"

    def test_delete_many(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        count = self.cache.delete_many(["key1", "key2", "key3"])
        assert count == 2

    def test_incr(self):
        self.cache.set("counter", 0)
        assert self.cache.incr("counter") == 1
        assert self.cache.incr("counter", 5) == 6

    def test_decr(self):
        self.cache.set("counter", 10)
        assert self.cache.decr("counter") == 9
        assert self.cache.decr("counter", 5) == 4

    def test_len(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        assert len(self.cache) == 2

    def test_contains(self):
        self.cache.set("key", "value")
        assert "key" in self.cache
        assert "nonexistent" not in self.cache


class TestCacheManager:
    def setup_method(self):
        clear_all_caches()

    def test_get_cache_default(self):
        cache = get_cache()
        assert cache is not None
        assert isinstance(cache, MemoryCache)

    def test_get_cache_named(self):
        cache1 = get_cache("cache1")
        cache2 = get_cache("cache1")
        assert cache1 is cache2

    def test_get_memory_cache_with_ttl(self):
        cache = get_memory_cache(default_ttl=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_clear_all_caches(self):
        cache1 = get_cache("cache1")
        cache2 = get_cache("cache2")
        cache1.set("key1", "value1")
        cache2.set("key2", "value2")
        clear_all_caches()
        assert cache1.get("key1") is None
        assert cache2.get("key2") is None


class TestCachedDecorator:
    def setup_method(self):
        clear_all_caches()
        self.call_count = 0

    def test_cached_sync(self):
        @cached(ttl=60)
        def expensive_func(x):
            self.call_count += 1
            return x * 2

        result1 = expensive_func(5)
        result2 = expensive_func(5)

        assert result1 == 10
        assert result2 == 10
        assert self.call_count == 1

    def test_cached_different_args(self):
        @cached()
        def func(x):
            self.call_count += 1
            return x

        func(1)
        func(2)
        func(1)

        assert self.call_count == 2

    def test_cached_with_key_prefix(self):
        @cached(key_prefix="test")
        def func(x):
            return x

        result = func(5)
        assert result == 5

    def test_invalidate_cache(self):
        @cached()
        def func(x):
            self.call_count += 1
            return x * 2

        func(5)
        invalidate_cache(func, 5)
        func(5)

        assert self.call_count == 2


class TestCachedAsyncDecorator:
    def setup_method(self):
        clear_all_caches()
        self.call_count = 0

    def test_cached_async(self):
        @cached_async(ttl=60)
        async def async_func(x):
            self.call_count += 1
            return x * 2

        async def run():
            result1 = await async_func(5)
            result2 = await async_func(5)
            assert result1 == 10
            assert result2 == 10
            assert self.call_count == 1

        asyncio.run(run())

    def test_cached_async_different_args(self):
        @cached_async()
        async def async_func(x):
            self.call_count += 1
            return x

        async def run():
            await async_func(1)
            await async_func(2)
            await async_func(1)
            assert self.call_count == 2

        asyncio.run(run())

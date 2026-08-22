import asyncio
import time

from investkit_utils.cache.decorators import (
    _CACHE_MISS,
    _make_cache_key,
    cache_result,
    cached,
    cached_async,
    invalidate_cache,
)
from investkit_utils.cache.manager import (
    clear_all_caches,
    get_cache,
    get_memory_cache,
    set_default_cache,
)
from investkit_utils.cache.memory import MemoryCache


class TestMakeCacheKey:
    def test_basic_key(self):
        def my_func(x, y):
            pass

        key = _make_cache_key(my_func, (1, 2), {})
        assert "my_func" in key

    def test_key_with_kwargs(self):
        def my_func(x, y=10):
            pass

        key = _make_cache_key(my_func, (1,), {"y": 20})
        assert "my_func" in key

    def test_key_with_prefix(self):
        def my_func(x):
            pass

        key = _make_cache_key(my_func, (1,), {}, key_prefix="test")
        assert key.startswith("test:")

    def test_different_args_different_keys(self):
        def my_func(x):
            pass

        key1 = _make_cache_key(my_func, (1,), {})
        key2 = _make_cache_key(my_func, (2,), {})
        assert key1 != key2


class TestCachedDecorator:
    def setup_method(self):
        clear_all_caches()

    def test_caches_result(self):
        call_count = 0

        @cached(ttl=60)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert func(5) == 10
        assert func(5) == 10
        assert call_count == 1

    def test_different_args(self):
        call_count = 0

        @cached()
        def func(x):
            nonlocal call_count
            call_count += 1
            return x

        func(1)
        func(2)
        func(1)
        assert call_count == 2

    def test_with_key_prefix(self):
        @cached(key_prefix="test")
        def func(x):
            return x

        assert func(5) == 5

    def test_cache_info(self):
        @cached(ttl=300, key_prefix="myapp")
        def func(x):
            return x

        assert func._cache_info["ttl"] == 300
        assert func._cache_info["key_prefix"] == "myapp"


class TestCachedAsyncDecorator:
    def setup_method(self):
        clear_all_caches()

    def test_caches_result(self):
        call_count = 0

        @cached_async(ttl=60)
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        async def run():
            assert await func(5) == 10
            assert await func(5) == 10
            assert call_count == 1

        asyncio.run(run())

    def test_different_args(self):
        call_count = 0

        @cached_async()
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x

        async def run():
            await func(1)
            await func(2)
            await func(1)
            assert call_count == 2

        asyncio.run(run())


class TestCacheResult:
    def setup_method(self):
        clear_all_caches()

    def test_sync_function(self):
        call_count = 0

        @cache_result(ttl=60)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert func(5) == 10
        assert func(5) == 10
        assert call_count == 1

    def test_async_function(self):
        call_count = 0

        @cache_result(ttl=60)
        async def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        async def run():
            assert await func(5) == 10
            assert await func(5) == 10
            assert call_count == 1

        asyncio.run(run())

    def test_without_parentheses(self):
        @cache_result
        def func(x):
            return x

        assert func(5) == 5


class TestInvalidateCache:
    def setup_method(self):
        clear_all_caches()

    def test_invalidate(self):
        call_count = 0

        @cached()
        def func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        func(5)
        invalidate_cache(func, 5)
        func(5)
        assert call_count == 2


class TestCacheManager:
    def setup_method(self):
        clear_all_caches()

    def test_get_cache_default(self):
        cache = get_cache()
        assert isinstance(cache, MemoryCache)

    def test_get_cache_named(self):
        c1 = get_cache("test1")
        c2 = get_cache("test1")
        assert c1 is c2

    def test_get_memory_cache_with_ttl(self):
        cache = get_memory_cache(default_ttl=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_set_default_cache(self):
        custom = MemoryCache()
        set_default_cache(custom)
        assert get_cache() is custom

    def test_clear_all(self):
        c1 = get_cache("a")
        c2 = get_cache("b")
        c1.set("k1", "v1")
        c2.set("k2", "v2")
        clear_all_caches()
        assert c1.get("k1") is None
        assert c2.get("k2") is None

import time

from investkit_utils.cache.memory import CacheEntry, MemoryCache


class TestCacheEntry:
    def test_not_expired(self):
        entry = CacheEntry("value", ttl=60)
        assert entry.is_expired() is False

    def test_no_ttl(self):
        entry = CacheEntry("value")
        assert entry.is_expired() is False

    def test_expired(self):
        entry = CacheEntry("value", ttl=1)
        time.sleep(1.1)
        assert entry.is_expired() is True


class TestMemoryCache:
    def setup_method(self):
        self.cache = MemoryCache()

    def test_set_and_get(self):
        self.cache.set("key", "value")
        assert self.cache.get("key") == "value"

    def test_get_default(self):
        assert self.cache.get("missing") is None
        assert self.cache.get("missing", default="default") == "default"

    def test_delete(self):
        self.cache.set("key", "value")
        assert self.cache.delete("key") is True
        assert self.cache.get("key") is None

    def test_delete_nonexistent(self):
        assert self.cache.delete("nokey") is False

    def test_exists(self):
        self.cache.set("key", "value")
        assert self.cache.exists("key") is True
        assert self.cache.exists("nokey") is False

    def test_clear(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.clear()
        assert self.cache.get("a") is None
        assert self.cache.get("b") is None

    def test_keys(self):
        self.cache.set("k1", 1)
        self.cache.set("k2", 2)
        keys = self.cache.keys()
        assert "k1" in keys
        assert "k2" in keys

    def test_keys_pattern(self):
        self.cache.set("user:1", "a")
        self.cache.set("user:2", "b")
        self.cache.set("item:1", "c")
        keys = self.cache.keys("user:*")
        assert len(keys) == 2

    def test_ttl_expiration(self):
        self.cache.set("key", "value", ttl=1)
        assert self.cache.get("key") == "value"
        time.sleep(1.1)
        assert self.cache.get("key") is None

    def test_default_ttl(self):
        cache = MemoryCache(default_ttl=1)
        cache.set("key", "value")
        assert cache.get("key") == "value"
        time.sleep(1.1)
        assert cache.get("key") is None

    def test_get_or_set(self):
        value = self.cache.get_or_set("key", "default")
        assert value == "default"
        assert self.cache.get("key") == "default"

    def test_get_or_set_callable(self):
        value = self.cache.get_or_set("key", lambda: "computed")
        assert value == "computed"

    def test_get_or_set_existing(self):
        self.cache.set("key", "existing")
        value = self.cache.get_or_set("key", "default")
        assert value == "existing"

    def test_get_many(self):
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        result = self.cache.get_many(["k1", "k2", "k3"])
        assert result["k1"] == "v1"
        assert result["k2"] == "v2"
        assert result["k3"] is None

    def test_set_many(self):
        self.cache.set_many({"k1": "v1", "k2": "v2"})
        assert self.cache.get("k1") == "v1"
        assert self.cache.get("k2") == "v2"

    def test_delete_many(self):
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        count = self.cache.delete_many(["k1", "k2", "k3"])
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
        self.cache.set("k1", 1)
        self.cache.set("k2", 2)
        assert len(self.cache) == 2

    def test_contains(self):
        self.cache.set("key", "value")
        assert "key" in self.cache
        assert "nokey" not in self.cache

    def test_expired_entry_auto_cleanup(self):
        self.cache.set("k1", "v1", ttl=1)
        time.sleep(1.1)
        self.cache.set("k2", "v2")
        keys = self.cache.keys()
        assert "k1" not in keys
        assert "k2" in keys

    def test_various_types(self):
        self.cache.set("int", 42)
        self.cache.set("float", 3.14)
        self.cache.set("list", [1, 2, 3])
        self.cache.set("dict", {"a": 1})
        self.cache.set("none", None)
        assert self.cache.get("int") == 42
        assert self.cache.get("float") == 3.14
        assert self.cache.get("list") == [1, 2, 3]
        assert self.cache.get("dict") == {"a": 1}
        assert self.cache.get("none") is None

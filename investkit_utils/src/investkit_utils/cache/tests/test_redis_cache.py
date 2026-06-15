from unittest.mock import MagicMock

from investkit_utils.cache.redis_cache import REDIS_AVAILABLE, RedisCache, _RedisConnectionError


class TestRedisCacheUnavailable:
    def test_import_error_when_no_redis(self):
        if not REDIS_AVAILABLE:
            try:
                RedisCache()
            except ImportError as e:
                assert "Redis is not installed" in str(e)


class TestRedisCache:
    def _make_cache(self):
        mock_redis = MagicMock()
        cache = RedisCache.__new__(RedisCache)
        cache._client = mock_redis
        cache._prefix = "investkit:"
        return cache, mock_redis

    def test_make_key(self):
        cache, _ = self._make_cache()
        assert cache._make_key("test") == "investkit:test"

    def test_serialize_deserialize(self):
        cache, _ = self._make_cache()
        data = {"key": "value", "num": 42}
        serialized = cache._serialize(data)
        deserialized = cache._deserialize(serialized)
        assert deserialized == data

    def test_deserialize_none(self):
        cache, _ = self._make_cache()
        assert cache._deserialize(None) is None

    def test_get_existing_key(self):
        cache, mock_redis = self._make_cache()
        mock_redis.get.return_value = '{"name": "test"}'
        result = cache.get("test")
        assert result == {"name": "test"}
        mock_redis.get.assert_called_once_with("investkit:test")

    def test_get_missing_key(self):
        cache, mock_redis = self._make_cache()
        mock_redis.get.return_value = None
        assert cache.get("test") is None

    def test_get_with_default(self):
        cache, mock_redis = self._make_cache()
        mock_redis.get.return_value = None
        assert cache.get("test", default="fallback") == "fallback"

    def test_set_without_ttl(self):
        cache, mock_redis = self._make_cache()
        cache.set("test", {"a": 1})
        mock_redis.set.assert_called_once_with("investkit:test", '{"a": 1}')

    def test_set_with_ttl(self):
        cache, mock_redis = self._make_cache()
        cache.set("test", "value", ttl=60)
        mock_redis.setex.assert_called_once_with("investkit:test", 60, '"value"')

    def test_delete_existing(self):
        cache, mock_redis = self._make_cache()
        mock_redis.delete.return_value = 1
        assert cache.delete("test") is True

    def test_delete_missing(self):
        cache, mock_redis = self._make_cache()
        mock_redis.delete.return_value = 0
        assert cache.delete("test") is False

    def test_exists(self):
        cache, mock_redis = self._make_cache()
        mock_redis.exists.return_value = 1
        assert cache.exists("test") is True

    def test_exists_missing(self):
        cache, mock_redis = self._make_cache()
        mock_redis.exists.return_value = 0
        assert cache.exists("test") is False

    def test_clear(self):
        cache, mock_redis = self._make_cache()
        mock_redis.scan.side_effect = [(1, ["investkit:k1", "investkit:k2"]), (0, [])]
        cache.clear()
        mock_redis.delete.assert_called_once_with("investkit:k1", "investkit:k2")

    def test_keys_with_pattern(self):
        cache, mock_redis = self._make_cache()
        mock_redis.scan.side_effect = [(0, ["investkit:user:1", "investkit:user:2"])]
        result = cache.keys("user:*")
        assert result == ["user:1", "user:2"]

    def test_keys_without_pattern(self):
        cache, mock_redis = self._make_cache()
        mock_redis.scan.side_effect = [(0, ["investkit:k1"])]
        result = cache.keys()
        assert result == ["k1"]

    def test_incr(self):
        cache, mock_redis = self._make_cache()
        mock_redis.incrby.return_value = 5
        assert cache.incr("counter", 1) == 5
        mock_redis.incrby.assert_called_once_with("investkit:counter", 1)

    def test_decr(self):
        cache, mock_redis = self._make_cache()
        mock_redis.incrby.return_value = 3
        assert cache.decr("counter", 2) == 3
        mock_redis.incrby.assert_called_once_with("investkit:counter", -2)

    def test_ping_success(self):
        cache, mock_redis = self._make_cache()
        mock_redis.ping.return_value = True
        assert cache.ping() is True

    def test_ping_failure(self):
        cache, mock_redis = self._make_cache()
        mock_redis.ping.side_effect = _RedisConnectionError("connection failed")
        assert cache.ping() is False

    def test_close(self):
        cache, mock_redis = self._make_cache()
        cache.close()
        mock_redis.close.assert_called_once()

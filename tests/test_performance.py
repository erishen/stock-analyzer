"""
Tests for Performance Optimization Module.
性能优化模块测试
"""

import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from src.utils.performance import (
    CacheManager,
    DatabaseOptimizer,
    IncrementalUpdater,
    IndexInfo,
    ParallelProcessor,
    get_cache_manager,
    get_incremental_updater,
    optimize_database,
    run_parallel,
)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE stock_analysis (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            close REAL,
            high REAL,
            low REAL,
            volume REAL
        )
    """)

    test_data = [
        ("sh600000", "2024-01-01", 10.0, 10.5, 10.8, 9.9, 1000000),
        ("sh600000", "2024-01-02", 10.5, 10.3, 10.6, 10.2, 1200000),
        ("sh600000", "2024-01-03", 10.3, 10.8, 10.9, 10.2, 1100000),
        ("sh600001", "2024-01-01", 20.0, 20.5, 20.8, 19.9, 2000000),
        ("sh600001", "2024-01-02", 20.5, 20.3, 20.6, 20.2, 2200000),
    ]

    conn.executemany(
        "INSERT INTO stock_analysis (code, date, open, close, high, low, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


@pytest.fixture
def temp_cache_dir():
    """创建临时缓存目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestIndexInfo:
    """测试 IndexInfo 数据类"""

    def test_index_info_creation(self):
        """测试创建索引信息"""
        index = IndexInfo("idx_test", "test_table", ["col1", "col2"], unique=True)
        assert index.name == "idx_test"
        assert index.table == "test_table"
        assert index.columns == ["col1", "col2"]
        assert index.unique is True

    def test_index_info_default_unique(self):
        """测试默认非唯一索引"""
        index = IndexInfo("idx_test", "test_table", ["col1"])
        assert index.unique is False


class TestDatabaseOptimizer:
    """测试数据库优化器"""

    def test_connect_and_close(self, temp_db):
        """测试连接和关闭"""
        optimizer = DatabaseOptimizer(temp_db)
        optimizer.connect()
        assert optimizer.conn is not None
        optimizer.close()
        assert optimizer.conn is None

    def test_get_existing_indexes(self, temp_db):
        """测试获取现有索引"""
        optimizer = DatabaseOptimizer(temp_db)
        indexes = optimizer.get_existing_indexes()
        assert isinstance(indexes, list)

    def test_get_table_info(self, temp_db):
        """测试获取表信息"""
        optimizer = DatabaseOptimizer(temp_db)
        info = optimizer.get_table_info()

        assert "columns" in info
        assert "column_count" in info
        assert "row_count" in info
        assert "code_count" in info
        assert "date_count" in info
        assert info["row_count"] == 5
        assert info["code_count"] == 2
        assert info["date_count"] == 3

    def test_create_index(self, temp_db):
        """测试创建索引"""
        optimizer = DatabaseOptimizer(temp_db)

        index = IndexInfo("idx_code_test", "stock_analysis", ["code"])
        result = optimizer.create_index(index)
        assert result is True

        result = optimizer.create_index(index)
        assert result is False

    def test_drop_index(self, temp_db):
        """测试删除索引"""
        optimizer = DatabaseOptimizer(temp_db)

        index = IndexInfo("idx_to_drop", "stock_analysis", ["code"])
        optimizer.create_index(index)

        result = optimizer.drop_index("idx_to_drop")
        assert result is True

    def test_optimize(self, temp_db):
        """测试完整优化流程"""
        optimizer = DatabaseOptimizer(temp_db)
        result = optimizer.optimize()

        assert "table_info" in result
        assert "indexes_before" in result
        assert "indexes_created" in result
        assert "indexes_existing" in result
        assert "indexes_after" in result

    def test_query_performance_test(self, temp_db):
        """测试查询性能测试"""
        optimizer = DatabaseOptimizer(temp_db)
        elapsed = optimizer.query_performance_test("SELECT COUNT(*) FROM stock_analysis")
        assert elapsed >= 0

    def test_context_manager_style(self, temp_db):
        """测试上下文管理器风格使用"""
        optimizer = DatabaseOptimizer(temp_db)
        optimizer.connect()
        try:
            info = optimizer.get_table_info()
            assert info["row_count"] == 5
        finally:
            optimizer.close()


class TestParallelProcessor:
    """测试并行处理器"""

    def test_map_thread_pool(self):
        """测试线程池映射"""

        def square(x):
            return x * x

        processor = ParallelProcessor(max_workers=2, use_process=False)
        results = processor.map(square, [1, 2, 3, 4, 5])

        assert len(results) == 5
        assert set(results) == {1, 4, 9, 16, 25}

    def test_map_with_progress(self):
        """测试带进度回调的映射"""
        progress_calls = []

        def track_progress(current, total):
            progress_calls.append((current, total))

        def identity(x):
            return x

        processor = ParallelProcessor(max_workers=2)
        processor.map(identity, [1, 2, 3], progress_callback=track_progress)

        assert len(progress_calls) == 3

    def test_map_with_error(self):
        """测试处理错误"""

        def raise_error(x):
            if x == 2:
                raise ValueError("test error")
            return x

        processor = ParallelProcessor(max_workers=2)
        results = processor.map(raise_error, [1, 2, 3])

        assert len(results) == 3
        assert 1 in results
        assert 3 in results
        assert any("error" in str(r) for r in results if isinstance(r, dict))

    def test_starmap(self):
        """测试星号映射"""

        def add(a, b):
            return a + b

        processor = ParallelProcessor(max_workers=2)
        results = processor.starmap(add, [(1, 2), (3, 4), (5, 6)])

        assert set(results) == {3, 7, 11}


class TestCacheManager:
    """测试缓存管理器"""

    def test_set_and_get(self, temp_cache_dir):
        """测试设置和获取缓存"""
        cache = CacheManager(cache_dir=temp_cache_dir, ttl=3600)

        cache.set("test_key", {"data": "test_value"})
        result = cache.get("test_key")

        assert result == {"data": "test_value"}

    def test_get_nonexistent(self, temp_cache_dir):
        """测试获取不存在的缓存"""
        cache = CacheManager(cache_dir=temp_cache_dir)
        result = cache.get("nonexistent_key")
        assert result is None

    def test_delete(self, temp_cache_dir):
        """测试删除缓存"""
        cache = CacheManager(cache_dir=temp_cache_dir)

        cache.set("to_delete", "value")
        assert cache.get("to_delete") == "value"

        cache.delete("to_delete")
        assert cache.get("to_delete") is None

    def test_clear(self, temp_cache_dir):
        """测试清空缓存"""
        cache = CacheManager(cache_dir=temp_cache_dir)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cached_decorator(self, temp_cache_dir):
        """测试缓存装饰器"""
        cache = CacheManager(cache_dir=temp_cache_dir, ttl=3600)
        call_count = 0

        @cache.cached
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    def test_ttl_expiration(self, temp_cache_dir):
        """测试 TTL 过期"""
        cache = CacheManager(cache_dir=temp_cache_dir, ttl=0)

        cache.set("expiring_key", "value")
        time.sleep(0.1)

        result = cache.get("expiring_key")
        assert result is None

    def test_get_cache_key(self, temp_cache_dir):
        """测试缓存键生成"""
        cache = CacheManager(cache_dir=temp_cache_dir)

        def test_func(a, b):
            return a + b

        key1 = cache._get_cache_key(test_func, 1, 2)
        key2 = cache._get_cache_key(test_func, 1, 2)
        key3 = cache._get_cache_key(test_func, 2, 3)

        assert key1 == key2
        assert key1 != key3


class TestIncrementalUpdater:
    """测试增量更新器"""

    def test_connect_and_close(self, temp_db):
        """测试连接和关闭"""
        updater = IncrementalUpdater(temp_db)
        updater.connect()
        assert updater.conn is not None
        updater.close()
        assert updater.conn is None

    def test_get_last_date(self, temp_db):
        """测试获取最后日期"""
        updater = IncrementalUpdater(temp_db)
        last_date = updater.get_last_date()
        assert last_date == "2024-01-03"

    def test_get_last_date_for_code(self, temp_db):
        """测试获取指定股票的最后日期"""
        updater = IncrementalUpdater(temp_db)
        last_date = updater.get_last_date("sh600001")
        assert last_date == "2024-01-02"

    def test_get_missing_dates(self, temp_db):
        """测试获取缺失日期"""
        updater = IncrementalUpdater(temp_db)
        missing = updater.get_missing_dates("sh600001", "2024-01-01", "2024-01-05")

        assert "2024-01-03" in missing
        assert "2024-01-05" in missing
        assert "2024-01-01" not in missing
        assert "2024-01-02" not in missing

    def test_get_stocks_needing_update(self, temp_db):
        """测试获取需要更新的股票"""
        updater = IncrementalUpdater(temp_db)
        stocks = updater.get_stocks_needing_update("2024-01-05")

        assert "sh600000" in stocks
        assert "sh600001" in stocks

    def test_get_update_stats(self, temp_db):
        """测试获取更新统计"""
        updater = IncrementalUpdater(temp_db)
        stats = updater.get_update_stats()

        assert stats["max_date"] == "2024-01-03"
        assert stats["min_date"] == "2024-01-01"
        assert stats["total_stocks"] == 2


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_optimize_database(self, temp_db):
        """测试数据库优化便捷函数"""
        result = optimize_database(temp_db)

        assert "table_info" in result
        assert "indexes_created" in result

    def test_run_parallel(self):
        """测试并行执行便捷函数"""

        def double(x):
            return x * 2

        results = run_parallel(double, [1, 2, 3, 4, 5], max_workers=2)

        assert len(results) == 5
        assert set(results) == {2, 4, 6, 8, 10}

    def test_get_cache_manager(self, temp_cache_dir):
        """测试获取缓存管理器"""
        cache = get_cache_manager(cache_dir=temp_cache_dir, ttl=7200)

        assert isinstance(cache, CacheManager)
        assert cache.ttl == 7200

    def test_get_incremental_updater(self, temp_db):
        """测试获取增量更新器"""
        updater = get_incremental_updater(temp_db)

        assert isinstance(updater, IncrementalUpdater)
        assert updater.db_path == temp_db

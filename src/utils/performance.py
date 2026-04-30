"""
Performance Optimization Module for Stock Analyzer.
性能优化模块

功能:
- 数据库索引优化
- 并行计算 (多进程处理)
- 缓存机制 (结果缓存)
- 增量更新 (只处理新数据)
"""

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any


@dataclass
class IndexInfo:
    """索引信息"""

    name: str
    table: str
    columns: list[str]
    unique: bool = False


class DatabaseOptimizer:
    """数据库优化器"""

    RECOMMENDED_INDEXES = [
        IndexInfo("idx_code", "stock_analysis", ["code"]),
        IndexInfo("idx_date", "stock_analysis", ["date"]),
        IndexInfo("idx_code_date", "stock_analysis", ["code", "date"], unique=True),
        IndexInfo("idx_date_code", "stock_analysis", ["date", "code"]),
    ]

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(str(self.db_path))

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_existing_indexes(self) -> list[str]:
        """获取现有索引"""
        if not self.conn:
            self.connect()

        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        return [row[0] for row in cursor.fetchall()]

    def get_table_info(self, table: str = "stock_analysis") -> dict:
        """获取表信息"""
        if not self.conn:
            self.connect()

        cursor = self.conn.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()

        cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]

        cursor = self.conn.execute(f"SELECT COUNT(DISTINCT code) FROM {table}")
        code_count = cursor.fetchone()[0]

        cursor = self.conn.execute(f"SELECT COUNT(DISTINCT date) FROM {table}")
        date_count = cursor.fetchone()[0]

        return {
            "columns": [col[1] for col in columns],
            "column_count": len(columns),
            "row_count": row_count,
            "code_count": code_count,
            "date_count": date_count,
        }

    def create_index(self, index: IndexInfo) -> bool:
        """创建索引"""
        if not self.conn:
            self.connect()

        existing = self.get_existing_indexes()
        if index.name in existing:
            return False

        unique_str = "UNIQUE" if index.unique else ""
        columns_str = ", ".join(index.columns)

        sql = f"CREATE {unique_str} INDEX {index.name} ON {index.table} ({columns_str})"

        try:
            self.conn.execute(sql)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"创建索引失败: {e}")
            return False

    def drop_index(self, index_name: str) -> bool:
        """删除索引"""
        if not self.conn:
            self.connect()

        try:
            self.conn.execute(f"DROP INDEX IF EXISTS {index_name}")
            self.conn.commit()
            return True
        except Exception:
            return False

    def optimize(self) -> dict:
        """优化数据库"""
        if not self.conn:
            self.connect()

        results = {
            "table_info": self.get_table_info(),
            "indexes_before": self.get_existing_indexes(),
            "indexes_created": [],
            "indexes_existing": [],
        }

        for index in self.RECOMMENDED_INDEXES:
            if self.create_index(index):
                results["indexes_created"].append(index.name)
            else:
                results["indexes_existing"].append(index.name)

        self.conn.execute("ANALYZE")
        self.conn.commit()

        self.conn.execute("VACUUM")
        self.conn.commit()

        results["indexes_after"] = self.get_existing_indexes()

        return results

    def query_performance_test(self, query: str) -> float:
        """查询性能测试"""
        if not self.conn:
            self.connect()

        start = time.time()
        self.conn.execute(query)
        return time.time() - start


class ParallelProcessor:
    """并行处理器"""

    def __init__(self, max_workers: int | None = None, use_process: bool = False):
        self.max_workers = max_workers
        self.use_process = use_process

    def map(
        self,
        func: Callable,
        items: list[Any],
        progress_callback: Callable | None = None,
    ) -> list[Any]:
        """并行映射"""
        executor_class = ProcessPoolExecutor if self.use_process else ThreadPoolExecutor

        results = []
        with executor_class(max_workers=self.max_workers) as executor:
            futures = {executor.submit(func, item): item for item in items}

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    if progress_callback:
                        progress_callback(len(results), len(items))
                except Exception as e:
                    results.append({"error": str(e)})

        return results

    def starmap(
        self,
        func: Callable,
        items: list[tuple],
        progress_callback: Callable | None = None,
    ) -> list[Any]:
        """并行星号映射"""
        executor_class = ProcessPoolExecutor if self.use_process else ThreadPoolExecutor

        results = []
        with executor_class(max_workers=self.max_workers) as executor:
            futures = {executor.submit(func, *item): item for item in items}

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    if progress_callback:
                        progress_callback(len(results), len(items))
                except Exception as e:
                    results.append({"error": str(e)})

        return results


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_dir: Path | None = None, ttl: int = 3600):
        self.cache_dir = cache_dir or Path(__file__).parent.parent.parent / "output" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._memory_cache: dict[str, tuple[Any, float]] = {}

    def _get_cache_key(self, func: Callable, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = {
            "func": func.__name__,
            "args": str(args),
            "kwargs": str(sorted(kwargs.items())),
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Any | None:
        """获取缓存"""
        if key in self._memory_cache:
            value, timestamp = self._memory_cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._memory_cache[key]

        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    data = json.load(f)
                if time.time() - data["timestamp"] < self.ttl:
                    self._memory_cache[key] = (data["value"], data["timestamp"])
                    return data["value"]
                cache_path.unlink()
            except Exception:
                pass

        return None

    def set(self, key: str, value: Any):
        """设置缓存"""
        timestamp = time.time()
        self._memory_cache[key] = (value, timestamp)

        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"value": value, "timestamp": timestamp}, f)
        except Exception:
            pass

    def delete(self, key: str):
        """删除缓存"""
        if key in self._memory_cache:
            del self._memory_cache[key]

        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()

    def clear(self):
        """清空缓存"""
        self._memory_cache.clear()

        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def cached(self, func: Callable) -> Callable:
        """缓存装饰器"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = self._get_cache_key(func, *args, **kwargs)
            cached_value = self.get(key)
            if cached_value is not None:
                return cached_value

            result = func(*args, **kwargs)
            self.set(key, result)
            return result

        return wrapper


class IncrementalUpdater:
    """增量更新器"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(str(self.db_path))

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_last_date(self, code: str | None = None) -> str | None:
        """获取最后日期"""
        if not self.conn:
            self.connect()

        if code:
            cursor = self.conn.execute("SELECT MAX(date) FROM stock_analysis WHERE code = ?", (code,))
        else:
            cursor = self.conn.execute("SELECT MAX(date) FROM stock_analysis")

        result = cursor.fetchone()
        return result[0] if result else None

    def get_missing_dates(self, code: str, start_date: str, end_date: str) -> list[str]:
        """获取缺失日期"""
        if not self.conn:
            self.connect()

        cursor = self.conn.execute(
            """
            SELECT date FROM stock_analysis
            WHERE code = ? AND date BETWEEN ? AND ?
            ORDER BY date
            """,
            (code, start_date, end_date),
        )
        existing_dates = {row[0] for row in cursor.fetchall()}

        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        all_dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                date_str = current.strftime("%Y-%m-%d")
                if date_str not in existing_dates:
                    all_dates.append(date_str)
            current += timedelta(days=1)

        return all_dates

    def get_stocks_needing_update(self, reference_date: str) -> list[str]:
        """获取需要更新的股票"""
        if not self.conn:
            self.connect()

        cursor = self.conn.execute(
            """
            SELECT code FROM stock_analysis
            GROUP BY code
            HAVING MAX(date) < ?
            """,
            (reference_date,),
        )
        return [row[0] for row in cursor.fetchall()]

    def get_update_stats(self) -> dict:
        """获取更新统计"""
        if not self.conn:
            self.connect()

        cursor = self.conn.execute("SELECT MAX(date) FROM stock_analysis")
        max_date = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT MIN(date) FROM stock_analysis")
        min_date = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(DISTINCT code) FROM stock_analysis")
        total_stocks = cursor.fetchone()[0]

        cursor = self.conn.execute(
            """
            SELECT code, MAX(date) as last_date
            FROM stock_analysis
            GROUP BY code
            ORDER BY last_date ASC
            LIMIT 10
            """
        )
        outdated_stocks = cursor.fetchall()

        return {
            "max_date": max_date,
            "min_date": min_date,
            "total_stocks": total_stocks,
            "outdated_stocks": outdated_stocks,
        }


def optimize_database(db_path: Path) -> dict:
    """优化数据库"""
    optimizer = DatabaseOptimizer(db_path)
    optimizer.connect()
    result = optimizer.optimize()
    optimizer.close()
    return result


def run_parallel(
    func: Callable,
    items: list[Any],
    max_workers: int | None = None,
    use_process: bool = False,
) -> list[Any]:
    """并行执行"""
    processor = ParallelProcessor(max_workers=max_workers, use_process=use_process)
    return processor.map(func, items)


def get_cache_manager(cache_dir: Path | None = None, ttl: int = 3600) -> CacheManager:
    """获取缓存管理器"""
    return CacheManager(cache_dir=cache_dir, ttl=ttl)


def get_incremental_updater(db_path: Path) -> IncrementalUpdater:
    """获取增量更新器"""
    return IncrementalUpdater(db_path)

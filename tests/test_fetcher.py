"""
Tests for Stock Data Fetcher Module.
股票数据获取模块测试
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.data.fetcher import (
    FetchResult,
    StockDataFetcher,
    run_fetch,
)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    db_path.unlink(missing_ok=True)


class TestFetchResult:
    """测试 FetchResult 数据类"""

    def test_create_result(self):
        """测试创建结果"""
        result = FetchResult(success=True, stocks_fetched=10, total_records=1000)
        assert result.success is True
        assert result.stocks_fetched == 10
        assert result.total_records == 1000
        assert result.errors == []

    def test_result_with_errors(self):
        """测试带错误的结果"""
        result = FetchResult(
            success=False,
            errors=["error1", "error2"],
            message="获取失败",
        )
        assert result.success is False
        assert len(result.errors) == 2
        assert result.message == "获取失败"

    def test_result_to_dict(self):
        """测试转换为字典"""
        result = FetchResult(
            success=True,
            stocks_fetched=5,
            total_records=500,
            errors=[],
            message="成功",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["stocks_fetched"] == 5
        assert d["total_records"] == 500


class TestStockDataFetcher:
    """测试股票数据获取器"""

    def test_init(self, temp_db):
        """测试初始化"""
        fetcher = StockDataFetcher(temp_db)
        assert fetcher.db_path == temp_db

    def test_connect_and_close(self, temp_db):
        """测试连接和关闭"""
        fetcher = StockDataFetcher(temp_db)
        fetcher.connect()
        assert fetcher._conn is not None
        fetcher.close()
        assert fetcher._conn is None

    def test_create_tables(self, temp_db):
        """测试创建表"""
        fetcher = StockDataFetcher(temp_db)
        fetcher.create_tables()

        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_klines'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_save_klines(self, temp_db):
        """测试保存 K 线数据"""
        fetcher = StockDataFetcher(temp_db)
        fetcher.create_tables()

        records = [
            {
                "code": "000001",
                "date": "2024-01-01",
                "open": 10.0,
                "close": 10.5,
                "high": 10.8,
                "low": 9.9,
                "volume": 1000000,
                "amount": 10500000,
                "amplitude": 9.0,
                "change_percent": 5.0,
                "change_amount": 0.5,
                "turnover_rate": 1.5,
            },
            {
                "code": "000001",
                "date": "2024-01-02",
                "open": 10.5,
                "close": 10.3,
                "high": 10.6,
                "low": 10.2,
                "volume": 1200000,
                "amount": 12360000,
                "amplitude": 3.8,
                "change_percent": -1.9,
                "change_amount": -0.2,
                "turnover_rate": 1.8,
            },
        ]

        fetcher.save_klines(records)

        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT COUNT(*) FROM stock_klines")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 2

    def test_get_stats(self, temp_db):
        """测试获取统计信息"""
        fetcher = StockDataFetcher(temp_db)
        fetcher.create_tables()

        records = [
            {
                "code": "000001",
                "date": "2024-01-01",
                "open": 10.0,
                "close": 10.5,
                "high": 10.8,
                "low": 9.9,
                "volume": 1000000,
                "amount": 10500000,
                "amplitude": 9.0,
                "change_percent": 5.0,
                "change_amount": 0.5,
                "turnover_rate": 1.5,
            },
            {
                "code": "000002",
                "date": "2024-01-02",
                "open": 20.0,
                "close": 20.5,
                "high": 20.8,
                "low": 19.9,
                "volume": 2000000,
                "amount": 41000000,
                "amplitude": 4.5,
                "change_percent": 2.5,
                "change_amount": 0.5,
                "turnover_rate": 2.0,
            },
        ]

        fetcher.save_klines(records)

        stats = fetcher.get_stats()
        assert stats["stock_count"] == 2
        assert stats["total_records"] == 2
        assert stats["min_date"] == "2024-01-01"
        assert stats["max_date"] == "2024-01-02"

    def test_save_klines_upsert(self, temp_db):
        """测试重复数据更新"""
        fetcher = StockDataFetcher(temp_db)
        fetcher.create_tables()

        record1 = {
            "code": "000001",
            "date": "2024-01-01",
            "open": 10.0,
            "close": 10.5,
            "high": 10.8,
            "low": 9.9,
            "volume": 1000000,
            "amount": 10500000,
            "amplitude": 9.0,
            "change_percent": 5.0,
            "change_amount": 0.5,
            "turnover_rate": 1.5,
        }

        fetcher.save_klines([record1])

        record2 = record1.copy()
        record2["close"] = 11.0
        fetcher.save_klines([record2])

        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT COUNT(*) FROM stock_klines")
        count = cursor.fetchone()[0]
        cursor = conn.execute("SELECT close FROM stock_klines WHERE code='000001'")
        close = cursor.fetchone()[0]
        conn.close()

        assert count == 1
        assert close == 11.0

    @patch("src.data.fetcher.StockDataFetcher.akshare")
    def test_get_stock_list(self, mock_akshare, temp_db):
        """测试获取股票列表"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {
                "代码": ["000001", "000002", "600519"],
                "名称": ["平安银行", "万科A", "贵州茅台"],
            }
        )
        mock_akshare.stock_zh_a_spot_em.return_value = mock_df

        fetcher = StockDataFetcher(temp_db)
        stocks = fetcher.get_stock_list()

        assert len(stocks) == 3
        assert stocks[0]["code"] == "000001"
        assert stocks[0]["name"] == "平安银行"

    @patch("src.data.fetcher.StockDataFetcher.akshare")
    def test_fetch_stock_klines(self, mock_akshare, temp_db):
        """测试获取 K 线数据"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {
                "日期": ["2024-01-01", "2024-01-02"],
                "开盘": [10.0, 10.5],
                "收盘": [10.5, 10.3],
                "最高": [10.8, 10.6],
                "最低": [9.9, 10.2],
                "成交量": [1000000, 1200000],
                "成交额": [10500000, 12360000],
                "振幅": [9.0, 3.8],
                "涨跌幅": [5.0, -1.9],
                "涨跌额": [0.5, -0.2],
                "换手率": [1.5, 1.8],
            }
        )
        mock_akshare.stock_zh_a_hist.return_value = mock_df

        fetcher = StockDataFetcher(temp_db)
        records = fetcher.fetch_stock_klines("000001")

        assert len(records) == 2
        assert records[0]["code"] == "000001"
        assert records[0]["open"] == 10.0

    def test_fetch_stock_klines_empty_result(self, temp_db):
        """测试获取 K 线数据返回空结果（当 akshare 未安装时）"""
        from unittest.mock import PropertyMock

        fetcher = StockDataFetcher(temp_db)

        with patch.object(
            StockDataFetcher,
            "akshare",
            new_callable=PropertyMock,
            side_effect=ImportError("akshare not installed"),
        ):
            records = fetcher.fetch_stock_klines("000001")
            assert records == []


class TestRunFetch:
    """测试运行获取"""

    @patch("src.data.fetcher.StockDataFetcher.fetch_stocks")
    @patch("src.data.fetcher.StockDataFetcher.get_stats")
    def test_run_fetch_with_codes(self, mock_stats, mock_fetch, temp_db):
        """测试指定股票获取"""
        mock_fetch.return_value = FetchResult(
            success=True,
            stocks_fetched=2,
            total_records=100,
        )
        mock_stats.return_value = {
            "stock_count": 2,
            "total_records": 100,
            "min_date": "2024-01-01",
            "max_date": "2024-01-31",
        }

        with patch("src.data.fetcher.Path") as mock_path:
            mock_path.return_value = temp_db
            result = run_fetch(db_path=temp_db, codes=["000001", "600519"])

        assert result.success is True

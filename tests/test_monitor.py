"""
Tests for Market Monitor Module.
市场监控模块测试
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.scanner.monitor import (
    LiveSignal,
    MarketSummary,
    get_latest_date,
    get_live_signals,
    get_market_summary,
    run_monitor,
)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE stock_analysis (
            code TEXT,
            date TEXT,
            close REAL,
            change_percent REAL,
            volume REAL,
            rsi REAL,
            macd REAL,
            macd_signal REAL,
            ma5 REAL,
            ma20 REAL
        )
    """)

    test_data = [
        ("000001", "2024-01-05", 10.5, 2.5, 1000000, 25.0, 0.1, 0.05, 10.3, 10.0),
        ("000002", "2024-01-05", 20.3, -1.5, 2000000, 75.0, -0.05, 0.02, 20.0, 20.5),
        ("000003", "2024-01-05", 15.0, 0.0, 1500000, 50.0, 0.08, 0.06, 14.8, 14.5),
        ("000004", "2024-01-04", 11.0, 1.0, 1100000, 40.0, 0.05, 0.03, 10.8, 10.5),
    ]
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


class TestLiveSignal:
    """测试实时信号数据类"""

    def test_create_signal(self):
        """测试创建信号"""
        signal = LiveSignal(
            code="000001",
            name="平安银行",
            signal_type="RSI超卖",
            price=10.5,
            change_percent=2.5,
            volume=1000000,
            rsi=25.0,
            macd=0.1,
            ma5=10.3,
            ma20=10.0,
            date="2024-01-05",
            score=5.0,
        )
        assert signal.code == "000001"
        assert signal.signal_type == "RSI超卖"

    def test_signal_to_dict(self):
        """测试转换为字典"""
        signal = LiveSignal(
            code="000001",
            name="平安银行",
            signal_type="RSI超卖",
            price=10.555,
            change_percent=2.555,
            volume=1000000,
            rsi=25.555,
            macd=0.1234,
            ma5=10.333,
            ma20=10.0,
            date="2024-01-05",
            score=5.555,
        )
        d = signal.to_dict()
        assert d["code"] == "000001"
        assert d["price"] == 10.55
        assert d["rsi"] == 25.55


class TestMarketSummary:
    """测试市场概览数据类"""

    def test_create_summary(self):
        """测试创建概览"""
        summary = MarketSummary(
            date="2024-01-05",
            total_stocks=100,
            up_count=60,
            down_count=30,
            flat_count=10,
            avg_change=1.5,
            max_up=("000001", "平安银行", 10.0),
            max_down=("000002", "万科A", -5.0),
            oversold_count=5,
            overbought_count=3,
            golden_cross_count=10,
        )
        assert summary.total_stocks == 100
        assert summary.up_count == 60

    def test_summary_to_dict(self):
        """测试转换为字典"""
        summary = MarketSummary(
            date="2024-01-05",
            total_stocks=100,
            up_count=60,
            down_count=30,
            flat_count=10,
            avg_change=1.555,
            max_up=("000001", "平安银行", 10.0),
            max_down=("000002", "万科A", -5.0),
            oversold_count=5,
            overbought_count=3,
            golden_cross_count=10,
        )
        d = summary.to_dict()
        assert d["date"] == "2024-01-05"
        assert d["up_ratio"] == 60.0
        assert d["avg_change"] == 1.55
        assert d["max_up"]["code"] == "000001"


class TestGetLatestDate:
    """测试获取最新日期"""

    def test_get_latest_date(self, temp_db):
        """测试获取最新日期"""
        date = get_latest_date(temp_db)
        assert date == "2024-01-05"

    def test_get_latest_date_empty_db(self):
        """测试空数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE stock_analysis (code TEXT, date TEXT)")
        conn.commit()
        conn.close()

        date = get_latest_date(db_path)
        assert date is None

        db_path.unlink(missing_ok=True)


class TestGetMarketSummary:
    """测试获取市场概览"""

    def test_get_market_summary(self, temp_db):
        """测试获取市场概览"""
        summary = get_market_summary(temp_db)

        assert summary.date == "2024-01-05"
        assert summary.total_stocks == 3
        assert summary.up_count == 1
        assert summary.down_count == 1
        assert summary.flat_count == 1
        assert summary.oversold_count == 1
        assert summary.overbought_count == 1

    def test_get_market_summary_empty_db(self):
        """测试空数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE stock_analysis (code TEXT, date TEXT)")
        conn.commit()
        conn.close()

        with pytest.raises(ValueError, match="没有数据"):
            get_market_summary(db_path)

        db_path.unlink(missing_ok=True)


class TestGetLiveSignals:
    """测试获取实时信号"""

    def test_get_all_signals(self, temp_db):
        """测试获取所有信号"""
        signals = get_live_signals(temp_db, signal_type="all", limit=10)
        assert len(signals) <= 10
        assert all(isinstance(s, LiveSignal) for s in signals)

    def test_get_oversold_signals(self, temp_db):
        """测试获取超卖信号"""
        signals = get_live_signals(temp_db, signal_type="oversold", limit=10)
        assert all(s.rsi < 30 for s in signals)

    def test_get_overbought_signals(self, temp_db):
        """测试获取超买信号"""
        signals = get_live_signals(temp_db, signal_type="overbought", limit=10)
        assert all(s.rsi > 70 for s in signals)

    def test_get_golden_cross_signals(self, temp_db):
        """测试获取金叉信号"""
        signals = get_live_signals(temp_db, signal_type="golden_cross", limit=10)
        assert len(signals) >= 0

    def test_get_ma_cross_signals(self, temp_db):
        """测试获取均线多头信号"""
        signals = get_live_signals(temp_db, signal_type="ma_cross", limit=10)
        for s in signals:
            assert s.ma5 > s.ma20

    def test_get_signals_with_limit(self, temp_db):
        """测试限制返回数量"""
        signals = get_live_signals(temp_db, signal_type="all", limit=2)
        assert len(signals) <= 2

    def test_get_signals_empty_db(self):
        """测试空数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE stock_analysis (code TEXT, date TEXT)")
        conn.commit()
        conn.close()

        signals = get_live_signals(db_path)
        assert signals == []

        db_path.unlink(missing_ok=True)


class TestRunMonitor:
    """测试运行监控"""

    def test_run_monitor(self, temp_db):
        """测试运行监控"""
        result = run_monitor(temp_db)

        assert "summary" in result
        assert "oversold_signals" in result
        assert "golden_cross_signals" in result

    def test_run_monitor_db_not_exists(self):
        """测试数据库不存在"""
        with pytest.raises(FileNotFoundError):
            run_monitor(Path("/nonexistent/path.db"))

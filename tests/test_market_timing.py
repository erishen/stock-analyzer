"""
Tests for Market Timing Module.
大盘择时模块测试
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.strategy.market_timing import (
    MarketIndicator,
    MarketState,
    MarketTiming,
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
            high REAL,
            low REAL,
            open REAL,
            volume REAL,
            change_percent REAL,
            macd REAL,
            rsi REAL,
            ma5 REAL,
            ma10 REAL,
            ma20 REAL,
            boll_upper REAL,
            boll_lower REAL
        )
    """)

    test_data = []
    for i in range(50):
        base_price = 10.0 + i * 0.1
        test_data.append(
            (
                f"00000{i % 3 + 1:02d}",
                f"2024-01-{(i % 28) + 1:02d}",
                base_price,
                base_price + 0.5,
                base_price - 0.3,
                base_price,
                1000000 + i * 10000,
                (i % 10) - 5 + 0.5,
                0.1 + i * 0.001,
                40 + (i % 40),
                base_price - 0.2,
                base_price - 0.3,
                base_price - 0.5,
                base_price + 0.8,
                base_price - 0.8,
            )
        )
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


class TestMarketState:
    """测试市场状态枚举"""

    def test_market_states(self):
        """测试市场状态"""
        assert MarketState.BULL.value == "bull"
        assert MarketState.BEAR.value == "bear"
        assert MarketState.SIDEWAYS.value == "sideways"
        assert MarketState.UNKNOWN.value == "unknown"


class TestMarketIndicator:
    """测试市场指标"""

    def test_create_indicator(self):
        """测试创建指标"""
        indicator = MarketIndicator(
            date="2024-01-01",
            state=MarketState.BULL,
            score=75.0,
            ma_trend="up",
            rsi_level="normal",
            volatility="low",
            breadth=0.6,
            signal="买入",
        )
        assert indicator.date == "2024-01-01"
        assert indicator.state == MarketState.BULL
        assert indicator.score == 75.0

    def test_indicator_to_dict(self):
        """测试转换为字典"""
        indicator = MarketIndicator(
            date="2024-01-01",
            state=MarketState.BULL,
            score=75.555,
            ma_trend="up",
            rsi_level="normal",
            volatility="low",
            breadth=0.655,
            signal="买入",
        )
        d = indicator.to_dict()
        assert d["date"] == "2024-01-01"
        assert d["state"] == "bull"
        assert d["score"] == 75.56
        assert d["breadth"] == 65.5


class TestMarketTiming:
    """测试大盘择时器"""

    def test_init(self):
        """测试初始化"""
        timing = MarketTiming()
        assert timing.ma_short == 5
        assert timing.ma_long == 20
        assert timing.rsi_oversold == 30
        assert timing.rsi_overbought == 70

    def test_init_with_params(self):
        """测试带参数初始化"""
        timing = MarketTiming(
            ma_short=10,
            ma_long=30,
            rsi_oversold=25,
            rsi_overbought=75,
            volatility_threshold=0.03,
        )
        assert timing.ma_short == 10
        assert timing.ma_long == 30
        assert timing.rsi_oversold == 25
        assert timing.rsi_overbought == 75
        assert timing.volatility_threshold == 0.03

    def test_analyze_market(self, temp_db):
        """测试分析市场"""
        timing = MarketTiming()

        result = timing.analyze_market(temp_db)

        assert isinstance(result, MarketIndicator)
        assert result.date is not None
        assert result.state in [MarketState.BULL, MarketState.BEAR, MarketState.SIDEWAYS, MarketState.UNKNOWN]

"""
Tests for Strategy Backtester Module.
策略回测模块测试
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.strategy.backtest import (
    BacktestResult,
    MeanReversionStrategy,
    MomentumStrategy,
    Trade,
    TrendFollowingStrategy,
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
            macd_signal REAL,
            rsi REAL,
            ma5 REAL,
            ma10 REAL,
            ma20 REAL,
            boll_upper REAL,
            boll_lower REAL
        )
    """)

    test_data = []
    for i in range(100):
        base_price = 10.0 + i * 0.05
        test_data.append(
            (
                "000001",
                f"2024-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}",
                base_price,
                base_price + 0.5,
                base_price - 0.3,
                base_price - 0.1,
                1000000 + i * 10000,
                (i % 10) - 5 + 0.5,
                0.1 + i * 0.001,
                0.08 + i * 0.001,
                40 + (i % 40),
                base_price - 0.2,
                base_price - 0.3,
                base_price - 0.5,
                base_price + 0.8,
                base_price - 0.8,
            )
        )
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


class TestTrade:
    """测试交易记录"""

    def test_create_trade(self):
        """测试创建交易"""
        trade = Trade(
            code="000001",
            name="平安银行",
            entry_date="2024-01-01",
            entry_price=10.5,
            exit_date="2024-01-05",
            exit_price=11.0,
            shares=1000,
            profit=500.0,
            profit_percent=4.76,
            holding_days=5,
        )
        assert trade.code == "000001"
        assert trade.entry_price == 10.5
        assert trade.profit == 500.0

    def test_trade_to_dict(self):
        """测试转换为字典"""
        trade = Trade(
            code="000001",
            name="平安银行",
            entry_date="2024-01-01",
            entry_price=10.5,
            exit_date="2024-01-05",
            exit_price=11.1,
            shares=1000,
            profit=567.0,
            profit_percent=5.38,
            holding_days=5,
            signal="MACD金叉",
            commission=5.0,
            stamp_tax=11.12,
            total_cost=16.12,
        )
        d = trade.to_dict()
        assert d["code"] == "000001"
        assert d["entry_price"] == 10.5
        assert d["exit_price"] == 11.1


class TestBacktestResult:
    """测试回测结果"""

    def test_create_result(self):
        """测试创建结果"""
        result = BacktestResult(
            strategy_name="动量策略",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            final_capital=120000,
            total_return=0.2,
            annualized_return=0.2,
            max_drawdown=0.1,
            win_rate=0.6,
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            avg_profit=0.05,
            avg_loss=0.03,
            profit_factor=1.67,
            sharpe_ratio=1.5,
            trades=[],
            equity_curve=[],
        )
        assert result.strategy_name == "动量策略"
        assert result.total_return == 0.2

    def test_result_to_dict(self):
        """测试转换为字典"""
        result = BacktestResult(
            strategy_name="动量策略",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            final_capital=120000,
            total_return=0.2,
            annualized_return=0.2,
            max_drawdown=0.1,
            win_rate=0.6,
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            avg_profit=0.05,
            avg_loss=0.03,
            profit_factor=1.67,
            sharpe_ratio=1.5,
            trades=[],
            equity_curve=[],
        )
        d = result.to_dict()
        assert d["strategy_name"] == "动量策略"
        assert d["total_return"] == 20.0


class TestMomentumStrategy:
    """测试动量策略"""

    def test_init(self):
        """测试初始化"""
        strategy = MomentumStrategy(lookback_days=20, top_n=10)
        assert strategy.lookback_days == 20
        assert strategy.top_n == 10

    def test_default_params(self):
        """测试默认参数"""
        strategy = MomentumStrategy()
        assert strategy.lookback_days == 20
        assert strategy.top_n == 10


class TestMeanReversionStrategy:
    """测试均值回归策略"""

    def test_init(self):
        """测试初始化"""
        strategy = MeanReversionStrategy(rsi_oversold=30, holding_days=10)
        assert strategy.rsi_oversold == 30
        assert strategy.holding_days == 10

    def test_default_params(self):
        """测试默认参数"""
        strategy = MeanReversionStrategy()
        assert strategy.rsi_oversold == 30
        assert strategy.holding_days == 5


class TestTrendFollowingStrategy:
    """测试趋势跟踪策略"""

    def test_init(self):
        """测试初始化"""
        strategy = TrendFollowingStrategy(holding_days=5, max_stocks=10)
        assert strategy.holding_days == 5
        assert strategy.max_stocks == 10

    def test_default_params(self):
        """测试默认参数"""
        strategy = TrendFollowingStrategy()
        assert strategy.holding_days == 5
        assert strategy.max_stocks == 10

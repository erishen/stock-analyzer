"""
Tests for Strategy Module.
策略模块测试
"""

from pathlib import Path

import numpy as np
import pandas as pd


from strategy.backtest import (
    BacktestResult,
    DynamicStopLoss,
    MeanReversionStrategy,
    MomentumStrategy,
    MultiFactorStrategy,
    PositionManager,
    Trade,
    TrendFollowingStrategy,
)


class TestMomentumStrategy:
    """动量策略测试"""

    def test_strategy_creation(self):
        """测试策略创建"""
        strategy = MomentumStrategy(
            lookback_days=20,
            top_n=10,
            holding_days=5,
            min_momentum=0.02,
            max_momentum=0.5,
            max_volatility=0.08,
            min_price=3.0,
            exclude_st=True,
        )
        assert strategy.lookback_days == 20
        assert strategy.top_n == 10
        assert strategy.holding_days == 5
        assert strategy.min_momentum == 0.02
        assert strategy.exclude_st is True

    def test_is_excluded(self):
        """测试 ST 排除逻辑"""
        strategy = MomentumStrategy(exclude_st=True)

        assert strategy.is_excluded("ST某某") is True
        assert strategy.is_excluded("*ST某某") is True
        assert strategy.is_excluded("某某退市") is True
        assert strategy.is_excluded("正常股票") is False

    def test_is_excluded_disabled(self):
        """测试禁用 ST 排除"""
        strategy = MomentumStrategy(exclude_st=False)
        assert strategy.is_excluded("ST某某") is False

    def test_calculate_volatility(self):
        """测试波动率计算"""
        strategy = MomentumStrategy()

        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        prices = 100 + np.cumsum(np.random.randn(30) * 2)
        df = pd.DataFrame(
            {
                "date": dates,
                "close": prices,
            }
        )

        vol = strategy.calculate_volatility(df, 25)
        assert vol >= 0

    def test_calculate_volatility_insufficient_data(self):
        """测试数据不足时的波动率计算"""
        strategy = MomentumStrategy()

        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=10, freq="D"),
                "close": [100] * 10,
            }
        )

        vol = strategy.calculate_volatility(df, 5)
        assert vol == 1.0

    def test_select_stocks_empty_data(self):
        """测试空数据选股"""
        strategy = MomentumStrategy()
        result = strategy.select_stocks({}, 0, "2024-01-01")
        assert result == []

    def test_select_stocks_with_data(self):
        """测试有数据时的选股"""
        strategy = MomentumStrategy(min_price=1.0)

        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        df = pd.DataFrame(
            {
                "date": dates,
                "close": np.linspace(100, 120, 30),
                "high": np.linspace(102, 122, 30),
                "low": np.linspace(98, 118, 30),
                "open": np.linspace(100, 120, 30),
                "volume": [1000000] * 30,
                "rsi": [50] * 30,
                "macd": [0] * 30,
                "macd_signal": [0] * 30,
                "ma5": np.linspace(100, 118, 30),
                "ma10": np.linspace(100, 116, 30),
                "ma20": np.linspace(100, 114, 30),
                "boll_upper": np.linspace(105, 125, 30),
                "boll_lower": np.linspace(95, 115, 30),
            }
        )

        all_data = {"sh600000": df}
        result = strategy.select_stocks(all_data, 25, "2024-01-26")

        assert isinstance(result, list)


class TestMeanReversionStrategy:
    """均值回归策略测试"""

    def test_strategy_creation(self):
        """测试策略创建"""
        strategy = MeanReversionStrategy(
            rsi_oversold=30,
            holding_days=5,
            max_stocks=10,
            min_price=2.0,
            exclude_st=True,
        )
        assert strategy.rsi_oversold == 30
        assert strategy.holding_days == 5

    def test_select_stocks_rsi_oversold(self):
        """测试 RSI 超卖选股"""
        strategy = MeanReversionStrategy(rsi_oversold=30, min_price=1.0)

        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        df = pd.DataFrame(
            {
                "date": dates,
                "close": [100] * 30,
                "rsi": [25] * 30,
            }
        )

        all_data = {"sh600000": df}
        result = strategy.select_stocks(all_data, 25, "2024-01-26")

        assert len(result) > 0
        assert result[0][0] == "sh600000"


class TestTrendFollowingStrategy:
    """趋势跟踪策略测试"""

    def test_strategy_creation(self):
        """测试策略创建"""
        strategy = TrendFollowingStrategy(
            holding_days=5,
            max_stocks=10,
            use_ma_cross=False,
        )
        assert strategy.holding_days == 5
        assert strategy.use_ma_cross is False

    def test_select_stocks_boll_breakout(self):
        """测试布林带突破选股"""
        strategy = TrendFollowingStrategy(min_price=1.0)

        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        df = pd.DataFrame(
            {
                "date": dates,
                "close": np.linspace(100, 130, 30),
                "boll_upper": np.linspace(105, 120, 30),
                "boll_lower": np.linspace(95, 110, 30),
                "ma5": np.linspace(100, 125, 30),
                "ma10": np.linspace(100, 120, 30),
                "ma20": np.linspace(100, 115, 30),
            }
        )

        all_data = {"sh600000": df}
        result = strategy.select_stocks(all_data, 29, "2024-01-30")

        assert isinstance(result, list)

    def test_select_stocks_ma_cross(self):
        """测试均线交叉选股"""
        strategy = TrendFollowingStrategy(min_price=1.0, use_ma_cross=True)

        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        df = pd.DataFrame(
            {
                "date": dates,
                "close": np.linspace(100, 130, 30),
                "boll_upper": np.linspace(105, 120, 30),
                "boll_lower": np.linspace(95, 110, 30),
                "ma5": np.linspace(100, 125, 30),
                "ma10": np.linspace(100, 120, 30),
                "ma20": np.linspace(100, 115, 30),
            }
        )

        all_data = {"sh600000": df}
        result = strategy.select_stocks(all_data, 29, "2024-01-30")

        assert isinstance(result, list)


class TestMultiFactorStrategy:
    """多因子策略测试"""

    def test_strategy_creation(self):
        """测试策略创建"""
        strategy = MultiFactorStrategy(
            holding_days=5,
            max_stocks=10,
            trend_weight=0.3,
            momentum_weight=0.3,
            volatility_weight=0.2,
            volume_weight=0.2,
        )
        assert strategy.trend_weight == 0.3
        assert strategy.momentum_weight == 0.3

    def test_calculate_factors(self):
        """测试因子计算"""
        strategy = MultiFactorStrategy()

        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        df = pd.DataFrame(
            {
                "date": dates,
                "close": np.linspace(100, 120, 30),
                "volume": [1000000] * 30,
                "rsi": [50] * 30,
                "ma5": np.linspace(100, 118, 30),
                "ma10": np.linspace(100, 116, 30),
                "ma20": np.linspace(100, 114, 30),
            }
        )

        factors = strategy.calculate_factors(df, 25)

        assert "trend" in factors
        assert "momentum" in factors
        assert "volatility" in factors
        assert "volume" in factors


class TestPositionManager:
    """仓位管理器测试"""

    def test_kelly_criterion(self):
        """测试凯利公式"""
        position = PositionManager.kelly_criterion(
            win_rate=0.5,
            avg_win=0.1,
            avg_loss=0.05,
        )
        assert 0 < position <= 0.2

    def test_kelly_criterion_zero_loss(self):
        """测试零亏损情况"""
        position = PositionManager.kelly_criterion(
            win_rate=0.5,
            avg_win=0.1,
            avg_loss=0,
        )
        assert position == 0.1

    def test_risk_parity(self):
        """测试风险平价"""
        volatilities = {
            "stock1": 0.02,
            "stock2": 0.04,
            "stock3": 0.01,
        }
        weights = PositionManager.risk_parity(volatilities)

        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_risk_parity_empty(self):
        """测试空波动率"""
        weights = PositionManager.risk_parity({})
        assert weights == {}

    def test_equal_weight(self):
        """测试等权分配"""
        weight = PositionManager.equal_weight(10)
        assert weight == 0.1

        weight = PositionManager.equal_weight(0)
        assert weight == 0.0


class TestDynamicStopLoss:
    """动态止损测试"""

    def test_calculate_atr_stop(self):
        """测试 ATR 止损计算"""
        stop_loss = DynamicStopLoss(atr_multiplier=2.0)

        stop_price, stop_type = stop_loss.calculate_atr_stop(
            entry_price=100,
            atr=2.0,
        )

        assert stop_price == 96.0
        assert stop_type == "ATR止损"

    def test_trailing_stop(self):
        """测试移动止损"""
        stop_loss = DynamicStopLoss(
            atr_multiplier=2.0,
            trailing_stop=0.05,
        )

        stop_price, stop_type = stop_loss.calculate_atr_stop(
            entry_price=100,
            atr=2.0,
            highest_price=110,
        )

        assert stop_price == 104.5
        assert stop_type == "移动止损"

    def test_should_stop_atr(self):
        """测试 ATR 止损触发"""
        stop_loss = DynamicStopLoss(atr_multiplier=2.0)

        should_stop, reason = stop_loss.should_stop(
            current_price=95,
            entry_price=100,
            highest_price=100,
            atr=2.0,
            holding_days=5,
        )

        assert should_stop is True
        assert "止损" in reason

    def test_should_stop_max_hold_days(self):
        """测试最大持仓天数"""
        stop_loss = DynamicStopLoss(max_hold_days=10)

        should_stop, reason = stop_loss.should_stop(
            current_price=100,
            entry_price=100,
            highest_price=100,
            atr=2.0,
            holding_days=10,
        )

        assert should_stop is True
        assert "持仓天数" in reason


class TestTrade:
    """交易记录测试"""

    def test_trade_creation(self):
        """测试交易创建"""
        trade = Trade(
            code="sh600000",
            name="浦发银行",
            entry_date="2024-01-01",
            entry_price=10.0,
            shares=1000,
        )
        assert trade.code == "sh600000"
        assert trade.shares == 1000

    def test_trade_to_dict(self):
        """测试交易转字典"""
        trade = Trade(
            code="sh600000",
            name="浦发银行",
            entry_date="2024-01-01",
            entry_price=10.0,
            exit_date="2024-01-05",
            exit_price=11.0,
            shares=1000,
            profit=1000.0,
            profit_percent=0.1,
            holding_days=5,
        )

        d = trade.to_dict()
        assert d["code"] == "sh600000"
        assert d["profit"] == 1000.0
        assert d["profit_percent"] == 0.1


class TestBacktestResult:
    """回测结果测试"""

    def test_result_creation(self):
        """测试结果创建"""
        result = BacktestResult(
            strategy_name="TestStrategy",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            final_capital=110000,
            total_return=0.1,
            annualized_return=0.1,
            max_drawdown=0.1,
            win_rate=0.5,
            total_trades=100,
            winning_trades=50,
            losing_trades=50,
            avg_profit=0.05,
            avg_loss=-0.03,
            profit_factor=1.5,
            sharpe_ratio=1.0,
            trades=[],
            equity_curve=[],
        )

        assert result.strategy_name == "TestStrategy"
        assert result.total_return == 0.1

    def test_result_to_dict(self):
        """测试结果转字典"""
        result = BacktestResult(
            strategy_name="TestStrategy",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            final_capital=110000,
            total_return=0.1,
            annualized_return=0.1,
            max_drawdown=0.1,
            win_rate=0.5,
            total_trades=100,
            winning_trades=50,
            losing_trades=50,
            avg_profit=0.05,
            avg_loss=-0.03,
            profit_factor=1.5,
            sharpe_ratio=1.0,
            trades=[],
            equity_curve=[],
            sortino_ratio=1.2,
            calmar_ratio=1.0,
            volatility=0.15,
        )

        d = result.to_dict()
        assert d["total_return"] == 10.0
        assert d["sharpe_ratio"] == 1.0
        assert d["sortino_ratio"] == 1.2

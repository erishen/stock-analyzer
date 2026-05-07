"""
Tests for Advanced Strategies.
高级策略测试
"""

from pathlib import Path

import numpy as np
import pandas as pd


from strategy.advanced import (
    BreakoutStrategy,
    EventDrivenStrategy,
    GridLevel,
    GridTradingStrategy,
    PairInfo,
    PairTradingStrategy,
)


class TestBreakoutStrategy:
    """突破策略测试"""

    def test_create_strategy(self):
        """测试创建策略"""
        strategy = BreakoutStrategy(breakout_type="price")
        assert strategy.breakout_type == "price"
        assert strategy.lookback_days == 20

    def test_is_excluded(self):
        """测试排除 ST 股票"""
        strategy = BreakoutStrategy(exclude_st=True)
        assert strategy.is_excluded("ST某某股票") is True
        assert strategy.is_excluded("正常股票") is False

    def test_detect_price_breakout(self):
        """测试价格突破检测"""
        strategy = BreakoutStrategy(breakout_type="price", breakout_threshold=0.02)

        dates = pd.date_range("2026-01-01", periods=25)
        df = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "close": [10.0] * 20 + [10.5, 10.6, 10.7, 10.8, 11.5],
                "high": [10.2] * 20 + [10.7, 10.8, 10.9, 11.0, 11.6],
            }
        )

        is_breakout, strength = strategy.detect_price_breakout(df, 24)
        assert is_breakout is True

    def test_detect_bollinger_breakout(self):
        """测试布林带突破检测"""
        strategy = BreakoutStrategy(breakout_type="bollinger")

        dates = pd.date_range("2026-01-01", periods=25)
        df = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "close": [10.0] * 20 + [10.5, 10.6, 10.7, 10.8, 12.0],
                "boll_upper": [11.0] * 25,
            }
        )

        is_breakout, strength = strategy.detect_bollinger_breakout(df, 24)
        assert is_breakout is True

    def test_detect_volume_breakout(self):
        """测试成交量突破检测"""
        strategy = BreakoutStrategy(breakout_type="volume", volume_multiplier=1.5)

        dates = pd.date_range("2026-01-01", periods=25)
        df = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "close": [10.0] * 20 + [10.5, 10.6, 10.7, 10.8, 11.0],
                "volume": [1000] * 20 + [1000, 1000, 1000, 1000, 3000],
            }
        )

        is_breakout, strength = strategy.detect_volume_breakout(df, 24)
        assert is_breakout is True


class TestGridTradingStrategy:
    """网格交易策略测试"""

    def test_create_strategy(self):
        """测试创建策略"""
        strategy = GridTradingStrategy(grid_count=10)
        assert strategy.grid_count == 10
        assert strategy.grid_spacing == 0.05

    def test_initialize_grids(self):
        """测试初始化网格"""
        strategy = GridTradingStrategy(grid_count=5)
        grids = strategy.initialize_grids("sh600000", 10.0)

        assert len(grids) == 10
        buy_grids = [g for g in grids if g.is_buy]
        sell_grids = [g for g in grids if not g.is_buy]
        assert len(buy_grids) == 5
        assert len(sell_grids) == 5

    def test_check_grid_trigger(self):
        """测试网格触发"""
        strategy = GridTradingStrategy(grid_count=5, grid_spacing=0.1)
        strategy.initialize_grids("sh600000", 10.0)

        action, shares, price = strategy.check_grid_trigger("sh600000", 8.5, 0.0)
        assert action == "buy"

    def test_grid_level(self):
        """测试网格层级"""
        level = GridLevel(price=10.0, shares=100, is_buy=True)
        assert level.price == 10.0
        assert level.shares == 100
        assert level.is_buy is True
        assert level.is_filled is False


class TestPairTradingStrategy:
    """配对交易策略测试"""

    def test_create_strategy(self):
        """测试创建策略"""
        strategy = PairTradingStrategy(entry_threshold=2.0)
        assert strategy.entry_threshold == 2.0
        assert strategy.min_correlation == 0.7

    def test_calculate_correlation(self):
        """测试相关性计算"""
        strategy = PairTradingStrategy()

        dates = pd.date_range("2026-01-01", periods=100)
        df1 = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "close": np.random.randn(100).cumsum() + 100,
            }
        )
        df2 = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "close": np.random.randn(100).cumsum() + 50,
            }
        )

        correlation = strategy.calculate_correlation(df1, df2)
        assert -1 <= correlation <= 1

    def test_calculate_spread(self):
        """测试价差计算"""
        strategy = PairTradingStrategy()
        spread = strategy.calculate_spread(100.0, 50.0, 2.0)
        assert spread == 0.0

    def test_generate_signal(self):
        """测试信号生成"""
        strategy = PairTradingStrategy(entry_threshold=2.0, exit_threshold=0.5)

        pair = PairInfo(
            code1="sh600000",
            code2="sh600001",
            spread_mean=0.0,
            spread_std=1.0,
            hedge_ratio=2.0,
            correlation=0.9,
        )

        signal, z_score = strategy.generate_signal(pair, 105.0, 50.0)
        assert signal in ["long_spread", "short_spread", "close", "hold"]

    def test_pair_info(self):
        """测试配对信息"""
        pair = PairInfo(
            code1="sh600000",
            code2="sh600001",
            spread_mean=0.5,
            spread_std=0.1,
            hedge_ratio=2.0,
            correlation=0.9,
        )
        assert pair.code1 == "sh600000"
        assert pair.correlation == 0.9


class TestEventDrivenStrategy:
    """事件驱动策略测试"""

    def test_create_strategy(self):
        """测试创建策略"""
        strategy = EventDrivenStrategy(event_types=["earnings", "technical"])
        assert "earnings" in strategy.event_types
        assert "technical" in strategy.event_types

    def test_is_excluded(self):
        """测试排除 ST 股票"""
        strategy = EventDrivenStrategy(exclude_st=True)
        assert strategy.is_excluded("ST某某股票") is True
        assert strategy.is_excluded("正常股票") is False

    def test_detect_earnings_event(self):
        """测试财报事件检测"""
        strategy = EventDrivenStrategy()

        dates = pd.date_range("2026-01-01", periods=25)
        df = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "close": [10.0] * 20 + [10.5, 10.8, 11.0, 11.5, 12.0],
                "volume": [1000] * 20 + [1000, 1000, 1000, 1000, 5000],
                "change_percent": [0.0] * 20 + [0.0, 0.0, 0.0, 0.0, 5.0],
            }
        )

        is_event, strength = strategy.detect_earnings_event(df, 24)
        assert is_event is True

    def test_detect_technical_event(self):
        """测试技术事件检测"""
        strategy = EventDrivenStrategy()

        dates = pd.date_range("2026-01-01", periods=35)
        df = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "close": [10.0] * 30 + [10.5, 10.8, 11.0, 11.2, 11.5],
                "macd": [0.0] * 30 + [0.1, 0.2, 0.3, 0.4, 0.5],
                "macd_signal": [0.0] * 30 + [0.05, 0.1, 0.15, 0.2, 0.25],
                "rsi": [50.0] * 30 + [25.0, 24.0, 23.0, 22.0, 21.0],
                "ma5": [10.0] * 35,
                "ma20": [9.8] * 35,
                "boll_upper": [11.0] * 35,
                "boll_lower": [9.0] * 35,
            }
        )

        is_event, strength = strategy.detect_technical_event(df, 34)
        assert is_event is True

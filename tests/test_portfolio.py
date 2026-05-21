"""
Tests for Multi-Strategy Portfolio Module.
多策略组合模块测试
"""

from pathlib import Path
from unittest.mock import patch

import logging
import numpy as np
import pytest

from src.strategy.portfolio import (
    MultiStrategyPortfolio,
    PortfolioResult,
    StrategyConfig,
    WeightMethod,
    print_portfolio_result,
    run_portfolio_backtest,
)


class TestWeightMethod:
    """测试权重方法枚举"""

    def test_weight_methods(self):
        assert WeightMethod.EQUAL.value == "equal"
        assert WeightMethod.RISK_PARITY.value == "risk_parity"
        assert WeightMethod.SHARPE.value == "sharpe"
        assert WeightMethod.CUSTOM.value == "custom"


class TestStrategyConfig:
    """测试策略配置"""

    def test_create_strategy_config(self):
        config = StrategyConfig(
            name="test_strategy",
            strategy_type="momentum",
            weight=0.5,
            params={"holding_days": 5},
        )
        assert config.name == "test_strategy"
        assert config.strategy_type == "momentum"
        assert config.weight == 0.5
        assert config.params == {"holding_days": 5}

    def test_strategy_config_to_dict(self):
        config = StrategyConfig(
            name="test_strategy",
            strategy_type="momentum",
            weight=0.333333,
            params={"holding_days": 5},
        )
        result = config.to_dict()
        assert result["name"] == "test_strategy"
        assert result["strategy_type"] == "momentum"
        assert result["weight"] == 0.3333
        assert result["params"] == {"holding_days": 5}


class TestPortfolioResult:
    """测试组合结果"""

    def test_create_portfolio_result(self):
        result = PortfolioResult(
            name="TestPortfolio",
            start_date="2025-01-01",
            end_date="2025-12-31",
            initial_capital=100000.0,
            final_capital=120000.0,
            total_return=0.2,
            annualized_return=0.2,
            max_drawdown=0.1,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=2.0,
            volatility=0.15,
            strategy_results=[],
            strategy_weights={"momentum": 0.5, "mean_reversion": 0.5},
            correlation_matrix={"momentum": {"momentum": 1.0, "mean_reversion": 0.3}},
            diversification_ratio=1.2,
        )
        assert result.name == "TestPortfolio"
        assert result.total_return == 0.2
        assert result.sharpe_ratio == 1.5

    def test_portfolio_result_to_dict(self):
        result = PortfolioResult(
            name="TestPortfolio",
            start_date="2025-01-01",
            end_date="2025-12-31",
            initial_capital=100000.0,
            final_capital=120000.0,
            total_return=0.12345,
            annualized_return=0.12345,
            max_drawdown=0.05678,
            sharpe_ratio=1.234,
            sortino_ratio=2.345,
            calmar_ratio=3.456,
            volatility=0.1111,
            strategy_results=[],
            strategy_weights={"momentum": 0.333333},
            correlation_matrix={},
            diversification_ratio=1.2345,
        )
        d = result.to_dict()
        assert d["total_return"] == 12.35
        assert d["annualized_return"] == 12.35
        assert d["max_drawdown"] == 5.68
        assert d["sharpe_ratio"] == 1.23


class TestMultiStrategyPortfolio:
    """测试多策略组合"""

    def test_create_portfolio(self):
        portfolio = MultiStrategyPortfolio(
            name="TestPortfolio",
            weight_method=WeightMethod.EQUAL,
        )
        assert portfolio.name == "TestPortfolio"
        assert portfolio.weight_method == WeightMethod.EQUAL
        assert len(portfolio.strategies) == 0

    def test_add_strategy(self):
        portfolio = MultiStrategyPortfolio()
        portfolio.add_strategy("momentum", "momentum", holding_days=5)
        assert len(portfolio.strategies) == 1
        assert portfolio.strategies[0].name == "momentum"
        assert portfolio.strategies[0].strategy_type == "momentum"

    def test_add_invalid_strategy(self):
        portfolio = MultiStrategyPortfolio()
        with pytest.raises(ValueError, match="未知策略类型"):
            portfolio.add_strategy("invalid", "invalid_type")

    def test_calculate_equal_weights(self):
        portfolio = MultiStrategyPortfolio(weight_method=WeightMethod.EQUAL)
        portfolio.add_strategy("s1", "momentum")
        portfolio.add_strategy("s2", "mean_reversion")

        returns = {"s1": [0.01, 0.02, -0.01], "s2": [0.02, -0.01, 0.01]}
        weights = portfolio._calculate_weights(returns)

        assert weights["s1"] == 0.5
        assert weights["s2"] == 0.5

    def test_calculate_risk_parity_weights(self):
        portfolio = MultiStrategyPortfolio(weight_method=WeightMethod.RISK_PARITY)
        portfolio.add_strategy("s1", "momentum")
        portfolio.add_strategy("s2", "mean_reversion")

        returns = {
            "s1": [0.01, 0.02, -0.01, 0.03, -0.02],
            "s2": [0.005, 0.003, -0.002, 0.004, -0.001],
        }
        weights = portfolio._calculate_weights(returns)

        assert abs(sum(weights.values()) - 1.0) < 0.0001
        vol1 = np.std(returns["s1"])
        vol2 = np.std(returns["s2"])
        if vol1 > vol2:
            assert weights["s2"] > weights["s1"]

    def test_calculate_sharpe_weights(self):
        portfolio = MultiStrategyPortfolio(weight_method=WeightMethod.SHARPE)
        portfolio.add_strategy("s1", "momentum")
        portfolio.add_strategy("s2", "mean_reversion")

        returns = {
            "s1": [0.02, 0.03, 0.01, 0.04, 0.02],
            "s2": [-0.01, -0.02, 0.01, -0.01, -0.02],
        }
        weights = portfolio._calculate_weights(returns)

        assert abs(sum(weights.values()) - 1.0) < 0.0001
        assert weights["s1"] > weights["s2"]

    def test_calculate_custom_weights(self):
        portfolio = MultiStrategyPortfolio(weight_method=WeightMethod.CUSTOM)
        portfolio.add_strategy("s1", "momentum", weight=0.3)
        portfolio.add_strategy("s2", "mean_reversion", weight=0.7)

        returns = {"s1": [0.01], "s2": [0.02]}
        weights = portfolio._calculate_weights(returns)

        assert weights["s1"] == 0.3
        assert weights["s2"] == 0.7

    def test_calculate_correlation(self):
        portfolio = MultiStrategyPortfolio()
        portfolio.add_strategy("s1", "momentum")
        portfolio.add_strategy("s2", "mean_reversion")

        returns = {
            "s1": [0.01, 0.02, -0.01, 0.03, -0.02],
            "s2": [0.02, 0.01, -0.02, 0.02, -0.01],
        }
        corr = portfolio._calculate_correlation(returns)

        assert corr["s1"]["s1"] == 1.0
        assert corr["s2"]["s2"] == 1.0
        assert -1 <= corr["s1"]["s2"] <= 1
        assert corr["s1"]["s2"] == corr["s2"]["s1"]

    def test_calculate_diversification_ratio(self):
        portfolio = MultiStrategyPortfolio()
        portfolio.add_strategy("s1", "momentum")
        portfolio.add_strategy("s2", "mean_reversion")

        returns = {
            "s1": [0.01, 0.02, -0.01, 0.03, -0.02],
            "s2": [0.02, 0.01, -0.02, 0.02, -0.01],
        }
        weights = {"s1": 0.5, "s2": 0.5}
        div_ratio = portfolio._calculate_diversification_ratio(weights, returns)

        assert div_ratio > 0

    def test_run_backtest_no_strategies(self):
        portfolio = MultiStrategyPortfolio()
        with pytest.raises(ValueError, match="请先添加策略"):
            portfolio.run_backtest(Path("test.db"))


class TestPrintPortfolioResult:
    """测试打印组合结果"""

    def test_print_portfolio_result(self, caplog):
        result = PortfolioResult(
            name="TestPortfolio",
            start_date="2025-01-01",
            end_date="2025-12-31",
            initial_capital=100000.0,
            final_capital=120000.0,
            total_return=0.2,
            annualized_return=0.2,
            max_drawdown=0.1,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=2.0,
            volatility=0.15,
            strategy_results=[],
            strategy_weights={"momentum": 0.5, "mean_reversion": 0.5},
            correlation_matrix={
                "momentum": {"momentum": 1.0, "mean_reversion": 0.3},
                "mean_reversion": {"momentum": 0.3, "mean_reversion": 1.0},
            },
            diversification_ratio=1.2,
        )
        with caplog.at_level(logging.INFO, logger="src.strategy.portfolio"):
            print_portfolio_result(result)
        log_output = caplog.text
        assert "TestPortfolio" in log_output
        assert "总收益率: +20.00%" in log_output
        assert "夏普比率: 1.50" in log_output


class TestRunPortfolioBacktest:
    """测试运行组合回测"""

    def test_run_portfolio_backtest_db_not_found(self):
        with pytest.raises(FileNotFoundError, match="数据库不存在"):
            run_portfolio_backtest(db_path=Path("/nonexistent/path.db"))

    @patch("src.strategy.portfolio.print_portfolio_result")
    @patch("src.strategy.portfolio.MultiStrategyPortfolio.run_backtest")
    @patch("src.strategy.portfolio.Path.exists")
    def test_run_portfolio_backtest_success(self, mock_exists, mock_run, mock_print):
        mock_exists.return_value = True
        mock_result = PortfolioResult(
            name="TestPortfolio",
            start_date="2025-01-01",
            end_date="2025-12-31",
            initial_capital=100000.0,
            final_capital=120000.0,
            total_return=0.2,
            annualized_return=0.2,
            max_drawdown=0.1,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=2.0,
            volatility=0.15,
            strategy_results=[],
            strategy_weights={"momentum": 0.5},
            correlation_matrix={},
            diversification_ratio=1.2,
        )
        mock_run.return_value = mock_result

        result = run_portfolio_backtest(
            db_path=Path("test.db"),
            weight_method="equal",
        )

        assert result is not None
        mock_run.assert_called_once()
        mock_print.assert_called_once()

"""
Tests for Strategy Comparison Module.
策略对比模块测试
"""

from unittest.mock import MagicMock

from strategy.comparison import (
    ComparisonResult,
    StrategyMetrics,
    compare_strategies,
    print_comparison,
)


class TestStrategyMetrics:
    """策略指标测试"""

    def test_metrics_creation(self):
        """测试指标创建"""
        metrics = StrategyMetrics(
            name="TestStrategy",
            total_return=0.1,
            annualized_return=0.1,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=2.0,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=100,
            volatility=0.15,
        )
        assert metrics.name == "TestStrategy"
        assert metrics.total_return == 0.1
        assert metrics.sharpe_ratio == 1.5

    def test_metrics_to_dict(self):
        """测试指标转字典"""
        metrics = StrategyMetrics(
            name="TestStrategy",
            total_return=0.1,
            annualized_return=0.1,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=2.0,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=100,
            volatility=0.15,
        )

        d = metrics.to_dict()
        assert d["name"] == "TestStrategy"
        assert d["total_return"] == 10.0
        assert d["sharpe_ratio"] == 1.5
        assert d["win_rate"] == 60.0


class TestComparisonResult:
    """对比结果测试"""

    def test_result_creation(self):
        """测试结果创建"""
        metrics = StrategyMetrics(
            name="Strategy1",
            total_return=0.1,
            annualized_return=0.1,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=2.0,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=100,
            volatility=0.15,
        )

        result = ComparisonResult(
            strategies=[metrics],
            best_return="Strategy1",
            best_sharpe="Strategy1",
            best_drawdown="Strategy1",
            best_win_rate="Strategy1",
            overall_ranking=[("Strategy1", 100.0)],
        )

        assert result.best_return == "Strategy1"
        assert len(result.strategies) == 1

    def test_result_to_dict(self):
        """测试结果转字典"""
        metrics = StrategyMetrics(
            name="Strategy1",
            total_return=0.1,
            annualized_return=0.1,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=2.0,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=100,
            volatility=0.15,
        )

        result = ComparisonResult(
            strategies=[metrics],
            best_return="Strategy1",
            best_sharpe="Strategy1",
            best_drawdown="Strategy1",
            best_win_rate="Strategy1",
            overall_ranking=[("Strategy1", 100.0)],
        )

        d = result.to_dict()
        assert d["best_return"] == "Strategy1"
        assert len(d["strategies"]) == 1
        assert len(d["overall_ranking"]) == 1


class TestCompareStrategies:
    """策略对比函数测试"""

    def test_compare_single_strategy(self):
        """测试单个策略对比"""
        mock_result = MagicMock()
        mock_result.strategy_name = "TestStrategy"
        mock_result.total_return = 0.1
        mock_result.annualized_return = 0.1
        mock_result.max_drawdown = 0.05
        mock_result.sharpe_ratio = 1.5
        mock_result.sortino_ratio = 1.8
        mock_result.calmar_ratio = 2.0
        mock_result.win_rate = 0.6
        mock_result.profit_factor = 2.0
        mock_result.total_trades = 100
        mock_result.volatility = 0.15

        result = compare_strategies([mock_result])

        assert result.best_return == "TestStrategy"
        assert result.best_sharpe == "TestStrategy"
        assert len(result.strategies) == 1

    def test_compare_multiple_strategies(self):
        """测试多个策略对比"""
        mock_result1 = MagicMock()
        mock_result1.strategy_name = "Strategy1"
        mock_result1.total_return = 0.1
        mock_result1.annualized_return = 0.1
        mock_result1.max_drawdown = 0.05
        mock_result1.sharpe_ratio = 1.5
        mock_result1.sortino_ratio = 1.8
        mock_result1.calmar_ratio = 2.0
        mock_result1.win_rate = 0.6
        mock_result1.profit_factor = 2.0
        mock_result1.total_trades = 100
        mock_result1.volatility = 0.15

        mock_result2 = MagicMock()
        mock_result2.strategy_name = "Strategy2"
        mock_result2.total_return = 0.2
        mock_result2.annualized_return = 0.2
        mock_result2.max_drawdown = 0.08
        mock_result2.sharpe_ratio = 2.0
        mock_result2.sortino_ratio = 2.5
        mock_result2.calmar_ratio = 2.5
        mock_result2.win_rate = 0.55
        mock_result2.profit_factor = 1.8
        mock_result2.total_trades = 120
        mock_result2.volatility = 0.18

        result = compare_strategies([mock_result1, mock_result2])

        assert result.best_return == "Strategy2"
        assert result.best_sharpe == "Strategy2"
        assert result.best_drawdown == "Strategy1"
        assert result.best_win_rate == "Strategy1"
        assert len(result.strategies) == 2
        assert len(result.overall_ranking) == 2

    def test_compare_ranking_order(self):
        """测试排名顺序"""
        mock_result1 = MagicMock()
        mock_result1.strategy_name = "GoodStrategy"
        mock_result1.total_return = 0.5
        mock_result1.annualized_return = 0.5
        mock_result1.max_drawdown = 0.05
        mock_result1.sharpe_ratio = 2.0
        mock_result1.sortino_ratio = 2.5
        mock_result1.calmar_ratio = 10.0
        mock_result1.win_rate = 0.7
        mock_result1.profit_factor = 3.0
        mock_result1.total_trades = 100
        mock_result1.volatility = 0.1

        mock_result2 = MagicMock()
        mock_result2.strategy_name = "BadStrategy"
        mock_result2.total_return = -0.2
        mock_result2.annualized_return = -0.2
        mock_result2.max_drawdown = 0.3
        mock_result2.sharpe_ratio = -0.5
        mock_result2.sortino_ratio = -0.6
        mock_result2.calmar_ratio = -0.67
        mock_result2.win_rate = 0.3
        mock_result2.profit_factor = 0.5
        mock_result2.total_trades = 100
        mock_result2.volatility = 0.25

        result = compare_strategies([mock_result1, mock_result2])

        assert result.overall_ranking[0][0] == "GoodStrategy"
        assert result.overall_ranking[1][0] == "BadStrategy"


class TestPrintComparison:
    """打印对比结果测试"""

    def test_print_comparison(self, capsys):
        """测试打印对比结果"""
        metrics = StrategyMetrics(
            name="TestStrategy",
            total_return=0.1,
            annualized_return=0.1,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=2.0,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=100,
            volatility=0.15,
        )

        result = ComparisonResult(
            strategies=[metrics],
            best_return="TestStrategy",
            best_sharpe="TestStrategy",
            best_drawdown="TestStrategy",
            best_win_rate="TestStrategy",
            overall_ranking=[("TestStrategy", 100.0)],
        )

        print_comparison(result)
        captured = capsys.readouterr()

        assert "TestStrategy" in captured.out
        assert "策略对比报告" in captured.out
        assert "综合排名" in captured.out

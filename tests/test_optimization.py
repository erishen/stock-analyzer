"""
Tests for Strategy Optimization.
策略优化测试
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


from strategy.optimization import (
    OptimizationResult,
    optimize_mean_reversion_strategy,
    optimize_momentum_strategy,
    run_optimization,
)


class TestOptimizationResult:
    """测试优化结果"""

    def test_create_result(self):
        """测试创建结果"""
        result = OptimizationResult(
            best_params={"holding_days": 5, "stop_loss": 0.05},
            best_return=0.15,
            best_sharpe=1.5,
            best_drawdown=-0.10,
            all_results=[],
            total_combinations=100,
        )

        assert result.best_params["holding_days"] == 5
        assert result.best_return == 0.15
        assert result.best_sharpe == 1.5

    def test_to_dict(self):
        """测试转换为字典"""
        result = OptimizationResult(
            best_params={"holding_days": 5},
            best_return=0.15,
            best_sharpe=1.5,
            best_drawdown=-0.10,
            all_results=[],
            total_combinations=100,
        )

        d = result.to_dict()
        assert d["best_return"] == 15.0
        assert d["total_combinations"] == 100


class TestOptimizeMomentumStrategy:
    """测试动量策略优化"""

    def test_optimize_basic(self):
        """测试基本优化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"

            with patch("strategy.optimization.BacktestEngine") as mock_engine:
                mock_instance = MagicMock()
                mock_instance.run_backtest.return_value = MagicMock(
                    total_return=0.15,
                    sharpe_ratio=1.5,
                    max_drawdown=-0.10,
                    win_rate=0.6,
                )
                mock_engine.return_value = mock_instance

                result = optimize_momentum_strategy(db_path=db_path)

                assert result is not None


class TestOptimizeMeanReversionStrategy:
    """测试均值回归策略优化"""

    def test_optimize_basic(self):
        """测试基本优化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"

            with patch("strategy.optimization.BacktestEngine") as mock_engine:
                mock_instance = MagicMock()
                mock_instance.run_backtest.return_value = MagicMock(
                    total_return=0.12,
                    sharpe_ratio=1.2,
                    max_drawdown=-0.08,
                    win_rate=0.55,
                )
                mock_engine.return_value = mock_instance

                result = optimize_mean_reversion_strategy(db_path=db_path)

                assert result is not None


class TestRunOptimization:
    """测试运行优化"""

    def test_run_optimization_momentum(self):
        """测试运行动量优化"""
        with patch("strategy.optimization.optimize_momentum_strategy") as mock_opt:
            mock_opt.return_value = OptimizationResult(
                best_params={"holding_days": 5},
                best_return=0.15,
                best_sharpe=1.5,
                best_drawdown=-0.10,
                all_results=[],
                total_combinations=10,
            )

            result = run_optimization(strategy_type="momentum")

            assert result is not None
            mock_opt.assert_called_once()

    def test_run_optimization_mean_reversion(self):
        """测试运行均值回归优化"""
        with patch("strategy.optimization.optimize_mean_reversion_strategy") as mock_opt:
            mock_opt.return_value = OptimizationResult(
                best_params={"rsi_threshold": 30},
                best_return=0.12,
                best_sharpe=1.2,
                best_drawdown=-0.08,
                all_results=[],
                total_combinations=10,
            )

            result = run_optimization(strategy_type="mean_reversion")

            assert result is not None
            mock_opt.assert_called_once()

    def test_run_optimization_invalid_strategy(self):
        """测试无效策略类型"""
        with pytest.raises(ValueError):
            run_optimization(strategy_type="invalid")

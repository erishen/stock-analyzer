"""
Tests for Benchmark Comparison Module.
基准对比模块测试
"""

import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.strategy.benchmark import (
    BenchmarkResult,
    calculate_equal_weight_benchmark,
    compare_with_benchmark,
    print_benchmark_comparison,
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
            close REAL
        )
    """)

    test_data = [
        ("000001", "2024-01-01", 10.0),
        ("000001", "2024-01-02", 10.5),
        ("000001", "2024-01-03", 10.3),
        ("000001", "2024-01-04", 10.8),
        ("000001", "2024-01-05", 11.0),
        ("000002", "2024-01-01", 20.0),
        ("000002", "2024-01-02", 20.5),
        ("000002", "2024-01-03", 20.3),
        ("000002", "2024-01-04", 20.8),
        ("000002", "2024-01-05", 21.0),
    ]
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


@dataclass
class MockBacktestResult:
    """模拟回测结果"""

    strategy_name: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    start_date: str
    end_date: str
    equity_curve: list[dict]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "equity_curve": self.equity_curve,
        }


class TestBenchmarkResult:
    """测试基准对比结果"""

    def test_create_result(self):
        """测试创建结果"""
        result = BenchmarkResult(
            strategy_name="test_strategy",
            strategy_return=0.15,
            benchmark_return=0.10,
            excess_return=0.05,
            strategy_sharpe=1.5,
            benchmark_sharpe=1.0,
            strategy_drawdown=0.05,
            benchmark_drawdown=0.08,
            alpha=0.03,
            beta=0.9,
            correlation=0.85,
            information_ratio=0.5,
            tracking_error=0.02,
        )
        assert result.strategy_name == "test_strategy"
        assert result.excess_return == 0.05

    def test_result_to_dict(self):
        """测试转换为字典"""
        result = BenchmarkResult(
            strategy_name="test_strategy",
            strategy_return=0.155,
            benchmark_return=0.105,
            excess_return=0.055,
            strategy_sharpe=1.555,
            benchmark_sharpe=1.055,
            strategy_drawdown=0.055,
            benchmark_drawdown=0.085,
            alpha=0.035,
            beta=0.95,
            correlation=0.855,
            information_ratio=0.555,
            tracking_error=0.025,
        )
        d = result.to_dict()
        assert d["strategy_return"] == 15.5
        assert d["benchmark_return"] == 10.5
        assert d["excess_return"] == 5.5
        assert d["alpha"] == 3.5


class TestCalculateEqualWeightBenchmark:
    """测试计算等权基准"""

    def test_calculate_benchmark(self, temp_db):
        """测试计算基准"""
        curve = calculate_equal_weight_benchmark(temp_db)

        assert len(curve) > 0
        assert curve[0]["equity"] == 100000.0
        assert curve[-1]["equity"] > 100000.0

    def test_calculate_benchmark_with_dates(self, temp_db):
        """测试指定日期范围"""
        curve = calculate_equal_weight_benchmark(
            temp_db,
            start_date="2024-01-02",
            end_date="2024-01-04",
        )

        assert len(curve) > 0

    def test_calculate_benchmark_empty_db(self):
        """测试空数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE stock_analysis (code TEXT, date TEXT, close REAL)")
        conn.commit()
        conn.close()

        curve = calculate_equal_weight_benchmark(db_path)
        assert curve == []

        db_path.unlink(missing_ok=True)


class TestCompareWithBenchmark:
    """测试与基准对比"""

    def test_compare_with_benchmark(self, temp_db):
        """测试对比"""
        backtest = MockBacktestResult(
            strategy_name="test_strategy",
            total_return=0.15,
            sharpe_ratio=1.5,
            max_drawdown=0.05,
            start_date="2024-01-01",
            end_date="2024-01-05",
            equity_curve=[
                {"date": "2024-01-01", "equity": 100000},
                {"date": "2024-01-02", "equity": 102000},
                {"date": "2024-01-03", "equity": 101000},
                {"date": "2024-01-04", "equity": 103000},
                {"date": "2024-01-05", "equity": 105000},
            ],
        )

        result = compare_with_benchmark(backtest, temp_db)

        assert isinstance(result, BenchmarkResult)
        assert result.strategy_name == "test_strategy"
        assert result.strategy_return == 0.15
        assert isinstance(result.benchmark_return, float)
        assert isinstance(result.excess_return, float)

    def test_compare_with_benchmark_high_correlation(self, temp_db):
        """测试高相关性策略"""
        backtest = MockBacktestResult(
            strategy_name="high_corr_strategy",
            total_return=0.10,
            sharpe_ratio=1.2,
            max_drawdown=0.06,
            start_date="2024-01-01",
            end_date="2024-01-05",
            equity_curve=[
                {"date": "2024-01-01", "equity": 100000},
                {"date": "2024-01-02", "equity": 101000},
                {"date": "2024-01-03", "equity": 100500},
                {"date": "2024-01-04", "equity": 102000},
                {"date": "2024-01-05", "equity": 103000},
            ],
        )

        result = compare_with_benchmark(backtest, temp_db)

        assert result.correlation >= -1.0
        assert result.correlation <= 1.0

    def test_compare_with_benchmark_empty_db(self):
        """测试空数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE stock_analysis (code TEXT, date TEXT, close REAL)")
        conn.commit()
        conn.close()

        backtest = MockBacktestResult(
            strategy_name="test",
            total_return=0.1,
            sharpe_ratio=1.0,
            max_drawdown=0.05,
            start_date="2024-01-01",
            end_date="2024-01-05",
            equity_curve=[{"date": "2024-01-01", "equity": 100000}],
        )

        with pytest.raises(ValueError, match="无法计算"):
            compare_with_benchmark(backtest, db_path)

        db_path.unlink(missing_ok=True)


class TestPrintBenchmarkComparison:
    """测试打印基准对比"""

    def test_print_comparison(self, capsys):
        """测试打印输出"""
        result = BenchmarkResult(
            strategy_name="test_strategy",
            strategy_return=0.15,
            benchmark_return=0.10,
            excess_return=0.05,
            strategy_sharpe=1.5,
            benchmark_sharpe=1.0,
            strategy_drawdown=0.05,
            benchmark_drawdown=0.08,
            alpha=0.03,
            beta=0.9,
            correlation=0.85,
            information_ratio=0.5,
            tracking_error=0.02,
        )

        print_benchmark_comparison(result)

        captured = capsys.readouterr()
        assert "test_strategy" in captured.out
        assert "15.00%" in captured.out or "+15.00%" in captured.out


class TestBenchmarkCalculations:
    """测试基准计算细节"""

    def test_sharpe_calculation(self, temp_db):
        """测试夏普比率计算"""
        backtest = MockBacktestResult(
            strategy_name="test",
            total_return=0.2,
            sharpe_ratio=2.0,
            max_drawdown=0.03,
            start_date="2024-01-01",
            end_date="2024-01-05",
            equity_curve=[
                {"date": "2024-01-01", "equity": 100000},
                {"date": "2024-01-02", "equity": 105000},
                {"date": "2024-01-03", "equity": 103000},
                {"date": "2024-01-04", "equity": 108000},
                {"date": "2024-01-05", "equity": 110000},
            ],
        )

        result = compare_with_benchmark(backtest, temp_db)

        assert result.strategy_sharpe == 2.0
        assert isinstance(result.benchmark_sharpe, float)

    def test_drawdown_calculation(self, temp_db):
        """测试回撤计算"""
        backtest = MockBacktestResult(
            strategy_name="test",
            total_return=0.1,
            sharpe_ratio=1.0,
            max_drawdown=0.05,
            start_date="2024-01-01",
            end_date="2024-01-05",
            equity_curve=[
                {"date": "2024-01-01", "equity": 100000},
                {"date": "2024-01-02", "equity": 105000},
                {"date": "2024-01-03", "equity": 98000},
                {"date": "2024-01-04", "equity": 102000},
                {"date": "2024-01-05", "equity": 108000},
            ],
        )

        result = compare_with_benchmark(backtest, temp_db)

        assert result.strategy_drawdown == 0.05
        assert isinstance(result.benchmark_drawdown, float)

    def test_alpha_beta_calculation(self, temp_db):
        """测试 Alpha Beta 计算"""
        np.random.seed(42)

        backtest = MockBacktestResult(
            strategy_name="test",
            total_return=0.12,
            sharpe_ratio=1.3,
            max_drawdown=0.04,
            start_date="2024-01-01",
            end_date="2024-01-05",
            equity_curve=[
                {"date": "2024-01-01", "equity": 100000},
                {"date": "2024-01-02", "equity": 101500},
                {"date": "2024-01-03", "equity": 100500},
                {"date": "2024-01-04", "equity": 103000},
                {"date": "2024-01-05", "equity": 105000},
            ],
        )

        result = compare_with_benchmark(backtest, temp_db)

        assert isinstance(result.alpha, float)
        assert isinstance(result.beta, float)
        assert result.beta >= 0

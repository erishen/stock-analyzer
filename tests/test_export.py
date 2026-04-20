"""
Tests for Data Export Module.
数据导出模块测试
"""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.utils.export import (
    export_backtest_trades,
    export_market_monitor,
    export_optimization_results,
    export_signals,
    export_stock_scores,
    export_to_csv,
    export_to_json,
)


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@dataclass
class SampleData:
    """测试数据类"""

    code: str
    name: str
    value: float

    def to_dict(self):
        return {"code": self.code, "name": self.name, "value": self.value}


class TestExportToCsv:
    """测试 CSV 导出"""

    def test_export_empty_data(self, temp_dir):
        """测试导出空数据"""
        output_path = temp_dir / "empty.csv"
        result = export_to_csv([], output_path)

        assert result == output_path
        assert output_path.exists()

    def test_export_dict_data(self, temp_dir):
        """测试导出字典数据"""
        data = [
            {"code": "000001", "name": "平安银行", "value": 10.5},
            {"code": "000002", "name": "万科A", "value": 20.3},
        ]
        output_path = temp_dir / "test.csv"

        result = export_to_csv(data, output_path)

        assert result == output_path
        assert output_path.exists()

        with open(output_path, encoding="utf-8") as f:
            content = f.read()
            assert "code" in content
            assert "000001" in content
            assert "平安银行" in content

    def test_export_dataclass(self, temp_dir):
        """测试导出数据类"""
        data = [
            SampleData("000001", "平安银行", 10.5),
            SampleData("000002", "万科A", 20.3),
        ]
        output_path = temp_dir / "test.csv"

        result = export_to_csv(data, output_path)

        assert result == output_path
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
            assert "000001" in content

    def test_export_with_fieldnames(self, temp_dir):
        """测试指定字段名"""
        data = [
            {"code": "000001", "name": "平安银行", "value": 10.5, "extra": "ignore"},
        ]
        output_path = temp_dir / "test.csv"

        export_to_csv(data, output_path, fieldnames=["code", "name"])

        with open(output_path, encoding="utf-8") as f:
            content = f.read()
            assert "extra" not in content
            assert "000001" in content


class TestExportToJson:
    """测试 JSON 导出"""

    def test_export_dict(self, temp_dir):
        """测试导出字典"""
        data = {"code": "000001", "name": "平安银行"}
        output_path = temp_dir / "test.json"

        result = export_to_json(data, output_path)

        assert result == output_path
        with open(output_path, encoding="utf-8") as f:
            loaded = json.load(f)
            assert loaded["code"] == "000001"

    def test_export_list(self, temp_dir):
        """测试导出列表"""
        data = [{"code": "000001"}, {"code": "000002"}]
        output_path = temp_dir / "test.json"

        export_to_json(data, output_path)

        with open(output_path, encoding="utf-8") as f:
            loaded = json.load(f)
            assert len(loaded) == 2

    def test_export_with_to_dict(self, temp_dir):
        """测试带 to_dict 方法的对象"""
        data = SampleData("000001", "平安银行", 10.5)
        output_path = temp_dir / "test.json"

        export_to_json(data, output_path)

        with open(output_path, encoding="utf-8") as f:
            loaded = json.load(f)
            assert loaded["code"] == "000001"


class MockTrade:
    """模拟交易记录"""

    def __init__(self, code, name, profit):
        self.code = code
        self.name = name
        self.profit = profit

    def to_dict(self):
        return {
            "code": self.code,
            "name": self.name,
            "entry_date": "2024-01-01",
            "entry_price": 10.0,
            "exit_date": "2024-01-05",
            "exit_price": 11.0,
            "shares": 100,
            "profit": self.profit,
            "profit_percent": 10.0,
            "holding_days": 5,
            "signal": "test",
            "commission": 5.0,
            "stamp_tax": 1.0,
            "total_cost": 6.0,
        }


class MockBacktestResult:
    """模拟回测结果"""

    def __init__(self, trades):
        self.trades = trades
        self.equity_curve = [
            {"date": "2024-01-01", "equity": 100000},
            {"date": "2024-01-02", "equity": 101000},
        ]
        self._data = {
            "total_return": 0.1,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.05,
        }

    def to_dict(self):
        return {
            **self._data,
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": self.equity_curve,
        }


class TestExportBacktestTrades:
    """测试导出回测交易"""

    def test_export_csv(self, temp_dir):
        """测试导出 CSV"""
        trades = [MockTrade("000001", "平安银行", 100)]
        result = MockBacktestResult(trades)

        paths = export_backtest_trades(result, temp_dir, format="csv")

        assert "trades" in paths
        assert "equity_curve" in paths
        assert "summary" in paths
        assert paths["trades"].exists()

    def test_export_json(self, temp_dir):
        """测试导出 JSON"""
        trades = [MockTrade("000001", "平安银行", 100)]
        result = MockBacktestResult(trades)

        paths = export_backtest_trades(result, temp_dir, format="json")

        assert paths["trades"].suffix == ".json"

    def test_export_no_trades(self, temp_dir):
        """测试无交易记录"""
        result = MockBacktestResult([])

        paths = export_backtest_trades(result, temp_dir)

        assert "trades" not in paths
        assert "summary" in paths


class TestExportSignals:
    """测试导出信号"""

    def test_export_empty(self, temp_dir):
        """测试空信号"""
        output_path = temp_dir / "signals.csv"
        result = export_signals([], output_path)
        assert result == output_path

    def test_export_signals_csv(self, temp_dir):
        """测试导出 CSV 信号"""

        class Signal:
            def to_dict(self):
                return {
                    "code": "000001",
                    "name": "平安银行",
                    "date": "2024-01-01",
                    "signal_type": "MACD金叉",
                    "strength": "strong",
                    "price": 10.5,
                    "volume": 1000000,
                    "description": "test",
                }

        output_path = temp_dir / "signals.csv"
        result = export_signals([Signal()], output_path, format="csv")

        assert result.suffix == ".csv"
        assert result.exists()

    def test_export_signals_json(self, temp_dir):
        """测试导出 JSON 信号"""

        class Signal:
            def to_dict(self):
                return {"code": "000001", "name": "平安银行"}

        output_path = temp_dir / "signals.json"
        result = export_signals([Signal()], output_path, format="json")

        assert result.suffix == ".json"


class TestExportStockScores:
    """测试导出股票评分"""

    def test_export_empty(self, temp_dir):
        """测试空评分"""
        output_path = temp_dir / "scores.csv"
        result = export_stock_scores([], output_path)
        assert result == output_path

    def test_export_scores_csv(self, temp_dir):
        """测试导出 CSV 评分"""

        class Score:
            def to_dict(self):
                return {
                    "rank": 1,
                    "code": "000001",
                    "name": "平安银行",
                    "total_score": 85.5,
                    "trend_score": 90,
                    "momentum_score": 80,
                    "volatility_score": 75,
                    "volume_score": 85,
                    "signal_score": 90,
                    "price": 10.5,
                    "change_percent": 2.5,
                    "recommendation": "买入",
                }

        output_path = temp_dir / "scores.csv"
        result = export_stock_scores([Score()], output_path, format="csv")

        assert result.exists()


class TestExportMarketMonitor:
    """测试导出市场监控"""

    def test_export_monitor(self, temp_dir):
        """测试导出监控数据"""
        monitor_data = {
            "summary": {"total_stocks": 100},
            "oversold_signals": [{"code": "000001"}],
            "golden_cross_signals": [{"code": "000002"}],
        }

        paths = export_market_monitor(monitor_data, temp_dir)

        assert "summary" in paths
        assert "oversold" in paths
        assert "golden_cross" in paths

    def test_export_partial_data(self, temp_dir):
        """测试部分数据"""
        monitor_data = {
            "summary": {"total_stocks": 100},
        }

        paths = export_market_monitor(monitor_data, temp_dir)

        assert "summary" in paths
        assert "oversold" not in paths


class TestExportOptimizationResults:
    """测试导出优化结果"""

    def test_export_empty(self, temp_dir):
        """测试空结果"""
        output_path = temp_dir / "optimization.csv"
        result = export_optimization_results([], output_path)
        assert result == output_path

    def test_export_results_csv(self, temp_dir):
        """测试导出 CSV 结果"""
        results = [
            {
                "total_return": 0.1,
                "sharpe_ratio": 1.5,
                "max_drawdown": 0.05,
                "win_rate": 0.6,
                "total_trades": 100,
                "params": {"lookback": 20, "holding": 5},
            }
        ]

        output_path = temp_dir / "optimization.csv"
        result = export_optimization_results(results, output_path, format="csv")

        assert result.exists()

    def test_export_results_json(self, temp_dir):
        """测试导出 JSON 结果"""
        results = [
            {
                "total_return": 0.1,
                "sharpe_ratio": 1.5,
                "params": {"lookback": 20},
            }
        ]

        output_path = temp_dir / "optimization.json"
        result = export_optimization_results(results, output_path, format="json")

        assert result.suffix == ".json"

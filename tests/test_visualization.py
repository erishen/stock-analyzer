"""
Tests for Strategy Visualization.
策略可视化测试
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from strategy.visualization import (
    BacktestChartData,
    generate_backtest_report,
    plot_drawdown,
    plot_equity_curve,
    plot_monthly_returns,
    plot_trade_distribution,
    visualize_backtest,
)


@pytest.fixture
def sample_chart_data():
    """创建示例图表数据"""
    return BacktestChartData(
        strategy_name="TestStrategy",
        equity_curve=[
            {"date": "2024-01-01", "equity": 100000},
            {"date": "2024-01-02", "equity": 101000},
            {"date": "2024-01-03", "equity": 100500},
            {"date": "2024-01-04", "equity": 102000},
            {"date": "2024-01-05", "equity": 103000},
            {"date": "2024-01-06", "equity": 102500},
            {"date": "2024-01-07", "equity": 104000},
            {"date": "2024-01-08", "equity": 105000},
        ],
        trades=[
            {"profit_percent": 0.05, "holding_days": 3},
            {"profit_percent": -0.02, "holding_days": 2},
            {"profit_percent": 0.03, "holding_days": 5},
            {"profit_percent": -0.01, "holding_days": 1},
            {"profit_percent": 0.08, "holding_days": 4},
        ],
        initial_capital=100000,
        final_capital=105000,
        total_return=5.0,
        max_drawdown=2.0,
        sharpe_ratio=1.5,
        win_rate=60.0,
    )


@pytest.fixture
def sample_json_file(sample_chart_data):
    """创建示例 JSON 文件"""
    data = {
        "strategy_name": sample_chart_data.strategy_name,
        "equity_curve": sample_chart_data.equity_curve,
        "trades": sample_chart_data.trades,
        "initial_capital": sample_chart_data.initial_capital,
        "final_capital": sample_chart_data.final_capital,
        "total_return": sample_chart_data.total_return,
        "max_drawdown": sample_chart_data.max_drawdown,
        "sharpe_ratio": sample_chart_data.sharpe_ratio,
        "win_rate": sample_chart_data.win_rate,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        json_path = Path(f.name)
    yield json_path
    json_path.unlink(missing_ok=True)


class TestBacktestChartData:
    """测试 BacktestChartData 数据类"""

    def test_from_json(self, sample_json_file, sample_chart_data):
        """测试从 JSON 文件加载"""
        result = BacktestChartData.from_json(sample_json_file)

        assert result.strategy_name == sample_chart_data.strategy_name
        assert len(result.equity_curve) == 8
        assert len(result.trades) == 5
        assert result.initial_capital == 100000
        assert result.final_capital == 105000

    def test_from_json_missing_fields(self):
        """测试从 JSON 文件加载缺少字段"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            json_path = Path(f.name)

        try:
            result = BacktestChartData.from_json(json_path)

            assert result.strategy_name == "Unknown"
            assert result.equity_curve == []
            assert result.trades == []
            assert result.initial_capital == 100000
        finally:
            json_path.unlink(missing_ok=True)


class TestPlotEquityCurve:
    """测试资金曲线绘制"""

    def test_plot_equity_curve_basic(self, sample_chart_data):
        """测试基本资金曲线绘制"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "equity_curve.png"

            with patch("strategy.visualization.setup_chinese_font"):
                result = plot_equity_curve(sample_chart_data, output_path)

            assert result == output_path
            assert output_path.exists()

    def test_plot_equity_curve_default_output(self, sample_chart_data):
        """测试默认输出路径"""
        with patch("strategy.visualization.setup_chinese_font"):
            result = plot_equity_curve(sample_chart_data)

        assert result == Path("output/charts/equity_curve.png")

    def test_plot_equity_curve_without_stats(self, sample_chart_data):
        """测试不显示统计信息"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "equity_curve.png"

            with patch("strategy.visualization.setup_chinese_font"):
                result = plot_equity_curve(sample_chart_data, output_path, show_stats=False)

            assert result == output_path


class TestPlotDrawdown:
    """测试回撤绘制"""

    def test_plot_drawdown_basic(self, sample_chart_data):
        """测试基本回撤绘制"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "drawdown.png"

            with patch("strategy.visualization.setup_chinese_font"):
                result = plot_drawdown(sample_chart_data, output_path)

            assert result == output_path
            assert output_path.exists()

    def test_plot_drawdown_empty_equity_curve(self):
        """测试空权益曲线"""
        chart_data = BacktestChartData(
            strategy_name="Empty",
            equity_curve=[],
            trades=[],
            initial_capital=100000,
            final_capital=100000,
            total_return=0,
            max_drawdown=0,
            sharpe_ratio=0,
            win_rate=0,
        )

        with patch("strategy.visualization.setup_chinese_font"):
            result = plot_drawdown(chart_data)

        assert result == Path("")


class TestPlotMonthlyReturns:
    """测试月度收益绘制"""

    def test_plot_monthly_returns_basic(self, sample_chart_data):
        """测试基本月度收益绘制"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "monthly_returns.png"

            with patch("strategy.visualization.setup_chinese_font"):
                result = plot_monthly_returns(sample_chart_data, output_path)

            assert result == output_path
            assert output_path.exists()

    def test_plot_monthly_returns_empty(self):
        """测试空权益曲线"""
        chart_data = BacktestChartData(
            strategy_name="Empty",
            equity_curve=[],
            trades=[],
            initial_capital=100000,
            final_capital=100000,
            total_return=0,
            max_drawdown=0,
            sharpe_ratio=0,
            win_rate=0,
        )

        with patch("strategy.visualization.setup_chinese_font"):
            result = plot_monthly_returns(chart_data)

        assert result == Path("")


class TestPlotTradeDistribution:
    """测试交易分布绘制"""

    def test_plot_trade_distribution_basic(self, sample_chart_data):
        """测试基本交易分布绘制"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "trade_distribution.png"

            with patch("strategy.visualization.setup_chinese_font"):
                result = plot_trade_distribution(sample_chart_data, output_path)

            assert result == output_path
            assert output_path.exists()

    def test_plot_trade_distribution_empty_trades(self):
        """测试空交易列表"""
        chart_data = BacktestChartData(
            strategy_name="Empty",
            equity_curve=[{"date": "2024-01-01", "equity": 100000}],
            trades=[],
            initial_capital=100000,
            final_capital=100000,
            total_return=0,
            max_drawdown=0,
            sharpe_ratio=0,
            win_rate=0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "trade_distribution.png"

            with patch("strategy.visualization.setup_chinese_font"):
                result = plot_trade_distribution(chart_data, output_path)

            assert result == output_path


class TestGenerateBacktestReport:
    """测试回测报告生成"""

    def test_generate_report_basic(self, sample_json_file):
        """测试基本报告生成"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch("strategy.visualization.setup_chinese_font"):
                paths = generate_backtest_report(sample_json_file, output_dir)

            assert "equity_curve" in paths
            assert "trade_distribution" in paths
            assert "monthly_returns" in paths
            assert "drawdown" in paths

    def test_generate_report_default_output(self, sample_json_file):
        """测试默认输出目录"""
        with patch("strategy.visualization.setup_chinese_font"):
            paths = generate_backtest_report(sample_json_file)

        assert len(paths) == 4


class TestVisualizeBacktest:
    """测试回测可视化便捷函数"""

    def test_visualize_backtest_with_file(self, sample_json_file):
        """测试指定文件的可视化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with patch("strategy.visualization.setup_chinese_font"):
                paths = visualize_backtest(sample_json_file, output_dir)

            assert len(paths) == 4

    def test_visualize_backtest_file_not_exists(self):
        """测试文件不存在"""
        with patch("strategy.visualization.setup_chinese_font"):
            paths = visualize_backtest(Path("/nonexistent/file.json"))

        assert paths == {}

    def test_visualize_backtest_default_path(self, sample_json_file):
        """测试默认路径"""
        default_path = Path("output/reports/backtest_report.json")
        default_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(default_path, "w") as f:
                json.dump(
                    {
                        "strategy_name": "DefaultTest",
                        "equity_curve": [{"date": "2024-01-01", "equity": 100000}],
                        "trades": [],
                        "initial_capital": 100000,
                        "final_capital": 100000,
                        "total_return": 0,
                        "max_drawdown": 0,
                        "sharpe_ratio": 0,
                        "win_rate": 0,
                    },
                    f,
                )

            with patch("strategy.visualization.setup_chinese_font"):
                paths = visualize_backtest()

            assert len(paths) == 4
        finally:
            if default_path.exists():
                default_path.unlink()

"""
Tests for Trade Report.
交易报告测试
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from strategy.trade_report import (
    MonthlyPerformance,
    StockPerformance,
    TradeReport,
    TradeStatistics,
    generate_trade_report,
    print_trade_report,
    save_trade_report,
)


@dataclass
class MockTrade:
    """模拟交易"""

    code: str
    name: str
    entry_date: str
    exit_date: str
    profit: float
    profit_percent: float
    holding_days: int


@dataclass
class MockBacktestResult:
    """模拟回测结果"""

    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    trades: list


@pytest.fixture
def sample_backtest_result():
    """创建示例回测结果"""
    return MockBacktestResult(
        strategy_name="动量策略",
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=100000,
        final_capital=110000,
        total_return=0.10,
        trades=[
            MockTrade(
                code="000001",
                name="平安银行",
                entry_date="2024-01-05",
                exit_date="2024-01-10",
                profit=500,
                profit_percent=0.05,
                holding_days=5,
            ),
            MockTrade(
                code="000002",
                name="万科A",
                entry_date="2024-01-15",
                exit_date="2024-01-18",
                profit=-200,
                profit_percent=-0.02,
                holding_days=3,
            ),
            MockTrade(
                code="000001",
                name="平安银行",
                entry_date="2024-02-01",
                exit_date="2024-02-06",
                profit=300,
                profit_percent=0.03,
                holding_days=5,
            ),
            MockTrade(
                code="000003",
                name="国农科技",
                entry_date="2024-02-10",
                exit_date="2024-02-12",
                profit=0,
                profit_percent=0,
                holding_days=2,
            ),
        ],
    )


@pytest.fixture
def empty_backtest_result():
    """创建空回测结果"""
    return MockBacktestResult(
        strategy_name="空策略",
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=100000,
        final_capital=100000,
        total_return=0,
        trades=[],
    )


class TestTradeStatistics:
    """测试交易统计"""

    def test_create_statistics(self):
        """测试创建统计"""
        stats = TradeStatistics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            even_trades=0,
            win_rate=0.60,
            avg_profit=0.05,
            avg_loss=-0.02,
            avg_holding_days=5.0,
            max_profit_trade=0.15,
            max_loss_trade=-0.08,
            profit_factor=2.5,
            expectancy=0.02,
        )

        assert stats.total_trades == 100
        assert stats.win_rate == 0.60
        assert stats.profit_factor == 2.5

    def test_to_dict(self):
        """测试转换为字典"""
        stats = TradeStatistics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            even_trades=0,
            win_rate=0.60,
            avg_profit=0.05,
            avg_loss=-0.02,
            avg_holding_days=5.0,
            max_profit_trade=0.15,
            max_loss_trade=-0.08,
            profit_factor=2.5,
            expectancy=0.02,
        )

        d = stats.to_dict()
        assert d["total_trades"] == 100
        assert d["win_rate"] == 60.0
        assert d["avg_profit"] == 5.0
        assert d["avg_loss"] == -2.0


class TestMonthlyPerformance:
    """测试月度表现"""

    def test_create_monthly(self):
        """测试创建月度表现"""
        monthly = MonthlyPerformance(
            month="2024-01",
            trades=20,
            wins=12,
            losses=8,
            return_pct=0.05,
            win_rate=0.60,
        )

        assert monthly.month == "2024-01"
        assert monthly.trades == 20

    def test_to_dict(self):
        """测试转换为字典"""
        monthly = MonthlyPerformance(
            month="2024-01",
            trades=20,
            wins=12,
            losses=8,
            return_pct=0.05,
            win_rate=0.60,
        )

        d = monthly.to_dict()
        assert d["month"] == "2024-01"
        assert d["return_pct"] == 5.0
        assert d["win_rate"] == 60.0


class TestStockPerformance:
    """测试个股表现"""

    def test_create_stock(self):
        """测试创建个股表现"""
        stock = StockPerformance(
            code="000001",
            name="平安银行",
            trades=10,
            wins=6,
            losses=4,
            total_profit=0.08,
            win_rate=0.60,
            avg_return=0.02,
        )

        assert stock.code == "000001"
        assert stock.trades == 10

    def test_to_dict(self):
        """测试转换为字典"""
        stock = StockPerformance(
            code="000001",
            name="平安银行",
            trades=10,
            wins=6,
            losses=4,
            total_profit=0.08,
            win_rate=0.60,
            avg_return=0.02,
        )

        d = stock.to_dict()
        assert d["code"] == "000001"
        assert d["total_profit"] == 8.0
        assert d["win_rate"] == 60.0


class TestTradeReport:
    """测试交易报告"""

    def test_create_report(self):
        """测试创建报告"""
        stats = TradeStatistics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            even_trades=0,
            win_rate=0.60,
            avg_profit=0.05,
            avg_loss=-0.02,
            avg_holding_days=5.0,
            max_profit_trade=0.15,
            max_loss_trade=-0.08,
            profit_factor=2.5,
            expectancy=0.02,
        )

        report = TradeReport(
            strategy_name="动量策略",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            final_capital=110000,
            total_return=0.10,
            statistics=stats,
            monthly_performance=[],
            top_winners=[],
            top_losers=[],
            stock_performance=[],
            holding_distribution={},
            weekday_performance={},
        )

        assert report.strategy_name == "动量策略"
        assert report.statistics.total_trades == 100
        assert report.initial_capital == 100000

    def test_to_dict(self):
        """测试转换为字典"""
        stats = TradeStatistics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            even_trades=0,
            win_rate=0.60,
            avg_profit=0.05,
            avg_loss=-0.02,
            avg_holding_days=5.0,
            max_profit_trade=0.15,
            max_loss_trade=-0.08,
            profit_factor=2.5,
            expectancy=0.02,
        )

        report = TradeReport(
            strategy_name="动量策略",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            final_capital=110000,
            total_return=0.10,
            statistics=stats,
            monthly_performance=[],
            top_winners=[],
            top_losers=[],
            stock_performance=[],
            holding_distribution={},
            weekday_performance={},
        )

        d = report.to_dict()
        assert d["strategy_name"] == "动量策略"
        assert d["total_return"] == 10.0


class TestGenerateTradeReport:
    """测试生成交易报告"""

    def test_generate_report_basic(self, sample_backtest_result):
        """测试基本报告生成"""
        report = generate_trade_report(sample_backtest_result)

        assert report.strategy_name == "动量策略"
        assert report.statistics.total_trades == 4
        assert report.statistics.winning_trades == 2
        assert report.statistics.losing_trades == 1
        assert report.statistics.even_trades == 1
        assert len(report.monthly_performance) == 2
        assert len(report.stock_performance) == 3

    def test_generate_report_empty(self, empty_backtest_result):
        """测试空交易列表"""
        report = generate_trade_report(empty_backtest_result)

        assert report.statistics.total_trades == 0
        assert report.statistics.winning_trades == 0
        assert report.statistics.losing_trades == 0

    def test_generate_report_top_trades(self, sample_backtest_result):
        """测试 Top 交易"""
        report = generate_trade_report(sample_backtest_result)

        assert len(report.top_winners) > 0
        assert len(report.top_losers) > 0
        assert report.top_winners[0]["profit_pct"] > 0

    def test_generate_report_holding_distribution(self, sample_backtest_result):
        """测试持仓分布"""
        report = generate_trade_report(sample_backtest_result)

        assert len(report.holding_distribution) > 0


class TestPrintTradeReport:
    """测试打印交易报告"""

    def test_print_report(self, sample_backtest_result):
        """测试打印报告"""
        report = generate_trade_report(sample_backtest_result)

        with patch("builtins.print"):
            print_trade_report(report)

    def test_print_empty_report(self, empty_backtest_result):
        """测试打印空报告"""
        report = generate_trade_report(empty_backtest_result)

        with patch("builtins.print"):
            print_trade_report(report)


class TestSaveTradeReport:
    """测试保存交易报告"""

    def test_save_report_json(self, sample_backtest_result):
        """测试保存 JSON 报告"""
        report = generate_trade_report(sample_backtest_result)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.json"
            save_trade_report(report, output_path)

            assert output_path.exists()

    def test_save_report_creates_directory(self, sample_backtest_result):
        """测试保存报告创建目录"""
        report = generate_trade_report(sample_backtest_result)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "subdir" / "report.json"
            save_trade_report(report, output_path)

            assert output_path.exists()
            assert output_path.parent.is_dir()

"""
Tests for Risk Control Module.
风控模块测试
"""

import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


from strategy.risk_control import (
    PortfolioOptimizationResult,
    PortfolioOptimizer,
    PositionLimit,
    PositionSizer,
    RiskAttributionResult,
    RiskAttributor,
    SignalBacktester,
    SignalBacktestResult,
    create_position_limit,
    run_signal_backtest,
)


class TestPositionLimit:
    """测试持仓限制配置"""

    def test_default_values(self):
        """测试默认值"""
        limit = PositionLimit()
        assert limit.max_positions == 10
        assert limit.max_single_position_pct == 0.15
        assert limit.max_sector_position_pct == 0.30
        assert limit.min_position_pct == 0.02

    def test_custom_values(self):
        """测试自定义值"""
        limit = PositionLimit(
            max_positions=20,
            max_single_position_pct=0.20,
            max_sector_position_pct=0.40,
            min_position_pct=0.05,
        )
        assert limit.max_positions == 20
        assert limit.max_single_position_pct == 0.20
        assert limit.max_sector_position_pct == 0.40
        assert limit.min_position_pct == 0.05

    def test_create_position_limit(self):
        """测试便捷创建函数"""
        limit = create_position_limit(
            max_positions=15,
            max_single_position_pct=0.12,
            max_sector_position_pct=0.25,
        )
        assert limit.max_positions == 15
        assert limit.max_single_position_pct == 0.12
        assert limit.max_sector_position_pct == 0.25


class TestSignalBacktestResult:
    """测试信号回测结果"""

    def test_create_result(self):
        """测试创建结果"""
        result = SignalBacktestResult(
            signal_type="MACD金叉",
            total_signals=100,
            winning_signals=60,
            losing_signals=40,
            win_rate=0.6,
            avg_return=0.05,
            avg_holding_days=5.0,
            max_return=0.20,
            max_loss=-0.10,
            profit_factor=1.5,
            sharpe_ratio=1.2,
        )
        assert result.signal_type == "MACD金叉"
        assert result.total_signals == 100
        assert result.win_rate == 0.6

    def test_to_dict(self):
        """测试转换为字典"""
        result = SignalBacktestResult(
            signal_type="MACD金叉",
            total_signals=100,
            winning_signals=60,
            losing_signals=40,
            win_rate=0.6,
            avg_return=0.05,
            avg_holding_days=5.0,
            max_return=0.20,
            max_loss=-0.10,
            profit_factor=1.5,
            sharpe_ratio=1.2,
        )
        d = result.to_dict()
        assert d["signal_type"] == "MACD金叉"
        assert d["win_rate"] == 60.0
        assert d["avg_return"] == 5.0


class TestSignalBacktester:
    """测试信号回测器"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                change_percent REAL
            )
        """)

        for i in range(20):
            conn.execute(
                """
                INSERT INTO stock_analysis (code, date, open, close, high, low, volume, change_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "000001",
                    f"2024-01-{i + 1:02d}",
                    10.0 + i * 0.1,
                    10.0 + i * 0.1 + 0.05,
                    10.0 + i * 0.1 + 0.1,
                    10.0 + i * 0.1 - 0.05,
                    1000000,
                    0.5,
                ),
            )

        conn.commit()
        conn.close()

        yield db_path

        db_path.unlink(missing_ok=True)

    def test_init(self, temp_db):
        """测试初始化"""
        backtester = SignalBacktester(temp_db)
        assert backtester.db_path == temp_db

    def test_connect_and_close(self, temp_db):
        """测试连接和关闭"""
        backtester = SignalBacktester(temp_db)
        backtester.connect()
        assert backtester.conn is not None
        backtester.close()
        backtester.conn = None

    def test_backtest_signal(self, temp_db):
        """测试信号回测"""
        backtester = SignalBacktester(temp_db)
        backtester.connect()

        result = backtester.backtest_signal("MACD金叉", holding_days=5)

        assert isinstance(result, SignalBacktestResult)
        assert result.signal_type == "MACD金叉"

        backtester.close()

    def test_backtest_signal_empty_db(self):
        """测试空数据库回测"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                change_percent REAL
            )
        """)
        conn.commit()
        conn.close()

        backtester = SignalBacktester(db_path)
        backtester.connect()

        result = backtester.backtest_signal("MACD金叉", holding_days=5)

        assert result.total_signals == 0
        assert result.win_rate == 0

        backtester.close()
        db_path.unlink(missing_ok=True)


class TestPortfolioOptimizer:
    """测试组合优化器"""

    def test_equal_weight(self):
        """测试等权重分配"""
        optimizer = PortfolioOptimizer()
        weights = optimizer.equal_weight(["000001", "000002", "000003"])

        assert len(weights) == 3
        assert abs(weights["000001"] - 1 / 3) < 0.001
        assert abs(weights["000002"] - 1 / 3) < 0.001
        assert abs(weights["000003"] - 1 / 3) < 0.001

    def test_equal_weight_single(self):
        """测试单个资产等权重"""
        optimizer = PortfolioOptimizer()
        weights = optimizer.equal_weight(["000001"])

        assert len(weights) == 1
        assert weights["000001"] == 1.0

    def test_risk_parity(self):
        """测试风险平价"""
        optimizer = PortfolioOptimizer()
        volatilities = {
            "000001": 0.02,
            "000002": 0.04,
            "000003": 0.01,
        }
        weights = optimizer.risk_parity(["000001", "000002", "000003"], volatilities)

        assert len(weights) == 3
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001

        assert weights["000003"] > weights["000001"]
        assert weights["000001"] > weights["000002"]

    def test_optimize_with_constraints(self):
        """测试带约束优化"""
        optimizer = PortfolioOptimizer()
        position_limit = PositionLimit(max_positions=5, max_single_position_pct=0.20)

        assets = ["000001", "000002", "000003", "000004", "000005"]
        expected_returns = {a: 0.01 for a in assets}
        volatilities = {a: 0.02 for a in assets}

        correlations = np.eye(5)

        result = optimizer.optimize_with_constraints(
            assets=assets,
            expected_returns=expected_returns,
            volatilities=volatilities,
            correlations=pd.DataFrame(correlations, index=assets, columns=assets),
            position_limit=position_limit,
        )

        assert isinstance(result, PortfolioOptimizationResult)
        assert len(result.weights) <= position_limit.max_positions

        for weight in result.weights.values():
            assert weight <= position_limit.max_single_position_pct + 0.001

    def test_optimize_empty_assets(self):
        """测试空资产列表"""
        optimizer = PortfolioOptimizer()
        position_limit = PositionLimit()

        result = optimizer.optimize_with_constraints(
            assets=[],
            expected_returns={},
            volatilities={},
            correlations=pd.DataFrame(),
            position_limit=position_limit,
        )

        assert result.expected_return == 0
        assert result.expected_volatility == 0


class TestRiskAttributor:
    """测试风险归因分析器"""

    def test_calculate_risk_attribution(self):
        """测试风险归因计算"""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=100)
        assets = ["000001", "000002", "000003"]
        returns_data = pd.DataFrame(
            np.random.randn(100, 3) * 0.02,
            index=dates,
            columns=assets,
        )
        weights = {a: 1 / 3 for a in assets}

        attributor = RiskAttributor(returns_data, weights)
        result = attributor.calculate_risk_attribution()

        assert isinstance(result, RiskAttributionResult)
        assert result.total_risk >= 0
        assert result.systematic_risk >= 0
        assert result.idiosyncratic_risk >= 0

    def test_calculate_risk_attribution_empty(self):
        """测试空数据风险归因"""
        returns_data = pd.DataFrame()
        weights = {}

        attributor = RiskAttributor(returns_data, weights)
        result = attributor.calculate_risk_attribution()

        assert result.total_risk == 0
        assert result.systematic_risk == 0


class TestPositionSizer:
    """测试仓位管理器"""

    def test_apply_limits_single_position(self):
        """测试单只股票仓位限制"""
        limit = PositionLimit(max_single_position_pct=0.15)
        sizer = PositionSizer(limit)

        weights = {"000001": 0.20, "000002": 0.10, "000003": 0.05}
        adjusted = sizer.apply_limits(weights)

        assert adjusted["000001"] == 0.15

    def test_apply_limits_sector(self):
        """测试行业仓位限制"""
        limit = PositionLimit(max_sector_position_pct=0.30)
        sizer = PositionSizer(limit)

        weights = {"000001": 0.20, "000002": 0.20, "000003": 0.10}
        sector_mapping = {"000001": "科技", "000002": "科技", "000003": "金融"}

        adjusted = sizer.apply_limits(weights, sector_mapping)

        sector_weights = {}
        for asset, weight in adjusted.items():
            sector = sector_mapping.get(asset, "未知")
            sector_weights[sector] = sector_weights.get(sector, 0) + weight

        assert sector_weights.get("科技", 0) <= 0.30 + 0.001

    def test_kelly_criterion(self):
        """测试凯利公式"""
        limit = PositionLimit(max_single_position_pct=0.20)
        sizer = PositionSizer(limit)

        kelly = sizer.kelly_criterion(
            win_rate=0.6,
            avg_win=0.10,
            avg_loss=0.05,
            fraction=0.5,
        )

        assert kelly > 0
        assert kelly <= limit.max_single_position_pct

    def test_kelly_criterion_zero_loss(self):
        """测试零亏损凯利公式"""
        limit = PositionLimit()
        sizer = PositionSizer(limit)

        kelly = sizer.kelly_criterion(
            win_rate=0.6,
            avg_win=0.10,
            avg_loss=0,
        )

        assert kelly == 0

    def test_volatility_targeting(self):
        """测试波动率目标仓位"""
        limit = PositionLimit(max_single_position_pct=0.20)
        sizer = PositionSizer(limit)

        new_weight = sizer.volatility_targeting(
            target_volatility=0.02,
            current_volatility=0.04,
            current_weight=0.10,
        )

        assert new_weight == 0.05

    def test_volatility_targeting_zero_vol(self):
        """测试零波动率目标仓位"""
        limit = PositionLimit()
        sizer = PositionSizer(limit)

        new_weight = sizer.volatility_targeting(
            target_volatility=0.02,
            current_volatility=0,
            current_weight=0.10,
        )

        assert new_weight == 0.10


class TestRunSignalBacktest:
    """测试信号回测便捷函数"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                change_percent REAL
            )
        """)
        conn.commit()
        conn.close()

        yield db_path
        db_path.unlink(missing_ok=True)

    def test_run_signal_backtest_single(self, temp_db):
        """测试单个信号回测"""
        result = run_signal_backtest(temp_db, signal_type="MACD金叉", holding_days=5)
        assert isinstance(result, SignalBacktestResult)

    def test_run_signal_backtest_all(self, temp_db):
        """测试所有信号回测"""
        results = run_signal_backtest(temp_db, signal_type=None, holding_days=5)
        assert isinstance(results, list)

"""
Tests for Scanner Accuracy.
信号准确率分析测试
"""

import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest


from scanner.accuracy import (
    AccuracyReport,
    SignalAccuracyAnalyzer,
    SignalPerformance,
)
from scanner.signals import SignalType


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_analysis (
            date TEXT,
            code TEXT,
            close REAL,
            high REAL,
            low REAL,
            open REAL,
            volume REAL,
            macd REAL,
            macd_signal REAL,
            rsi REAL,
            kdj_k REAL,
            kdj_d REAL,
            ma5 REAL,
            ma10 REAL,
            ma20 REAL,
            boll_upper REAL,
            boll_lower REAL
        )
    """)

    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    for i, date in enumerate(dates):
        date_str = date.strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT INTO stock_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                date_str,
                "000001",
                10.0 + i * 0.1,
                10.5 + i * 0.1,
                9.5 + i * 0.1,
                10.0 + i * 0.1,
                1000000,
                0.1 + i * 0.01,
                0.05 + i * 0.01,
                50.0 + (i % 30),
                50.0 + (i % 20),
                45.0 + (i % 15),
                10.0 + i * 0.1,
                9.8 + i * 0.1,
                9.5 + i * 0.1,
                11.0 + i * 0.1,
                9.0 + i * 0.1,
            ),
        )

    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


class TestSignalPerformance:
    """测试信号表现"""

    def test_create_performance(self):
        """测试创建信号表现"""
        perf = SignalPerformance(
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            total_signals=100,
            win_count=60,
            loss_count=40,
            win_rate=0.60,
            avg_return=0.05,
            avg_win_return=0.08,
            avg_loss_return=-0.03,
            max_return=0.20,
            max_loss=-0.10,
            best_holding_days=5,
        )

        assert perf.signal_type == SignalType.MACD_GOLDEN_CROSS
        assert perf.total_signals == 100
        assert perf.win_rate == 0.60

    def test_performance_to_dict(self):
        """测试信号表现转字典"""
        perf = SignalPerformance(
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            total_signals=100,
            win_count=60,
            loss_count=40,
            win_rate=0.60,
            avg_return=0.05,
            avg_win_return=0.08,
            avg_loss_return=-0.03,
            max_return=0.20,
            max_loss=-0.10,
            best_holding_days=5,
        )

        d = perf.to_dict()

        assert d["signal_type"] == "MACD金叉"
        assert d["total_signals"] == 100
        assert d["win_rate"] == 60.0
        assert d["avg_return"] == 5.0

    def test_performance_defaults(self):
        """测试信号表现默认值"""
        perf = SignalPerformance(signal_type=SignalType.RSI_OVERSOLD)

        assert perf.total_signals == 0
        assert perf.win_count == 0
        assert perf.win_rate == 0.0
        assert perf.returns_by_days == {}


class TestAccuracyReport:
    """测试准确率报告"""

    def test_create_report(self):
        """测试创建准确率报告"""
        perfs = [
            SignalPerformance(
                signal_type=SignalType.MACD_GOLDEN_CROSS,
                total_signals=50,
                win_count=30,
                win_rate=0.60,
            )
        ]

        report = AccuracyReport(
            analysis_date="2024-01-01",
            total_signals_analyzed=50,
            date_range="2023-01-01 ~ 2024-01-01",
            signal_performances=perfs,
            overall_win_rate=0.60,
            best_signal="MACD金叉",
            worst_signal="RSI超买",
            recommendations=["建议关注MACD金叉信号"],
        )

        assert report.analysis_date == "2024-01-01"
        assert report.total_signals_analyzed == 50
        assert report.overall_win_rate == 0.60

    def test_report_to_dict(self):
        """测试准确率报告转字典"""
        perfs = [
            SignalPerformance(
                signal_type=SignalType.MACD_GOLDEN_CROSS,
                total_signals=50,
                win_count=30,
                win_rate=0.60,
            )
        ]

        report = AccuracyReport(
            analysis_date="2024-01-01",
            total_signals_analyzed=50,
            date_range="2023-01-01 ~ 2024-01-01",
            signal_performances=perfs,
            overall_win_rate=0.60,
            best_signal="MACD金叉",
            worst_signal="RSI超买",
            recommendations=["建议关注MACD金叉信号"],
        )

        d = report.to_dict()

        assert d["analysis_date"] == "2024-01-01"
        assert d["total_signals_analyzed"] == 50
        assert d["overall_win_rate"] == 60.0
        assert len(d["signal_performances"]) == 1


class TestSignalAccuracyAnalyzer:
    """测试信号准确率分析器"""

    def test_init(self, temp_db):
        """测试初始化"""
        analyzer = SignalAccuracyAnalyzer(temp_db)

        assert analyzer.db_path == temp_db
        assert analyzer.conn is None

    def test_connect(self, temp_db):
        """测试连接数据库"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        assert analyzer.conn is not None

        analyzer.close()

    def test_connect_db_not_exists(self):
        """测试连接不存在的数据库"""
        analyzer = SignalAccuracyAnalyzer(Path("/nonexistent/db.db"))

        with pytest.raises(FileNotFoundError):
            analyzer.connect()

    def test_close(self, temp_db):
        """测试关闭连接"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()
        analyzer.close()

    def test_get_stock_data(self, temp_db):
        """测试获取股票数据"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 60

        analyzer.close()

    def test_detect_signal_at_date(self, temp_db):
        """测试检测指定日期信号"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        signals = analyzer.detect_signal_at_date(df, 30)

        assert isinstance(signals, list)

        analyzer.close()

    def test_detect_signal_at_boundary(self, temp_db):
        """测试边界条件检测信号"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        signals = analyzer.detect_signal_at_date(df, 0)
        assert signals == []

        signals = analyzer.detect_signal_at_date(df, len(df))
        assert signals == []

        analyzer.close()

    def test_calculate_future_return(self, temp_db):
        """测试计算未来收益"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        ret = analyzer.calculate_future_return(df, 30, 5)

        assert ret is not None
        assert isinstance(ret, float)

        analyzer.close()

    def test_calculate_future_return_out_of_range(self, temp_db):
        """测试计算未来收益超出范围"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        ret = analyzer.calculate_future_return(df, 55, 10)

        assert ret is None

        analyzer.close()

    def test_analyze_signal_performance(self, temp_db):
        """测试分析信号表现"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        result = analyzer.analyze_signal_performance(df, SignalType.MACD_GOLDEN_CROSS)

        assert isinstance(result, dict)
        assert "signal_type" in result
        assert "total_signals" in result
        assert "win_rate" in result

        analyzer.close()

    def test_find_best_holding_period(self, temp_db):
        """测试找到最佳持有天数"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        period = analyzer.find_best_holding_period("000001", SignalType.MACD_GOLDEN_CROSS)

        assert isinstance(period, int)
        assert period in [1, 3, 5, 10, 20]

        analyzer.close()

    def test_generate_report(self, temp_db):
        """测试生成准确率报告"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        report = analyzer.generate_report(holding_days=5)

        assert isinstance(report, AccuracyReport)
        assert report.analysis_date is not None

        analyzer.close()


class TestBullishBearishSignals:
    """测试多空信号分类"""

    def test_bullish_signals_list(self):
        """测试看涨信号列表"""
        bullish = SignalAccuracyAnalyzer.BULLISH_SIGNALS

        assert SignalType.MACD_GOLDEN_CROSS in bullish
        assert SignalType.RSI_OVERSOLD in bullish
        assert SignalType.TREND_UP in bullish

    def test_bearish_signals_list(self):
        """测试看跌信号列表"""
        bearish = SignalAccuracyAnalyzer.BEARISH_SIGNALS

        assert SignalType.MACD_DEATH_CROSS in bearish
        assert SignalType.RSI_OVERBOUGHT in bearish
        assert SignalType.TREND_DOWN in bearish

    def test_holding_periods(self):
        """测试持有周期"""
        periods = SignalAccuracyAnalyzer.HOLDING_PERIODS

        assert 1 in periods
        assert 5 in periods
        assert 10 in periods

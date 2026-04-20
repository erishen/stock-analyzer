"""
Tests for Signal Accuracy Analyzer Module.
信号准确率分析模块测试
"""

import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.scanner.accuracy import (
    AccuracyReport,
    SignalAccuracyAnalyzer,
    SignalPerformance,
)
from src.scanner.signals import SignalType


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

    test_data = [
        ("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.0, 1000000, 0.05, 0.03, 45.0, 50.0, 45.0, 10.0, 9.9, 9.8, 10.5, 9.5),
        ("000001", "2024-01-02", 10.5, 10.8, 10.2, 10.3, 1200000, 0.08, 0.05, 50.0, 55.0, 50.0, 10.2, 10.0, 9.9, 10.8, 9.8),
        ("000001", "2024-01-03", 10.3, 10.5, 10.0, 10.4, 1100000, 0.10, 0.08, 55.0, 52.0, 55.0, 10.3, 10.1, 10.0, 10.6, 9.9),
        ("000001", "2024-01-04", 10.8, 11.0, 10.5, 10.6, 1300000, 0.12, 0.10, 48.0, 58.0, 52.0, 10.5, 10.2, 10.1, 11.0, 10.0),
        ("000001", "2024-01-05", 11.0, 11.2, 10.8, 10.9, 1400000, 0.15, 0.12, 52.0, 60.0, 55.0, 10.8, 10.4, 10.2, 11.2, 10.2),
    ]
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


class TestSignalPerformance:
    """测试信号表现数据类"""

    def test_create_performance(self):
        """测试创建信号表现"""
        perf = SignalPerformance(
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            total_signals=100,
            win_count=60,
            loss_count=40,
            win_rate=0.6,
            avg_return=0.05,
        )
        assert perf.signal_type == SignalType.MACD_GOLDEN_CROSS
        assert perf.total_signals == 100
        assert perf.win_rate == 0.6

    def test_performance_to_dict(self):
        """测试转换为字典"""
        perf = SignalPerformance(
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            total_signals=100,
            win_count=60,
            loss_count=40,
            win_rate=0.6,
            avg_return=0.055,
            avg_win_return=0.08,
            avg_loss_return=-0.03,
            max_return=0.15,
            max_loss=-0.08,
            best_holding_days=5,
        )
        d = perf.to_dict()
        assert d["signal_type"] == "MACD金叉"
        assert d["total_signals"] == 100
        assert d["win_rate"] == 60.0
        assert d["avg_return"] == 5.5


class TestAccuracyReport:
    """测试准确率报告"""

    def test_create_report(self):
        """测试创建报告"""
        report = AccuracyReport(
            analysis_date="2024-01-05",
            total_signals_analyzed=100,
            date_range="2024-01-01 ~ 2024-01-05",
            signal_performances=[],
            overall_win_rate=0.55,
            best_signal="MACD金叉",
            worst_signal="RSI超买",
            recommendations=["建议1", "建议2"],
        )
        assert report.analysis_date == "2024-01-05"
        assert report.total_signals_analyzed == 100

    def test_report_to_dict(self):
        """测试转换为字典"""
        perf = SignalPerformance(
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            total_signals=50,
            win_count=30,
            win_rate=0.6,
        )
        report = AccuracyReport(
            analysis_date="2024-01-05",
            total_signals_analyzed=50,
            date_range="2024-01-01 ~ 2024-01-05",
            signal_performances=[perf],
            overall_win_rate=0.6,
            best_signal="MACD金叉",
            worst_signal="RSI超买",
            recommendations=["建议"],
        )
        d = report.to_dict()
        assert d["analysis_date"] == "2024-01-05"
        assert d["overall_win_rate"] == 60.0
        assert len(d["signal_performances"]) == 1


class TestSignalAccuracyAnalyzer:
    """测试信号准确率分析器"""

    def test_init(self, temp_db):
        """测试初始化"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        assert analyzer.db_path == temp_db
        assert analyzer.conn is None

    def test_bullish_signals_constant(self, temp_db):
        """测试看涨信号常量"""
        bullish_values = [s.value for s in SignalAccuracyAnalyzer.BULLISH_SIGNALS]
        assert "MACD金叉" in bullish_values
        assert "RSI超卖" in bullish_values

    def test_bearish_signals_constant(self, temp_db):
        """测试看跌信号常量"""
        bearish_values = [s.value for s in SignalAccuracyAnalyzer.BEARISH_SIGNALS]
        assert "MACD死叉" in bearish_values
        assert "RSI超买" in bearish_values

    def test_connect(self, temp_db):
        """测试连接"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()
        assert analyzer.conn is not None
        analyzer.close()

    def test_connect_db_not_exists(self):
        """测试数据库不存在"""
        analyzer = SignalAccuracyAnalyzer(Path("/nonexistent/path.db"))
        with pytest.raises(FileNotFoundError):
            analyzer.connect()

    def test_close(self, temp_db):
        """测试关闭"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()
        analyzer.close()

    def test_get_stock_data(self, temp_db):
        """测试获取股票数据"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert "date" in df.columns
        assert "close" in df.columns

        analyzer.close()

    def test_get_stock_data_empty(self, temp_db):
        """测试获取不存在的股票数据"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("999999")

        assert df.empty

        analyzer.close()

    def test_detect_signal_at_date(self, temp_db):
        """测试检测信号"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        signals = analyzer.detect_signal_at_date(df, 1)
        assert isinstance(signals, list)

        analyzer.close()

    def test_detect_signal_out_of_range(self, temp_db):
        """测试索引超出范围"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        signals = analyzer.detect_signal_at_date(df, 0)
        assert signals == []

        signals = analyzer.detect_signal_at_date(df, 100)
        assert signals == []

        analyzer.close()

    def test_calculate_future_return(self, temp_db):
        """测试计算未来收益"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        ret = analyzer.calculate_future_return(df, 0, 1)
        assert isinstance(ret, float)

        ret = analyzer.calculate_future_return(df, 0, 100)
        assert ret is None

        analyzer.close()

    def test_analyze_signal_performance(self, temp_db):
        """测试分析信号表现"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        result = analyzer.analyze_signal_performance(
            df=df,
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            holding_days=2,
        )

        assert isinstance(result, dict)
        assert "signal_type" in result

        analyzer.close()

    def test_analyze_all_signals(self, temp_db):
        """测试分析所有信号"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        result = analyzer.analyze_all_signals(holding_days=2)

        assert result is not None
        analyzer.close()


class TestSignalDetection:
    """测试信号检测逻辑"""

    def test_detect_macd_golden_cross(self, temp_db):
        """测试 MACD 金叉检测"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        for i in range(1, len(df)):
            signals = analyzer.detect_signal_at_date(df, i)
            for s in signals:
                if s == SignalType.MACD_GOLDEN_CROSS:
                    assert df.iloc[i]["macd"] > df.iloc[i]["macd_signal"]

        analyzer.close()

    def test_detect_rsi_oversold(self, temp_db):
        """测试 RSI 超卖检测"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        for i in range(1, len(df)):
            signals = analyzer.detect_signal_at_date(df, i)
            for s in signals:
                if s == SignalType.RSI_OVERSOLD:
                    assert df.iloc[i]["rsi"] < 30

        analyzer.close()

    def test_detect_trend_up(self, temp_db):
        """测试上升趋势检测"""
        analyzer = SignalAccuracyAnalyzer(temp_db)
        analyzer.connect()

        df = analyzer.get_stock_data("000001")

        for i in range(1, len(df)):
            signals = analyzer.detect_signal_at_date(df, i)
            for s in signals:
                if s == SignalType.TREND_UP:
                    row = df.iloc[i]
                    assert row["ma5"] > row["ma10"] > row["ma20"]

        analyzer.close()

"""
Tests for Signal Scanner.
信号扫描器测试
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scanner.signals import (
    MarketScanner,
    ScanResult,
    Signal,
    SignalDetector,
    SignalStrength,
    SignalType,
)


@pytest.fixture
def sample_stock_data():
    """创建示例股票数据 (含技术指标)"""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    np.random.seed(42)

    close = 10 + np.cumsum(np.random.randn(100) * 0.5)

    data = {
        "code": ["sh600000"] * 100,
        "date": dates,
        "open": close + np.random.uniform(-0.5, 0.5, 100),
        "close": close,
        "high": close + np.random.uniform(0, 1, 100),
        "low": close - np.random.uniform(0, 1, 100),
        "volume": np.random.uniform(100000, 500000, 100),
        "amount": np.random.uniform(1000000, 5000000, 100),
        "change_percent": np.random.uniform(-5, 5, 100),
        "ma5": pd.Series(close).rolling(5).mean(),
        "ma10": pd.Series(close).rolling(10).mean(),
        "ma20": pd.Series(close).rolling(20).mean(),
        "ma60": pd.Series(close).rolling(60).mean(),
        "macd": np.random.uniform(-0.5, 0.5, 100),
        "macd_signal": np.random.uniform(-0.5, 0.5, 100),
        "macd_hist": np.random.uniform(-0.2, 0.2, 100),
        "rsi": np.random.uniform(20, 80, 100),
        "boll_upper": close + 2,
        "boll_lower": close - 2,
        "boll_mid": close,
        "boll_position": np.random.uniform(0, 1, 100),
        "kdj_k": np.random.uniform(20, 80, 100),
        "kdj_d": np.random.uniform(20, 80, 100),
        "kdj_j": np.random.uniform(0, 100, 100),
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_macd_golden_cross():
    """创建 MACD 金叉数据"""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")

    macd = np.linspace(-1, 1, 100)
    macd_signal = np.linspace(0, 0.5, 100)
    macd[50] = -0.1
    macd_signal[50] = 0.1
    macd[51] = 0.2
    macd_signal[51] = 0.1

    data = {
        "code": ["sh600000"] * 100,
        "date": dates,
        "open": np.random.uniform(10, 20, 100),
        "close": np.random.uniform(10, 20, 100),
        "high": np.random.uniform(15, 25, 100),
        "low": np.random.uniform(5, 15, 100),
        "volume": np.random.uniform(100000, 500000, 100),
        "change_percent": np.random.uniform(-5, 5, 100),
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd - macd_signal,
        "rsi": np.random.uniform(30, 70, 100),
        "boll_upper": np.random.uniform(20, 25, 100),
        "boll_lower": np.random.uniform(5, 10, 100),
        "boll_position": np.random.uniform(0.3, 0.7, 100),
        "kdj_k": np.random.uniform(30, 70, 100),
        "kdj_d": np.random.uniform(30, 70, 100),
        "kdj_j": np.random.uniform(30, 70, 100),
        "ma5": np.random.uniform(12, 18, 100),
        "ma10": np.random.uniform(12, 18, 100),
        "ma20": np.random.uniform(12, 18, 100),
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_rsi_oversold():
    """创建 RSI 超卖数据"""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")

    rsi = np.random.uniform(40, 60, 100)
    rsi[-1] = 25

    data = {
        "code": ["sh600000"] * 100,
        "date": dates,
        "open": np.random.uniform(10, 20, 100),
        "close": np.random.uniform(10, 20, 100),
        "high": np.random.uniform(15, 25, 100),
        "low": np.random.uniform(5, 15, 100),
        "volume": np.random.uniform(100000, 500000, 100),
        "change_percent": np.random.uniform(-5, 5, 100),
        "rsi": rsi,
        "macd": np.random.uniform(-0.5, 0.5, 100),
        "macd_signal": np.random.uniform(-0.5, 0.5, 100),
        "boll_upper": np.random.uniform(20, 25, 100),
        "boll_lower": np.random.uniform(5, 10, 100),
        "boll_position": np.random.uniform(0.3, 0.7, 100),
        "kdj_k": np.random.uniform(30, 70, 100),
        "kdj_d": np.random.uniform(30, 70, 100),
        "kdj_j": np.random.uniform(30, 70, 100),
        "ma5": np.random.uniform(12, 18, 100),
        "ma10": np.random.uniform(12, 18, 100),
        "ma20": np.random.uniform(12, 18, 100),
    }
    return pd.DataFrame(data)


class TestSignalDetector:
    """信号检测器测试"""

    def test_detect_all_signals(self, sample_stock_data):
        """测试检测所有信号"""
        detector = SignalDetector()
        signals = detector.detect_all_signals(sample_stock_data)

        assert isinstance(signals, list)
        for signal in signals:
            assert isinstance(signal, Signal)
            assert signal.code == "sh600000"
            assert isinstance(signal.signal_type, SignalType)
            assert isinstance(signal.strength, SignalStrength)
            assert signal.score >= 0

    def test_detect_rsi_oversold(self, sample_rsi_oversold):
        """测试 RSI 超卖信号检测"""
        detector = SignalDetector()
        signals = detector.detect_all_signals(sample_rsi_oversold)

        rsi_signals = [s for s in signals if s.signal_type == SignalType.RSI_OVERSOLD]
        assert len(rsi_signals) == 1
        assert rsi_signals[0].strength in [SignalStrength.STRONG, SignalStrength.MEDIUM]

    def test_detect_trend_up(self):
        """测试上升趋势信号检测"""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        close = np.linspace(10, 20, 100)

        data = pd.DataFrame(
            {
                "code": ["sh600000"] * 100,
                "date": dates,
                "open": close,
                "close": close,
                "high": close + 1,
                "low": close - 1,
                "volume": np.random.uniform(100000, 500000, 100),
                "change_percent": np.random.uniform(-5, 5, 100),
                "ma5": close - 0.5,
                "ma10": close - 1,
                "ma20": close - 2,
                "macd": np.random.uniform(-0.5, 0.5, 100),
                "macd_signal": np.random.uniform(-0.5, 0.5, 100),
                "rsi": np.random.uniform(40, 60, 100),
                "boll_upper": close + 2,
                "boll_lower": close - 2,
                "boll_position": np.random.uniform(0.3, 0.7, 100),
                "kdj_k": np.random.uniform(30, 70, 100),
                "kdj_d": np.random.uniform(30, 70, 100),
                "kdj_j": np.random.uniform(30, 70, 100),
            }
        )

        detector = SignalDetector()
        signals = detector.detect_all_signals(data)

        trend_signals = [s for s in signals if s.signal_type == SignalType.TREND_UP]
        assert len(trend_signals) == 1

    def test_empty_data(self):
        """测试空数据"""
        detector = SignalDetector()
        signals = detector.detect_all_signals(pd.DataFrame())

        assert signals == []

    def test_insufficient_data(self):
        """测试数据不足"""
        detector = SignalDetector()
        df = pd.DataFrame({"code": ["sh600000"], "close": [10]})
        signals = detector.detect_all_signals(df)

        assert signals == []


class TestSignal:
    """信号测试"""

    def test_signal_to_dict(self):
        """测试信号转换为字典"""
        signal = Signal(
            code="sh600000",
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            strength=SignalStrength.STRONG,
            date="2024-01-01",
            price=10.5,
            change_percent=2.5,
            score=75.0,
            name="测试股票",
        )

        d = signal.to_dict()

        assert d["code"] == "sh600000"
        assert d["name"] == "测试股票"
        assert d["signal_type"] == "MACD金叉"
        assert d["strength"] == "强"
        assert d["score"] == 75.0


class TestSignalType:
    """信号类型测试"""

    def test_signal_type_values(self):
        """测试信号类型值"""
        assert SignalType.MACD_GOLDEN_CROSS.value == "MACD金叉"
        assert SignalType.MACD_DEATH_CROSS.value == "MACD死叉"
        assert SignalType.RSI_OVERSOLD.value == "RSI超卖"
        assert SignalType.RSI_OVERBOUGHT.value == "RSI超买"
        assert SignalType.TREND_UP.value == "上升趋势"
        assert SignalType.TREND_DOWN.value == "下降趋势"


class TestSignalStrength:
    """信号强度测试"""

    def test_signal_strength_values(self):
        """测试信号强度值"""
        assert SignalStrength.STRONG.value == "强"
        assert SignalStrength.MEDIUM.value == "中"
        assert SignalStrength.WEAK.value == "弱"


class TestMarketScanner:
    """市场扫描器测试"""

    def test_scanner_creation(self):
        """测试扫描器创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            scanner = MarketScanner(db_path)
            assert scanner.db_path == db_path

    def test_connect_db_not_found(self):
        """测试连接不存在的数据库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nonexistent.db"
            scanner = MarketScanner(db_path)

            with pytest.raises(FileNotFoundError):
                scanner.connect()

    def test_get_stock_codes_with_sqlite(self):
        """测试获取股票代码"""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE stock_analysis (
                    code TEXT,
                    date TEXT,
                    close REAL
                )
            """)
            # 使用固定日期测试
            conn.execute("INSERT INTO stock_analysis VALUES ('sh600000', '2026-04-17', 10.0)")
            conn.execute("INSERT INTO stock_analysis VALUES ('sh600001', '2026-04-17', 10.0)")
            conn.execute("INSERT INTO stock_analysis VALUES ('sh600002', '2026-03-01', 10.0)")
            conn.commit()
            conn.close()

            scanner = MarketScanner(db_path)
            scanner.connect()

            # 测试排除退市股票（最近7天无数据）
            codes = scanner.get_stock_codes(exclude_delisted=True, min_recent_days=7)
            assert "sh600000" in codes
            assert "sh600001" in codes
            assert "sh600002" not in codes  # 超过7天无数据

            # 测试不排除
            all_codes = scanner.get_stock_codes(exclude_delisted=False)
            assert len(all_codes) == 3

            scanner.close()


class TestScanResult:
    """扫描结果测试"""

    def test_scan_result_creation(self):
        """测试扫描结果创建"""
        result = ScanResult(
            scan_time="2026-04-17T10:00:00",
            total_stocks=5000,
            signals_found=100,
            signals=[],
            top_signals=[],
            summary={"MACD金叉": 50},
        )

        assert result.total_stocks == 5000
        assert result.signals_found == 100

    def test_scan_result_to_dict(self):
        """测试扫描结果转换为字典"""
        signal = Signal(
            code="sh600000",
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            strength=SignalStrength.STRONG,
            date="2026-04-17",
            price=10.5,
            change_percent=2.5,
            score=75.0,
            name="浦发银行",
        )

        result = ScanResult(
            scan_time="2026-04-17T10:00:00",
            total_stocks=5000,
            signals_found=1,
            signals=[signal],
            top_signals=[signal],
            summary={"MACD金叉": 1},
        )

        d = result.to_dict()
        assert d["total_stocks"] == 5000
        assert len(d["signals"]) == 1
        assert d["signals"][0]["code"] == "sh600000"

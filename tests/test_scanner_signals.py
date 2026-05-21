"""
Tests for Scanner Signals.
信号扫描器测试
"""

import pandas as pd
import pytest

from scanner.signals import (
    ScanResult,
    Signal,
    SignalDetector,
    SignalStrength,
    SignalType,
)


@pytest.fixture
def sample_df():
    """创建示例数据"""
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    data = {
        "date": dates,
        "code": ["000001"] * 60,
        "open": [10.0 + i * 0.1 for i in range(60)],
        "high": [10.5 + i * 0.1 for i in range(60)],
        "low": [9.5 + i * 0.1 for i in range(60)],
        "close": [10.0 + i * 0.1 for i in range(60)],
        "volume": [1000000] * 60,
        "change_percent": [0.5] * 60,
        "macd": [0.1 + i * 0.01 for i in range(60)],
        "macd_signal": [0.05 + i * 0.01 for i in range(60)],
        "macd_hist": [0.05] * 60,
        "rsi": [50 + (i % 20) for i in range(60)],
        "kdj_k": [50 + (i % 30) for i in range(60)],
        "kdj_d": [45 + (i % 25) for i in range(60)],
        "kdj_j": [55 + (i % 35) for i in range(60)],
        "ma5": [10.0 + i * 0.1 for i in range(60)],
        "ma10": [9.8 + i * 0.1 for i in range(60)],
        "ma20": [9.5 + i * 0.1 for i in range(60)],
        "boll_upper": [11.0 + i * 0.1 for i in range(60)],
        "boll_mid": [10.0 + i * 0.1 for i in range(60)],
        "boll_lower": [9.0 + i * 0.1 for i in range(60)],
        "obv": [1000000 + i * 10000 for i in range(60)],
        "atr": [0.5] * 60,
        "cci": [50 + (i % 100) for i in range(60)],
        "williams": [-30 + (i % 40) for i in range(60)],
    }
    return pd.DataFrame(data)


class TestSignalType:
    """测试信号类型枚举"""

    def test_signal_type_values(self):
        """测试信号类型值"""
        assert SignalType.MACD_GOLDEN_CROSS.value == "MACD金叉"
        assert SignalType.MACD_DEATH_CROSS.value == "MACD死叉"
        assert SignalType.RSI_OVERSOLD.value == "RSI超卖"
        assert SignalType.RSI_OVERBOUGHT.value == "RSI超买"

    def test_signal_type_count(self):
        """测试信号类型数量"""
        types = list(SignalType)
        assert len(types) >= 20


class TestSignalStrength:
    """测试信号强度枚举"""

    def test_signal_strength_values(self):
        """测试信号强度值"""
        assert SignalStrength.STRONG.value == "强"
        assert SignalStrength.MEDIUM.value == "中"
        assert SignalStrength.WEAK.value == "弱"


class TestSignal:
    """测试信号数据类"""

    def test_create_signal(self):
        """测试创建信号"""
        signal = Signal(
            code="000001",
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            strength=SignalStrength.STRONG,
            date="2024-01-01",
            price=10.0,
            change_percent=2.5,
            details={"macd": 0.1},
            score=85.0,
            name="平安银行",
        )

        assert signal.code == "000001"
        assert signal.signal_type == SignalType.MACD_GOLDEN_CROSS
        assert signal.strength == SignalStrength.STRONG
        assert signal.score == 85.0

    def test_signal_to_dict(self):
        """测试信号转字典"""
        signal = Signal(
            code="000001",
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            strength=SignalStrength.STRONG,
            date="2024-01-01",
            price=10.0,
            change_percent=2.5,
            details={"macd": 0.1},
            score=85.0,
            name="平安银行",
        )

        d = signal.to_dict()

        assert d["code"] == "000001"
        assert d["signal_type"] == "MACD金叉"
        assert d["strength"] == "强"
        assert d["price"] == 10.0
        assert d["score"] == 85.0

    def test_signal_defaults(self):
        """测试信号默认值"""
        signal = Signal(
            code="000001",
            signal_type=SignalType.RSI_OVERSOLD,
            strength=SignalStrength.WEAK,
            date="2024-01-01",
            price=10.0,
        )

        assert signal.change_percent == 0.0
        assert signal.details == {}
        assert signal.score == 0.0
        assert signal.name == ""


class TestScanResult:
    """测试扫描结果"""

    def test_create_scan_result(self):
        """测试创建扫描结果"""
        signals = [
            Signal(
                code="000001",
                signal_type=SignalType.MACD_GOLDEN_CROSS,
                strength=SignalStrength.STRONG,
                date="2024-01-01",
                price=10.0,
            )
        ]

        result = ScanResult(
            scan_time="2024-01-01 15:00:00",
            total_stocks=100,
            signals_found=10,
            signals=signals,
            summary={"MACD金叉": 5, "RSI超卖": 5},
            top_signals=signals,
        )

        assert result.total_stocks == 100
        assert result.signals_found == 10
        assert len(result.signals) == 1

    def test_scan_result_to_dict(self):
        """测试扫描结果转字典"""
        signals = [
            Signal(
                code="000001",
                signal_type=SignalType.MACD_GOLDEN_CROSS,
                strength=SignalStrength.STRONG,
                date="2024-01-01",
                price=10.0,
                name="平安银行",
            )
        ]

        result = ScanResult(
            scan_time="2024-01-01 15:00:00",
            total_stocks=100,
            signals_found=10,
            signals=signals,
            summary={"MACD金叉": 5},
            top_signals=signals,
        )

        d = result.to_dict()

        assert d["total_stocks"] == 100
        assert d["signals_found"] == 10
        assert len(d["signals"]) == 1
        assert len(d["top_signals"]) == 1


class TestSignalDetector:
    """测试信号检测器"""

    def test_detect_all_signals_insufficient_data(self):
        """测试数据不足"""
        detector = SignalDetector()
        df = pd.DataFrame({"close": [10.0] * 20})

        signals = detector.detect_all_signals(df)

        assert signals == []

    def test_detect_all_signals(self, sample_df):
        """测试检测所有信号"""
        detector = SignalDetector()
        signals = detector.detect_all_signals(sample_df)

        assert isinstance(signals, list)

    def test_detect_macd_signals(self, sample_df):
        """测试 MACD 信号检测"""
        detector = SignalDetector()

        latest = sample_df.iloc[-1]
        code = latest.get("code", "")
        date = latest.get("date", "")
        price = float(latest.get("close", 0))
        change_percent = float(latest.get("change_percent", 0))

        signals = detector._detect_macd_signals(sample_df, code, date, price, change_percent)

        assert isinstance(signals, list)

    def test_detect_rsi_signals(self, sample_df):
        """测试 RSI 信号检测"""
        detector = SignalDetector()

        latest = sample_df.iloc[-1]
        code = latest.get("code", "")
        date = latest.get("date", "")
        price = float(latest.get("close", 0))
        change_percent = float(latest.get("change_percent", 0))

        signals = detector._detect_rsi_signals(sample_df, code, date, price, change_percent)

        assert isinstance(signals, list)

    def test_detect_ma_signals(self, sample_df):
        """测试 MA 信号检测"""
        detector = SignalDetector()

        latest = sample_df.iloc[-1]
        code = latest.get("code", "")
        date = latest.get("date", "")
        price = float(latest.get("close", 0))
        change_percent = float(latest.get("change_percent", 0))

        signals = detector._detect_ma_signals(sample_df, code, date, price, change_percent)

        assert isinstance(signals, list)

    def test_detect_volume_signals(self, sample_df):
        """测试成交量信号检测"""
        detector = SignalDetector()

        latest = sample_df.iloc[-1]
        code = latest.get("code", "")
        date = latest.get("date", "")
        price = float(latest.get("close", 0))
        change_percent = float(latest.get("change_percent", 0))

        signals = detector._detect_volume_signals(sample_df, code, date, price, change_percent)

        assert isinstance(signals, list)

    def test_detect_boll_signals(self, sample_df):
        """测试布林带信号检测"""
        detector = SignalDetector()

        latest = sample_df.iloc[-1]
        code = latest.get("code", "")
        date = latest.get("date", "")
        price = float(latest.get("close", 0))
        change_percent = float(latest.get("change_percent", 0))

        signals = detector._detect_boll_signals(sample_df, code, date, price, change_percent)

        assert isinstance(signals, list)

    def test_detect_kdj_signals(self, sample_df):
        """测试 KDJ 信号检测"""
        detector = SignalDetector()

        latest = sample_df.iloc[-1]
        code = latest.get("code", "")
        date = latest.get("date", "")
        price = float(latest.get("close", 0))
        change_percent = float(latest.get("change_percent", 0))

        signals = detector._detect_kdj_signals(sample_df, code, date, price, change_percent)

        assert isinstance(signals, list)

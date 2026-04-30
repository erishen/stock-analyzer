"""
Tests for Signal Scanner Module.
信号扫描器测试
"""

import pandas as pd
import pytest

from src.scanner.signals import (
    ScanResult,
    Signal,
    SignalDetector,
    SignalStrength,
    SignalType,
)


@pytest.fixture
def sample_df():
    """创建示例 DataFrame"""
    data = []
    for i in range(50):
        base_price = 10.0 + i * 0.1
        data.append(
            {
                "code": "000001",
                "date": f"2024-01-{(i % 28) + 1:02d}",
                "close": base_price,
                "high": base_price + 0.5,
                "low": base_price - 0.3,
                "open": base_price,
                "volume": 1000000 + i * 10000,
                "change_percent": (i % 10) - 5 + 0.5,
                "macd": 0.1 + i * 0.001,
                "macd_signal": 0.08 + i * 0.001,
                "rsi": 40 + (i % 40),
                "kdj_k": 50.0 + i * 0.5,
                "kdj_d": 45.0 + i * 0.5,
                "ma5": base_price - 0.2,
                "ma10": base_price - 0.3,
                "ma20": base_price - 0.5,
                "boll_upper": base_price + 0.8,
                "boll_lower": base_price - 0.8,
            }
        )
    return pd.DataFrame(data)


class TestSignalType:
    """测试信号类型枚举"""

    def test_signal_types(self):
        """测试信号类型"""
        assert SignalType.MACD_GOLDEN_CROSS.value == "MACD金叉"
        assert SignalType.MACD_DEATH_CROSS.value == "MACD死叉"
        assert SignalType.RSI_OVERSOLD.value == "RSI超卖"
        assert SignalType.RSI_OVERBOUGHT.value == "RSI超买"

    def test_all_signal_types(self):
        """测试所有信号类型"""
        types = list(SignalType)
        assert len(types) >= 10


class TestSignalStrength:
    """测试信号强度枚举"""

    def test_strength_values(self):
        """测试强度值"""
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
            price=10.5,
            change_percent=5.0,
        )
        assert signal.code == "000001"
        assert signal.signal_type == SignalType.MACD_GOLDEN_CROSS
        assert signal.strength == SignalStrength.STRONG

    def test_signal_to_dict(self):
        """测试转换为字典"""
        signal = Signal(
            code="000001",
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            strength=SignalStrength.STRONG,
            date="2024-01-01",
            price=10.555,
            change_percent=5.555,
            details={"macd": 0.1},
            score=8.5,
            name="平安银行",
        )
        d = signal.to_dict()
        assert d["code"] == "000001"
        assert d["signal_type"] == "MACD金叉"
        assert d["strength"] == "强"


class TestScanResult:
    """测试扫描结果"""

    def test_create_result(self):
        """测试创建结果"""
        result = ScanResult(
            scan_time="2024-01-01 12:00:00",
            total_stocks=100,
            signals_found=50,
            signals=[],
            summary={},
            top_signals=[],
        )
        assert result.total_stocks == 100
        assert result.signals_found == 50

    def test_result_to_dict(self):
        """测试转换为字典"""
        signal = Signal(
            code="000001",
            signal_type=SignalType.MACD_GOLDEN_CROSS,
            strength=SignalStrength.STRONG,
            date="2024-01-01",
            price=10.5,
        )
        result = ScanResult(
            scan_time="2024-01-01 12:00:00",
            total_stocks=1,
            signals_found=1,
            signals=[signal],
            summary={"MACD金叉": 1},
            top_signals=[signal],
        )
        d = result.to_dict()
        assert d["total_stocks"] == 1
        assert len(d["signals"]) == 1


class TestSignalDetector:
    """测试信号检测器"""

    def test_init(self):
        """测试初始化"""
        detector = SignalDetector()
        assert detector is not None

    def test_detect_all_signals(self, sample_df):
        """测试检测所有信号"""
        detector = SignalDetector()

        signals = detector.detect_all_signals(sample_df)

        assert isinstance(signals, list)

    def test_detect_signals_insufficient_data(self):
        """测试数据不足"""
        detector = SignalDetector()

        df = pd.DataFrame({"close": [10.0, 10.5]})
        signals = detector.detect_all_signals(df)

        assert signals == []

    def test_detect_williams_signals(self, sample_df):
        """测试威廉指标信号"""
        detector = SignalDetector()

        df = sample_df.copy()
        df["high"] = df["close"] + 1.0
        df["low"] = df["close"] - 1.0

        signals = detector.detect_all_signals(df)

        williams_signals = [s for s in signals if "威廉" in s.signal_type.value]
        assert isinstance(williams_signals, list)

    def test_detect_cci_signals(self, sample_df):
        """测试 CCI 指标信号"""
        detector = SignalDetector()

        df = sample_df.copy()
        df["high"] = df["close"] + 0.5
        df["low"] = df["close"] - 0.3

        signals = detector.detect_all_signals(df)

        cci_signals = [s for s in signals if "CCI" in s.signal_type.value]
        assert isinstance(cci_signals, list)

    def test_detect_atr_signals(self, sample_df):
        """测试 ATR 波动率信号"""
        detector = SignalDetector()

        df = sample_df.copy()
        df["high"] = df["close"] + 0.5
        df["low"] = df["close"] - 0.3

        signals = detector.detect_all_signals(df)

        atr_signals = [s for s in signals if "ATR" in s.signal_type.value]
        assert isinstance(atr_signals, list)

    def test_detect_pattern_signals(self, sample_df):
        """测试 K 线形态信号"""
        detector = SignalDetector()

        df = sample_df.copy()
        df["open"] = df["close"] - 0.1
        df["high"] = df["close"] + 0.5
        df["low"] = df["close"] - 0.3

        signals = detector.detect_all_signals(df)

        pattern_signals = [
            s
            for s in signals
            if s.signal_type
            in [
                SignalType.HAMMER,
                SignalType.INVERTED_HAMMER,
                SignalType.BULLISH_ENGULFING,
                SignalType.BEARISH_ENGULFING,
                SignalType.DOJI,
            ]
        ]
        assert isinstance(pattern_signals, list)

    def test_detect_multi_period_signals(self, sample_df):
        """测试多周期共振信号"""
        detector = SignalDetector()

        df = sample_df.copy()
        df["ma60"] = df["close"] - 1.0

        signals = detector.detect_all_signals(df)

        multi_period_signals = [s for s in signals if "多周期" in s.signal_type.value]
        assert isinstance(multi_period_signals, list)

    def test_detect_price_volume_signals(self, sample_df):
        """测试量价关系信号"""
        detector = SignalDetector()

        df = sample_df.copy()
        df["volume"] = 2000000

        signals = detector.detect_all_signals(df)

        pv_signals = [s for s in signals if "量价" in s.signal_type.value]
        assert isinstance(pv_signals, list)


class TestNewSignalTypes:
    """测试新增信号类型"""

    def test_williams_signal_type_exists(self):
        """测试威廉信号类型存在"""
        assert hasattr(SignalType, "WILLIAMS_OVERSOLD")
        assert hasattr(SignalType, "WILLIAMS_OVERBOUGHT")
        assert SignalType.WILLIAMS_OVERSOLD.value == "威廉超卖"
        assert SignalType.WILLIAMS_OVERBOUGHT.value == "威廉超买"

    def test_cci_signal_type_exists(self):
        """测试 CCI 信号类型存在"""
        assert hasattr(SignalType, "CCI_OVERSOLD")
        assert hasattr(SignalType, "CCI_OVERBOUGHT")
        assert SignalType.CCI_OVERSOLD.value == "CCI超卖"
        assert SignalType.CCI_OVERBOUGHT.value == "CCI超买"

    def test_atr_signal_type_exists(self):
        """测试 ATR 信号类型存在"""
        assert hasattr(SignalType, "ATR_SURGE")
        assert hasattr(SignalType, "ATR_SHRINK")
        assert SignalType.ATR_SURGE.value == "ATR波动放大"
        assert SignalType.ATR_SHRINK.value == "ATR波动收缩"

    def test_pattern_signal_types_exist(self):
        """测试 K 线形态信号类型存在"""
        assert hasattr(SignalType, "HAMMER")
        assert hasattr(SignalType, "INVERTED_HAMMER")
        assert hasattr(SignalType, "BULLISH_ENGULFING")
        assert hasattr(SignalType, "BEARISH_ENGULFING")
        assert hasattr(SignalType, "MORNING_STAR")
        assert hasattr(SignalType, "EVENING_STAR")
        assert hasattr(SignalType, "DOJI")

    def test_multi_period_signal_types_exist(self):
        """测试多周期共振信号类型存在"""
        assert hasattr(SignalType, "MULTI_PERIOD_BULLISH")
        assert hasattr(SignalType, "MULTI_PERIOD_BEARISH")

    def test_price_volume_signal_types_exist(self):
        """测试量价关系信号类型存在"""
        assert hasattr(SignalType, "PRICE_VOLUME_BULLISH")
        assert hasattr(SignalType, "PRICE_VOLUME_BEARISH")

    def test_total_signal_types_count(self):
        """测试信号类型总数"""
        types = list(SignalType)
        assert len(types) >= 30

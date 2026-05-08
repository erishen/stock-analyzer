"""
Signal Scanner for Stock Analyzer.
信号扫描器 - 扫描全市场技术信号，发现交易机会

信号类型:
- 金叉/死叉: MACD, KDJ, MA
- 超卖/超买: RSI, Williams %R
- 突破信号: 布林带, 价格突破
- 量价信号: OBV, 成交量异动
- 趋势信号: MA 排列, 动量
"""

import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
import pandas as pd

from config import get_stock_analysis_db_path


class SignalType(Enum):
    """信号类型"""

    MACD_GOLDEN_CROSS = "MACD金叉"
    MACD_DEATH_CROSS = "MACD死叉"
    KDJ_GOLDEN_CROSS = "KDJ金叉"
    KDJ_DEATH_CROSS = "KDJ死叉"
    MA5_CROSS_UP_MA20 = "MA5上穿MA20"
    MA5_CROSS_DOWN_MA20 = "MA5下穿MA20"
    RSI_OVERSOLD = "RSI超卖"
    RSI_OVERBOUGHT = "RSI超买"
    BOLL_UPPER_BREAK = "突破布林上轨"
    BOLL_LOWER_BREAK = "跌破布林下轨"
    VOLUME_SURGE = "成交量异动"
    PRICE_BREAKOUT = "价格突破"
    TREND_UP = "上升趋势"
    TREND_DOWN = "下降趋势"
    OBV_DIVERGENCE = "OBV背离"
    WILLIAMS_OVERSOLD = "威廉超卖"
    WILLIAMS_OVERBOUGHT = "威廉超买"
    CCI_OVERSOLD = "CCI超卖"
    CCI_OVERBOUGHT = "CCI超买"
    ATR_SURGE = "ATR波动放大"
    ATR_SHRINK = "ATR波动收缩"
    HAMMER = "锤子线"
    INVERTED_HAMMER = "倒锤线"
    BULLISH_ENGULFING = "看涨吞没"
    BEARISH_ENGULFING = "看跌吞没"
    MORNING_STAR = "启明星"
    EVENING_STAR = "黄昏星"
    DOJI = "十字星"
    MULTI_PERIOD_BULLISH = "多周期看涨共振"
    MULTI_PERIOD_BEARISH = "多周期看跌共振"
    PRICE_VOLUME_BULLISH = "量价齐升"
    PRICE_VOLUME_BEARISH = "量价背离"


class SignalStrength(Enum):
    """信号强度"""

    STRONG = "强"
    MEDIUM = "中"
    WEAK = "弱"


@dataclass
class Signal:
    """信号"""

    code: str
    signal_type: SignalType
    strength: SignalStrength
    date: str
    price: float
    change_percent: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "signal_type": self.signal_type.value,
            "strength": self.strength.value,
            "date": self.date,
            "price": self.price,
            "change_percent": round(self.change_percent, 2),
            "details": self.details,
            "score": round(self.score, 2),
        }


@dataclass
class ScanResult:
    """扫描结果"""

    scan_time: str
    total_stocks: int
    signals_found: int
    signals: list[Signal]
    summary: dict[str, int]
    top_signals: list[Signal]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_time": self.scan_time,
            "total_stocks": self.total_stocks,
            "signals_found": self.signals_found,
            "signals": [s.to_dict() for s in self.signals],
            "summary": self.summary,
            "top_signals": [s.to_dict() for s in self.top_signals],
        }


class SignalDetector:
    """信号检测器 - 检测单只股票的技术信号"""

    def detect_all_signals(self, df: pd.DataFrame) -> list[Signal]:
        """检测所有信号"""
        if len(df) < 30:
            return []

        signals = []
        latest = df.iloc[-1]

        code = latest.get("code", "")
        date = latest.get("date", "")
        price = float(latest.get("close", 0))
        change_percent = float(latest.get("change_percent", 0))

        macd_signals = self._detect_macd_signals(df, code, date, price, change_percent)
        signals.extend(macd_signals)

        kdj_signals = self._detect_kdj_signals(df, code, date, price, change_percent)
        signals.extend(kdj_signals)

        ma_signals = self._detect_ma_signals(df, code, date, price, change_percent)
        signals.extend(ma_signals)

        rsi_signals = self._detect_rsi_signals(df, code, date, price, change_percent)
        signals.extend(rsi_signals)

        boll_signals = self._detect_boll_signals(df, code, date, price, change_percent)
        signals.extend(boll_signals)

        volume_signals = self._detect_volume_signals(df, code, date, price, change_percent)
        signals.extend(volume_signals)

        trend_signals = self._detect_trend_signals(df, code, date, price, change_percent)
        signals.extend(trend_signals)

        williams_signals = self._detect_williams_signals(df, code, date, price, change_percent)
        signals.extend(williams_signals)

        cci_signals = self._detect_cci_signals(df, code, date, price, change_percent)
        signals.extend(cci_signals)

        atr_signals = self._detect_atr_signals(df, code, date, price, change_percent)
        signals.extend(atr_signals)

        pattern_signals = self._detect_pattern_signals(df, code, date, price, change_percent)
        signals.extend(pattern_signals)

        multi_period_signals = self._detect_multi_period_signals(df, code, date, price, change_percent)
        signals.extend(multi_period_signals)

        price_volume_signals = self._detect_price_volume_signals(df, code, date, price, change_percent)
        signals.extend(price_volume_signals)

        for signal in signals:
            signal.score = self._calculate_signal_score(signal, df)

        return signals

    def _detect_macd_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测 MACD 信号"""
        signals = []
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        macd = latest.get("macd", 0) or 0
        macd_signal = latest.get("macd_signal", 0) or 0
        macd_hist = latest.get("macd_hist", 0) or 0

        prev_macd = prev.get("macd", 0) or 0
        prev_signal = prev.get("macd_signal", 0) or 0

        if prev_macd <= prev_signal and macd > macd_signal:
            strength = SignalStrength.STRONG if macd_hist > 0 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.MACD_GOLDEN_CROSS,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"macd": round(macd, 4), "signal": round(macd_signal, 4)},
                )
            )

        elif prev_macd >= prev_signal and macd < macd_signal:
            strength = SignalStrength.STRONG if macd_hist < 0 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.MACD_DEATH_CROSS,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"macd": round(macd, 4), "signal": round(macd_signal, 4)},
                )
            )

        return signals

    def _detect_kdj_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测 KDJ 信号"""
        signals = []
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        kdj_k = latest.get("kdj_k", 50) or 50
        kdj_d = latest.get("kdj_d", 50) or 50
        kdj_j = latest.get("kdj_j", 50) or 50

        prev_k = prev.get("kdj_k", 50) or 50
        prev_d = prev.get("kdj_d", 50) or 50

        if prev_k <= prev_d and kdj_k > kdj_d:
            strength = SignalStrength.STRONG if kdj_j < 20 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.KDJ_GOLDEN_CROSS,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"K": round(kdj_k, 2), "D": round(kdj_d, 2), "J": round(kdj_j, 2)},
                )
            )

        elif prev_k >= prev_d and kdj_k < kdj_d:
            strength = SignalStrength.STRONG if kdj_j > 80 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.KDJ_DEATH_CROSS,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"K": round(kdj_k, 2), "D": round(kdj_d, 2), "J": round(kdj_j, 2)},
                )
            )

        return signals

    def _detect_ma_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测均线信号"""
        signals = []
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        ma5 = latest.get("ma5", price) or price
        ma20 = latest.get("ma20", price) or price
        prev_ma5 = prev.get("ma5", price) or price
        prev_ma20 = prev.get("ma20", price) or price

        if prev_ma5 <= prev_ma20 and ma5 > ma20:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.MA5_CROSS_UP_MA20,
                    strength=SignalStrength.MEDIUM,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"ma5": round(ma5, 2), "ma20": round(ma20, 2)},
                )
            )

        elif prev_ma5 >= prev_ma20 and ma5 < ma20:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.MA5_CROSS_DOWN_MA20,
                    strength=SignalStrength.MEDIUM,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"ma5": round(ma5, 2), "ma20": round(ma20, 2)},
                )
            )

        return signals

    def _detect_rsi_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测 RSI 信号"""
        signals = []
        latest = df.iloc[-1]

        rsi = latest.get("rsi", 50) or 50

        if rsi < 30:
            strength = SignalStrength.STRONG if rsi < 20 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.RSI_OVERSOLD,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"rsi": round(rsi, 2)},
                )
            )

        elif rsi > 70:
            strength = SignalStrength.STRONG if rsi > 80 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.RSI_OVERBOUGHT,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"rsi": round(rsi, 2)},
                )
            )

        return signals

    def _detect_boll_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测布林带信号"""
        signals = []
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        boll_upper = latest.get("boll_upper", price) or price
        boll_lower = latest.get("boll_lower", price) or price
        boll_position = latest.get("boll_position", 0.5) or 0.5

        prev_close = prev.get("close", price) or price
        prev_boll_upper = prev.get("boll_upper", price) or price
        prev_boll_lower = prev.get("boll_lower", price) or price

        if prev_close <= prev_boll_upper and price > boll_upper:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.BOLL_UPPER_BREAK,
                    strength=SignalStrength.STRONG,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"boll_upper": round(boll_upper, 2), "position": round(boll_position, 2)},
                )
            )

        elif prev_close >= prev_boll_lower and price < boll_lower:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.BOLL_LOWER_BREAK,
                    strength=SignalStrength.STRONG,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"boll_lower": round(boll_lower, 2), "position": round(boll_position, 2)},
                )
            )

        return signals

    def _detect_volume_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测成交量信号"""
        signals = []
        latest = df.iloc[-1]

        volume = latest.get("volume", 0) or 0
        turnover_rate = latest.get("turnover_rate", 0) or 0

        if len(df) >= 5:
            avg_volume = df["volume"].iloc[-5:].mean()
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1

            if volume_ratio > 2.0:
                strength = SignalStrength.STRONG if volume_ratio > 3.0 else SignalStrength.MEDIUM
                signals.append(
                    Signal(
                        code=code,
                        signal_type=SignalType.VOLUME_SURGE,
                        strength=strength,
                        date=date,
                        price=price,
                        change_percent=change_percent,
                        details={"volume_ratio": round(volume_ratio, 2), "turnover_rate": round(turnover_rate, 2)},
                    )
                )

        return signals

    def _detect_trend_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测趋势信号"""
        signals = []
        latest = df.iloc[-1]

        ma5 = latest.get("ma5", price) or price
        ma10 = latest.get("ma10", price) or price
        ma20 = latest.get("ma20", price) or price

        if ma5 > ma10 > ma20:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.TREND_UP,
                    strength=SignalStrength.MEDIUM,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"ma5": round(ma5, 2), "ma10": round(ma10, 2), "ma20": round(ma20, 2)},
                )
            )

        elif ma5 < ma10 < ma20:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.TREND_DOWN,
                    strength=SignalStrength.MEDIUM,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"ma5": round(ma5, 2), "ma10": round(ma10, 2), "ma20": round(ma20, 2)},
                )
            )

        return signals

    def _detect_williams_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测威廉指标信号"""
        signals = []
        if len(df) < 14:
            return signals

        high_14 = df["high"].iloc[-14:].max()
        low_14 = df["low"].iloc[-14:].min()
        latest = df.iloc[-1]
        close = latest.get("close", price)

        if high_14 != low_14:
            williams = -100 * (high_14 - close) / (high_14 - low_14)
        else:
            williams = -50

        if williams > -20:
            strength = SignalStrength.STRONG if williams > -10 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.WILLIAMS_OVERBOUGHT,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"williams": round(williams, 2)},
                )
            )
        elif williams < -80:
            strength = SignalStrength.STRONG if williams < -90 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.WILLIAMS_OVERSOLD,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"williams": round(williams, 2)},
                )
            )

        return signals

    def _detect_cci_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测 CCI 指标信号"""
        signals = []
        if len(df) < 20:
            return signals

        tp = (df["high"] + df["low"] + df["close"]) / 3
        sma_tp = tp.rolling(window=20).mean()
        mad = tp.rolling(window=20).apply(lambda x: abs(x - x.mean()).mean())
        cci = (tp - sma_tp) / (0.015 * mad)
        latest_cci = cci.iloc[-1]

        if latest_cci > 100:
            strength = SignalStrength.STRONG if latest_cci > 200 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.CCI_OVERBOUGHT,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"cci": round(latest_cci, 2)},
                )
            )
        elif latest_cci < -100:
            strength = SignalStrength.STRONG if latest_cci < -200 else SignalStrength.MEDIUM
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.CCI_OVERSOLD,
                    strength=strength,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"cci": round(latest_cci, 2)},
                )
            )

        return signals

    def _detect_atr_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测 ATR 波动率信号"""
        signals = []
        if len(df) < 20:
            return signals

        high = df["high"]
        low = df["low"]
        close = df["close"].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()

        if len(atr) >= 20:
            atr_ma = atr.rolling(window=20).mean()
            atr_ratio = atr.iloc[-1] / atr_ma.iloc[-1] if atr_ma.iloc[-1] > 0 else 1

            if atr_ratio > 1.5:
                strength = SignalStrength.STRONG if atr_ratio > 2.0 else SignalStrength.MEDIUM
                signals.append(
                    Signal(
                        code=code,
                        signal_type=SignalType.ATR_SURGE,
                        strength=strength,
                        date=date,
                        price=price,
                        change_percent=change_percent,
                        details={"atr_ratio": round(atr_ratio, 2), "atr": round(atr.iloc[-1], 4)},
                    )
                )
            elif atr_ratio < 0.7:
                strength = SignalStrength.MEDIUM
                signals.append(
                    Signal(
                        code=code,
                        signal_type=SignalType.ATR_SHRINK,
                        strength=strength,
                        date=date,
                        price=price,
                        change_percent=change_percent,
                        details={"atr_ratio": round(atr_ratio, 2), "atr": round(atr.iloc[-1], 4)},
                    )
                )

        return signals

    def _detect_pattern_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测 K 线形态信号"""
        signals = []
        if len(df) < 5:
            return signals

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        prev2 = df.iloc[-3] if len(df) > 2 else prev

        open_price = latest.get("open", price)
        high_price = latest.get("high", price)
        low_price = latest.get("low", price)
        close_price = latest.get("close", price)

        prev_open = prev.get("open", price)
        prev_close = prev.get("close", price)

        body = abs(close_price - open_price)
        upper_shadow = high_price - max(open_price, close_price)
        lower_shadow = min(open_price, close_price) - low_price
        total_range = high_price - low_price if high_price != low_price else 1

        if lower_shadow > body * 2 and upper_shadow < body * 0.5 and close_price > open_price and change_percent < 0:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.HAMMER,
                    strength=SignalStrength.STRONG,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"pattern": "锤子线", "body_ratio": round(body / total_range, 2)},
                )
            )

        if upper_shadow > body * 2 and lower_shadow < body * 0.5 and close_price < open_price and change_percent > 0:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.INVERTED_HAMMER,
                    strength=SignalStrength.MEDIUM,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"pattern": "倒锤线", "body_ratio": round(body / total_range, 2)},
                )
            )

        if prev_close < prev_open and close_price > open_price and close_price > prev_open and open_price < prev_close:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.BULLISH_ENGULFING,
                    strength=SignalStrength.STRONG,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"pattern": "看涨吞没"},
                )
            )

        if prev_close > prev_open and close_price < open_price and close_price < prev_open and open_price > prev_close:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.BEARISH_ENGULFING,
                    strength=SignalStrength.STRONG,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"pattern": "看跌吞没"},
                )
            )

        if body < total_range * 0.1:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.DOJI,
                    strength=SignalStrength.WEAK,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"pattern": "十字星"},
                )
            )

        prev2_close = prev2.get("close", price)
        prev2_open = prev2.get("open", price)

        if (
            prev2_close < prev2_open
            and prev_close < prev_open
            and close_price > open_price
            and close_price > prev_close
        ):
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.MORNING_STAR,
                    strength=SignalStrength.STRONG,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"pattern": "启明星"},
                )
            )

        if (
            prev2_close > prev2_open
            and prev_close > prev_open
            and close_price < open_price
            and close_price < prev_close
        ):
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.EVENING_STAR,
                    strength=SignalStrength.STRONG,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"pattern": "黄昏星"},
                )
            )

        return signals

    def _detect_multi_period_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测多周期共振信号"""
        signals = []
        if len(df) < 60:
            return signals

        latest = df.iloc[-1]

        ma5 = latest.get("ma5", price) or price
        ma10 = latest.get("ma10", price) or price
        ma20 = latest.get("ma20", price) or price
        ma60 = latest.get("ma60", price) or price

        macd = latest.get("macd", 0) or 0
        macd_signal = latest.get("macd_signal", 0) or 0
        kdj_k = latest.get("kdj_k", 50) or 50
        kdj_d = latest.get("kdj_d", 50) or 50

        bullish_count = 0
        if ma5 > ma10:
            bullish_count += 1
        if ma10 > ma20:
            bullish_count += 1
        if ma20 > ma60:
            bullish_count += 1
        if macd > macd_signal:
            bullish_count += 1
        if kdj_k > kdj_d:
            bullish_count += 1

        if bullish_count >= 4:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.MULTI_PERIOD_BULLISH,
                    strength=SignalStrength.STRONG if bullish_count == 5 else SignalStrength.MEDIUM,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"bullish_count": bullish_count, "total": 5},
                )
            )

        bearish_count = 0
        if ma5 < ma10:
            bearish_count += 1
        if ma10 < ma20:
            bearish_count += 1
        if ma20 < ma60:
            bearish_count += 1
        if macd < macd_signal:
            bearish_count += 1
        if kdj_k < kdj_d:
            bearish_count += 1

        if bearish_count >= 4:
            signals.append(
                Signal(
                    code=code,
                    signal_type=SignalType.MULTI_PERIOD_BEARISH,
                    strength=SignalStrength.STRONG if bearish_count == 5 else SignalStrength.MEDIUM,
                    date=date,
                    price=price,
                    change_percent=change_percent,
                    details={"bearish_count": bearish_count, "total": 5},
                )
            )

        return signals

    def _detect_price_volume_signals(
        self, df: pd.DataFrame, code: str, date: str, price: float, change_percent: float
    ) -> list[Signal]:
        """检测量价关系信号"""
        signals = []
        if len(df) < 5:
            return signals

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        volume = latest.get("volume", 0) or 0
        prev_volume = prev.get("volume", 0) or 0
        close_price = latest.get("close", price)
        prev_close = prev.get("close", price)

        if volume > 0 and prev_volume > 0:
            volume_change = (volume - prev_volume) / prev_volume
            price_change = (close_price - prev_close) / prev_close if prev_close > 0 else 0

            if volume_change > 0.5 and price_change > 0.02:
                strength = SignalStrength.STRONG if volume_change > 1.0 else SignalStrength.MEDIUM
                signals.append(
                    Signal(
                        code=code,
                        signal_type=SignalType.PRICE_VOLUME_BULLISH,
                        strength=strength,
                        date=date,
                        price=price,
                        change_percent=change_percent,
                        details={
                            "volume_change": round(volume_change * 100, 2),
                            "price_change": round(price_change * 100, 2),
                        },
                    )
                )

            if volume_change > 0.3 and price_change < -0.01:
                signals.append(
                    Signal(
                        code=code,
                        signal_type=SignalType.PRICE_VOLUME_BEARISH,
                        strength=SignalStrength.MEDIUM,
                        date=date,
                        price=price,
                        change_percent=change_percent,
                        details={
                            "volume_change": round(volume_change * 100, 2),
                            "price_change": round(price_change * 100, 2),
                        },
                    )
                )

        return signals

    def _calculate_signal_score(self, signal: Signal, df: pd.DataFrame) -> float:
        """计算信号综合得分"""
        score = 0.0

        strength_scores = {
            SignalStrength.STRONG: 30,
            SignalStrength.MEDIUM: 20,
            SignalStrength.WEAK: 10,
        }
        score += strength_scores.get(signal.strength, 10)

        bullish_signals = [
            SignalType.MACD_GOLDEN_CROSS,
            SignalType.KDJ_GOLDEN_CROSS,
            SignalType.MA5_CROSS_UP_MA20,
            SignalType.RSI_OVERSOLD,
            SignalType.BOLL_LOWER_BREAK,
            SignalType.TREND_UP,
            SignalType.WILLIAMS_OVERSOLD,
            SignalType.CCI_OVERSOLD,
            SignalType.HAMMER,
            SignalType.INVERTED_HAMMER,
            SignalType.BULLISH_ENGULFING,
            SignalType.MORNING_STAR,
            SignalType.MULTI_PERIOD_BULLISH,
            SignalType.PRICE_VOLUME_BULLISH,
        ]

        if signal.signal_type in bullish_signals:
            score += 20
        else:
            score -= 10

        if len(df) >= 5:
            momentum_5d = df["close"].iloc[-1] / df["close"].iloc[-5] - 1
            if signal.signal_type in bullish_signals:
                score += momentum_5d * 100
            else:
                score -= momentum_5d * 50

        if signal.signal_type == SignalType.VOLUME_SURGE:
            volume_ratio = signal.details.get("volume_ratio", 1)
            score += min(volume_ratio * 5, 15)

        if signal.signal_type == SignalType.MULTI_PERIOD_BULLISH:
            bullish_count = signal.details.get("bullish_count", 4)
            score += bullish_count * 5

        if signal.signal_type == SignalType.PRICE_VOLUME_BULLISH:
            volume_change = signal.details.get("volume_change", 0)
            score += min(volume_change / 10, 10)

        return max(0, min(100, score))


class MarketScanner:
    """市场扫描器 - 扫描全市场股票信号"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.detector = SignalDetector()
        self.conn = None

    def connect(self):
        """连接数据库"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库不存在: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()

    def get_stock_codes(self, exclude_delisted: bool = True, min_recent_days: int = 7) -> list[str]:
        """
        获取所有股票代码

        Args:
            exclude_delisted: 是否排除退市股票
            min_recent_days: 最近多少天有数据才算活跃（默认7天）
        """
        if exclude_delisted:
            query = """
                SELECT DISTINCT code FROM stock_analysis
                WHERE date >= date((SELECT MAX(date) FROM stock_analysis), ? || ' days')
                ORDER BY code
            """
            cursor = self.conn.execute(query, (f"-{min_recent_days}",))
        else:
            query = "SELECT DISTINCT code FROM stock_analysis ORDER BY code"
            cursor = self.conn.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def get_stock_data(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取股票数据"""
        query = """
            SELECT * FROM stock_analysis
            WHERE code = ?
            ORDER BY date DESC
            LIMIT ?
        """
        df = pd.read_sql_query(query, self.conn, params=(code, days))
        if not df.empty:
            df = df.sort_values("date").reset_index(drop=True)
        return df

    def scan_all(
        self, signal_types: list[SignalType] | None = None, min_score: float = 0, exclude_delisted: bool = True
    ) -> ScanResult:
        """
        扫描全市场

        Args:
            signal_types: 筛选信号类型
            min_score: 最低得分
            exclude_delisted: 是否排除退市股票

        Returns:
            扫描结果
        """

        from data import get_stock_name

        scan_time = datetime.now().isoformat()
        all_signals: list[Signal] = []

        codes = self.get_stock_codes(exclude_delisted=exclude_delisted)
        total_stocks = len(codes)

        print(f"\n🔍 开始扫描 {total_stocks} 只股票...")

        name_cache: dict[str, str] = {}

        for i, code in enumerate(codes, 1):
            try:
                df = self.get_stock_data(code)
                if df.empty:
                    continue

                signals = self.detector.detect_all_signals(df)

                if signal_types:
                    signals = [s for s in signals if s.signal_type in signal_types]

                if min_score > 0:
                    signals = [s for s in signals if s.score >= min_score]

                if code not in name_cache:
                    name_cache[code] = get_stock_name(code)

                for s in signals:
                    s.name = name_cache[code]

                all_signals.extend(signals)

                if i % 500 == 0:
                    print(f"   进度: {i}/{total_stocks} ({i / total_stocks * 100:.1f}%)")

            except Exception:
                continue

        all_signals.sort(key=lambda x: x.score, reverse=True)

        summary: dict[str, int] = {}
        for signal in all_signals:
            key = signal.signal_type.value
            summary[key] = summary.get(key, 0) + 1

        top_signals = all_signals[:20]

        result = ScanResult(
            scan_time=scan_time,
            total_stocks=total_stocks,
            signals_found=len(all_signals),
            signals=all_signals,
            summary=summary,
            top_signals=top_signals,
        )

        print(f"\n✅ 扫描完成: 发现 {len(all_signals)} 个信号")

        return result

    def scan_by_type(self, signal_type: SignalType) -> list[Signal]:
        """按类型扫描"""
        result = self.scan_all(signal_types=[signal_type])
        return result.signals

    def scan_bullish(self) -> list[Signal]:
        """扫描看涨信号"""
        bullish_types = [
            SignalType.MACD_GOLDEN_CROSS,
            SignalType.KDJ_GOLDEN_CROSS,
            SignalType.MA5_CROSS_UP_MA20,
            SignalType.RSI_OVERSOLD,
            SignalType.BOLL_LOWER_BREAK,
            SignalType.TREND_UP,
            SignalType.WILLIAMS_OVERSOLD,
            SignalType.CCI_OVERSOLD,
            SignalType.HAMMER,
            SignalType.INVERTED_HAMMER,
            SignalType.BULLISH_ENGULFING,
            SignalType.MORNING_STAR,
            SignalType.MULTI_PERIOD_BULLISH,
            SignalType.PRICE_VOLUME_BULLISH,
        ]
        result = self.scan_all(signal_types=bullish_types)
        return result.signals

    def scan_bearish(self) -> list[Signal]:
        """扫描看跌信号"""
        bearish_types = [
            SignalType.MACD_DEATH_CROSS,
            SignalType.KDJ_DEATH_CROSS,
            SignalType.MA5_CROSS_DOWN_MA20,
            SignalType.RSI_OVERBOUGHT,
            SignalType.BOLL_UPPER_BREAK,
            SignalType.TREND_DOWN,
            SignalType.WILLIAMS_OVERBOUGHT,
            SignalType.CCI_OVERBOUGHT,
            SignalType.BEARISH_ENGULFING,
            SignalType.EVENING_STAR,
            SignalType.MULTI_PERIOD_BEARISH,
            SignalType.PRICE_VOLUME_BEARISH,
        ]
        result = self.scan_all(signal_types=bearish_types)
        return result.signals

    def scan_parallel(
        self,
        signal_types: list[SignalType] | None = None,
        min_score: float = 0,
        exclude_delisted: bool = True,
        max_workers: int = 4,
    ) -> ScanResult:
        """
        并行扫描全市场

        Args:
            signal_types: 筛选信号类型
            min_score: 最低得分
            exclude_delisted: 是否排除退市股票
            max_workers: 最大并行数

        Returns:
            扫描结果
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from data import get_stock_name

        scan_time = datetime.now().isoformat()
        all_signals: list[Signal] = []

        codes = self.get_stock_codes(exclude_delisted=exclude_delisted)
        total_stocks = len(codes)

        print(f"\n🔍 开始并行扫描 {total_stocks} 只股票 (workers={max_workers})...")

        name_cache: dict[str, str] = {}
        completed = 0

        def process_stock(code: str) -> list[Signal]:
            try:
                df = self.get_stock_data(code)
                if df.empty:
                    return []

                signals = self.detector.detect_all_signals(df)

                if signal_types:
                    signals = [s for s in signals if s.signal_type in signal_types]

                if min_score > 0:
                    signals = [s for s in signals if s.score >= min_score]

                return signals
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_stock, code): code for code in codes}

            for future in as_completed(futures):
                code = futures[future]
                try:
                    signals = future.result()

                    if code not in name_cache:
                        name_cache[code] = get_stock_name(code)

                    for s in signals:
                        s.name = name_cache[code]

                    all_signals.extend(signals)
                except Exception:
                    pass

                completed += 1
                if completed % 500 == 0:
                    print(f"   进度: {completed}/{total_stocks} ({completed / total_stocks * 100:.1f}%)")

        all_signals.sort(key=lambda x: x.score, reverse=True)

        summary: dict[str, int] = {}
        for signal in all_signals:
            key = signal.signal_type.value
            summary[key] = summary.get(key, 0) + 1

        top_signals = all_signals[:20]

        result = ScanResult(
            scan_time=scan_time,
            total_stocks=total_stocks,
            signals_found=len(all_signals),
            signals=all_signals,
            summary=summary,
            top_signals=top_signals,
        )

        print(f"\n✅ 并行扫描完成: 发现 {len(all_signals)} 个信号")

        return result


def run_scan(
    db_path: Path | None = None,
    signal_type: str | None = None,
    min_score: float = 0,
    exclude_delisted: bool = True,
    parallel: bool = False,
    max_workers: int = 4,
) -> ScanResult:
    """
    运行扫描的便捷函数

    Args:
        db_path: 数据库路径
        signal_type: 信号类型筛选
        min_score: 最低得分
        exclude_delisted: 是否排除退市股票
        parallel: 是否并行扫描
        max_workers: 并行工作数

    Returns:
        扫描结果
    """
    project_root = Path(__file__).parent.parent.parent
    project_root / "data"

    db_path = db_path or get_stock_analysis_db_path()

    scanner = MarketScanner(db_path)
    scanner.connect()

    try:
        signal_types = None
        if signal_type:
            try:
                st = SignalType(signal_type)
                signal_types = [st]
            except ValueError:
                print(f"未知的信号类型: {signal_type}")

        if parallel:
            return scanner.scan_parallel(
                signal_types=signal_types,
                min_score=min_score,
                exclude_delisted=exclude_delisted,
                max_workers=max_workers,
            )
        else:
            return scanner.scan_all(
                signal_types=signal_types,
                min_score=min_score,
                exclude_delisted=exclude_delisted,
            )
    finally:
        scanner.close()

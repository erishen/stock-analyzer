"""
Market Timing Module.
大盘择时模块 - 基于市场状态调整策略
"""

import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from config import get_stock_analysis_db_path


class MarketState(Enum):
    """市场状态"""

    BULL = "bull"  # 牛市
    BEAR = "bear"  # 熊市
    SIDEWAYS = "sideways"  # 震荡
    UNKNOWN = "unknown"  # 未知


@dataclass
class MarketIndicator:
    """市场指标"""

    date: str
    state: MarketState
    score: float
    ma_trend: str
    rsi_level: str
    volatility: str
    breadth: float
    signal: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "state": self.state.value,
            "score": round(self.score, 2),
            "ma_trend": self.ma_trend,
            "rsi_level": self.rsi_level,
            "volatility": self.volatility,
            "breadth": round(self.breadth * 100, 2),
            "signal": self.signal,
        }


class MarketTiming:
    """大盘择时器"""

    def __init__(
        self,
        ma_short: int = 5,
        ma_long: int = 20,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        volatility_threshold: float = 0.02,
    ):
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.volatility_threshold = volatility_threshold

    def analyze_market(
        self,
        db_path: Path,
        date: str | None = None,
    ) -> MarketIndicator:
        """
        分析市场状态

        Args:
            db_path: 数据库路径
            date: 分析日期 (None 表示最新日期)

        Returns:
            市场指标
        """
        with sqlite3.connect(str(db_path)) as conn:
            if date is None:
                cursor = conn.execute("SELECT MAX(date) FROM stock_analysis")
                date = cursor.fetchone()[0]

            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN change_percent > 0 THEN 1 ELSE 0 END) as up_count,
                    SUM(CASE WHEN change_percent < 0 THEN 1 ELSE 0 END) as down_count,
                    AVG(change_percent) as avg_change,
                    AVG(rsi) as avg_rsi,
                    AVG(ma5) as avg_ma5,
                    AVG(ma20) as avg_ma20
                FROM stock_analysis
                WHERE date = ?
            """,
                (date,),
            )
            row = cursor.fetchone()

            if not row or row[0] == 0:
                return MarketIndicator(
                    date=date,
                    state=MarketState.UNKNOWN,
                    score=0,
                    ma_trend="未知",
                    rsi_level="未知",
                    volatility="未知",
                    breadth=0,
                    signal="无数据",
                )

            total, up_count, _down_count, avg_change, avg_rsi, avg_ma5, avg_ma20 = row

            breadth = up_count / total if total > 0 else 0

            cursor = conn.execute(
                """
                SELECT date, AVG(change_percent) as avg_change
                FROM stock_analysis
                WHERE date <= ?
                GROUP BY date
                ORDER BY date DESC
                LIMIT 30
            """,
                (date,),
            )
            market_returns = pd.DataFrame(cursor.fetchall(), columns=["date", "avg_change"])

        volatility = 0
        if len(market_returns) > 1:
            returns = market_returns["avg_change"].dropna() / 100
            volatility = returns.std()

        score = 0

        if avg_ma5 and avg_ma20:
            if avg_ma5 > avg_ma20:
                ma_trend = "多头排列"
                score += 20
            else:
                ma_trend = "空头排列"
                score -= 10
        else:
            ma_trend = "未知"

        if avg_rsi:
            if avg_rsi < self.rsi_oversold:
                rsi_level = "超卖"
                score += 15
            elif avg_rsi > self.rsi_overbought:
                rsi_level = "超买"
                score -= 10
            elif avg_rsi < 50:
                rsi_level = "偏弱"
            else:
                rsi_level = "偏强"
                score += 5
        else:
            rsi_level = "未知"

        if volatility > self.volatility_threshold * 2:
            volatility_level = "高波动"
            score -= 10
        elif volatility > self.volatility_threshold:
            volatility_level = "中等波动"
        else:
            volatility_level = "低波动"
            score += 5

        if breadth > 0.7:
            score += 15
        elif breadth > 0.5:
            score += 5
        elif breadth < 0.3:
            score -= 15

        if avg_change and avg_change > 2:
            score += 10
        elif avg_change and avg_change < -2:
            score -= 10

        if score >= 30:
            state = MarketState.BULL
            signal = "积极做多"
        elif score <= -20:
            state = MarketState.BEAR
            signal = "谨慎观望"
        else:
            state = MarketState.SIDEWAYS
            signal = "轻仓操作"

        return MarketIndicator(
            date=date,
            state=state,
            score=score,
            ma_trend=ma_trend,
            rsi_level=rsi_level,
            volatility=volatility_level,
            breadth=breadth,
            signal=signal,
        )

    def should_trade(self, market_indicator: MarketIndicator) -> tuple[bool, float]:
        """
        判断是否应该交易

        Args:
            market_indicator: 市场指标

        Returns:
            (是否交易, 建议仓位比例)
        """
        if market_indicator.state == MarketState.BULL:
            return True, 1.0
        elif market_indicator.state == MarketState.BEAR:
            return False, 0.0
        else:
            return True, 0.5

    def get_position_adjustment(self, market_indicator: MarketIndicator) -> float:
        """
        获取仓位调整系数

        Args:
            market_indicator: 市场指标

        Returns:
            仓位调整系数 (0-1)
        """
        score = market_indicator.score

        if score >= 40:
            return 1.2
        elif score >= 20:
            return 1.0
        elif score >= 0:
            return 0.7
        elif score >= -20:
            return 0.4
        else:
            return 0.2


def print_market_timing(indicator: MarketIndicator):
    """打印市场择时信息"""
    state_emoji = {
        MarketState.BULL: "🐂",
        MarketState.BEAR: "🐻",
        MarketState.SIDEWAYS: "📊",
        MarketState.UNKNOWN: "❓",
    }

    print(f"\n{'=' * 50}")
    print("📊 大盘择时分析")
    print(f"{'=' * 50}")

    print(f"\n📅 日期: {indicator.date}")
    print(f"📈 市场状态: {state_emoji.get(indicator.state, '')} {indicator.state.value.upper()}")
    print(f"📊 综合得分: {indicator.score}")

    print("\n📋 市场指标:")
    print(f"   均线趋势: {indicator.ma_trend}")
    print(f"   RSI 水平: {indicator.rsi_level}")
    print(f"   波动水平: {indicator.volatility}")
    print(f"   市场宽度: {indicator.breadth:.1f}% 上涨")

    print(f"\n💡 交易建议: {indicator.signal}")

    if indicator.state == MarketState.BULL:
        print("   建议仓位: 80-100%")
    elif indicator.state == MarketState.SIDEWAYS:
        print("   建议仓位: 30-50%")
    else:
        print("   建议仓位: 0-20% 或空仓")


def run_market_timing(db_path: Path | None = None) -> MarketIndicator:
    """运行大盘择时分析"""
    project_root = Path(__file__).parent.parent.parent
    project_root / "data"
    db_path = db_path or get_stock_analysis_db_path()

    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    timing = MarketTiming()
    indicator = timing.analyze_market(db_path)
    print_market_timing(indicator)

    return indicator

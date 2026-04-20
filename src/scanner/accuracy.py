"""
Signal Accuracy Analyzer for Stock Analyzer.
信号准确率分析 - 统计历史信号的准确率和收益

分析内容:
- 各类信号的胜率
- 信号后的涨跌幅度
- 最佳持有天数
- 信号有效性评分
"""

import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from scanner.signals import SignalType


@dataclass
class SignalPerformance:
    """信号表现"""

    signal_type: SignalType
    total_signals: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    avg_win_return: float = 0.0
    avg_loss_return: float = 0.0
    max_return: float = 0.0
    max_loss: float = 0.0
    best_holding_days: int = 0
    returns_by_days: dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type.value,
            "total_signals": self.total_signals,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(self.win_rate * 100, 2),
            "avg_return": round(self.avg_return * 100, 2),
            "avg_win_return": round(self.avg_win_return * 100, 2),
            "avg_loss_return": round(self.avg_loss_return * 100, 2),
            "max_return": round(self.max_return * 100, 2),
            "max_loss": round(self.max_loss * 100, 2),
            "best_holding_days": self.best_holding_days,
        }


@dataclass
class AccuracyReport:
    """准确率报告"""

    analysis_date: str
    total_signals_analyzed: int
    date_range: str
    signal_performances: list[SignalPerformance]
    overall_win_rate: float
    best_signal: str
    worst_signal: str
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_date": self.analysis_date,
            "total_signals_analyzed": self.total_signals_analyzed,
            "date_range": self.date_range,
            "signal_performances": [p.to_dict() for p in self.signal_performances],
            "overall_win_rate": round(self.overall_win_rate * 100, 2),
            "best_signal": self.best_signal,
            "worst_signal": self.worst_signal,
            "recommendations": self.recommendations,
        }


class SignalAccuracyAnalyzer:
    """信号准确率分析器"""

    BULLISH_SIGNALS = [
        SignalType.MACD_GOLDEN_CROSS,
        SignalType.KDJ_GOLDEN_CROSS,
        SignalType.MA5_CROSS_UP_MA20,
        SignalType.RSI_OVERSOLD,
        SignalType.BOLL_LOWER_BREAK,
        SignalType.TREND_UP,
    ]

    BEARISH_SIGNALS = [
        SignalType.MACD_DEATH_CROSS,
        SignalType.KDJ_DEATH_CROSS,
        SignalType.MA5_CROSS_DOWN_MA20,
        SignalType.RSI_OVERBOUGHT,
        SignalType.BOLL_UPPER_BREAK,
        SignalType.TREND_DOWN,
    ]

    HOLDING_PERIODS = [1, 3, 5, 10, 20]

    def __init__(self, db_path: Path):
        self.db_path = db_path
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

    def get_stock_data(self, code: str) -> pd.DataFrame:
        """获取股票数据"""
        query = """
            SELECT date, close, high, low, open, volume,
                   macd, macd_signal, rsi, kdj_k, kdj_d,
                   ma5, ma10, ma20, boll_upper, boll_lower
            FROM stock_analysis
            WHERE code = ?
            ORDER BY date ASC
        """
        df = pd.read_sql_query(query, self.conn, params=(code,))
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def detect_signal_at_date(self, df: pd.DataFrame, idx: int) -> list[SignalType]:
        """检测指定日期的信号"""
        signals = []

        if idx < 1 or idx >= len(df):
            return signals

        row = df.iloc[idx]
        prev = df.iloc[idx - 1]

        if prev["macd"] <= prev["macd_signal"] and row["macd"] > row["macd_signal"]:
            signals.append(SignalType.MACD_GOLDEN_CROSS)
        elif prev["macd"] >= prev["macd_signal"] and row["macd"] < row["macd_signal"]:
            signals.append(SignalType.MACD_DEATH_CROSS)

        if prev["kdj_k"] <= prev["kdj_d"] and row["kdj_k"] > row["kdj_d"]:
            signals.append(SignalType.KDJ_GOLDEN_CROSS)
        elif prev["kdj_k"] >= prev["kdj_d"] and row["kdj_k"] < row["kdj_d"]:
            signals.append(SignalType.KDJ_DEATH_CROSS)

        if prev["ma5"] <= prev["ma20"] and row["ma5"] > row["ma20"]:
            signals.append(SignalType.MA5_CROSS_UP_MA20)
        elif prev["ma5"] >= prev["ma20"] and row["ma5"] < row["ma20"]:
            signals.append(SignalType.MA5_CROSS_DOWN_MA20)

        if row["rsi"] < 30:
            signals.append(SignalType.RSI_OVERSOLD)
        elif row["rsi"] > 70:
            signals.append(SignalType.RSI_OVERBOUGHT)

        if row["close"] > row["boll_upper"]:
            signals.append(SignalType.BOLL_UPPER_BREAK)
        elif row["close"] < row["boll_lower"]:
            signals.append(SignalType.BOLL_LOWER_BREAK)

        if row["ma5"] > row["ma10"] > row["ma20"]:
            signals.append(SignalType.TREND_UP)
        elif row["ma5"] < row["ma10"] < row["ma20"]:
            signals.append(SignalType.TREND_DOWN)

        return signals

    def calculate_future_return(self, df: pd.DataFrame, idx: int, days: int) -> float | None:
        """计算未来 N 天的收益率"""
        if idx + days >= len(df):
            return None

        current_price = df.iloc[idx]["close"]
        future_price = df.iloc[idx + days]["close"]

        return (future_price - current_price) / current_price

    def analyze_signal_performance(
        self,
        df: pd.DataFrame,
        signal_type: SignalType,
        holding_days: int = 5,
    ) -> dict:
        """分析单个信号的表现"""
        returns = []
        win_threshold = 0.0

        for idx in range(1, len(df) - holding_days):
            signals = self.detect_signal_at_date(df, idx)

            if signal_type in signals:
                ret = self.calculate_future_return(df, idx, holding_days)
                if ret is not None:
                    if signal_type in self.BEARISH_SIGNALS:
                        ret = -ret
                    returns.append(ret)

        if not returns:
            return {
                "signal_type": signal_type,
                "total_signals": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0.0,
                "avg_return": 0.0,
                "returns": [],
            }

        returns_arr = np.array(returns)
        wins = returns_arr[returns_arr > win_threshold]
        losses = returns_arr[returns_arr <= win_threshold]

        return {
            "signal_type": signal_type,
            "total_signals": len(returns),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": len(wins) / len(returns) if returns else 0,
            "avg_return": float(np.mean(returns_arr)),
            "avg_win_return": float(np.mean(wins)) if len(wins) > 0 else 0,
            "avg_loss_return": float(np.mean(losses)) if len(losses) > 0 else 0,
            "max_return": float(np.max(returns_arr)),
            "max_loss": float(np.min(returns_arr)),
            "returns": returns,
        }

    def analyze_all_signals(self, holding_days: int = 5) -> list[SignalPerformance]:
        """分析所有信号的表现"""
        cursor = self.conn.execute("SELECT DISTINCT code FROM stock_analysis")
        codes = [row[0] for row in cursor.fetchall()]

        signal_stats: dict[SignalType, dict] = {}

        for signal_type in list(SignalType):
            signal_stats[signal_type] = {
                "returns": [],
                "win_count": 0,
                "loss_count": 0,
            }

        print(f"\n📊 分析 {len(codes)} 只股票的信号准确率...")

        for i, code in enumerate(codes, 1):
            try:
                df = self.get_stock_data(code)
                if len(df) < holding_days + 20:
                    continue

                for idx in range(20, len(df) - holding_days):
                    signals = self.detect_signal_at_date(df, idx)

                    for signal_type in signals:
                        ret = self.calculate_future_return(df, idx, holding_days)
                        if ret is not None:
                            if signal_type in self.BEARISH_SIGNALS:
                                ret = -ret
                            signal_stats[signal_type]["returns"].append(ret)
                            if ret > 0:
                                signal_stats[signal_type]["win_count"] += 1
                            else:
                                signal_stats[signal_type]["loss_count"] += 1

            except Exception:
                continue

            if i % 500 == 0:
                print(f"   进度: {i}/{len(codes)} ({i / len(codes) * 100:.1f}%)")

        performances = []
        for signal_type, stats in signal_stats.items():
            returns = stats["returns"]
            if not returns:
                continue

            returns_arr = np.array(returns)
            wins = returns_arr[returns_arr > 0]
            losses = returns_arr[returns_arr <= 0]

            perf = SignalPerformance(
                signal_type=signal_type,
                total_signals=len(returns),
                win_count=len(wins),
                loss_count=len(losses),
                win_rate=len(wins) / len(returns) if returns else 0,
                avg_return=float(np.mean(returns_arr)),
                avg_win_return=float(np.mean(wins)) if len(wins) > 0 else 0,
                avg_loss_return=float(np.mean(losses)) if len(losses) > 0 else 0,
                max_return=float(np.max(returns_arr)),
                max_loss=float(np.min(returns_arr)),
            )
            performances.append(perf)

        performances.sort(key=lambda x: x.win_rate, reverse=True)
        return performances

    def find_best_holding_period(self, code: str, signal_type: SignalType) -> int:
        """找到最佳持有天数"""
        df = self.get_stock_data(code)
        if len(df) < 30:
            return 5

        returns_by_period = {p: [] for p in self.HOLDING_PERIODS}

        for idx in range(20, len(df) - max(self.HOLDING_PERIODS)):
            signals = self.detect_signal_at_date(df, idx)
            if signal_type in signals:
                for period in self.HOLDING_PERIODS:
                    ret = self.calculate_future_return(df, idx, period)
                    if ret is not None:
                        if signal_type in self.BEARISH_SIGNALS:
                            ret = -ret
                        returns_by_period[period].append(ret)

        best_period = 5
        best_avg_return = 0

        for period, returns in returns_by_period.items():
            if returns:
                avg = np.mean(returns)
                if avg > best_avg_return:
                    best_avg_return = avg
                    best_period = period

        return best_period

    def generate_report(self, holding_days: int = 5) -> AccuracyReport:
        """生成准确率报告"""
        performances = self.analyze_all_signals(holding_days)

        if not performances:
            return AccuracyReport(
                analysis_date=datetime.now().isoformat(),
                total_signals_analyzed=0,
                date_range="",
                signal_performances=[],
                overall_win_rate=0,
                best_signal="",
                worst_signal="",
                recommendations=["没有足够的信号数据进行分析"],
            )

        total_signals = sum(p.total_signals for p in performances)
        total_wins = sum(p.win_count for p in performances)
        overall_win_rate = total_wins / total_signals if total_signals > 0 else 0

        best_signal = performances[0].signal_type.value if performances else ""
        worst_signal = performances[-1].signal_type.value if performances else ""

        recommendations = self._generate_recommendations(performances)

        cursor = self.conn.execute("SELECT MIN(date), MAX(date) FROM stock_analysis")
        row = cursor.fetchone()
        date_range = f"{row[0]} ~ {row[1]}"

        return AccuracyReport(
            analysis_date=datetime.now().isoformat(),
            total_signals_analyzed=total_signals,
            date_range=date_range,
            signal_performances=performances,
            overall_win_rate=overall_win_rate,
            best_signal=best_signal,
            worst_signal=worst_signal,
            recommendations=recommendations,
        )

    def _generate_recommendations(self, performances: list[SignalPerformance]) -> list[str]:
        """生成投资建议"""
        recommendations = []

        high_win_signals = [p for p in performances if p.win_rate > 0.55]
        if high_win_signals:
            recommendations.append(f"高胜率信号: {', '.join([p.signal_type.value for p in high_win_signals[:3]])}")

        high_return_signals = [p for p in performances if p.avg_return > 0.02]
        if high_return_signals:
            recommendations.append(f"高收益信号: {', '.join([p.signal_type.value for p in high_return_signals[:3]])}")

        low_win_signals = [p for p in performances if p.win_rate < 0.45]
        if low_win_signals:
            recommendations.append(f"谨慎使用: {', '.join([p.signal_type.value for p in low_win_signals[:3]])}")

        return recommendations


def run_accuracy_analysis(db_path: Path | None = None, holding_days: int = 5) -> AccuracyReport:
    """
    运行准确率分析

    Args:
        db_path: 数据库路径
        holding_days: 持有天数

    Returns:
        准确率报告
    """
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"

    db_path = db_path or data_dir / "stock_analysis.db"

    analyzer = SignalAccuracyAnalyzer(db_path)
    analyzer.connect()

    try:
        return analyzer.generate_report(holding_days)
    finally:
        analyzer.close()

"""
Stock Scoring System for Stock Analyzer.
选股评分系统 - 多因子综合评分排名

评分因子:
- 趋势因子: MA 排列、动量
- 动量因子: RSI、MACD、ROC
- 波动因子: ATR、布林带宽度
- 量价因子: OBV、成交量比
- 技术形态: KDJ、突破信号
"""

import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_stock_analysis_db_path
from data import get_stock_name


@dataclass
class ScoringFactor:
    """评分因子"""

    name: str
    weight: float
    score: float = 0.0
    value: float = 0.0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "score": round(self.score, 2),
            "value": round(self.value, 4) if isinstance(self.value, float) else self.value,
            "description": self.description,
        }


@dataclass
class StockScore:
    """股票评分"""

    code: str
    name: str
    total_score: float
    rank: int = 0
    factors: list[ScoringFactor] = field(default_factory=list)
    price: float = 0.0
    change_percent: float = 0.0
    recommendation: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "total_score": round(self.total_score, 2),
            "rank": self.rank,
            "factors": [f.to_dict() for f in self.factors],
            "price": round(self.price, 2),
            "change_percent": round(self.change_percent, 2),
            "recommendation": self.recommendation,
            "details": self.details,
        }


@dataclass
class ScoringReport:
    """评分报告"""

    scoring_date: str
    total_stocks: int
    top_stocks: list[StockScore]
    bottom_stocks: list[StockScore]
    factor_summary: dict[str, dict]
    market_overview: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scoring_date": self.scoring_date,
            "total_stocks": self.total_stocks,
            "top_stocks": [s.to_dict() for s in self.top_stocks],
            "bottom_stocks": [s.to_dict() for s in self.bottom_stocks],
            "factor_summary": self.factor_summary,
            "market_overview": self.market_overview,
        }


class StockScorer:
    """股票评分器"""

    FACTOR_WEIGHTS: ClassVar[dict[str, float]] = {
        "trend": 0.25,
        "momentum": 0.25,
        "volatility": 0.15,
        "volume": 0.15,
        "signal": 0.20,
    }

    def __init__(self):
        self.factors: list[ScoringFactor] = []

    def calculate_all_factors(self, df: pd.DataFrame) -> list[ScoringFactor]:
        """计算所有评分因子"""
        if len(df) < 30:
            return []

        factors = []
        latest = df.iloc[-1]

        trend_factor = self._calculate_trend_score(df, latest)
        factors.append(trend_factor)

        momentum_factor = self._calculate_momentum_score(df, latest)
        factors.append(momentum_factor)

        volatility_factor = self._calculate_volatility_score(df, latest)
        factors.append(volatility_factor)

        volume_factor = self._calculate_volume_score(df, latest)
        factors.append(volume_factor)

        signal_factor = self._calculate_signal_score(df, latest)
        factors.append(signal_factor)

        return factors

    def _calculate_trend_score(self, df: pd.DataFrame, latest: pd.Series) -> ScoringFactor:
        """计算趋势因子得分"""
        score = 0.0
        details = []

        ma5 = latest.get("ma5", 0) or 0
        ma10 = latest.get("ma10", 0) or 0
        ma20 = latest.get("ma20", 0) or 0
        close = latest.get("close", 0) or 0

        if ma5 > ma10 > ma20:
            score += 40
            details.append("多头排列")
        elif ma5 < ma10 < ma20:
            score -= 30
            details.append("空头排列")

        if close > ma5:
            score += 15
            details.append("价格在MA5之上")
        elif close < ma5:
            score -= 10
            details.append("价格在MA5之下")

        if close > ma20:
            score += 10
            details.append("价格在MA20之上")

        if len(df) >= 20:
            ma20_slope = (df["ma20"].iloc[-1] - df["ma20"].iloc[-5]) / df["ma20"].iloc[-5] * 100
            if ma20_slope > 2:
                score += 15
                details.append("MA20上升趋势")
            elif ma20_slope < -2:
                score -= 15
                details.append("MA20下降趋势")

        return ScoringFactor(
            name="趋势因子",
            weight=self.FACTOR_WEIGHTS["trend"],
            score=max(0, min(100, score + 50)),
            value=ma5 / ma20 if ma20 > 0 else 1,
            description=", ".join(details) if details else "中性",
        )

    def _calculate_momentum_score(self, df: pd.DataFrame, latest: pd.Series) -> ScoringFactor:
        """计算动量因子得分"""
        score = 50.0
        details = []

        rsi = latest.get("rsi", 50) or 50
        if rsi < 30:
            score += 25
            details.append(f"RSI超卖({rsi:.1f})")
        elif rsi > 70:
            score -= 20
            details.append(f"RSI超买({rsi:.1f})")
        elif 40 <= rsi <= 60:
            score += 10
            details.append(f"RSI中性({rsi:.1f})")

        macd = latest.get("macd", 0) or 0
        macd_signal = latest.get("macd_signal", 0) or 0
        macd_hist = latest.get("macd_hist", 0) or 0

        if macd > macd_signal:
            score += 15
            details.append("MACD金叉区域")
        else:
            score -= 10
            details.append("MACD死叉区域")

        if macd_hist > 0:
            score += 10
            details.append("MACD柱状图为正")

        if len(df) >= 10:
            momentum_10d = (df["close"].iloc[-1] / df["close"].iloc[-10] - 1) * 100
            if momentum_10d > 10:
                score += 10
                details.append(f"10日涨幅{momentum_10d:.1f}%")
            elif momentum_10d < -10:
                score -= 15
                details.append(f"10日跌幅{abs(momentum_10d):.1f}%")

        return ScoringFactor(
            name="动量因子",
            weight=self.FACTOR_WEIGHTS["momentum"],
            score=max(0, min(100, score)),
            value=rsi,
            description=", ".join(details) if details else "中性",
        )

    def _calculate_volatility_score(self, df: pd.DataFrame, latest: pd.Series) -> ScoringFactor:
        """计算波动因子得分"""
        score = 50.0
        details = []

        atr_ratio = latest.get("atr_ratio", 0) or 0
        if atr_ratio < 0.02:
            score += 20
            details.append("低波动")
        elif atr_ratio > 0.05:
            score -= 15
            details.append("高波动")

        boll_width = latest.get("boll_width", 0) or 0
        if boll_width < 0.05:
            score += 15
            details.append("布林带收窄(可能突破)")
        elif boll_width > 0.15:
            score -= 10
            details.append("布林带扩张")

        boll_position = latest.get("boll_position", 0.5) or 0.5
        if 0.3 <= boll_position <= 0.7:
            score += 10
            details.append("价格在布林带中轨附近")
        elif boll_position < 0.1:
            score += 20
            details.append("接近布林带下轨(可能反弹)")
        elif boll_position > 0.9:
            score -= 15
            details.append("接近布林带上轨(可能回调)")

        if len(df) >= 20:
            volatility_20d = df["close"].pct_change().std() * 100
            if volatility_20d < 2:
                score += 10
            elif volatility_20d > 5:
                score -= 10

        return ScoringFactor(
            name="波动因子",
            weight=self.FACTOR_WEIGHTS["volatility"],
            score=max(0, min(100, score)),
            value=atr_ratio,
            description=", ".join(details) if details else "中性",
        )

    def _calculate_volume_score(self, df: pd.DataFrame, latest: pd.Series) -> ScoringFactor:
        """计算量价因子得分"""
        score = 50.0
        details = []

        volume = latest.get("volume", 0) or 0
        if len(df) >= 5:
            avg_volume = df["volume"].iloc[-5:].mean()
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1

            if volume_ratio > 2:
                score += 20
                details.append(f"放量({volume_ratio:.1f}倍)")
            elif volume_ratio < 0.5:
                score -= 10
                details.append(f"缩量({volume_ratio:.1f}倍)")

        obv = latest.get("obv", 0) or 0
        obv_ma10 = latest.get("obv_ma10", 0) or 0
        if obv > obv_ma10:
            score += 15
            details.append("OBV上升")
        else:
            score -= 10
            details.append("OBV下降")

        turnover_rate = latest.get("turnover_rate", 0) or 0
        if 3 <= turnover_rate <= 10:
            score += 10
            details.append(f"换手率适中({turnover_rate:.1f}%)")
        elif turnover_rate > 15:
            score -= 5
            details.append(f"换手率过高({turnover_rate:.1f}%)")

        return ScoringFactor(
            name="量价因子",
            weight=self.FACTOR_WEIGHTS["volume"],
            score=max(0, min(100, score)),
            value=volume,
            description=", ".join(details) if details else "中性",
        )

    def _calculate_signal_score(self, df: pd.DataFrame, latest: pd.Series) -> ScoringFactor:
        """计算信号因子得分"""
        score = 50.0
        details = []

        kdj_k = latest.get("kdj_k", 50) or 50
        kdj_d = latest.get("kdj_d", 50) or 50
        kdj_j = latest.get("kdj_j", 50) or 50

        if kdj_k > kdj_d:
            score += 15
            details.append("KDJ金叉区域")
        else:
            score -= 10
            details.append("KDJ死叉区域")

        if kdj_j < 20:
            score += 15
            details.append(f"KDJ超卖(J={kdj_j:.1f})")
        elif kdj_j > 80:
            score -= 15
            details.append(f"KDJ超买(J={kdj_j:.1f})")

        if len(df) >= 2:
            prev = df.iloc[-2]
            if (prev.get("macd", 0) or 0) <= (prev.get("macd_signal", 0) or 0) and (latest.get("macd", 0) or 0) > (latest.get("macd_signal", 0) or 0):
                score += 20
                details.append("MACD金叉信号")

            if (prev.get("kdj_k", 0) or 0) <= (prev.get("kdj_d", 0) or 0) and (latest.get("kdj_k", 0) or 0) > (latest.get("kdj_d", 0) or 0):
                score += 15
                details.append("KDJ金叉信号")

        return ScoringFactor(
            name="信号因子",
            weight=self.FACTOR_WEIGHTS["signal"],
            score=max(0, min(100, score)),
            value=kdj_k,
            description=", ".join(details) if details else "中性",
        )

    def calculate_total_score(self, factors: list[ScoringFactor]) -> float:
        """计算综合得分"""
        if not factors:
            return 0.0

        total = sum(f.score * f.weight for f in factors)
        return min(100, max(0, total))


class StockRankingSystem:
    """股票排名系统"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.scorer = StockScorer()
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

    def get_stock_codes(self) -> list[str]:
        """获取所有股票代码"""
        query = "SELECT DISTINCT code FROM stock_analysis ORDER BY code"
        cursor = self.conn.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def get_stock_data(self, code: str) -> pd.DataFrame:
        """获取股票数据"""
        query = """
            SELECT * FROM stock_analysis
            WHERE code = ?
            ORDER BY date DESC
            LIMIT 60
        """
        df = pd.read_sql_query(query, self.conn, params=(code,))
        if not df.empty:
            df = df.sort_values("date").reset_index(drop=True)
        return df

    def score_stock(self, code: str) -> StockScore | None:
        """对单只股票评分"""
        name = get_stock_name(code)

        if self._is_excluded_stock(name):
            return None

        df = self.get_stock_data(code)
        if len(df) < 30:
            return None

        factors = self.scorer.calculate_all_factors(df)
        if not factors:
            return None

        total_score = self.scorer.calculate_total_score(factors)
        latest = df.iloc[-1]

        price = float(latest.get("close", 0) or 0)
        change_percent = float(latest.get("change_percent", 0) or 0)

        recommendation = self._get_recommendation(total_score, factors)

        return StockScore(
            code=code,
            name=name,
            total_score=total_score,
            factors=factors,
            price=price,
            change_percent=change_percent,
            recommendation=recommendation,
            details={
                "rsi": float(latest.get("rsi", 50) or 50),
                "macd": float(latest.get("macd", 0) or 0),
                "kdj_j": float(latest.get("kdj_j", 50) or 50),
            },
        )

    def _is_excluded_stock(self, name: str) -> bool:
        """判断是否为排除的股票类型"""
        excluded_keywords = [
            "ST",
            "st",
            "*ST",
            "SST",
            "S*ST",
            "退市",
            "退",
            "PT",
            "停牌",
        ]
        return any(keyword in name for keyword in excluded_keywords)

    def _get_recommendation(self, total_score: float, factors: list[ScoringFactor]) -> str:
        """获取投资建议"""
        if total_score >= 70:
            return "强烈推荐"
        elif total_score >= 60:
            return "推荐关注"
        elif total_score >= 50:
            return "中性观望"
        elif total_score >= 40:
            return "谨慎观望"
        else:
            return "建议回避"

    def rank_all_stocks(self, top_n: int = 50) -> list[StockScore]:
        """对所有股票进行排名"""
        codes = self.get_stock_codes()
        scores: list[StockScore] = []

        print(f"\n📊 对 {len(codes)} 只股票进行评分...")

        for i, code in enumerate(codes, 1):
            try:
                score = self.score_stock(code)
                if score:
                    scores.append(score)
            except Exception:
                continue

            if i % 500 == 0:
                print(f"   进度: {i}/{len(codes)} ({i / len(codes) * 100:.1f}%)")

        scores.sort(key=lambda x: x.total_score, reverse=True)

        for i, score in enumerate(scores, 1):
            score.rank = i

        return scores[:top_n]

    def generate_report(self, top_n: int = 50) -> ScoringReport:
        """生成评分报告"""
        all_scores = self.rank_all_stocks(top_n * 2)

        top_stocks = all_scores[:top_n]
        bottom_stocks = all_scores[-10:] if len(all_scores) >= 10 else all_scores[-len(all_scores) :]

        factor_summary = self._calculate_factor_summary(all_scores)

        market_overview = self._calculate_market_overview(all_scores)

        return ScoringReport(
            scoring_date=datetime.now().isoformat(),
            total_stocks=len(all_scores),
            top_stocks=top_stocks,
            bottom_stocks=bottom_stocks,
            factor_summary=factor_summary,
            market_overview=market_overview,
        )

    def _calculate_factor_summary(self, scores: list[StockScore]) -> dict[str, dict]:
        """计算因子汇总"""
        summary = {}

        factor_names = ["趋势因子", "动量因子", "波动因子", "量价因子", "信号因子"]

        for name in factor_names:
            factor_scores = []
            for score in scores:
                for factor in score.factors:
                    if factor.name == name:
                        factor_scores.append(factor.score)
                        break

            if factor_scores:
                summary[name] = {
                    "avg_score": round(np.mean(factor_scores), 2),
                    "max_score": round(max(factor_scores), 2),
                    "min_score": round(min(factor_scores), 2),
                }

        return summary

    def _calculate_market_overview(self, scores: list[StockScore]) -> dict[str, Any]:
        """计算市场概览"""
        if not scores:
            return {}

        total_scores = [s.total_score for s in scores]

        strong_count = len([s for s in scores if s.total_score >= 60])
        weak_count = len([s for s in scores if s.total_score < 40])

        return {
            "avg_score": round(np.mean(total_scores), 2),
            "median_score": round(np.median(total_scores), 2),
            "strong_count": strong_count,
            "weak_count": weak_count,
            "strong_ratio": round(strong_count / len(scores) * 100, 2) if scores else 0,
        }


def run_scoring(db_path: Path | None = None, top_n: int = 50) -> ScoringReport:
    """
    运行评分系统

    Args:
        db_path: 数据库路径
        top_n: 返回前 N 只股票

    Returns:
        评分报告
    """
    project_root = Path(__file__).parent.parent.parent
    project_root / "data"

    db_path = db_path or get_stock_analysis_db_path()

    system = StockRankingSystem(db_path)
    system.connect()

    try:
        return system.generate_report(top_n)
    finally:
        system.close()

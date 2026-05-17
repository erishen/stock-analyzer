"""
Sector Rotation Analysis Module.
行业轮动分析模块 - 分析行业强弱、轮动信号
"""

import json
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from config import get_stock_analysis_db_path


class SectorStrength(Enum):
    """行业强度"""

    STRONG = "strong"  # 强势
    WEAK = "weak"  # 弱势
    NEUTRAL = "neutral"  # 中性


class RotationSignal(Enum):
    """轮动信号"""

    ENTER = "enter"  # 进入
    EXIT = "exit"  # 退出
    HOLD = "hold"  # 持有
    REDUCE = "reduce"  # 减仓


@dataclass
class SectorInfo:
    """行业信息"""

    name: str
    stocks: list[str]
    avg_return: float
    avg_volume: float
    strength: SectorStrength
    rank: int
    momentum: float
    trend: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "stock_count": len(self.stocks),
            "avg_return": round(self.avg_return * 100, 2),
            "avg_volume": self.avg_volume,
            "strength": self.strength.value,
            "rank": self.rank,
            "momentum": round(self.momentum * 100, 2),
            "trend": self.trend,
        }


@dataclass
class SectorRotation:
    """行业轮动信号"""

    sector: str
    signal: RotationSignal
    score: float
    reason: str
    recommended_weight: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sector": self.sector,
            "signal": self.signal.value,
            "score": round(self.score, 2),
            "reason": self.reason,
            "recommended_weight": round(self.recommended_weight * 100, 2),
        }


@dataclass
class SectorAnalysisResult:
    """行业分析结果"""

    date: str
    sectors: list[SectorInfo]
    rotations: list[SectorRotation]
    top_sectors: list[str]
    bottom_sectors: list[str]
    market_breadth: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "sectors": [s.to_dict() for s in self.sectors],
            "rotations": [r.to_dict() for r in self.rotations],
            "top_sectors": self.top_sectors,
            "bottom_sectors": self.bottom_sectors,
            "market_breadth": round(self.market_breadth * 100, 2),
        }


DEFAULT_SECTORS = {
    "银行": ["sh600000", "sh600016", "sh600036", "sh601166", "sh601288", "sh601398", "sh601939", "sh601988"],
    "证券": ["sh600030", "sh600837", "sh601211", "sh601688", "sh601901"],
    "保险": ["sh601318", "sh601601", "sh601628"],
    "房地产": ["sh000002", "sh600048", "sh600383", "sh001979"],
    "建筑": ["sh600068", "sh601186", "sh601390", "sh601668"],
    "钢铁": ["sh600019", "sh600782", "sh601003"],
    "煤炭": ["sh601088", "sh601225", "sh601666"],
    "石油": ["sh600028", "sh601857"],
    "电力": ["sh600011", "sh600900", "sh601985"],
    "汽车": ["sh600104", "sh600066", "sh601238", "sh601633", "sh002594"],
    "家电": ["sh000333", "sh000651", "sh600690"],
    "食品饮料": ["sh000568", "sh000858", "sh600519", "sh600887"],
    "医药": ["sh000538", "sh600276", "sh600196", "sh000661", "sh300760"],
    "白酒": ["sh000568", "sh000596", "sh000858", "sh600519", "sh600809"],
    "半导体": ["sh002049", "sh002371", "sh603501", "sh603986", "sh688981"],
    "计算机": ["sh002230", "sh002410", "sh300033", "sh300059", "sh688111"],
    "通信": ["sh000063", "sh002475", "sh600050", "sh603160"],
    "电子": ["sh000725", "sh002241", "sh002475", "sh603160"],
    "传媒": ["sh000156", "sh002445", "sh300059", "sh601801"],
    "军工": ["sh600038", "sh600893", "sh601989"],
}


class SectorRotationAnalyzer:
    """行业轮动分析器"""

    def __init__(
        self,
        lookback_days: int = 20,
        top_n: int = 5,
        momentum_threshold: float = 0.05,
    ):
        self.lookback_days = lookback_days
        self.top_n = top_n
        self.momentum_threshold = momentum_threshold
        self.sector_mapping = DEFAULT_SECTORS.copy()

    def load_sector_mapping(self, mapping_file: Path):
        """加载行业映射文件"""
        if mapping_file.exists():
            with open(mapping_file, encoding="utf-8") as f:
                self.sector_mapping = json.load(f)

    def get_sector_stocks(self, sector: str) -> list[str]:
        """获取行业股票列表"""
        return self.sector_mapping.get(sector, [])

    def calculate_sector_metrics(
        self,
        sector: str,
        db_path: Path,
        date: str,
    ) -> SectorInfo | None:
        """计算行业指标"""
        stocks = self.get_sector_stocks(sector)
        if not stocks:
            return None

        placeholders = ",".join(["?" for _ in stocks])
        query = f"""
            SELECT code, change_percent, volume, close, ma5, ma20
            FROM stock_analysis
            WHERE date = ? AND code IN ({placeholders})
        """
        params = [date, *stocks]

        try:
            with sqlite3.connect(str(db_path)) as conn:
                df = pd.read_sql_query(query, conn, params=params)
        except Exception:
            return None

        if df.empty:
            return None

        avg_return = df["change_percent"].mean() / 100 if "change_percent" in df else 0
        avg_volume = df["volume"].mean() if "volume" in df else 0

        valid_stocks = df["code"].tolist()

        momentum = avg_return

        if "ma5" in df and "ma20" in df:
            ma5_avg = df["ma5"].mean()
            ma20_avg = df["ma20"].mean()
            if ma5_avg > ma20_avg:
                trend = "多头"
            elif ma5_avg < ma20_avg:
                trend = "空头"
            else:
                trend = "震荡"
        else:
            trend = "未知"

        if momentum > self.momentum_threshold:
            strength = SectorStrength.STRONG
        elif momentum < -self.momentum_threshold:
            strength = SectorStrength.WEAK
        else:
            strength = SectorStrength.NEUTRAL

        return SectorInfo(
            name=sector,
            stocks=valid_stocks,
            avg_return=avg_return,
            avg_volume=avg_volume,
            strength=strength,
            rank=0,
            momentum=momentum,
            trend=trend,
        )

    def analyze_sectors(
        self,
        db_path: Path,
        date: str | None = None,
    ) -> SectorAnalysisResult:
        """
        分析所有行业

        Args:
            db_path: 数据库路径
            date: 分析日期

        Returns:
            行业分析结果
        """
        if date is None:
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.execute("SELECT MAX(date) FROM stock_analysis")
                date = cursor.fetchone()[0]

        sector_metrics = []
        for sector in self.sector_mapping:
            metrics = self.calculate_sector_metrics(sector, db_path, date)
            if metrics:
                sector_metrics.append(metrics)

        sector_metrics.sort(key=lambda x: x.momentum, reverse=True)

        for i, metrics in enumerate(sector_metrics):
            metrics.rank = i + 1

        rotations = []
        for metrics in sector_metrics:
            signal, score, reason, weight = self._generate_rotation_signal(metrics, sector_metrics)
            rotations.append(
                SectorRotation(
                    sector=metrics.name,
                    signal=signal,
                    score=score,
                    reason=reason,
                    recommended_weight=weight,
                )
            )

        top_sectors = [s.name for s in sector_metrics[: self.top_n]]
        bottom_sectors = [s.name for s in sector_metrics[-self.top_n :]]

        strong_count = sum(1 for s in sector_metrics if s.strength == SectorStrength.STRONG)
        market_breadth = strong_count / len(sector_metrics) if sector_metrics else 0

        return SectorAnalysisResult(
            date=date,
            sectors=sector_metrics,
            rotations=rotations,
            top_sectors=top_sectors,
            bottom_sectors=bottom_sectors,
            market_breadth=market_breadth,
        )

    def _generate_rotation_signal(
        self,
        sector: SectorInfo,
        all_sectors: list[SectorInfo],
    ) -> tuple[RotationSignal, float, str, float]:
        """生成轮动信号"""
        total_sectors = len(all_sectors)
        rank_percentile = sector.rank / total_sectors if total_sectors > 0 else 0.5

        score = 0
        reasons = []

        if sector.strength == SectorStrength.STRONG:
            score += 30
            reasons.append("行业强势")
        elif sector.strength == SectorStrength.WEAK:
            score -= 20
            reasons.append("行业弱势")

        if rank_percentile <= 0.2:
            score += 25
            reasons.append("排名靠前")
        elif rank_percentile >= 0.8:
            score -= 25
            reasons.append("排名靠后")

        if sector.trend == "多头":
            score += 15
            reasons.append("趋势向上")
        elif sector.trend == "空头":
            score -= 15
            reasons.append("趋势向下")

        if sector.momentum > 0.1:
            score += 20
            reasons.append("动量强劲")
        elif sector.momentum < -0.1:
            score -= 20
            reasons.append("动量疲弱")

        if score >= 50:
            signal = RotationSignal.ENTER
            weight = min(0.3, 0.1 + score / 200)
        elif score >= 20:
            signal = RotationSignal.HOLD
            weight = 0.1
        elif score >= -20:
            signal = RotationSignal.REDUCE
            weight = 0.05
        else:
            signal = RotationSignal.EXIT
            weight = 0.0

        reason = "; ".join(reasons) if reasons else "中性"

        return signal, score, reason, weight

    def get_sector_allocation(
        self,
        analysis_result: SectorAnalysisResult,
    ) -> dict[str, float]:
        """
        获取行业配置建议

        Args:
            analysis_result: 分析结果

        Returns:
            行业配置权重
        """
        allocations = {}

        enter_sectors = [r for r in analysis_result.rotations if r.signal == RotationSignal.ENTER]
        hold_sectors = [r for r in analysis_result.rotations if r.signal == RotationSignal.HOLD]

        total_weight = sum(r.recommended_weight for r in enter_sectors + hold_sectors)

        if total_weight > 0:
            for r in enter_sectors + hold_sectors:
                allocations[r.sector] = r.recommended_weight / total_weight
        else:
            for sector in analysis_result.top_sectors[:3]:
                allocations[sector] = 1.0 / 3

        return allocations


def print_sector_analysis(result: SectorAnalysisResult):
    """打印行业分析结果"""
    print(f"\n{'=' * 70}")
    print("📊 行业轮动分析")
    print(f"{'=' * 70}")

    print(f"\n📅 日期: {result.date}")
    print(f"📈 市场宽度: {result.market_breadth * 100:.1f}% 行业强势")

    print("\n🏆 行业排名 (按动量):")
    print(f"{'排名':<6} {'行业':<12} {'强度':<8} {'动量':<12} {'趋势':<8} {'信号':<8}")
    print("-" * 65)

    sector_signal_map = {r.sector: r for r in result.rotations}

    for sector in result.sectors[:10]:
        rotation = sector_signal_map.get(sector.name)
        signal_str = rotation.signal.value if rotation else "hold"
        print(
            f"{sector.rank:<6} {sector.name:<12} {sector.strength.value:<8} "
            f"{sector.momentum * 100:>+8.2f}%    {sector.trend:<8} {signal_str:<8}"
        )

    print("\n📈 强势行业 (建议关注):")
    for sector in result.top_sectors:
        print(f"   ✅ {sector}")

    print("\n📉 弱势行业 (建议回避):")
    for sector in result.bottom_sectors:
        print(f"   ⚠️ {sector}")

    print("\n💡 轮动信号:")
    enter_signals = [r for r in result.rotations if r.signal == RotationSignal.ENTER]
    exit_signals = [r for r in result.rotations if r.signal == RotationSignal.EXIT]

    if enter_signals:
        print(f"   🟢 建议进入: {', '.join([r.sector for r in enter_signals])}")
    if exit_signals:
        print(f"   🔴 建议退出: {', '.join([r.sector for r in exit_signals])}")

    print("\n📊 配置建议:")
    analyzer = SectorRotationAnalyzer()
    allocation = analyzer.get_sector_allocation(result)

    if allocation:
        total = sum(allocation.values())
        for sector, weight in sorted(allocation.items(), key=lambda x: x[1], reverse=True):
            print(f"   {sector}: {weight / total * 100:.1f}%")


def run_sector_analysis(
    db_path: Path | None = None,
    date: str | None = None,
) -> SectorAnalysisResult:
    """运行行业轮动分析"""
    project_root = Path(__file__).parent.parent.parent
    project_root / "data"
    db_path = db_path or get_stock_analysis_db_path()

    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    analyzer = SectorRotationAnalyzer()
    result = analyzer.analyze_sectors(db_path, date)
    print_sector_analysis(result)

    return result

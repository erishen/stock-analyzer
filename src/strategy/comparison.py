"""
Strategy Comparison Module.
策略对比模块 - 多策略横向对比分析
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class StrategyMetrics:
    """策略指标"""

    name: str
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    volatility: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_return": round(self.total_return * 100, 2),
            "annualized_return": round(self.annualized_return * 100, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "win_rate": round(self.win_rate * 100, 2),
            "profit_factor": round(self.profit_factor, 2),
            "total_trades": self.total_trades,
            "volatility": round(self.volatility * 100, 2),
        }


@dataclass
class ComparisonResult:
    """对比结果"""

    strategies: list[StrategyMetrics]
    best_return: str
    best_sharpe: str
    best_drawdown: str
    best_win_rate: str
    overall_ranking: list[tuple[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategies": [s.to_dict() for s in self.strategies],
            "best_return": self.best_return,
            "best_sharpe": self.best_sharpe,
            "best_drawdown": self.best_drawdown,
            "best_win_rate": self.best_win_rate,
            "overall_ranking": [{"strategy": r[0], "score": round(r[1], 2)} for r in self.overall_ranking],
        }


def compare_strategies(
    backtest_results: list[Any],
) -> ComparisonResult:
    """
    对比多个策略

    Args:
        backtest_results: 回测结果列表

    Returns:
        对比结果
    """
    metrics_list = []

    for result in backtest_results:
        metrics = StrategyMetrics(
            name=result.strategy_name,
            total_return=result.total_return,
            annualized_return=result.annualized_return,
            max_drawdown=result.max_drawdown,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            calmar_ratio=result.calmar_ratio,
            win_rate=result.win_rate,
            profit_factor=result.profit_factor,
            total_trades=result.total_trades,
            volatility=result.volatility,
        )
        metrics_list.append(metrics)

    best_return = max(metrics_list, key=lambda x: x.total_return).name
    best_sharpe = max(metrics_list, key=lambda x: x.sharpe_ratio).name
    best_drawdown = min(metrics_list, key=lambda x: x.max_drawdown).name
    best_win_rate = max(metrics_list, key=lambda x: x.win_rate).name

    ranking_scores = []
    for m in metrics_list:
        score = 0

        score += m.total_return * 100

        score += m.sharpe_ratio * 20

        score -= m.max_drawdown * 50

        score += m.win_rate * 30

        score += m.calmar_ratio * 10

        ranking_scores.append((m.name, score))

    ranking_scores.sort(key=lambda x: x[1], reverse=True)

    return ComparisonResult(
        strategies=metrics_list,
        best_return=best_return,
        best_sharpe=best_sharpe,
        best_drawdown=best_drawdown,
        best_win_rate=best_win_rate,
        overall_ranking=ranking_scores,
    )


def print_comparison(result: ComparisonResult):
    """打印对比结果"""
    print(f"\n{'=' * 80}")
    print("📊 策略对比报告")
    print(f"{'=' * 80}")

    print("\n📈 策略指标对比:")
    print(f"{'策略':<25} {'收益率':<12} {'夏普':<8} {'回撤':<10} {'胜率':<10} {'交易数':<8}")
    print("-" * 80)
    for m in result.strategies:
        print(
            f"{m.name:<25} {m.total_return * 100:>+8.2f}%    {m.sharpe_ratio:>6.2f}  "
            f"{m.max_drawdown * 100:>6.2f}%    {m.win_rate * 100:>6.2f}%    {m.total_trades:<8}"
        )

    print("\n🏆 各项最佳:")
    print(f"   最高收益: {result.best_return}")
    print(f"   最高夏普: {result.best_sharpe}")
    print(f"   最低回撤: {result.best_drawdown}")
    print(f"   最高胜率: {result.best_win_rate}")

    print("\n📊 综合排名:")
    for i, (name, score) in enumerate(result.overall_ranking, 1):
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "  "))
        print(f"   {medal} 第{i}名: {name} (得分: {score:.1f})")


def run_comparison(
    db_path: Path | None = None,
    strategies: list[str] | None = None,
    holding_days: int = 5,
) -> ComparisonResult:
    """
    运行策略对比

    Args:
        db_path: 数据库路径
        strategies: 策略列表
        holding_days: 持有天数

    Returns:
        对比结果
    """
    from .backtest import (
        run_backtest,
    )

    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"
    db_path = db_path or data_dir / "stock_analysis.db"

    if strategies is None:
        strategies = ["momentum", "mean_reversion", "trend_following", "multi_factor"]

    results = []

    print("\n🔄 运行策略对比...")
    print(f"   策略: {', '.join(strategies)}")
    print(f"   持有天数: {holding_days}")

    for strategy_type in strategies:
        print(f"\n   运行 {strategy_type}...")
        try:
            result = run_backtest(
                db_path=db_path,
                strategy_type=strategy_type,
                holding_days=holding_days,
            )
            results.append(result)
        except Exception as e:
            print(f"   ❌ {strategy_type} 运行失败: {e}")

    if not results:
        raise ValueError("没有有效的回测结果")

    comparison = compare_strategies(results)
    print_comparison(comparison)

    return comparison

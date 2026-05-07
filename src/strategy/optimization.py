"""
Parameter Optimization Module.
参数优化模块 - 网格搜索最优策略参数
"""

from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Callable

from .backtest import (
    BacktestEngine,
    MeanReversionStrategy,
    MomentumStrategy,
)


@dataclass
class OptimizationResult:
    """优化结果"""

    best_params: dict[str, Any]
    best_return: float
    best_sharpe: float
    best_drawdown: float
    all_results: list[dict[str, Any]]
    total_combinations: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_params": self.best_params,
            "best_return": round(self.best_return * 100, 2),
            "best_sharpe": round(self.best_sharpe, 2),
            "best_drawdown": round(self.best_drawdown * 100, 2),
            "total_combinations": self.total_combinations,
            "top_10_results": [
                {
                    "params": r["params"],
                    "total_return": round(r["total_return"] * 100, 2),
                    "sharpe_ratio": round(r["sharpe_ratio"], 2),
                    "max_drawdown": round(r["max_drawdown"] * 100, 2),
                    "win_rate": round(r["win_rate"] * 100, 2),
                }
                for r in sorted(self.all_results, key=lambda x: x["sharpe_ratio"], reverse=True)[:10]
            ],
        }


def optimize_momentum_strategy(
    db_path: Path,
    lookback_range: tuple[int, int] = (10, 30),
    holding_range: tuple[int, int] = (3, 10),
    momentum_range: tuple[float, float] = (0.0, 0.1),
    volatility_range: tuple[float, float] = (0.05, 0.15),
    initial_capital: float = 100000.0,
    progress_callback: Callable | None = None,
) -> OptimizationResult:
    """
    优化动量策略参数

    Args:
        db_path: 数据库路径
        lookback_range: 回看天数范围 (min, max, step=5)
        holding_range: 持有天数范围 (min, max, step=2)
        momentum_range: 最小动量范围 (min, max, step=0.02)
        volatility_range: 最大波动率范围 (min, max, step=0.02)
        initial_capital: 初始资金
        progress_callback: 进度回调函数

    Returns:
        优化结果
    """
    lookback_values = list(range(lookback_range[0], lookback_range[1] + 1, 5))
    holding_values = list(range(holding_range[0], holding_range[1] + 1, 2))
    momentum_values = [round(x * 0.02, 2) for x in range(int(momentum_range[0] * 50), int(momentum_range[1] * 50) + 1)]
    volatility_values = [
        round(x * 0.02, 2) for x in range(int(volatility_range[0] * 50), int(volatility_range[1] * 50) + 1)
    ]

    combinations = list(product(lookback_values, holding_values, momentum_values, volatility_values))
    total = len(combinations)

    print("\n🔧 参数优化 - 动量策略")
    print(f"   参数组合数: {total}")
    print(f"   回看天数: {lookback_values}")
    print(f"   持有天数: {holding_values}")
    print(f"   最小动量: {momentum_values}")
    print(f"   最大波动率: {volatility_values}")

    engine = BacktestEngine(db_path)
    engine.connect()

    all_results = []
    best_result = None
    best_sharpe = -float("inf")

    try:
        for i, (lookback, holding, min_mom, max_vol) in enumerate(combinations):
            if progress_callback:
                progress_callback(i + 1, total)

            if (i + 1) % 10 == 0 or i == 0:
                print(f"   进度: {i + 1}/{total} ({(i + 1) / total * 100:.1f}%)")

            try:
                strategy = MomentumStrategy(
                    lookback_days=lookback,
                    holding_days=holding,
                    min_momentum=min_mom,
                    max_volatility=max_vol,
                    exclude_st=True,
                )

                result = engine.run_backtest(strategy, initial_capital)

                result_data = {
                    "params": {
                        "lookback_days": lookback,
                        "holding_days": holding,
                        "min_momentum": min_mom,
                        "max_volatility": max_vol,
                    },
                    "total_return": result.total_return,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                }

                all_results.append(result_data)

                if result.sharpe_ratio > best_sharpe:
                    best_sharpe = result.sharpe_ratio
                    best_result = result_data

            except Exception:
                continue

    finally:
        engine.close()

    if best_result is None:
        raise ValueError("优化失败，没有有效的结果")

    return OptimizationResult(
        best_params=best_result["params"],
        best_return=best_result["total_return"],
        best_sharpe=best_result["sharpe_ratio"],
        best_drawdown=best_result["max_drawdown"],
        all_results=all_results,
        total_combinations=total,
    )


def optimize_mean_reversion_strategy(
    db_path: Path,
    rsi_range: tuple[int, int] = (20, 35),
    holding_range: tuple[int, int] = (3, 10),
    initial_capital: float = 100000.0,
    progress_callback: Callable | None = None,
) -> OptimizationResult:
    """
    优化均值回归策略参数

    Args:
        db_path: 数据库路径
        rsi_range: RSI 超卖阈值范围 (min, max, step=5)
        holding_range: 持有天数范围 (min, max, step=2)
        initial_capital: 初始资金
        progress_callback: 进度回调函数

    Returns:
        优化结果
    """
    rsi_values = list(range(rsi_range[0], rsi_range[1] + 1, 5))
    holding_values = list(range(holding_range[0], holding_range[1] + 1, 2))

    combinations = list(product(rsi_values, holding_values))
    total = len(combinations)

    print("\n🔧 参数优化 - 均值回归策略")
    print(f"   参数组合数: {total}")
    print(f"   RSI 超卖阈值: {rsi_values}")
    print(f"   持有天数: {holding_values}")

    engine = BacktestEngine(db_path)
    engine.connect()

    all_results = []
    best_result = None
    best_sharpe = -float("inf")

    try:
        for i, (rsi_oversold, holding) in enumerate(combinations):
            if progress_callback:
                progress_callback(i + 1, total)

            if (i + 1) % 5 == 0 or i == 0:
                print(f"   进度: {i + 1}/{total} ({(i + 1) / total * 100:.1f}%)")

            try:
                strategy = MeanReversionStrategy(
                    rsi_oversold=rsi_oversold,
                    holding_days=holding,
                    exclude_st=True,
                )

                result = engine.run_backtest(strategy, initial_capital)

                result_data = {
                    "params": {
                        "rsi_oversold": rsi_oversold,
                        "holding_days": holding,
                    },
                    "total_return": result.total_return,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                }

                all_results.append(result_data)

                if result.sharpe_ratio > best_sharpe:
                    best_sharpe = result.sharpe_ratio
                    best_result = result_data

            except Exception:
                continue

    finally:
        engine.close()

    if best_result is None:
        raise ValueError("优化失败，没有有效的结果")

    return OptimizationResult(
        best_params=best_result["params"],
        best_return=best_result["total_return"],
        best_sharpe=best_result["sharpe_ratio"],
        best_drawdown=best_result["max_drawdown"],
        all_results=all_results,
        total_combinations=total,
    )


def run_optimization(
    db_path: Path | None = None,
    strategy_type: str = "momentum",
) -> OptimizationResult:
    """运行参数优化的便捷函数"""
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"

    db_path = db_path or get_stock_analysis_db_path()

    if strategy_type == "momentum":
        return optimize_momentum_strategy(db_path)
    elif strategy_type == "mean_reversion":
        return optimize_mean_reversion_strategy(db_path)
    else:
        raise ValueError(f"未知策略类型: {strategy_type}")

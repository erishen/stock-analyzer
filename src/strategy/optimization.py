"""
Parameter Optimization Module.
参数优化模块 - 网格搜索最优策略参数
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

from config import get_stock_analysis_db_path

from .backtest import (
    BacktestEngine,
    MeanReversionStrategy,
    MomentumStrategy,
)

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """优化结果"""

    best_params: dict[str, Any]
    best_return: float
    best_sharpe: float
    best_drawdown: float
    all_results: list[dict[str, Any]]
    total_combinations: int
    # 训练/验证分段指标 (未分段时为空字符串)
    train_start: str = ""
    train_end: str = ""
    val_start: str = ""
    val_end: str = ""
    val_return: float = 0.0
    val_sharpe: float = 0.0
    val_drawdown: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_params": self.best_params,
            "best_return": round(self.best_return * 100, 2),
            "best_sharpe": round(self.best_sharpe, 2),
            "best_drawdown": round(self.best_drawdown * 100, 2),
            "total_combinations": self.total_combinations,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "val_start": self.val_start,
            "val_end": self.val_end,
            "val_return": round(self.val_return * 100, 2),
            "val_sharpe": round(self.val_sharpe, 2),
            "val_drawdown": round(self.val_drawdown * 100, 2),
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

    logger.info("\n🔧 参数优化 - 动量策略")
    logger.info(f"   参数组合数: {total}")
    logger.info(f"   回看天数: {lookback_values}")
    logger.info(f"   持有天数: {holding_values}")
    logger.info(f"   最小动量: {momentum_values}")
    logger.info(f"   最大波动率: {volatility_values}")

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
                logger.info(f"   进度: {i + 1}/{total} ({(i + 1) / total * 100:.1f}%)")

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

    logger.info("\n🔧 参数优化 - 均值回归策略")
    logger.info(f"   参数组合数: {total}")
    logger.info(f"   RSI 超卖阈值: {rsi_values}")
    logger.info(f"   持有天数: {holding_values}")

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
                logger.info(f"   进度: {i + 1}/{total} ({(i + 1) / total * 100:.1f}%)")

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
    project_root / "data"

    db_path = db_path or get_stock_analysis_db_path()

    if strategy_type == "momentum":
        return optimize_momentum_strategy(db_path)
    elif strategy_type == "mean_reversion":
        return optimize_mean_reversion_strategy(db_path)
    else:
        raise ValueError(f"未知策略类型: {strategy_type}")


def _split_trading_dates(
    engine: BacktestEngine,
    start_date: str | None,
    end_date: str | None,
) -> tuple[list[str], str, str, str]:
    """返回 (全部交易日, 训练起始, 训练结束, 验证结束)。

    将 [start_date, end_date] 按交易日中位分割: 前半段训练, 后半段验证。
    未指定日期时取数据库实际最早/最晚。
    """
    all_data = engine.get_all_stock_data()
    dates = engine.get_date_range(all_data)
    if start_date:
        dates = [d for d in dates if d >= start_date]
    if end_date:
        dates = [d for d in dates if d <= end_date]
    if len(dates) < 10:
        raise ValueError("有效交易日不足，无法分段寻优")

    train_end = dates[len(dates) // 2]
    train_start = dates[0]
    val_end = dates[-1]
    return dates, train_start, train_end, val_end


def optimize_with_split(
    db_path: Path,
    strategy_type: str,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_capital: float = 100000.0,
    progress_callback: Callable | None = None,
) -> OptimizationResult:
    """带训练/验证分段的参数寻优 (避免过拟合选参)。

    训练段: 网格搜索全部参数组合, 按夏普比率取最优。
    验证段: 将训练最优参数套用到后半段独立回测, 得到验证指标。
    """
    # 确定该策略的网格范围
    if strategy_type == "momentum":
        # 5 回看 × 4 持有 × 3 动量 × 2 波动率 = 120 组 (聚焦关键参数, 控制耗时)
        lookback_values = list(range(10, 31, 5))  # 10,15,20,25,30
        holding_values = list(range(5, 21, 5))  # 5,10,15,20 (含默认20)
        momentum_values = [round(x * 0.05, 2) for x in range(0, 3)]  # 0.0,0.05,0.10
        volatility_values = [round(x, 2) for x in (0.08, 0.14)]  # 0.08,0.14
    elif strategy_type == "mean_reversion":
        rsi_values = list(range(20, 36, 5))
        holding_values = list(range(3, 11, 2))
    else:
        raise ValueError(f"未知策略类型: {strategy_type}")

    engine = BacktestEngine(db_path)
    engine.connect()
    try:
        _, train_start, train_end, val_end = _split_trading_dates(engine, start_date, end_date)
        # 验证段起始 = 训练结束的下一交易日
        all_dates = engine.get_date_range(engine.get_all_stock_data())
        ordered = [d for d in all_dates if not start_date or d >= start_date]
        ordered = [d for d in ordered if not end_date or d <= end_date]
        val_start = ""
        for d in ordered:
            if d > train_end:
                val_start = d
                break

        # 组装参数组合
        if strategy_type == "momentum":
            combinations = list(product(lookback_values, holding_values, momentum_values, volatility_values))
        else:
            combinations = list(product(rsi_values, holding_values))
        total = len(combinations)

        logger.info("\n🔧 自动寻优 (训练/验证分段) - %s", strategy_type)
        logger.info(f"   组合数: {total}")
        logger.info(f"   训练段: {train_start} ~ {train_end}")
        logger.info(f"   验证段: {val_start} ~ {val_end}")

        all_results: list[dict[str, Any]] = []
        best_result: dict[str, Any] | None = None
        best_sharpe = -float("inf")

        for i, combo in enumerate(combinations):
            if progress_callback:
                progress_callback(i + 1, total)
            try:
                if strategy_type == "momentum":
                    lookback, holding, min_mom, max_vol = combo
                    strategy = MomentumStrategy(
                        lookback_days=lookback,
                        holding_days=holding,
                        min_momentum=min_mom,
                        max_volatility=max_vol,
                        exclude_st=True,
                    )
                    params = {
                        "lookback_days": lookback,
                        "holding_days": holding,
                        "min_momentum": min_mom,
                        "max_volatility": max_vol,
                    }
                else:
                    rsi_oversold, holding = combo
                    strategy = MeanReversionStrategy(
                        rsi_oversold=rsi_oversold,
                        holding_days=holding,
                        exclude_st=True,
                    )
                    params = {"rsi_oversold": rsi_oversold, "holding_days": holding}

                # 训练段回测
                train_result = (
                    engine.run_backtest(strategy, initial_capital, start_date=train_start, end_date=train_end)
                    if strategy_type == "momentum" or strategy_type == "mean_reversion"
                    else None
                )
                # 注: run_backtest 第二个参数 position_size 默认0.1; 此处按默认即可

                if train_result is None or train_result.total_trades == 0:
                    continue

                all_results.append(
                    {
                        "params": params,
                        "total_return": train_result.total_return,
                        "sharpe_ratio": train_result.sharpe_ratio,
                        "max_drawdown": train_result.max_drawdown,
                        "win_rate": train_result.win_rate,
                        "total_trades": train_result.total_trades,
                    }
                )

                if train_result.sharpe_ratio > best_sharpe:
                    best_sharpe = train_result.sharpe_ratio
                    best_result = all_results[-1]
            except Exception:
                continue

        if best_result is None:
            raise ValueError("寻优失败，训练段没有有效结果")

        # 验证段: 用训练最优参数独立回测
        val_result = None
        if val_start:
            if strategy_type == "momentum":
                best_strat = MomentumStrategy(
                    lookback_days=best_result["params"]["lookback_days"],
                    holding_days=best_result["params"]["holding_days"],
                    min_momentum=best_result["params"]["min_momentum"],
                    max_volatility=best_result["params"]["max_volatility"],
                    exclude_st=True,
                )
            else:
                best_strat = MeanReversionStrategy(
                    rsi_oversold=best_result["params"]["rsi_oversold"],
                    holding_days=best_result["params"]["holding_days"],
                    exclude_st=True,
                )
            try:
                val_result = engine.run_backtest(best_strat, initial_capital, start_date=val_start, end_date=val_end)
            except Exception:
                val_result = None

        return OptimizationResult(
            best_params=best_result["params"],
            best_return=best_result["total_return"],
            best_sharpe=best_result["sharpe_ratio"],
            best_drawdown=best_result["max_drawdown"],
            all_results=all_results,
            total_combinations=total,
            train_start=train_start,
            train_end=train_end,
            val_start=val_start,
            val_end=val_end,
            val_return=val_result.total_return if val_result else 0.0,
            val_sharpe=val_result.sharpe_ratio if val_result else 0.0,
            val_drawdown=val_result.max_drawdown if val_result else 0.0,
        )
    finally:
        engine.close()

"""
Benchmark Comparison Module.
基准对比模块 - 与基准指数对比策略表现
"""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基准对比结果"""

    strategy_name: str
    strategy_return: float
    benchmark_return: float
    excess_return: float
    strategy_sharpe: float
    benchmark_sharpe: float
    strategy_drawdown: float
    benchmark_drawdown: float
    alpha: float
    beta: float
    correlation: float
    information_ratio: float
    tracking_error: float
    # 基准计费口径: 建仓+清仓一次性成本(小数), 0 表示未计费(旧行为)
    benchmark_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "strategy_return": round(self.strategy_return * 100, 2),
            "benchmark_return": round(self.benchmark_return * 100, 2),
            "excess_return": round(self.excess_return * 100, 2),
            "benchmark_cost_pct": round(self.benchmark_cost * 100, 3),
            "strategy_sharpe": round(self.strategy_sharpe, 2),
            "benchmark_sharpe": round(self.benchmark_sharpe, 2),
            "strategy_drawdown": round(self.strategy_drawdown * 100, 2),
            "benchmark_drawdown": round(self.benchmark_drawdown * 100, 2),
            "alpha": round(self.alpha * 100, 2),
            "beta": round(self.beta, 2),
            "correlation": round(self.correlation, 2),
            "information_ratio": round(self.information_ratio, 2),
            "tracking_error": round(self.tracking_error * 100, 2),
        }


def calculate_equal_weight_benchmark(
    db_path: Path,
    start_date: str | None = None,
    end_date: str | None = None,
    cost_rate: float = 0.0,
) -> list[dict]:
    """等权买入持有基准(整段窗口只建仓一次, 权重随价格自然漂移)。

    口径修正(2026-11-28):
      - 旧实现每天把权重重置回等权, 等于隐含「免费日度再平衡」, 而策略那条腿
        要付调仓成本; 两个口径不一致, 超额收益被高估。这里改为真正持有的
        买入持有: 首日按等权建仓, 之后不再调仓。
      - 旧实现不扣任何成本。``cost_rate`` 为一次性成本(建仓+清仓合计, 小数),
        例如佣金万三双边+印花税千一+滑点 → ``2*0.0003 + 0.001 + 2*0.0005``。
    """
    query = """
        SELECT code, date, close
        FROM stock_analysis
        WHERE close > 0
    """
    if start_date:
        query += f" AND date >= '{start_date}'"
    if end_date:
        query += f" AND date <= '{end_date}'"

    with sqlite3.connect(str(db_path)) as conn:
        df = pd.read_sql_query(query, conn)

    if df.empty:
        return []

    df["date"] = pd.to_datetime(df["date"])
    pivot = df.pivot_table(index="date", columns="code", values="close", aggfunc="last").sort_index()

    # 只保留建仓日有收盘价的标的（之后停牌/退市的按最后可得价格持有）
    first_row = pivot.iloc[0]
    codes = first_row.dropna().index
    if len(codes) == 0:
        return []

    entry = first_row[codes]
    rel = pivot[codes].ffill() / entry
    index_level = rel.mean(axis=1).dropna()

    # 一次性成本: 建仓买入 + 期末卖出
    gross = 100000.0 * (1.0 - cost_rate)
    equity_curve = [
        {"date": idx.strftime("%Y-%m-%d"), "equity": round(float(v) * gross, 2)}
        for idx, v in index_level.items()
    ]
    return equity_curve


def calculate_equal_weight_benchmark_from_summary(
    db_path: Path,
    start_date: str | None = None,
    end_date: str | None = None,
    cost_rate: float = 0.0,
) -> list[dict]:
    """从 `market_daily` 汇总表快速构造等权基准(毫秒级, 供在线接口用)。

    与上面的逐票版本口径一致: 每日全市场等权收益连乘。逐票版本用于离线报告,
    这个版本用于请求路径——`stock_analysis` 700 万行每次全表读要 5s+。
    汇总表由 ETL 末尾增量维护; 表不存在时返回空列表, 调用方自行降级。
    """
    query = "SELECT date, avg_change FROM market_daily WHERE avg_change IS NOT NULL"
    if start_date:
        query += f" AND date >= '{start_date}'"
    if end_date:
        query += f" AND date <= '{end_date}'"
    query += " ORDER BY date"

    try:
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(query).fetchall()
    except sqlite3.OperationalError:
        return []
    if not rows:
        return []

    equity = 1.0 - cost_rate
    curve = [{"date": rows[0][0], "equity": round(equity * 100000.0, 2)}]
    for _, chg in rows[1:]:
        equity *= 1.0 + float(chg) / 100.0
        curve.append({"date": _, "equity": round(equity * 100000.0, 2)})
    return curve


def compare_with_benchmark(
    backtest_result: Any,
    db_path: Path,
    cost_rate: float = 0.0,
) -> BenchmarkResult:
    """
    将策略与基准对比

    Args:
        backtest_result: 回测结果
        db_path: 数据库路径
        cost_rate: 基准一次性成本(建仓+清仓合计, 小数)。策略那条腿已经扣了
            佣金/印花税/滑点, 基准不扣就会把成本差算进"超额收益", 因此默认
            由调用方传入与策略相同的费率(见 main.py 的 backtest-benchmark)。

    Returns:
        基准对比结果
    """
    benchmark_curve = calculate_equal_weight_benchmark(
        db_path,
        start_date=backtest_result.start_date,
        end_date=backtest_result.end_date,
        cost_rate=cost_rate,
    )

    if not benchmark_curve:
        raise ValueError("无法计算基准收益")

    benchmark_equities = [e["equity"] for e in benchmark_curve]
    strategy_equities = [e["equity"] for e in backtest_result.equity_curve]

    min_len = min(len(benchmark_equities), len(strategy_equities))
    benchmark_equities = benchmark_equities[:min_len]
    strategy_equities = strategy_equities[:min_len]

    benchmark_return = (benchmark_equities[-1] - benchmark_equities[0]) / benchmark_equities[0]
    strategy_return = backtest_result.total_return

    excess_return = strategy_return - benchmark_return

    def calc_sharpe(equities):
        returns = []
        for i in range(1, len(equities)):
            if equities[i - 1] > 0:
                ret = (equities[i] - equities[i - 1]) / equities[i - 1]
                returns.append(ret)
        if not returns:
            return 0.0
        avg_ret = np.mean(returns)
        std_ret = np.std(returns)
        if std_ret > 0:
            return avg_ret / std_ret * np.sqrt(252)
        return 0.0

    def calc_drawdown(equities):
        peak = equities[0]
        max_dd = 0.0
        for e in equities:
            if e > peak:
                peak = e
            if peak > 0:
                dd = (peak - e) / peak
                if dd > max_dd:
                    max_dd = dd
        return max_dd

    strategy_sharpe = backtest_result.sharpe_ratio
    benchmark_sharpe = calc_sharpe(benchmark_equities)

    strategy_drawdown = backtest_result.max_drawdown
    benchmark_drawdown = calc_drawdown(benchmark_equities)

    strategy_returns = []
    benchmark_returns = []

    for i in range(1, min_len):
        if strategy_equities[i - 1] > 0:
            strategy_returns.append((strategy_equities[i] - strategy_equities[i - 1]) / strategy_equities[i - 1])
        if benchmark_equities[i - 1] > 0:
            benchmark_returns.append((benchmark_equities[i] - benchmark_equities[i - 1]) / benchmark_equities[i - 1])

    min_returns = min(len(strategy_returns), len(benchmark_returns))
    strategy_returns = strategy_returns[:min_returns]
    benchmark_returns = benchmark_returns[:min_returns]

    if len(strategy_returns) > 1 and len(benchmark_returns) > 1:
        correlation = np.corrcoef(strategy_returns, benchmark_returns)[0, 1]

        covariance = np.cov(strategy_returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0.0

        rf = 0.02 / 252
        alpha = (np.mean(strategy_returns) - rf) - beta * (np.mean(benchmark_returns) - rf)
        alpha = alpha * 252

        excess_returns = [s - b for s, b in zip(strategy_returns, benchmark_returns, strict=False)]
        tracking_error = np.std(excess_returns) * np.sqrt(252)

        information_ratio = np.mean(excess_returns) * np.sqrt(252) / tracking_error if tracking_error > 0 else 0.0
    else:
        alpha = 0.0
        beta = 0.0
        correlation = 0.0
        information_ratio = 0.0
        tracking_error = 0.0

    return BenchmarkResult(
        strategy_name=backtest_result.strategy_name,
        strategy_return=strategy_return,
        benchmark_return=benchmark_return,
        excess_return=excess_return,
        strategy_sharpe=strategy_sharpe,
        benchmark_sharpe=benchmark_sharpe,
        strategy_drawdown=strategy_drawdown,
        benchmark_drawdown=benchmark_drawdown,
        alpha=alpha,
        beta=beta,
        correlation=correlation,
        information_ratio=information_ratio,
        tracking_error=tracking_error,
        benchmark_cost=cost_rate,
    )


def print_benchmark_comparison(result: BenchmarkResult):
    """打印基准对比结果"""
    logger.info("\n📊 基准对比结果:")
    logger.info(f"   策略: {result.strategy_name}")
    logger.info(f"   基准: 等权买入持有 (一次性成本 {result.benchmark_cost * 100:.2f}%)")

    logger.info("\n📈 收益对比:")
    logger.info(f"   策略收益: {result.strategy_return * 100:+.2f}%")
    logger.info(f"   基准收益: {result.benchmark_return * 100:+.2f}%")
    logger.info(f"   超额收益: {result.excess_return * 100:+.2f}%")

    logger.info("\n📉 风险对比:")
    logger.info(f"   策略夏普: {result.strategy_sharpe:.2f}")
    logger.info(f"   基准夏普: {result.benchmark_sharpe:.2f}")
    logger.info(f"   策略回撤: {result.strategy_drawdown * 100:.2f}%")
    logger.info(f"   基准回撤: {result.benchmark_drawdown * 100:.2f}%")

    logger.info("\n📐 风险指标:")
    logger.info(f"   Alpha: {result.alpha * 100:+.2f}%")
    logger.info(f"   Beta: {result.beta:.2f}")
    logger.info(f"   相关性: {result.correlation:.2f}")
    logger.info(f"   信息比率: {result.information_ratio:.2f}")
    logger.error(f"   跟踪误差: {result.tracking_error * 100:.2f}%")

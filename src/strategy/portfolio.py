"""
Multi-Strategy Portfolio Module.
多策略组合模块 - 组合多个策略进行回测
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from config import get_stock_analysis_db_path

from .backtest import (
    BacktestEngine,
    BacktestResult,
    MeanReversionStrategy,
    MomentumStrategy,
    MultiFactorStrategy,
    TrendFollowingStrategy,
)

logger = logging.getLogger(__name__)


class WeightMethod(Enum):
    """权重方法"""

    EQUAL = "equal"  # 等权
    RISK_PARITY = "risk_parity"  # 风险平价
    SHARPE = "sharpe"  # 夏普加权
    CUSTOM = "custom"  # 自定义


@dataclass
class StrategyConfig:
    """策略配置"""

    name: str
    strategy_type: str
    weight: float
    params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "strategy_type": self.strategy_type,
            "weight": round(self.weight, 4),
            "params": self.params,
        }


@dataclass
class PortfolioResult:
    """组合回测结果"""

    name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility: float
    strategy_results: list[BacktestResult]
    strategy_weights: dict[str, float]
    correlation_matrix: dict[str, dict[str, float]]
    diversification_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": round(self.initial_capital, 2),
            "final_capital": round(self.final_capital, 2),
            "total_return": round(self.total_return * 100, 2),
            "annualized_return": round(self.annualized_return * 100, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "volatility": round(self.volatility * 100, 2),
            "strategy_results": [r.to_dict() for r in self.strategy_results],
            "strategy_weights": {k: round(v, 4) for k, v in self.strategy_weights.items()},
            "correlation_matrix": self.correlation_matrix,
            "diversification_ratio": round(self.diversification_ratio, 2),
        }


class MultiStrategyPortfolio:
    """多策略组合"""

    STRATEGY_MAP: ClassVar[dict[str, type]] = {
        "momentum": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
        "trend_following": TrendFollowingStrategy,
        "multi_factor": MultiFactorStrategy,
    }

    def __init__(
        self,
        name: str = "MultiStrategyPortfolio",
        weight_method: WeightMethod = WeightMethod.EQUAL,
    ):
        self.name = name
        self.weight_method = weight_method
        self.strategies: list[StrategyConfig] = []

    def add_strategy(
        self,
        name: str,
        strategy_type: str,
        weight: float = 0.0,
        **params,
    ):
        """添加策略"""
        if strategy_type not in self.STRATEGY_MAP:
            raise ValueError(f"未知策略类型: {strategy_type}")

        self.strategies.append(
            StrategyConfig(
                name=name,
                strategy_type=strategy_type,
                weight=weight,
                params=params,
            )
        )

    def _calculate_weights(self, strategy_returns: dict[str, list[float]]) -> dict[str, float]:
        """计算策略权重"""
        if self.weight_method == WeightMethod.EQUAL:
            n = len(self.strategies)
            return {s.name: 1.0 / n for s in self.strategies}

        elif self.weight_method == WeightMethod.RISK_PARITY:
            volatilities = {}
            for name, returns in strategy_returns.items():
                if returns:
                    volatilities[name] = np.std(returns)
                else:
                    volatilities[name] = 1.0

            inv_vols = {k: 1 / v for k, v in volatilities.items() if v > 0}
            total = sum(inv_vols.values())
            return {k: v / total for k, v in inv_vols.items()}

        elif self.weight_method == WeightMethod.SHARPE:
            sharpes = {}
            for name, returns in strategy_returns.items():
                if returns:
                    avg_ret = np.mean(returns)
                    std_ret = np.std(returns)
                    sharpes[name] = avg_ret / std_ret if std_ret > 0 else 0
                else:
                    sharpes[name] = 0

            positive_sharpes = {k: max(0, v) for k, v in sharpes.items()}
            total = sum(positive_sharpes.values())
            if total > 0:
                return {k: v / total for k, v in positive_sharpes.items()}
            else:
                n = len(self.strategies)
                return {s.name: 1.0 / n for s in self.strategies}

        elif self.weight_method == WeightMethod.CUSTOM:
            total = sum(s.weight for s in self.strategies)
            if total > 0:
                return {s.name: s.weight / total for s in self.strategies}
            else:
                n = len(self.strategies)
                return {s.name: 1.0 / n for s in self.strategies}

        else:
            n = len(self.strategies)
            return {s.name: 1.0 / n for s in self.strategies}

    def _calculate_correlation(
        self,
        strategy_returns: dict[str, list[float]],
    ) -> dict[str, dict[str, float]]:
        """计算策略相关性"""
        names = list(strategy_returns.keys())
        min_len = min(len(r) for r in strategy_returns.values() if r)

        if min_len < 2:
            return {n1: {n2: 0.0 for n2 in names} for n1 in names}

        aligned_returns = {}
        for name, returns in strategy_returns.items():
            aligned_returns[name] = returns[:min_len]

        corr_matrix = {}
        for n1 in names:
            corr_matrix[n1] = {}
            for n2 in names:
                if n1 == n2:
                    corr_matrix[n1][n2] = 1.0
                else:
                    corr = np.corrcoef(aligned_returns[n1], aligned_returns[n2])[0, 1]
                    corr_matrix[n1][n2] = round(corr, 4) if not np.isnan(corr) else 0.0

        return corr_matrix

    def _calculate_diversification_ratio(
        self,
        weights: dict[str, float],
        strategy_returns: dict[str, list[float]],
    ) -> float:
        """计算分散度比率"""
        if not strategy_returns:
            return 1.0

        volatilities = {}
        for name, returns in strategy_returns.items():
            if returns:
                volatilities[name] = np.std(returns)
            else:
                volatilities[name] = 0

        weighted_vol_sum = sum(weights.get(name, 0) * vol for name, vol in volatilities.items())

        min_len = min(len(r) for r in strategy_returns.values() if r)
        if min_len < 2:
            return 1.0

        aligned_returns = np.array([r[:min_len] for r in strategy_returns.values()])
        weights_array = np.array([weights.get(s.name, 0) for s in self.strategies])

        cov_matrix = np.cov(aligned_returns)
        portfolio_var = np.dot(weights_array, np.dot(cov_matrix, weights_array))
        portfolio_vol = np.sqrt(portfolio_var) if portfolio_var > 0 else 0

        if portfolio_vol > 0:
            return weighted_vol_sum / portfolio_vol
        else:
            return 1.0

    def run_backtest(
        self,
        db_path: Path,
        initial_capital: float = 100000.0,
        position_size: float = 0.1,
    ) -> PortfolioResult:
        """
        运行组合回测

        Args:
            db_path: 数据库路径
            initial_capital: 初始资金
            position_size: 单只股票仓位

        Returns:
            组合回测结果
        """
        if not self.strategies:
            raise ValueError("请先添加策略")

        logger.info("\n📊 运行多策略组合回测")
        logger.info(f"   组合名称: {self.name}")
        logger.info(f"   策略数量: {len(self.strategies)}")
        logger.info(f"   权重方法: {self.weight_method.value}")

        engine = BacktestEngine(db_path)
        engine.connect()

        strategy_results = []
        strategy_returns = {}

        try:
            for config in self.strategies:
                logger.info(f"\n   运行策略: {config.name} ({config.strategy_type})")

                strategy_class = self.STRATEGY_MAP[config.strategy_type]
                strategy = strategy_class(**config.params)

                result = engine.run_backtest(strategy, initial_capital, position_size)
                strategy_results.append(result)

                returns = []
                for i in range(1, len(result.equity_curve)):
                    prev_equity = result.equity_curve[i - 1]["equity"]
                    curr_equity = result.equity_curve[i]["equity"]
                    if prev_equity > 0:
                        returns.append((curr_equity - prev_equity) / prev_equity)
                strategy_returns[config.name] = returns

        finally:
            engine.close()

        weights = self._calculate_weights(strategy_returns)
        logger.info(f"\n   策略权重: {weights}")

        correlation_matrix = self._calculate_correlation(strategy_returns)

        div_ratio = self._calculate_diversification_ratio(weights, strategy_returns)

        combined_equity = []
        min_len = min(len(r.equity_curve) for r in strategy_results)

        for i in range(min_len):
            equity = 0
            for result in strategy_results:
                strategy_name = result.strategy_name.replace("Strategy", "").lower()
                for config in self.strategies:
                    if config.strategy_type.replace("_", "") in strategy_name:
                        weight = weights.get(config.name, 1.0 / len(self.strategies))
                        equity += result.equity_curve[i]["equity"] * weight
                        break

            combined_equity.append(
                {
                    "date": strategy_results[0].equity_curve[i]["date"],
                    "equity": equity,
                }
            )

        total_return = (combined_equity[-1]["equity"] - combined_equity[0]["equity"]) / combined_equity[0]["equity"]

        returns = []
        for i in range(1, len(combined_equity)):
            prev = combined_equity[i - 1]["equity"]
            curr = combined_equity[i]["equity"]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            volatility = std_return * np.sqrt(252)
            sharpe_ratio = avg_return / std_return * np.sqrt(252) if std_return > 0 else 0

            negative_returns = [r for r in returns if r < 0]
            downside_std = np.std(negative_returns) if negative_returns else 0
            sortino_ratio = avg_return / downside_std * np.sqrt(252) if downside_std > 0 else 0
        else:
            volatility = 0
            sharpe_ratio = 0
            sortino_ratio = 0

        peak = combined_equity[0]["equity"]
        max_drawdown = 0
        for e in combined_equity:
            if e["equity"] > peak:
                peak = e["equity"]
            if peak > 0:
                dd = (peak - e["equity"]) / peak
                if dd > max_drawdown:
                    max_drawdown = dd

        days = len(combined_equity)
        annualized_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0

        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        return PortfolioResult(
            name=self.name,
            start_date=combined_equity[0]["date"],
            end_date=combined_equity[-1]["date"],
            initial_capital=initial_capital,
            final_capital=combined_equity[-1]["equity"],
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            volatility=volatility,
            strategy_results=strategy_results,
            strategy_weights=weights,
            correlation_matrix=correlation_matrix,
            diversification_ratio=div_ratio,
        )


def print_portfolio_result(result: PortfolioResult):
    """打印组合结果"""
    logger.info(f"\n{'=' * 70}")
    logger.info("📊 多策略组合回测结果")
    logger.info(f"{'=' * 70}")

    logger.info(f"\n📅 组合名称: {result.name}")
    logger.info(f"📅 回测区间: {result.start_date} ~ {result.end_date}")

    logger.info("\n💰 收益指标:")
    logger.info(f"   初始资金: {result.initial_capital:,.0f}")
    logger.info(f"   最终资金: {result.final_capital:,.0f}")
    logger.info(f"   总收益率: {result.total_return * 100:+.2f}%")
    logger.info(f"   年化收益: {result.annualized_return * 100:+.2f}%")

    logger.info("\n📉 风险指标:")
    logger.info(f"   最大回撤: {result.max_drawdown * 100:.2f}%")
    logger.info(f"   年化波动: {result.volatility * 100:.2f}%")
    logger.info(f"   夏普比率: {result.sharpe_ratio:.2f}")
    logger.info(f"   索提诺比率: {result.sortino_ratio:.2f}")
    logger.info(f"   卡玛比率: {result.calmar_ratio:.2f}")

    logger.info("\n📊 组合分析:")
    logger.info(f"   分散度比率: {result.diversification_ratio:.2f}")
    logger.info("   (越高表示分散效果越好，>1 表示有分散效果)")

    logger.info("\n⚖️ 策略权重:")
    for name, weight in result.strategy_weights.items():
        logger.info(f"   {name}: {weight * 100:.1f}%")

    logger.info("\n📈 策略相关性矩阵:")
    names = list(result.correlation_matrix.keys())
    header = "         " + "  ".join([f"{n[:8]:>8}" for n in names])
    logger.info(header)
    for n1 in names:
        row = f"{n1[:8]:>8} "
        for n2 in names:
            corr = result.correlation_matrix[n1][n2]
            row += f"{corr:>8.2f} "
        logger.info(row)

    logger.info("\n📋 各策略表现:")
    logger.info(f"{'策略':<20} {'收益率':<12} {'夏普':<10} {'回撤':<10}")
    logger.info("-" * 55)
    for r in result.strategy_results:
        name = r.strategy_name
        logger.info(
            f"{name:<20} {r.total_return * 100:>+8.2f}%    {r.sharpe_ratio:>6.2f}     {r.max_drawdown * 100:>6.2f}%"
        )


def run_portfolio_backtest(
    db_path: Path | None = None,
    strategies: list[dict] | None = None,
    weight_method: str = "equal",
    initial_capital: float = 100000.0,
) -> PortfolioResult:
    """
    运行组合回测的便捷函数

    Args:
        db_path: 数据库路径
        strategies: 策略配置列表
        weight_method: 权重方法
        initial_capital: 初始资金

    Returns:
        组合回测结果
    """
    project_root = Path(__file__).parent.parent.parent
    project_root / "data"
    db_path = db_path or get_stock_analysis_db_path()

    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    weight_enum = WeightMethod(weight_method)

    portfolio = MultiStrategyPortfolio(
        name="DefaultPortfolio",
        weight_method=weight_enum,
    )

    if strategies is None:
        portfolio.add_strategy("momentum", "momentum", holding_days=5)
        portfolio.add_strategy("mean_reversion", "mean_reversion", holding_days=9)
        portfolio.add_strategy("trend_following", "trend_following", holding_days=5)
    else:
        for s in strategies:
            portfolio.add_strategy(
                name=s.get("name", s["type"]),
                strategy_type=s["type"],
                weight=s.get("weight", 0),
                **s.get("params", {}),
            )

    result = portfolio.run_backtest(db_path, initial_capital)
    print_portfolio_result(result)

    return result

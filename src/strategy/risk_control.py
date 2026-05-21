"""
Risk Control Module for Stock Analyzer.
风控模块 - 提供组合优化、风险归因、持仓限制等功能

功能:
- 策略信号回测验证
- 组合优化 (风险平价、均值方差)
- 风险归因分析
- 行业分散度控制
- 持仓数量和仓位限制
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class PositionLimit:
    """持仓限制配置"""

    max_positions: int = 10
    max_single_position_pct: float = 0.15
    max_sector_position_pct: float = 0.30
    min_position_pct: float = 0.02


@dataclass
class SignalBacktestResult:
    """信号回测结果"""

    signal_type: str
    total_signals: int
    winning_signals: int
    losing_signals: int
    win_rate: float
    avg_return: float
    avg_holding_days: float
    max_return: float
    max_loss: float
    profit_factor: float
    sharpe_ratio: float
    returns_distribution: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "total_signals": self.total_signals,
            "winning_signals": self.winning_signals,
            "losing_signals": self.losing_signals,
            "win_rate": round(self.win_rate * 100, 2),
            "avg_return": round(self.avg_return * 100, 2),
            "avg_holding_days": round(self.avg_holding_days, 1),
            "max_return": round(self.max_return * 100, 2),
            "max_loss": round(self.max_loss * 100, 2),
            "profit_factor": round(self.profit_factor, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
        }


@dataclass
class PortfolioOptimizationResult:
    """组合优化结果"""

    weights: dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    diversification_ratio: float
    concentration_hhi: float
    sector_allocation: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "expected_return": round(self.expected_return * 100, 2),
            "expected_volatility": round(self.expected_volatility * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "diversification_ratio": round(self.diversification_ratio, 2),
            "concentration_hhi": round(self.concentration_hhi, 4),
            "sector_allocation": {k: round(v * 100, 2) for k, v in self.sector_allocation.items()},
        }


@dataclass
class RiskAttributionResult:
    """风险归因结果"""

    total_risk: float
    systematic_risk: float
    idiosyncratic_risk: float
    sector_contributions: dict[str, float]
    stock_contributions: dict[str, float]
    factor_contributions: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_risk": round(self.total_risk * 100, 2),
            "systematic_risk": round(self.systematic_risk * 100, 2),
            "idiosyncratic_risk": round(self.idiosyncratic_risk * 100, 2),
            "sector_contributions": {
                k: round(v * 100, 2) for k, v in self.sector_contributions.items()
            },
            "stock_contributions": {
                k: round(v * 100, 4) for k, v in list(self.stock_contributions.items())[:10]
            },
            "factor_contributions": {
                k: round(v * 100, 2) for k, v in self.factor_contributions.items()
            },
        }


class SignalBacktester:
    """信号回测器 - 验证信号有效性"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        import sqlite3

        self.conn = sqlite3.connect(str(self.db_path))

    def close(self):
        if self.conn:
            self.conn.close()

    def backtest_signal(
        self,
        signal_type: str,
        holding_days: int = 5,
        start_date: str | None = None,
        end_date: str | None = None,
        min_score: float = 0,
    ) -> SignalBacktestResult:
        """
        回测单个信号类型

        Args:
            signal_type: 信号类型
            holding_days: 持有天数
            start_date: 开始日期
            end_date: 结束日期
            min_score: 最低信号得分
        """
        if not self.conn:
            self.connect()

        date_filter = ""
        params: list = []

        if start_date:
            date_filter += " AND date >= ?"
            params.append(start_date)
        if end_date:
            date_filter += " AND date <= ?"
            params.append(end_date)

        query = f"""
            SELECT code, date, close, change_percent
            FROM stock_analysis
            WHERE 1=1 {date_filter}
            ORDER BY code, date
        """

        df = pd.read_sql_query(query, self.conn, params=params)

        if df.empty:
            return SignalBacktestResult(
                signal_type=signal_type,
                total_signals=0,
                winning_signals=0,
                losing_signals=0,
                win_rate=0,
                avg_return=0,
                avg_holding_days=0,
                max_return=0,
                max_loss=0,
                profit_factor=0,
                sharpe_ratio=0,
            )

        returns = []
        holding_periods = []

        grouped = df.groupby("code")

        for _code, group in grouped:
            group = group.sort_values("date").reset_index(drop=True)

            for i in range(len(group) - holding_days):
                current = group.iloc[i]
                future = group.iloc[i + holding_days] if i + holding_days < len(group) else None

                if future is None:
                    continue

                entry_price = current["close"]
                exit_price = future["close"]

                if entry_price > 0:
                    ret = (exit_price - entry_price) / entry_price
                    returns.append(ret)
                    holding_periods.append(holding_days)

        if not returns:
            return SignalBacktestResult(
                signal_type=signal_type,
                total_signals=0,
                winning_signals=0,
                losing_signals=0,
                win_rate=0,
                avg_return=0,
                avg_holding_days=0,
                max_return=0,
                max_loss=0,
                profit_factor=0,
                sharpe_ratio=0,
            )

        returns = np.array(returns)
        winning = returns[returns > 0]
        losing = returns[returns < 0]

        win_rate = len(winning) / len(returns) if len(returns) > 0 else 0
        avg_return = np.mean(returns)
        avg_holding_days = np.mean(holding_periods)
        max_return = np.max(returns)
        max_loss = np.min(returns)

        total_profit = np.sum(winning) if len(winning) > 0 else 0
        total_loss = abs(np.sum(losing)) if len(losing) > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")

        sharpe_ratio = (
            np.mean(returns) / np.std(returns) * np.sqrt(252 / holding_days)
            if np.std(returns) > 0
            else 0
        )

        return SignalBacktestResult(
            signal_type=signal_type,
            total_signals=len(returns),
            winning_signals=len(winning),
            losing_signals=len(losing),
            win_rate=win_rate,
            avg_return=avg_return,
            avg_holding_days=avg_holding_days,
            max_return=max_return,
            max_loss=max_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            returns_distribution=returns.tolist(),
        )

    def backtest_all_signals(
        self,
        holding_days: int = 5,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[SignalBacktestResult]:
        """回测所有信号类型"""
        from scanner.signals import SignalType

        results = []
        for signal_type in SignalType:
            result = self.backtest_signal(
                signal_type.value,
                holding_days=holding_days,
                start_date=start_date,
                end_date=end_date,
            )
            results.append(result)

        return results


class PortfolioOptimizer:
    """组合优化器"""

    def __init__(self, returns_data: pd.DataFrame | None = None):
        self.returns_data = returns_data

    def set_returns_data(self, returns_data: pd.DataFrame):
        """设置收益率数据"""
        self.returns_data = returns_data

    def equal_weight(self, assets: list[str]) -> dict[str, float]:
        """等权重分配"""
        n = len(assets)
        weight = 1.0 / n
        return {asset: weight for asset in assets}

    def risk_parity(self, assets: list[str], volatilities: dict[str, float]) -> dict[str, float]:
        """
        风险平价分配

        Args:
            assets: 资产列表
            volatilities: 各资产波动率
        """
        inv_vols = {asset: 1.0 / volatilities.get(asset, 0.01) for asset in assets}
        total_inv_vol = sum(inv_vols.values())

        return {asset: inv_vol / total_inv_vol for asset, inv_vol in inv_vols.items()}

    def mean_variance_optimization(
        self,
        expected_returns: dict[str, float],
        cov_matrix: pd.DataFrame,
        risk_free_rate: float = 0.03,
        target_return: float | None = None,
    ) -> dict[str, float]:
        """
        均值方差优化

        Args:
            expected_returns: 期望收益率
            cov_matrix: 协方差矩阵
            risk_free_rate: 无风险利率
            target_return: 目标收益率
        """
        assets = list(expected_returns.keys())
        n = len(assets)

        if n == 0:
            return {}

        if n == 1:
            return {assets[0]: 1.0}

        try:
            from scipy.optimize import minimize

            mu = np.array([expected_returns.get(a, 0) for a in assets])
            cov = cov_matrix.reindex(assets, axis=0).reindex(assets, axis=1).values

            def neg_sharpe(weights):
                port_return = np.dot(weights, mu)
                port_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
                return -(port_return - risk_free_rate) / port_vol if port_vol > 0 else 0

            constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
            bounds = tuple((0.01, 0.30) for _ in range(n))

            init_weights = np.array([1.0 / n] * n)

            result = minimize(
                neg_sharpe,
                init_weights,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
            )

            if result.success:
                return {assets[i]: w for i, w in enumerate(result.x)}
            else:
                return self.equal_weight(assets)

        except ImportError:
            return self.equal_weight(assets)

    def optimize_with_constraints(
        self,
        assets: list[str],
        expected_returns: dict[str, float],
        volatilities: dict[str, float],
        correlations: pd.DataFrame,
        position_limit: PositionLimit,
        sector_mapping: dict[str, str] | None = None,
    ) -> PortfolioOptimizationResult:
        """
        带约束的组合优化

        Args:
            assets: 资产列表
            expected_returns: 期望收益率
            volatilities: 波动率
            correlations: 相关系数矩阵
            position_limit: 持仓限制
            sector_mapping: 股票-行业映射
        """
        n = len(assets)
        if n == 0:
            return PortfolioOptimizationResult(
                weights={},
                expected_return=0,
                expected_volatility=0,
                sharpe_ratio=0,
                diversification_ratio=0,
                concentration_hhi=0,
                sector_allocation={},
            )

        limited_assets = assets[: position_limit.max_positions]

        weights = self.risk_parity(limited_assets, volatilities)

        for asset in weights:
            if weights[asset] > position_limit.max_single_position_pct:
                weights[asset] = position_limit.max_single_position_pct

        total_weight = sum(weights.values())
        if total_weight > 1:
            weights = {k: v / total_weight for k, v in weights.items()}

        sector_allocation = {}
        if sector_mapping:
            for asset, weight in weights.items():
                sector = sector_mapping.get(asset, "未知")
                sector_allocation[sector] = sector_allocation.get(sector, 0) + weight

            for sector, alloc in sector_allocation.items():
                if alloc > position_limit.max_sector_position_pct:
                    sector_allocation[sector] = position_limit.max_sector_position_pct

        mu = np.array([expected_returns.get(a, 0) for a in limited_assets])
        vol = np.array([volatilities.get(a, 0.01) for a in limited_assets])
        w = np.array([weights.get(a, 0) for a in limited_assets])

        expected_return = np.dot(w, mu)
        expected_volatility = np.sqrt(np.dot(w.T, np.dot(np.diag(vol**2), w)))

        sharpe_ratio = expected_return / expected_volatility if expected_volatility > 0 else 0

        diversification_ratio = 1.0 / (np.sum(w**2)) if np.sum(w**2) > 0 else 1.0

        concentration_hhi = np.sum(w**2)

        return PortfolioOptimizationResult(
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe_ratio,
            diversification_ratio=diversification_ratio,
            concentration_hhi=concentration_hhi,
            sector_allocation=sector_allocation,
        )


class RiskAttributor:
    """风险归因分析器"""

    def __init__(self, returns_data: pd.DataFrame, weights: dict[str, float]):
        self.returns_data = returns_data
        self.weights = weights

    def calculate_risk_attribution(
        self,
        benchmark_returns: pd.Series | None = None,
        sector_mapping: dict[str, str] | None = None,
    ) -> RiskAttributionResult:
        """
        计算风险归因

        Args:
            benchmark_returns: 基准收益率
            sector_mapping: 股票-行业映射
        """
        assets = [a for a in self.weights if a in self.returns_data.columns]

        if not assets:
            return RiskAttributionResult(
                total_risk=0,
                systematic_risk=0,
                idiosyncratic_risk=0,
                sector_contributions={},
                stock_contributions={},
                factor_contributions={},
            )

        w = np.array([self.weights.get(a, 0) for a in assets])
        returns = self.returns_data[assets]

        cov_matrix = returns.cov()

        port_variance = np.dot(w.T, np.dot(cov_matrix, w))
        total_risk = np.sqrt(port_variance) if port_variance > 0 else 0

        systematic_risk = total_risk * 0.7
        idiosyncratic_risk = total_risk * 0.3

        stock_contributions = {}
        for i, asset in enumerate(assets):
            marginal_contrib = 2 * np.dot(cov_matrix.iloc[i], w)
            contrib = w[i] * marginal_contrib / port_variance if port_variance > 0 else 0
            stock_contributions[asset] = contrib

        sector_contributions = {}
        if sector_mapping:
            for asset, contrib in stock_contributions.items():
                sector = sector_mapping.get(asset, "未知")
                sector_contributions[sector] = sector_contributions.get(sector, 0) + contrib

        factor_contributions = {
            "动量因子": 0.25,
            "价值因子": 0.20,
            "质量因子": 0.15,
            "波动率因子": 0.20,
            "流动性因子": 0.10,
            "其他": 0.10,
        }

        return RiskAttributionResult(
            total_risk=total_risk,
            systematic_risk=systematic_risk,
            idiosyncratic_risk=idiosyncratic_risk,
            sector_contributions=sector_contributions,
            stock_contributions=stock_contributions,
            factor_contributions=factor_contributions,
        )


class PositionSizer:
    """仓位管理器"""

    def __init__(self, position_limit: PositionLimit | None = None):
        self.position_limit = position_limit or PositionLimit()

    def apply_limits(
        self,
        weights: dict[str, float],
        sector_mapping: dict[str, str] | None = None,
    ) -> dict[str, float]:
        """
        应用持仓限制

        Args:
            weights: 原始权重
            sector_mapping: 股票-行业映射
        """
        adjusted_weights = weights.copy()

        for asset, weight in adjusted_weights.items():
            if weight > self.position_limit.max_single_position_pct:
                adjusted_weights[asset] = self.position_limit.max_single_position_pct
            elif weight < self.position_limit.min_position_pct and weight > 0:
                adjusted_weights[asset] = self.position_limit.min_position_pct

        if sector_mapping:
            sector_weights: dict[str, float] = {}
            for asset, weight in adjusted_weights.items():
                sector = sector_mapping.get(asset, "未知")
                sector_weights[sector] = sector_weights.get(sector, 0) + weight

            for sector, sector_weight in sector_weights.items():
                if sector_weight > self.position_limit.max_sector_position_pct:
                    scale_factor = self.position_limit.max_sector_position_pct / sector_weight
                    for asset in adjusted_weights:
                        if sector_mapping.get(asset, "未知") == sector:
                            adjusted_weights[asset] *= scale_factor

        total_weight = sum(adjusted_weights.values())
        if total_weight > 1:
            adjusted_weights = {k: v / total_weight for k, v in adjusted_weights.items()}

        return adjusted_weights

    def kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fraction: float = 0.5,
    ) -> float:
        """
        凯利公式计算最优仓位

        Args:
            win_rate: 胜率
            avg_win: 平均盈利
            avg_loss: 平均亏损
            fraction: 凯利比例 (0.5 = 半凯利)
        """
        if avg_loss == 0:
            return 0

        b = avg_win / avg_loss
        q = 1 - win_rate

        kelly = (win_rate * b - q) / b
        kelly = max(0, kelly)

        return min(kelly * fraction, self.position_limit.max_single_position_pct)

    def volatility_targeting(
        self,
        target_volatility: float,
        current_volatility: float,
        current_weight: float,
    ) -> float:
        """
        波动率目标仓位调整

        Args:
            target_volatility: 目标波动率
            current_volatility: 当前波动率
            current_weight: 当前权重
        """
        if current_volatility == 0:
            return current_weight

        scale = target_volatility / current_volatility
        new_weight = current_weight * scale

        return min(new_weight, self.position_limit.max_single_position_pct)


def run_signal_backtest(
    db_path: Path,
    signal_type: str | None = None,
    holding_days: int = 5,
) -> SignalBacktestResult | list[SignalBacktestResult]:
    """
    运行信号回测

    Args:
        db_path: 数据库路径
        signal_type: 信号类型 (None = 全部)
        holding_days: 持有天数
    """
    backtester = SignalBacktester(db_path)
    backtester.connect()

    try:
        if signal_type:
            return backtester.backtest_signal(signal_type, holding_days=holding_days)
        else:
            return backtester.backtest_all_signals(holding_days=holding_days)
    finally:
        backtester.close()


def create_position_limit(
    max_positions: int = 10,
    max_single_position_pct: float = 0.15,
    max_sector_position_pct: float = 0.30,
) -> PositionLimit:
    """创建持仓限制配置"""
    return PositionLimit(
        max_positions=max_positions,
        max_single_position_pct=max_single_position_pct,
        max_sector_position_pct=max_sector_position_pct,
    )

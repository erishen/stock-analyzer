"""
API Schemas for Stock Analyzer Web.
API 数据模型
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BacktestRequest:
    """回测请求"""

    strategy: str = "momentum"
    holding_days: int = 5
    lookback_days: int = 20
    initial_capital: float = 100000.0
    min_price: float = 2.0
    max_volatility: float = 0.15
    stop_loss: float = 0.0
    take_profit: float = 0.0
    exclude_st: bool = True


@dataclass
class BacktestResponse:
    """回测响应"""

    success: bool
    strategy_name: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "strategy_name": self.strategy_name,
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
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate * 100, 2),
            "profit_factor": round(self.profit_factor, 2),
            "trades": self.trades[:50],
            "equity_curve": self.equity_curve[-100:],
            "error": self.error,
        }


@dataclass
class ScanRequest:
    """扫描请求"""

    signal_type: str | None = None
    min_score: float = 0.0
    limit: int = 50


@dataclass
class SignalItem:
    """信号项"""

    code: str
    name: str
    signal_type: str
    strength: str
    score: float
    price: float
    change_percent: float
    date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "signal_type": self.signal_type,
            "strength": self.strength,
            "score": round(self.score, 2),
            "price": round(self.price, 2),
            "change_percent": round(self.change_percent, 2),
            "date": self.date,
        }


@dataclass
class ScanResponse:
    """扫描响应"""

    success: bool
    total_stocks: int = 0
    signals_found: int = 0
    signals: list[SignalItem] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "total_stocks": self.total_stocks,
            "signals_found": self.signals_found,
            "signals": [s.to_dict() for s in self.signals],
            "summary": self.summary,
            "error": self.error,
        }


@dataclass
class PortfolioRequest:
    """组合请求"""

    strategies: list[str] = field(default_factory=lambda: ["momentum", "mean_reversion", "trend_following"])
    weight_method: str = "equal"
    holding_days: int = 5
    initial_capital: float = 100000.0


@dataclass
class PortfolioResponse:
    """组合响应"""

    success: bool
    name: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    volatility: float = 0.0
    diversification_ratio: float = 0.0
    strategy_weights: dict[str, float] = field(default_factory=dict)
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    strategy_results: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "name": self.name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": round(self.initial_capital, 2),
            "final_capital": round(self.final_capital, 2),
            "total_return": round(self.total_return * 100, 2),
            "annualized_return": round(self.annualized_return * 100, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "volatility": round(self.volatility * 100, 2),
            "diversification_ratio": round(self.diversification_ratio, 2),
            "strategy_weights": {k: round(v, 4) for k, v in self.strategy_weights.items()},
            "correlation_matrix": self.correlation_matrix,
            "strategy_results": self.strategy_results,
            "error": self.error,
        }


@dataclass
class SectorItem:
    """行业项"""

    name: str
    momentum: float
    strength: str
    stock_count: int
    top_stocks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "momentum": round(self.momentum * 100, 2),
            "strength": self.strength,
            "stock_count": self.stock_count,
            "top_stocks": self.top_stocks[:5],
        }


@dataclass
class SectorResponse:
    """行业响应"""

    success: bool
    analysis_date: str = ""
    sectors: list[SectorItem] = field(default_factory=list)
    rotation_signals: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "analysis_date": self.analysis_date,
            "sectors": [s.to_dict() for s in self.sectors],
            "rotation_signals": self.rotation_signals,
            "error": self.error,
        }


@dataclass
class MarketTimingResponse:
    """大盘择时响应"""

    success: bool
    state: str = ""
    score: int = 0
    position_advice: str = ""
    indicators: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "state": self.state,
            "score": self.score,
            "position_advice": self.position_advice,
            "indicators": self.indicators,
            "error": self.error,
        }


@dataclass
class StatsResponse:
    """统计响应"""

    success: bool
    stock_count: int = 0
    total_records: int = 0
    min_date: str = ""
    max_date: str = ""
    indicator_count: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "stock_count": self.stock_count,
            "total_records": self.total_records,
            "min_date": self.min_date,
            "max_date": self.max_date,
            "indicator_count": self.indicator_count,
            "error": self.error,
        }

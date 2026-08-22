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
    holding_days: int = 20
    lookback_days: int = 20
    initial_capital: float = 100000.0
    min_price: float = 2.0
    max_volatility: float = 0.15
    stop_loss: float = 0.0
    take_profit: float = 0.0
    exclude_st: bool = True
    start_date: str | None = None
    end_date: str | None = None
    refresh: bool = False


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
    refresh: bool = False


@dataclass
class ScreenerCondition:
    """自定义规则选股条件(全部 AND)"""

    field: str = ""
    op: str = ">"
    value: float = 0.0


@dataclass
class ScreenerRequest:
    """自定义规则选股请求"""

    conditions: list[dict] = field(default_factory=list)
    limit: int = 50
    offset: int = 0
    sort_field: str = "change_percent"
    sort_dir: str = "desc"


@dataclass
class ScreenerResponse:
    """自定义规则选股响应"""

    success: bool
    total: int = 0
    date: str = ""
    items: list[dict] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "total": self.total,
            "date": self.date,
            "items": self.items,
            "error": self.error,
        }


@dataclass
class PaperAddRequest:
    """模拟仓建仓请求"""

    code: str
    buy_price: float
    shares: float
    buy_date: str | None = None
    stop_loss: float = 0.08
    take_profit: float = 0.20


@dataclass
class PaperCloseRequest:
    """模拟仓卖出请求"""

    code: str
    sell_price: float
    sell_date: str | None = None
    shares: float | None = None


@dataclass
class AgentChatRequest:
    """Agent 对话请求: 携带历史消息回传给生成模型"""

    messages: list[dict]


@dataclass
class LLMSettingsRequest:
    """LLM 模型配置请求(设置 Tab): 空字段表示该项沿用 .env 默认。"""

    base_url: str = ""
    api_key: str = ""
    model: str = ""


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
class StockRowItem:
    """股票行情行"""

    code: str
    name: str
    market: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    change_percent: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    turnover_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "market": self.market,
            "open": round(self.open, 2),
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "close": round(self.close, 2),
            "change_percent": round(self.change_percent, 2),
            "volume": self.volume,
            "amount": self.amount,
            "turnover_rate": round(self.turnover_rate, 2),
        }


@dataclass
class StocksResponse:
    """股票行情分页响应"""

    success: bool
    date: str = ""
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0
    items: list[StockRowItem] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "date": self.date,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "items": [i.to_dict() for i in self.items],
            "error": self.error,
        }


@dataclass
class KlinePoint:
    """单只股票 K 线点"""

    date: str
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    change_percent: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "open": round(self.open, 2),
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "close": round(self.close, 2),
            "volume": self.volume,
            "change_percent": round(self.change_percent, 2),
            "ma5": round(self.ma5, 2),
            "ma10": round(self.ma10, 2),
            "ma20": round(self.ma20, 2),
            "ma60": round(self.ma60, 2),
        }


@dataclass
class StockDetailResponse:
    """单只股票详情响应"""

    success: bool
    code: str = ""
    name: str = ""
    market: str = ""
    latest: dict[str, Any] = field(default_factory=dict)
    indicators: dict[str, Any] = field(default_factory=dict)
    period_returns: dict[str, float] = field(default_factory=dict)
    kline: list[dict[str, Any]] = field(default_factory=list)
    asset: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "code": self.code,
            "name": self.name,
            "market": self.market,
            "latest": self.latest,
            "indicators": self.indicators,
            "period_returns": self.period_returns,
            "kline": self.kline,
            "asset": self.asset,
            "error": self.error,
        }


@dataclass
class PortfolioRequest:
    """组合请求"""

    strategies: list[str] = field(default_factory=lambda: ["momentum", "mean_reversion", "trend_following"])
    weight_method: str = "equal"
    holding_days: int = 5
    initial_capital: float = 100000.0
    refresh: bool = False


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
class MarketHistoryResponse:
    """全市场近期走势响应"""

    success: bool
    days: int = 0
    start_date: str = ""
    end_date: str = ""
    dates: list[str] = field(default_factory=list)
    avg_close: list[float] = field(default_factory=list)
    avg_ma5: list[float] = field(default_factory=list)
    avg_ma20: list[float] = field(default_factory=list)
    avg_change: list[float] = field(default_factory=list)
    avg_rsi: list[float] = field(default_factory=list)
    breadth: list[float] = field(default_factory=list)
    volatility: list[float] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        def num(v):
            return round(v, 2) if v is not None else None

        return {
            "success": self.success,
            "days": self.days,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "dates": self.dates,
            "avg_close": self.avg_close,
            "avg_ma5": self.avg_ma5,
            "avg_ma20": self.avg_ma20,
            "avg_change": [num(v) for v in self.avg_change],
            "avg_rsi": [num(v) for v in self.avg_rsi],
            "breadth": [num(v) for v in self.breadth],
            "volatility": [round(v, 4) if v is not None else None for v in self.volatility],
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


@dataclass
class OptimizeRequest:
    """参数寻优请求"""

    strategy: str = "momentum"
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float = 100000.0


@dataclass
class OptimizeResponse:
    """参数寻优响应"""

    success: bool
    strategy: str = ""
    best_params: dict = field(default_factory=dict)
    best_return: float = 0.0
    best_sharpe: float = 0.0
    best_drawdown: float = 0.0
    total_combinations: int = 0
    train_start: str = ""
    train_end: str = ""
    val_start: str = ""
    val_end: str = ""
    val_return: float = 0.0
    val_sharpe: float = 0.0
    val_drawdown: float = 0.0
    top_results: list[dict] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "strategy": self.strategy,
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
            "top_results": [
                {
                    **r,
                    "total_return": round(r["total_return"] * 100, 2),
                    "max_drawdown": round(r["max_drawdown"] * 100, 2),
                    "win_rate": round(r["win_rate"] * 100, 2),
                }
                for r in self.top_results
            ],
            "error": self.error,
        }

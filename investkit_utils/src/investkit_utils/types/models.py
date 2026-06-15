from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from investkit_utils.types.enums import (
    Market,
    OrderStatus,
    OrderType,
    SignalType,
)
from investkit_utils.utils.data_utils import ToDictMixin


@dataclass
class StockInfo(ToDictMixin):
    code: str
    name: str
    market: Market
    industry: str | None = None
    sector: str | None = None
    list_date: date | None = None
    total_shares: float | None = None
    float_shares: float | None = None


@dataclass
class Price(ToDictMixin):
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float | None = None
    timestamp: datetime | None = None


@dataclass
class TradeSignal(ToDictMixin):
    symbol: str
    signal_type: SignalType
    price: float | None = None
    quantity: float | None = None
    confidence: float | None = None
    reason: str | None = None
    indicators: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Position(ToDictMixin):
    symbol: str
    quantity: float
    cost_price: float
    current_price: float | None = None
    market_value: float | None = None
    profit_loss: float | None = None
    profit_loss_pct: float | None = None

    def __post_init__(self):
        if self.current_price is not None:
            self.market_value = self.quantity * self.current_price
            self.profit_loss = (self.current_price - self.cost_price) * self.quantity
            if self.cost_price > 0:
                self.profit_loss_pct = (self.current_price - self.cost_price) / self.cost_price * 100


@dataclass
class Portfolio(ToDictMixin):
    name: str
    positions: list[Position] = field(default_factory=list)
    cash: float = 0.0
    total_value: float | None = None
    total_cost: float | None = None
    total_profit_loss: float | None = None
    total_profit_loss_pct: float | None = None

    def calculate_totals(self) -> None:
        self.total_cost = sum(p.quantity * p.cost_price for p in self.positions)
        position_value = sum(p.market_value or 0 for p in self.positions)
        self.total_value = position_value + self.cash

        if self.total_cost and self.total_cost > 0:
            self.total_profit_loss = self.total_value - self.total_cost
            self.total_profit_loss_pct = (self.total_value - self.total_cost) / self.total_cost * 100


@dataclass
class Order(ToDictMixin):
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: OrderType
    quantity: float
    price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    order_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: datetime | None = None
    filled_price: float | None = None
    filled_quantity: float | None = None


@dataclass
class RiskMetrics(ToDictMixin):
    symbol: str | None = None
    var_95: float | None = None
    var_99: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    volatility: float | None = None
    beta: float | None = None
    alpha: float | None = None
    expected_shortfall: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None
    concentration_risk: float | None = None


@dataclass
class MLPrediction(ToDictMixin):
    symbol: str
    prediction: float
    confidence: float
    model_name: str
    features_used: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

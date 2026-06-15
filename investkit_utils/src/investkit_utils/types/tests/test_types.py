"""InvestKit 类型模块测试"""

from investkit_utils.types import (
    AssetType,
    Market,
    MLPrediction,
    Order,
    OrderStatus,
    OrderType,
    Portfolio,
    Position,
    Price,
    RiskLevel,
    RiskMetrics,
    SignalType,
    StockInfo,
    TradeSignal,
)


class TestEnums:
    def test_signal_type_values(self):
        assert SignalType.BUY
        assert SignalType.SELL
        assert SignalType.HOLD

    def test_order_type_values(self):
        assert OrderType.MARKET
        assert OrderType.LIMIT

    def test_market_values(self):
        assert Market.SH
        assert Market.SZ
        assert Market.HK
        assert Market.US

    def test_asset_type_values(self):
        assert AssetType.STOCK
        assert AssetType.FUND
        assert AssetType.BOND

    def test_risk_level_values(self):
        assert RiskLevel.LOW
        assert RiskLevel.MEDIUM
        assert RiskLevel.HIGH

    def test_order_status_values(self):
        assert OrderStatus.PENDING
        assert OrderStatus.FILLED
        assert OrderStatus.CANCELLED


class TestPrice:
    def test_creation(self):
        p = Price(open=10.0, high=11.0, low=9.5, close=10.5, volume=10000)
        assert p.close == 10.5
        assert p.volume == 10000

    def test_to_dict(self):
        p = Price(open=10.0, high=11.0, low=9.5, close=10.5, volume=10000)
        d = p.to_dict()
        assert d["close"] == 10.5


class TestStockInfo:
    def test_creation(self):
        info = StockInfo(code="600519", name="贵州茅台", market=Market.SH)
        assert info.code == "600519"
        assert info.name == "贵州茅台"


class TestOrder:
    def test_creation(self):
        order = Order(symbol="600519", side="BUY", order_type=OrderType.LIMIT, quantity=100, price=1800.0)
        assert order.symbol == "600519"
        assert order.quantity == 100


class TestTradeSignal:
    def test_creation(self):
        signal = TradeSignal(symbol="600519", signal_type=SignalType.BUY, price=1800.0)
        assert signal.symbol == "600519"
        assert signal.signal_type == SignalType.BUY


class TestPosition:
    def test_creation(self):
        pos = Position(symbol="600519", quantity=100, cost_price=1700.0)
        assert pos.symbol == "600519"
        assert pos.quantity == 100


class TestPortfolio:
    def test_creation(self):
        portfolio = Portfolio(name="test")
        assert portfolio.name == "test"


class TestRiskMetrics:
    def test_creation(self):
        metrics = RiskMetrics()
        assert metrics is not None

    def test_with_values(self):
        metrics = RiskMetrics(symbol="600519", volatility=0.25, sharpe_ratio=1.5)
        assert metrics.symbol == "600519"
        assert metrics.volatility == 0.25


class TestMLPrediction:
    def test_creation(self):
        pred = MLPrediction(symbol="600519", prediction=1.0, confidence=0.85, model_name="lgb")
        assert pred.symbol == "600519"
        assert pred.confidence == 0.85

from investkit_utils.types.enums import AssetType, Market, OrderStatus, OrderType, RiskLevel, SignalType
from investkit_utils.types.models import MLPrediction, Order, Portfolio, Position, Price, RiskMetrics, StockInfo, TradeSignal
from datetime import datetime
from decimal import Decimal


class TestSignalType:
    def test_values(self):
        assert SignalType.BUY.value == "BUY"
        assert SignalType.SELL.value == "SELL"
        assert SignalType.HOLD.value == "HOLD"

    def test_is_str(self):
        assert isinstance(SignalType.BUY, str)


class TestOrderType:
    def test_values(self):
        assert OrderType.MARKET.value == "MARKET"
        assert OrderType.LIMIT.value == "LIMIT"
        assert OrderType.STOP.value == "STOP"
        assert OrderType.STOP_LIMIT.value == "STOP_LIMIT"


class TestOrderStatus:
    def test_values(self):
        assert OrderStatus.PENDING.value == "PENDING"
        assert OrderStatus.SUBMITTED.value == "SUBMITTED"
        assert OrderStatus.FILLED.value == "FILLED"
        assert OrderStatus.CANCELLED.value == "CANCELLED"
        assert OrderStatus.REJECTED.value == "REJECTED"


class TestMarket:
    def test_values(self):
        assert Market.SH.value == "SH"
        assert Market.SZ.value == "SZ"
        assert Market.BJ.value == "BJ"
        assert Market.HK.value == "HK"
        assert Market.US.value == "US"


class TestAssetType:
    def test_values(self):
        assert AssetType.STOCK.value == "STOCK"
        assert AssetType.FUND.value == "FUND"
        assert AssetType.BOND.value == "BOND"
        assert AssetType.CRYPTO.value == "CRYPTO"
        assert AssetType.CASH.value == "CASH"
        assert AssetType.OTHER.value == "OTHER"


class TestRiskLevelEnum:
    def test_values(self):
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.CRITICAL.value == "CRITICAL"


class TestStockInfoModel:
    def test_creation_minimal(self):
        info = StockInfo(code="600519", name="贵州茅台", market=Market.SH)
        assert info.code == "600519"
        assert info.name == "贵州茅台"
        assert info.market == Market.SH
        assert info.industry is None
        assert info.list_date is None

    def test_creation_full(self):
        from datetime import date
        info = StockInfo(
            code="00700",
            name="腾讯控股",
            market=Market.HK,
            industry="互联网",
            sector="科技",
            list_date=date(2004, 6, 16),
            total_shares=9500000000,
            float_shares=9400000000,
        )
        assert info.industry == "互联网"
        assert info.total_shares == 9500000000

    def test_to_dict(self):
        info = StockInfo(code="600519", name="贵州茅台", market=Market.SH)
        d = info.to_dict()
        assert d["code"] == "600519"
        assert d["market"] == "SH"


class TestPriceModel:
    def test_creation(self):
        p = Price(open=10.0, high=11.0, low=9.5, close=10.5, volume=10000)
        assert p.close == 10.5
        assert p.amount is None
        assert p.timestamp is None

    def test_to_dict(self):
        p = Price(open=10.0, high=11.0, low=9.5, close=10.5, volume=10000)
        d = p.to_dict()
        assert d["open"] == 10.0
        assert d["close"] == 10.5


class TestPositionModel:
    def test_creation_without_current_price(self):
        pos = Position(symbol="600519", quantity=100, cost_price=1700.0)
        assert pos.current_price is None
        assert pos.market_value is None
        assert pos.profit_loss is None

    def test_post_init_with_current_price(self):
        pos = Position(symbol="600519", quantity=100, cost_price=1700.0, current_price=1800.0)
        assert pos.market_value == 180000.0
        assert pos.profit_loss == 10000.0
        assert pos.profit_loss_pct == pytest.approx(5.8824, rel=0.01)

    def test_post_init_loss(self):
        pos = Position(symbol="600519", quantity=100, cost_price=1800.0, current_price=1700.0)
        assert pos.profit_loss == -10000.0
        assert pos.profit_loss_pct < 0

    def test_to_dict(self):
        pos = Position(symbol="600519", quantity=100, cost_price=1700.0, current_price=1800.0)
        d = pos.to_dict()
        assert d["symbol"] == "600519"
        assert d["quantity"] == 100


class TestPortfolioModel:
    def test_creation(self):
        portfolio = Portfolio(name="test")
        assert portfolio.name == "test"
        assert portfolio.positions == []
        assert portfolio.cash == 0.0

    def test_calculate_totals(self):
        pos1 = Position(symbol="A", quantity=100, cost_price=10.0, current_price=12.0)
        pos2 = Position(symbol="B", quantity=200, cost_price=5.0, current_price=6.0)
        portfolio = Portfolio(name="test", positions=[pos1, pos2], cash=1000.0)
        portfolio.calculate_totals()
        assert portfolio.total_cost == 2000.0
        assert portfolio.total_value == 3400.0
        assert portfolio.total_profit_loss == 1400.0

    def test_calculate_totals_empty(self):
        portfolio = Portfolio(name="empty", cash=5000.0)
        portfolio.calculate_totals()
        assert portfolio.total_value == 5000.0

    def test_to_dict(self):
        portfolio = Portfolio(name="test", cash=1000.0)
        d = portfolio.to_dict()
        assert d["name"] == "test"
        assert d["cash"] == 1000.0


class TestOrderModel:
    def test_creation(self):
        order = Order(symbol="600519", side="BUY", order_type=OrderType.LIMIT, quantity=100, price=1800.0)
        assert order.status == OrderStatus.PENDING
        assert order.filled_price is None

    def test_to_dict(self):
        order = Order(symbol="600519", side="BUY", order_type=OrderType.MARKET, quantity=100)
        d = order.to_dict()
        assert d["symbol"] == "600519"
        assert d["side"] == "BUY"


class TestTradeSignalModel:
    def test_creation(self):
        signal = TradeSignal(symbol="600519", signal_type=SignalType.BUY, price=1800.0, confidence=0.85)
        assert signal.signal_type == SignalType.BUY
        assert signal.confidence == 0.85
        assert signal.indicators == []

    def test_to_dict(self):
        signal = TradeSignal(symbol="600519", signal_type=SignalType.SELL, price=1900.0)
        d = signal.to_dict()
        assert d["signal_type"] == "SELL"


class TestRiskMetricsModel:
    def test_defaults(self):
        metrics = RiskMetrics()
        assert metrics.var_95 is None
        assert metrics.volatility is None

    def test_with_values(self):
        metrics = RiskMetrics(symbol="600519", volatility=0.25, sharpe_ratio=1.5, max_drawdown=0.15)
        assert metrics.symbol == "600519"
        assert metrics.volatility == 0.25

    def test_to_dict(self):
        metrics = RiskMetrics(symbol="600519", beta=1.2)
        d = metrics.to_dict()
        assert d["symbol"] == "600519"
        assert d["beta"] == 1.2


class TestMLPredictionModel:
    def test_creation(self):
        pred = MLPrediction(symbol="600519", prediction=1.0, confidence=0.85, model_name="lgb")
        assert pred.features_used == []

    def test_with_features(self):
        pred = MLPrediction(
            symbol="600519",
            prediction=1.0,
            confidence=0.85,
            model_name="lgb",
            features_used=["ma5", "ma10", "rsi"],
        )
        assert len(pred.features_used) == 3

    def test_to_dict(self):
        pred = MLPrediction(symbol="600519", prediction=1.0, confidence=0.85, model_name="lgb")
        d = pred.to_dict()
        assert d["model_name"] == "lgb"


import pytest

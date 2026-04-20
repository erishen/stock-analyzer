"""
Tests for Web API Module.
Web API 模块测试
"""

from src.web.api import app, get_default_html
from src.web.schemas import (
    BacktestRequest,
    BacktestResponse,
    MarketTimingResponse,
    PortfolioRequest,
    PortfolioResponse,
    ScanResponse,
    SectorItem,
    SignalItem,
    StatsResponse,
)


class TestBacktestRequest:
    """测试回测请求"""

    def test_default_values(self):
        req = BacktestRequest()
        assert req.strategy == "momentum"
        assert req.holding_days == 5
        assert req.initial_capital == 100000.0
        assert req.exclude_st is True

    def test_custom_values(self):
        req = BacktestRequest(
            strategy="mean_reversion",
            holding_days=10,
            initial_capital=50000.0,
            stop_loss=0.05,
            take_profit=0.1,
        )
        assert req.strategy == "mean_reversion"
        assert req.holding_days == 10
        assert req.stop_loss == 0.05


class TestBacktestResponse:
    """测试回测响应"""

    def test_success_response(self):
        resp = BacktestResponse(
            success=True,
            strategy_name="MomentumStrategy",
            total_return=0.15,
            sharpe_ratio=1.5,
        )
        assert resp.success is True
        assert resp.total_return == 0.15

    def test_to_dict(self):
        resp = BacktestResponse(
            success=True,
            total_return=0.12345,
            max_drawdown=0.05678,
            sharpe_ratio=1.234,
        )
        d = resp.to_dict()
        assert d["total_return"] == 12.35
        assert d["max_drawdown"] == 5.68
        assert d["sharpe_ratio"] == 1.23

    def test_error_response(self):
        resp = BacktestResponse(success=False, error="Database not found")
        assert resp.success is False
        assert resp.error == "Database not found"


class TestSignalItem:
    """测试信号项"""

    def test_create_signal(self):
        signal = SignalItem(
            code="sh600000",
            name="浦发银行",
            signal_type="macd_golden_cross",
            strength="强",
            score=85.5,
            price=10.5,
            change_percent=2.5,
            date="2026-04-17",
        )
        assert signal.code == "sh600000"
        assert signal.name == "浦发银行"

    def test_to_dict(self):
        signal = SignalItem(
            code="sh600000",
            name="浦发银行",
            signal_type="macd_golden_cross",
            strength="强",
            score=85.567,
            price=10.567,
            change_percent=2.567,
            date="2026-04-17",
        )
        d = signal.to_dict()
        assert d["score"] == 85.57
        assert d["price"] == 10.57


class TestScanResponse:
    """测试扫描响应"""

    def test_success_response(self):
        signals = [
            SignalItem(
                code="sh600000",
                name="浦发银行",
                signal_type="macd_golden_cross",
                strength="强",
                score=85.0,
                price=10.5,
                change_percent=2.5,
                date="2026-04-17",
            )
        ]
        resp = ScanResponse(
            success=True,
            total_stocks=5000,
            signals_found=100,
            signals=signals,
            summary={"macd_golden_cross": 50},
        )
        assert resp.success is True
        assert resp.total_stocks == 5000
        assert len(resp.signals) == 1


class TestPortfolioRequest:
    """测试组合请求"""

    def test_default_values(self):
        req = PortfolioRequest()
        assert req.strategies == ["momentum", "mean_reversion", "trend_following"]
        assert req.weight_method == "equal"

    def test_custom_values(self):
        req = PortfolioRequest(
            strategies=["momentum", "mean_reversion"],
            weight_method="sharpe",
            holding_days=10,
        )
        assert len(req.strategies) == 2
        assert req.weight_method == "sharpe"


class TestPortfolioResponse:
    """测试组合响应"""

    def test_to_dict(self):
        resp = PortfolioResponse(
            success=True,
            total_return=0.12345,
            strategy_weights={"momentum": 0.333333},
            correlation_matrix={"momentum": {"momentum": 1.0}},
        )
        d = resp.to_dict()
        assert d["total_return"] == 12.35
        assert d["strategy_weights"]["momentum"] == 0.3333


class TestSectorItem:
    """测试行业项"""

    def test_to_dict(self):
        item = SectorItem(
            name="银行",
            momentum=0.0567,
            strength="strong",
            stock_count=40,
            top_stocks=["sh600000", "sh601398"],
        )
        d = item.to_dict()
        assert d["momentum"] == 5.67
        assert d["strength"] == "strong"


class TestMarketTimingResponse:
    """测试大盘择时响应"""

    def test_to_dict(self):
        resp = MarketTimingResponse(
            success=True,
            state="bull",
            score=75,
            position_advice="建议仓位80%",
            indicators={"MA": {"value": 1.5, "signal": "bullish"}},
        )
        d = resp.to_dict()
        assert d["state"] == "bull"
        assert d["score"] == 75


class TestStatsResponse:
    """测试统计响应"""

    def test_to_dict(self):
        resp = StatsResponse(
            success=True,
            stock_count=5189,
            total_records=1105545,
            min_date="2025-01-07",
            max_date="2026-04-17",
            indicator_count=51,
        )
        d = resp.to_dict()
        assert d["stock_count"] == 5189
        assert d["indicator_count"] == 51


class TestGetDefaultHtml:
    """测试默认 HTML"""

    def test_default_html(self):
        html = get_default_html()
        assert "<!DOCTYPE html>" in html
        assert "Stock Analyzer" in html
        assert "/docs" in html


class TestFastAPIApp:
    """测试 FastAPI 应用"""

    def test_app_creation(self):
        assert app is not None
        assert app.title == "Stock Analyzer API"

    def test_routes_exist(self):
        routes = [route.path for route in app.routes]
        assert "/" in routes
        assert "/api/stats" in routes
        assert "/api/scan" in routes
        assert "/api/backtest" in routes
        assert "/api/portfolio" in routes
        assert "/api/sector" in routes
        assert "/api/market-timing" in routes

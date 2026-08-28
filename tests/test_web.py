"""
Tests for Web API Module.
Web API 模块测试
"""

import os
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

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

# 与 src/etl/pipeline.py 中 stock_analysis 全量建表 DDL 保持一致。
# 该测试不依赖未入库的 4.8GB 真实 data/stock_analysis.db, 自带 seed 库。
_STOCK_ANALYSIS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    close REAL,
    high REAL,
    low REAL,
    volume REAL,
    amount REAL,
    amplitude REAL,
    change_percent REAL,
    change_amount REAL,
    turnover_rate REAL,
    ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL,
    close_ma5_ratio REAL, close_ma10_ratio REAL, close_ma20_ratio REAL, close_ma60_ratio REAL,
    ema12 REAL, ema26 REAL,
    macd REAL, macd_signal REAL, macd_hist REAL, macd_cross INTEGER,
    rsi REAL, rsi_oversold INTEGER, rsi_overbought INTEGER,
    boll_mid REAL, boll_std REAL, boll_upper REAL, boll_lower REAL, boll_width REAL, boll_position REAL,
    kdj_rsv REAL, kdj_k REAL, kdj_d REAL, kdj_j REAL, kdj_cross INTEGER,
    atr REAL, atr_ratio REAL,
    obv REAL, obv_ma10 REAL, obv_signal INTEGER,
    williams_r REAL, williams_oversold INTEGER, williams_overbought INTEGER,
    momentum_5d REAL, momentum_10d REAL, momentum_20d REAL,
    roc_10 REAL, roc_20 REAL,
    pct_change REAL,
    volatility_5d REAL, volatility_10d REAL, volatility_20d REAL, volatility_ratio REAL,
    high_low_ratio REAL, close_open_ratio REAL,
    upper_shadow REAL, lower_shadow REAL, body_size REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, date)
);
"""


class TestBacktestRequest:
    """测试回测请求"""

    def test_default_values(self):
        req = BacktestRequest()
        assert req.strategy == "momentum"
        assert req.holding_days == 20
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
        assert "/api/stock/{code}" in routes


class TestStockDetailEndpoint:
    """测试股票详情接口 /api/stock/{code} (回归: 列索引错位曾导致 tuple index out of range)

    不依赖未入库的 4.8GB 真实 data/stock_analysis.db; 自带最小 seed 库,
    并通过 patch src.web.api.db_path 指向临时库, 与 test_api.py 的临时库做法一致。
    """

    @staticmethod
    def _build_seed_db() -> Path:
        """构建最小自包含 seed DB: stock_analysis 全量表 + sh600887 若干交易日数据。"""
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db_path = Path(name)
        conn = sqlite3.connect(str(db_path))
        conn.executescript(_STOCK_ANALYSIS_SCHEMA)
        rows = []
        base = date(2023, 1, 1)
        for i in range(300):
            d = (base + timedelta(days=i)).isoformat()
            close = 10.0 + i * 0.01
            rows.append(
                (
                    "sh600887",
                    d,
                    10.0,
                    close,
                    close + 0.5,
                    close - 0.5,
                    1_000_000,
                    10_500_000,
                    0.5,
                    20.0,
                    20.0,
                    20.0,
                    20.0,  # ma5/ma10/ma20/ma60
                    0.1,
                    0.02,
                    55.0,  # macd/macd_hist/rsi
                    20.0,
                    20.0,
                    20.0,  # kdj_k/kdj_d/kdj_j
                    11.0,
                    10.0,
                    9.0,  # boll_upper/mid/lower
                    1.5,  # atr
                )
            )
        conn.executemany(
            """
            INSERT INTO stock_analysis
                (code, date, open, close, high, low, volume, amount, change_percent,
                 ma5, ma10, ma20, ma60, macd, macd_hist, rsi,
                 kdj_k, kdj_d, kdj_j, boll_upper, boll_mid, boll_lower, atr)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def seed_db(self):
        db_path = self._build_seed_db()
        yield db_path
        db_path.unlink(missing_ok=True)

    def _client(self):
        from starlette.testclient import TestClient

        return TestClient(app)

    def test_stock_detail_success(self, seed_db):
        """已知存在的 seed 股票应返回 success=true 且字段齐全, 不再越界崩溃"""
        with patch("src.web.api.db_path", seed_db):
            client = self._client()
            resp = client.get("/api/stock/sh600887?limit=120&days=2500")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True, body.get("error")
        assert body["code"] == "sh600887"
        # 关键字段齐全且为数值 (曾因 last[22] 越界使详情弹窗崩溃)
        assert body["latest"]["close"] is not None
        assert isinstance(body["indicators"]["atr"], (int, float))
        assert isinstance(body["indicators"]["ma5"], (int, float))
        assert len(body["kline"]) > 0
        # 每条 kline 的 OHLC 均非 None
        for k in body["kline"]:
            assert k["close"] is not None
            assert k["ma5"] is not None

    def test_stock_detail_unknown_code(self, seed_db):
        """不存在的股票应优雅返回 success=false, 不抛 500"""
        with patch("src.web.api.db_path", seed_db):
            client = self._client()
            resp = client.get("/api/stock/sh000000?limit=120&days=2500")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error"]

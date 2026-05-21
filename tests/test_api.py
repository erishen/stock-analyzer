"""
Tests for Web API Module.
Web API 模块测试
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.web.api import app
from src.web.schemas import StatsResponse


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE stock_analysis (
            code TEXT,
            date TEXT,
            open REAL,
            close REAL,
            high REAL,
            low REAL,
            volume REAL,
            amount REAL,
            change_percent REAL,
            macd REAL,
            rsi REAL,
            ma5 REAL,
            ma20 REAL
        )
    """)

    test_data = [
        (
            "000001",
            "2024-01-01",
            10.0,
            10.5,
            10.8,
            9.9,
            1000000,
            10500000,
            5.0,
            0.1,
            45.0,
            10.2,
            10.0,
        ),
        (
            "000001",
            "2024-01-02",
            10.5,
            10.3,
            10.6,
            10.2,
            1200000,
            12360000,
            -2.0,
            0.08,
            50.0,
            10.3,
            10.1,
        ),
        (
            "000002",
            "2024-01-01",
            20.0,
            20.5,
            20.8,
            19.9,
            2000000,
            41000000,
            2.5,
            0.05,
            55.0,
            20.2,
            20.0,
        ),
    ]
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


class TestStatsEndpoint:
    """测试统计接口"""

    def test_get_stats_db_not_exists(self, client):
        """测试数据库不存在"""
        with patch("src.web.api.db_path", Path("/nonexistent/path.db")):
            response = client.get("/api/stats")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_get_stats_success(self, client, temp_db):
        """测试获取统计成功"""
        with patch("src.web.api.db_path", temp_db):
            response = client.get("/api/stats")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["stock_count"] == 2
            assert data["total_records"] == 3


class TestIndexEndpoint:
    """测试主页接口"""

    def test_index_returns_html(self, client):
        """测试主页返回 HTML"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestScanEndpoint:
    """测试扫描接口"""

    def test_scan_default(self, client, temp_db):
        """测试默认扫描"""
        with patch("src.web.api.db_path", temp_db):
            response = client.post("/api/scan", json={})
            assert response.status_code == 200
            data = response.json()
            assert "signals" in data or "success" in data

    def test_scan_with_params(self, client, temp_db):
        """测试带参数扫描"""
        with patch("src.web.api.db_path", temp_db):
            response = client.post("/api/scan", json={"signal_type": "rsi_oversold", "limit": 10})
            assert response.status_code == 200


class TestBacktestEndpoint:
    """测试回测接口"""

    def test_backtest_default(self, client, temp_db):
        """测试默认回测"""
        with patch("src.web.api.db_path", temp_db):
            response = client.post("/api/backtest", json={})
            assert response.status_code == 200
            data = response.json()
            assert "success" in data


class TestPortfolioEndpoint:
    """测试组合接口"""

    def test_portfolio_default(self, client, temp_db):
        """测试默认组合"""
        with patch("src.web.api.db_path", temp_db):
            response = client.post("/api/portfolio", json={})
            assert response.status_code == 200
            data = response.json()
            assert "success" in data


class TestSectorEndpoint:
    """测试行业接口"""

    def test_sector_default(self, client, temp_db):
        """测试默认行业"""
        with patch("src.web.api.db_path", temp_db):
            response = client.get("/api/sector")
            assert response.status_code == 200
            data = response.json()
            assert "sectors" in data


class TestMarketTimingEndpoint:
    """测试择时接口"""

    def test_market_timing_default(self, client, temp_db):
        """测试默认择时"""
        with patch("src.web.api.db_path", temp_db):
            response = client.get("/api/market-timing")
            assert response.status_code == 200
            data = response.json()
            assert "success" in data


class TestSchemas:
    """测试数据模型"""

    def test_stats_response(self):
        """测试统计响应"""
        response = StatsResponse(
            success=True,
            stock_count=100,
            total_records=10000,
            min_date="2024-01-01",
            max_date="2024-12-31",
            indicator_count=50,
        )
        d = response.to_dict()
        assert d["success"] is True
        assert d["stock_count"] == 100

    def test_stats_response_error(self):
        """测试错误响应"""
        response = StatsResponse(success=False, error="测试错误")
        d = response.to_dict()
        assert d["success"] is False
        assert d["error"] == "测试错误"

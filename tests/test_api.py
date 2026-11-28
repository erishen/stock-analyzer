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


class TestMLAPI:
    """ML 模型接口测试 (依赖 sklearn; 缺失时整类跳过)"""

    @pytest.fixture(autouse=True)
    def _ensure_ml(self):
        pytest.importorskip("sklearn")

    def _build_ml_db(self, n=120) -> Path:
        """构造含 ANOMALY/CLUSTER 特征列的临时分析库。"""
        import tempfile

        from ml.common import ANOMALY_FEATURES, CLUSTER_FEATURES

        cols = set(ANOMALY_FEATURES) | set(CLUSTER_FEATURES)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE stock_analysis (code TEXT, date TEXT, " + ", ".join(f"{c} REAL" for c in cols) + ")")
        import random

        rng = random.Random(42)
        for i in range(n):
            vals = [f"60{i:04d}", "2026-11-18"]
            for c in cols:
                vals.append(round(rng.uniform(0.01, 100), 4))
            conn.execute("INSERT INTO stock_analysis VALUES (" + ",".join("?" for _ in vals) + ")", vals)
        conn.commit()
        conn.close()
        return db_path

    def _patch_db(self, db: Path):
        """patch api 的 db_path 与 api_cache 的 _DB_PATH, 隔离缓存避免污染真实 data/cache。"""
        return [
            patch("src.web.api.db_path", db),
            patch("src.web.api_cache._DB_PATH", db),
        ]

    def test_status(self, client):
        """依赖可用性接口返回三件套。"""
        resp = client.get("/api/ml/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert set(body["available"]) == {"lightgbm", "sklearn", "arch"}

    def test_anomaly_no_db(self, client):
        """库不存在时返回可读错误。"""
        with patch("src.web.api.db_path", Path("/nonexistent/path.db")):
            resp = client.get("/api/ml/anomaly")
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_anomaly_success(self, client):
        """正常跑异常检测, 返回 top_anomalies。"""
        db = self._build_ml_db()
        try:
            patches = self._patch_db(db)
            for p in patches:
                p.start()
            resp = client.get("/api/ml/anomaly")
            for p in patches:
                p.stop()
            body = resp.json()
            assert resp.status_code == 200
            assert body["success"] is True
            assert body["total_stocks"] > 0
            assert "top_anomalies" in body
        finally:
            db.unlink(missing_ok=True)

    def test_cluster_success(self, client):
        """正常跑聚类, 返回簇列表。"""
        db = self._build_ml_db()
        try:
            patches = self._patch_db(db)
            for p in patches:
                p.start()
            resp = client.get("/api/ml/cluster?k=4")
            for p in patches:
                p.stop()
            body = resp.json()
            assert resp.status_code == 200
            assert body["success"] is True
            assert 2 <= body["n_clusters"] <= 4
            assert len(body["clusters"]) > 0
        finally:
            db.unlink(missing_ok=True)

    def test_gbm_reads_report(self, client):
        """读取最近 gbm 报告: 无报告时给可读提示, 有则返回 report。"""
        resp = client.get("/api/ml/gbm")
        assert resp.status_code == 200
        assert "success" in resp.json()

    def test_gbm_train_submit_and_status(self, client):
        """提交训练任务 (转发宿主) 返回 task_id, 状态接口透传宿主。"""
        from src.web import api

        calls = {}

        def fake_host_call(method, path, payload=None, timeout=30.0):
            calls[(method, path)] = payload
            if path == "/ml-gbm":
                return True, '{"success":true,"stage":"训练中 (宿主)..."}'
            if path == "/ml-gbm/status":
                return True, '{"status":"success","stage":"done","result":{"rankic":{"mean_ic":0.1}}}'
            return True, "{}"

        original = api._host_call
        api._host_call = fake_host_call
        try:
            resp = client.post("/api/ml/gbm/train", json={"start_year": 2024, "end_year": 2026})
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert body["task_id"] == "host"
            assert calls.get(("POST", "/ml-gbm")) == {"start_year": 2024, "end_year": 2026}
            # 状态接口透传宿主, success 字段补全
            s = client.get("/api/ml/gbm/train/status/host")
            assert s.status_code == 200
            assert s.json()["success"] is True
            assert s.json()["status"] == "done"
            assert s.json()["result"]["rankic"]["mean_ic"] == 0.1
        finally:
            api._host_call = original

    def test_gbm_train_bad_window(self, client):
        """非法训练窗口在容器侧即拒绝 (不依赖宿主)。"""
        resp = client.post("/api/ml/gbm/train", json={"start_year": 2030, "end_year": 2020})
        assert resp.status_code == 200
        assert resp.json()["success"] is False
        resp2 = client.post("/api/ml/gbm/train", json={"start_year": 2020, "end_year": 2035})
        assert resp2.status_code == 200
        assert resp2.json()["success"] is False


def test_methodology_endpoint_shape(client):
    """方法论页: 四个分区齐全, 每个算法都带"局限"字段(页面不能只写优点)。"""
    resp = client.get("/api/methodology")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["updated_at"]
    assert "不是投资建议" in data["disclaimer"]  # 页面必须自带"不是投资建议"声明
    ids = [s["id"] for s in data["sections"]]
    assert ids == ["scan", "backtest", "ml", "universe"]
    for section in data["sections"]:
        assert section["title"] and section["summary"]
        assert section["items"], f"{section['id']} 至少要有一条算法说明"
        for item in section["items"]:
            for key in ("name", "what", "how", "limits"):
                assert item[key], f"{section['id']}/{item.get('name')} 缺 {key}"

"""公网 Demo 算力护栏测试。

覆盖 DEMO_READONLY=1 下的三类行为: 禁用后台重计算入口、禁止强制刷新(refresh)、
以及对耗时接口的按 IP 滑动窗口限流。非演示模式必须完全放行(本地部署不受影响)。
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.web import api


def _make_request(ip: str = "203.0.113.7") -> Request:
    """构造带 X-Forwarded-For 的请求对象(模拟 Render 反代后的来源 IP)。"""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/scan",
            "headers": [(b"x-forwarded-for", ip.encode())],
            "client": (ip, 1234),
        }
    )


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def demo(monkeypatch):
    """开启演示模式并清空限流计数, 用例结束后恢复。"""
    monkeypatch.setenv("DEMO_READONLY", "1")
    api._demo_hits.clear()
    yield
    api._demo_hits.clear()


class TestDemoGuardOff:
    def test_noop_when_disabled(self, monkeypatch):
        monkeypatch.delenv("DEMO_READONLY", raising=False)
        api._demo_protect(_make_request(), "optimize")
        api._demo_protect(_make_request(), "scan", refresh=True)


class TestDemoGuardOn:
    def test_blocks_optimize(self, demo, client):
        r = client.post("/api/optimize", json={"strategy": "momentum"})
        assert r.status_code == 403
        assert r.json()["detail"]["disabled"] is True

    def test_blocks_gbm_train(self, demo, client):
        r = client.post("/api/ml/gbm/train", json={})
        assert r.status_code == 403

    def test_blocks_asset_refresh(self, demo, client):
        r = client.post("/api/asset/refresh")
        assert r.status_code == 403

    def test_blocks_scan_refresh(self, demo, client):
        r = client.post("/api/scan", json={"refresh": True})
        assert r.status_code == 403

    def test_blocks_cached_endpoint_refresh(self, demo, client):
        for path in ("/api/sector?refresh=true", "/api/market-timing?refresh=true", "/api/ml/anomaly?refresh=true"):
            assert client.get(path).status_code == 403

    def test_rate_limit_per_action(self, demo):
        req = _make_request()
        for _ in range(6):  # scan 每分钟 6 次
            api._demo_protect(req, "scan")
        with pytest.raises(HTTPException) as exc:
            api._demo_protect(req, "scan")
        assert exc.value.status_code == 429

    def test_rate_limit_is_per_client(self, demo):
        for _ in range(6):
            api._demo_protect(_make_request("198.51.100.1"), "scan")
        # 另一个来源 IP 不受影响
        api._demo_protect(_make_request("198.51.100.2"), "scan")


class TestEnabledFlags:
    """前端靠 /api/enabled 决定是否显示"演示环境"横幅, 标志必须真实反映环境变量。"""

    def test_demo_flag_on(self, client, demo):
        assert client.get("/api/enabled").json()["demo"] is True

    def test_demo_flag_off(self, client, monkeypatch):
        monkeypatch.delenv("DEMO_READONLY", raising=False)
        assert client.get("/api/enabled").json()["demo"] is False

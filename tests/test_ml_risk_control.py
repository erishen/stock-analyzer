"""
Tests for GARCH volatility-based position sizing (strategy.risk_control).
GARCH 波动率仓位管理测试
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("arch")

from strategy.risk_control import PositionSizer, garch_volatility_sizing_report


def _simulate_returns(n=300, seed=5) -> pd.Series:
    """带波动率聚类的合成日收益。"""
    rng = np.random.default_rng(seed)
    sigma2 = np.zeros(n)
    eps = np.zeros(n)
    omega, alpha, beta = 0.00001, 0.1, 0.85
    sigma2[0] = omega / (1 - alpha - beta)
    for t in range(1, n):
        eps[t - 1] = np.sqrt(sigma2[t - 1]) * rng.standard_normal()
        sigma2[t] = omega + alpha * eps[t - 1] ** 2 + beta * sigma2[t - 1]
    eps[-1] = np.sqrt(sigma2[-1]) * rng.standard_normal()
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.Series(eps, index=idx, name="log_return")


@pytest.fixture
def mock_returns(monkeypatch):
    """monkeypatch ml.volatility.load_stock_returns 避免访问真实数据库。"""
    from ml import volatility as vol

    def _fake(code, window=300, db_path=None):
        return _simulate_returns()

    monkeypatch.setattr(vol, "load_stock_returns", _fake)


def test_sizing_report(mock_returns):
    """报告含每只股票的 GARCH 波动率与归一化建议权重。"""
    weights = {"600000": 0.3, "600519": 0.3, "000001": 0.4}
    report = garch_volatility_sizing_report(weights, target_volatility=0.15, horizon=5, window=300)
    details = report["details"]
    assert len(details) == 3
    for d in details:
        assert d["code"] in weights
        assert 0 < d["forecast_vol_pct"] < 20
        assert 0 < d["annualized_vol_pct"] < 100
        assert d["suggested_weight"] > 0
        assert "error" not in d
    # 归一化: 建议权重之和 ≈ 1
    assert abs(sum(d["suggested_weight"] for d in details) - 1.0) < 0.01


def test_position_sizer_targeting(mock_returns):
    """PositionSizer.garch_volatility_targeting 尊重单票上限且不超配。"""
    weights = {"600000": 0.2, "600519": 0.2, "000001": 0.2, "000002": 0.2, "000003": 0.2}
    sizer = PositionSizer()
    out = sizer.garch_volatility_targeting(weights, target_volatility=0.15, horizon=5, window=300)
    assert set(out) == set(weights)
    # 不超配(可保留现金), 且单票不超过上限
    assert sum(out.values()) <= 1.0 + 1e-6
    assert all(0 < v <= sizer.position_limit.max_single_position_pct + 1e-6 for v in out.values())

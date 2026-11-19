"""
Tests for ml.volatility GARCH model.
ml.volatility GARCH 波动率模型测试
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("arch")

from ml.volatility import GARCHVolatility


def _simulate_garch(n=800, omega=0.00001, alpha=0.1, beta=0.85, seed=123) -> pd.Series:
    """模拟 GARCH(1,1) 收益序列（含波动率聚类）。"""
    rng = np.random.default_rng(seed)
    sigma2 = np.zeros(n)
    eps = np.zeros(n)
    sigma2[0] = omega / (1 - alpha - beta)
    for t in range(1, n):
        eps[t - 1] = np.sqrt(sigma2[t - 1]) * rng.standard_normal()
        sigma2[t] = omega + alpha * eps[t - 1] ** 2 + beta * sigma2[t - 1]
    eps[-1] = np.sqrt(sigma2[-1]) * rng.standard_normal()
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.Series(eps, index=idx, name="log_return")


def test_fit_and_forecast():
    ret = _simulate_garch()
    model = GARCHVolatility(horizon=5)
    model.fit(ret)
    s = model.summary(ret)

    # 参数在合理范围
    assert 0.0 < s["params"]["alpha"] < 1.0
    assert 0.0 < s["params"]["beta"] < 1.0
    assert 0.0 < s["params"]["persistence"] < 1.0
    # 波动率输出为正且量级合理
    assert 0.0 < s["current_conditional_vol_pct"] < 20.0
    assert 0.0 < s["forecast_vol_pct"] < 20.0
    assert 0.0 < s["annualized_vol_pct"] < 100.0
    # 已实现波动率有值
    assert np.isfinite(s["realized_vol_30d_pct"])


def test_fit_high_persistence():
    """高持续性数据应恢复出较高的 alpha+beta。"""
    ret = _simulate_garch(alpha=0.15, beta=0.82)
    model = GARCHVolatility()
    model.fit(ret)
    assert model._params()["persistence"] > 0.7

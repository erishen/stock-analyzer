"""
Tests for ml.anomaly Isolation Forest detector.
ml.anomaly Isolation Forest 异常检测测试
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from ml.anomaly import IsolationForestDetector
from ml.common import ANOMALY_FEATURES


def _make_cross_section(n=400) -> pd.DataFrame:
    """合成横截面: 大部分正常, 少量极端离群（异常）。"""
    rng = np.random.default_rng(42)
    rows = []
    for i in range(n):
        rows.append(
            {
                "code": f"60{i:04d}",
                "name": f"股票{i}",
                "date": "2024-06-03",
                "change_percent": float(rng.normal(0, 2)),
                "amplitude": float(abs(rng.normal(2, 1))),
                "turnover_rate": float(abs(rng.normal(3, 2))),
                "volume": float(rng.uniform(1e5, 1e6)),
                "amount": float(rng.uniform(1e6, 1e7)),
                "rsi": float(rng.uniform(20, 80)),
                "macd_hist": float(rng.normal(0, 0.1)),
                "kdj_j": float(rng.uniform(0, 100)),
                "williams_r": float(rng.uniform(-100, 0)),
                "boll_position": float(rng.uniform(0, 1)),
                "boll_width": float(rng.uniform(0.02, 0.2)),
                "atr_ratio": float(rng.uniform(0.01, 0.06)),
                "volatility_20d": float(rng.uniform(0.01, 0.05)),
            }
        )
    df = pd.DataFrame(rows)
    # 注入 20 只极端异常股
    df.loc[:19, "change_percent"] = 20.0
    df.loc[:19, "turnover_rate"] = 50.0
    df.loc[:19, "amplitude"] = 15.0
    df.loc[:19, "boll_width"] = 0.9
    return df


def test_detect_flags_anomalies():
    df = _make_cross_section()
    detector = IsolationForestDetector(contamination=0.05)
    result = detector.detect(df)
    n_anom = int((result["label"] == -1).sum())
    assert n_anom > 0
    # 异常股应主要来自注入的极端组
    flagged = set(result[result["label"] == -1]["code"])
    injected = set(df.head(20)["code"])
    assert flagged & injected, "极端离群股应被判为异常"


def test_feature_matrix_shape():
    df = _make_cross_section(n=50)
    detector = IsolationForestDetector()
    x = detector._feature_matrix(df)
    assert x.shape == (50, len(ANOMALY_FEATURES))
    assert np.isfinite(x).all()

"""
Tests for ml.clustering K-Means clusterer.
ml.clustering K-Means 聚类测试
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from ml.clustering import KMeansClusterer


def _make_cross_section(n=300) -> pd.DataFrame:
    """合成横截面: 三个风格簇(低波动/高动量/高波动)。"""
    rng = np.random.default_rng(7)
    rows = []
    for i in range(n):
        style = i % 3
        if style == 0:  # 低波动价值
            change, vol, mom = rng.normal(0.1, 0.5), 0.01, 0.02
        elif style == 1:  # 高动量
            change, vol, mom = rng.normal(2.5, 0.8), 0.03, 0.15
        else:  # 高波动
            change, vol, mom = rng.normal(-1.5, 3.0), 0.08, -0.05
        rows.append(
            {
                "code": f"60{i:04d}",
                "name": f"股票{i}",
                "date": "2024-06-03",
                "change_percent": float(change),
                "amplitude": float(abs(vol * 100)),
                "turnover_rate": float(abs(rng.normal(3, 1))),
                "rsi": float(rng.uniform(20, 80)),
                "macd_hist": float(rng.normal(0, 0.1)),
                "kdj_k": float(rng.uniform(0, 100)),
                "williams_r": float(rng.uniform(-100, 0)),
                "momentum_10d": float(mom),
                "momentum_20d": float(mom),
                "volatility_10d": float(vol),
                "volatility_20d": float(vol),
                "boll_position": float(rng.uniform(0, 1)),
                "boll_width": float(vol * 5),
                "atr_ratio": float(vol),
                "close_ma5_ratio": float(1 + mom / 10),
                "close_ma20_ratio": float(1 + mom / 20),
                "close_ma60_ratio": float(1 + mom / 30),
            }
        )
    return pd.DataFrame(rows)


def test_cluster_recover_styles():
    df = _make_cross_section()
    clusterer = KMeansClusterer(n_clusters=3, random_state=42)
    labels = clusterer.fit_predict(df)
    assert len(set(labels)) == 3
    desc = clusterer.describe(df, labels)
    assert len(desc) == 3
    for c in desc:
        assert c["size"] > 0
        assert "profile_zscore" in c
        assert "top_stocks" in c
    # 规模占比合理
    assert sum(c["share_pct"] for c in desc) > 90


def test_auto_k_picks_within_range():
    df = _make_cross_section()
    clusterer = KMeansClusterer(n_clusters=3)
    best_k, sil = clusterer.pick_k_by_silhouette(df, k_range=range(3, 6))
    assert 3 <= best_k <= 5
    assert sil > -1.0  # 有轮廓系数

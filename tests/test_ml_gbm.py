"""
Tests for ml.gbm_rank LightGBM rank model.
ml.gbm_rank LightGBM 排名模型测试
"""

import numpy as np
import pandas as pd
import pytest

from ml.common import add_cross_sectional_ranks, add_target_rank, compute_forward_return
from ml.gbm_rank import GBMRankModel, backtest_topn, equal_weight_baseline

lgb = pytest.importorskip("lightgbm")


def _make_train_panel(n_stocks=30, n_days=120, horizon=5) -> pd.DataFrame:
    """合成面板: 特征与未来收益相关, 用于训练/预测冒烟测试。"""
    rows = []
    dates = pd.date_range("2023-01-01", periods=n_days, freq="B").strftime("%Y-%m-%d")
    for s in range(n_stocks):
        # 每股有一个固定特征信号, close 按信号随机游走
        signal = float(s) / n_stocks
        close = 10.0
        for d in dates:
            close *= 1 + (signal - 0.5) * 0.01
            rows.append(
                {
                    "code": f"60{s:04d}",
                    "date": d,
                    "close": close,
                    "change_percent": signal * 100,
                    "rsi": 30 + signal * 40,
                    "macd_hist": signal,
                    "volatility_20d": 0.02,
                }
            )
    df = pd.DataFrame(rows)
    df = compute_forward_return(df, horizon)
    return df


class TestBacktestTopN:
    def test_ml_beats_ranked(self):
        """Top-N 选高 pred 应该跑赢选低 pred（合成数据单调）。"""
        rng = np.random.default_rng(0)
        dates = [f"2024-01-{d:02d}" for d in range(1, 11)]
        rows = []
        for d in dates:
            for i in range(50):
                pred = float(i)
                fwd = pred * 0.01 + float(rng.normal(0, 0.001))
                rows.append({"date": d, "code": f"{i:06d}", "pred": pred, "fwd": fwd})
        test = pd.DataFrame(rows)
        cap_hi, _ = backtest_topn(test, dates, top_n=5)
        _cap_lo, _ = backtest_topn(test, dates, top_n=5, seed=1)
        assert cap_hi > 0


class TestGBMRankModel:
    def test_fit_predict(self):
        """训练 + 预测 + 特征重要性冒烟测试。"""
        df = _make_train_panel()
        feats = ["close", "change_percent", "rsi", "macd_hist", "volatility_20d"]
        df = add_cross_sectional_ranks(df, feats)
        df = add_target_rank(df)

        cut = "2023-04-15"
        train = df[df["date"] <= cut].dropna(subset=["target"])
        valid = df[df["date"] > cut].dropna(subset=["target"])
        assert len(train) > 50 and len(valid) > 50

        model = GBMRankModel(
            features=feats,
            horizon=5,
            params={
                "objective": "regression",
                "metric": "None",
                "learning_rate": 0.1,
                "num_leaves": 7,
                "min_data_in_leaf": 20,
                "feature_fraction": 1.0,
                "bagging_fraction": 1.0,
                "bagging_freq": 1,
                "lambda_l2": 1.0,
                "num_threads": 1,
                "verbosity": -1,
            },
        )
        model.fit(train, valid)
        assert model.best_iteration >= 1

        preds = model.predict(valid)
        assert len(preds) == len(valid)
        assert np.isfinite(preds).all()

        imp = model.feature_importance()
        assert len(imp) == len(feats)
        assert sum(w for _, w in imp) > 0

    def test_predict_before_fit_raises(self):
        model = GBMRankModel()
        with pytest.raises(RuntimeError):
            model.predict(pd.DataFrame({"close": [1.0]}))


class TestEqualWeightBaseline:
    def test_baseline(self):
        dates = ["2024-01-01", "2024-01-02"]
        rows = [{"date": d, "code": c, "fwd": 0.01, "pred": 1.0} for d in dates for c in ["1", "2", "3", "4", "5"]]
        test = pd.DataFrame(rows)
        stats = equal_weight_baseline(test, dates)
        assert stats["final_capital"] > 100_000

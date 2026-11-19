"""
Tests for ml.common shared utilities.
ml.common 公共工具测试
"""

import numpy as np
import pandas as pd
import pytest

from ml.common import (
    add_cross_sectional_ranks,
    add_target_rank,
    compute_forward_return,
    daily_rankic,
    filter_universe,
    is_st,
)


def _make_panel(n_stocks=5, n_days=8) -> pd.DataFrame:
    """构造合成面板: n_stocks 只 x n_days 个交易日。"""
    rows = []
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B").strftime("%Y-%m-%d")
    for s, code in enumerate([f"60{i:04d}" for i in range(n_stocks)]):
        close = 10.0 + s
        for d in dates:
            close *= 1 + 0.01 * ((s + 1) % 3)
            rows.append({"code": code, "date": d, "close": close, "rsi": 50 + s, "macd_hist": s * 0.1})
    return pd.DataFrame(rows)


def test_is_st():
    assert is_st("*ST海投")
    assert is_st("ST板块")
    assert is_st("退市美尚")
    assert not is_st("浦发银行")


def test_compute_forward_return():
    df = _make_panel(n_stocks=3, n_days=8)
    out = compute_forward_return(df, horizon=2)
    # 尾部 horizon 行为 NaN
    last_two = out.groupby("code")["fwd"].apply(lambda s: s.tail(2).isna().all())
    assert last_two.all()
    # 中间行有值且非零
    mid = out[out["fwd"].notna()]["fwd"]
    assert len(mid) > 0


def test_add_cross_sectional_ranks():
    df = _make_panel(n_stocks=5, n_days=4)
    out = add_cross_sectional_ranks(df, ["rsi", "macd_hist"])
    assert "rsi" in out.columns
    # 每个日期内 rsi 排名在 (0,1]
    for _, g in out.groupby("date"):
        assert g["rsi"].between(0, 1, inclusive="both").all()


def test_add_target_rank():
    df = _make_panel(n_stocks=5, n_days=6)
    df = compute_forward_return(df, horizon=2)
    out = add_target_rank(df)
    non_null = out["target"].notna().sum()
    assert non_null > 0
    # fwd 为 NaN 的行 target 亦为 NaN；非空 target 在 (0,1]
    assert out.loc[out["fwd"].isna(), "target"].isna().all()
    assert out["target"].dropna().between(0, 1, inclusive="both").all()


def test_daily_rankic_perfect():
    """pred 与 fwd 完全单调 -> 每日 IC=1。"""
    rows = []
    for d in ["2024-01-01", "2024-01-02"]:
        for i in range(40):
            rows.append({"date": d, "pred": float(i), "fwd": float(i * 2)})
    df = pd.DataFrame(rows)
    ic = daily_rankic(df).dropna()
    assert len(ic) == 2
    assert np.allclose(ic.values, 1.0, atol=1e-6)


def test_daily_rankic_needs_min_samples():
    """样本 < 30 的当日返回 NaN。"""
    rows = [{"date": "2024-01-01", "pred": float(i), "fwd": float(i)} for i in range(10)]
    ic = daily_rankic(pd.DataFrame(rows)).dropna()
    assert len(ic) == 0


def test_filter_universe(monkeypatch):
    """ST 与低价过滤（monkeypatch 名称缓存避免读真实 data/）。"""
    df = _make_panel(n_stocks=5, n_days=3)
    # codes[0] 将被 ST 过滤; codes[1] 低价(<2) 过滤; 其余正常
    # 行按 code 分组(每股 n_days 行), 用 np.repeat 对齐每股价格
    df["close"] = np.repeat([3.0, 1.5, 8.0, 20.0, 50.0], 3)
    codes = df["code"].unique().tolist()
    name_map = {codes[0]: "ST板块", codes[1]: "低价股", codes[2]: "正常A", codes[3]: "正常B", codes[4]: "正常C"}
    monkeypatch.setattr("ml.common.load_names", lambda: name_map)
    out = filter_universe(df, min_price=2.0)
    kept = set(out["code"].unique())
    assert codes[0] not in kept  # ST 被过滤
    assert codes[1] not in kept  # 低价被过滤
    assert set(codes[2:]) == kept


def test_import_ml_helper_raises():
    """require_ml 对未知包给出可读错误。"""
    from ml.common import require_ml

    with pytest.raises(RuntimeError):
        require_ml("does_not_exist_pkg")

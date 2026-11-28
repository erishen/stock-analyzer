"""滚动样本外验证 (walk-forward) 的口径与统计测试。

模型用桩模型（predict = 特征线性组合），不依赖 lightgbm，测试只验证:
  1) 窗口切分与 embargo 不越界；
  2) IC 汇总 / bootstrap p 值的统计口径与可复现性；
  3) walk_forward 在这些窗口上真的按期产出 IC，且跳过逻辑正确。
"""

import numpy as np
import pandas as pd
import pytest

from src.ml.common import GBM_FEATURES
from src.ml.walk_forward import (
    WalkForwardConfig,
    aggregate_ic,
    bootstrap_ic,
    build_periods,
    walk_forward,
)


def _dates(n: int) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2020-01-01", periods=n)]


class TestBuildPeriods:
    def test_no_period_before_warmup(self):
        dates = _dates(200)
        cfg = WalkForwardConfig(train_days=100, embargo=20, step=20)
        periods = build_periods(dates, cfg)
        assert periods, "应有可用期"
        assert periods[0]["signal_day"] == dates[120]

    def test_embargo_is_respected(self):
        dates = _dates(300)
        cfg = WalkForwardConfig(train_days=100, embargo=20, step=20)
        idx = {d: i for i, d in enumerate(dates)}
        for p in build_periods(dates, cfg):
            gap = idx[p["signal_day"]] - idx[p["train_end"]]
            assert gap == 20, f"train_end 与 signal_day 之间应正好留 20 个交易日, 实际 {gap}"

    def test_valid_window_inside_train_window(self):
        dates = _dates(300)
        cfg = WalkForwardConfig(train_days=150, valid_days=40, embargo=20, step=20)
        idx = {d: i for i, d in enumerate(dates)}
        for p in build_periods(dates, cfg):
            assert idx[p["valid_start"]] <= idx[p["valid_end"]] == idx[p["train_end"]]
            assert idx[p["valid_start"]] >= idx[p["train_start"]]

    def test_max_periods_keeps_tail(self):
        dates = _dates(300)
        cfg = WalkForwardConfig(train_days=100, embargo=20, step=20, max_periods=3)
        periods = build_periods(dates, cfg)
        assert len(periods) == 3
        # 300 天 / warmup 120 / step 20 → 按期落在 120,140,...,280
        assert periods[-1]["signal_day"] == dates[280]


class TestAggregateIc:
    def test_basic_stats(self):
        stats = aggregate_ic([0.2, 0.1, -0.05, 0.3])
        assert stats["n_periods"] == 4
        assert stats["mean"] == pytest.approx(0.1375, abs=1e-4)
        assert stats["positive_rate"] == pytest.approx(0.75)
        assert stats["icir"] > 0

    def test_all_negative_gives_zero_positive_rate(self):
        stats = aggregate_ic([-0.1, -0.2, -0.3])
        assert stats["positive_rate"] == 0.0
        assert stats["t_stat"] < 0

    def test_empty_and_nan(self):
        assert aggregate_ic([])["n_periods"] == 0
        assert aggregate_ic([float("nan")])["n_periods"] == 0

    def test_single_period_has_no_icir(self):
        stats = aggregate_ic([0.3])
        assert stats["icir"] is None


class TestBootstrapIc:
    def test_deterministic_with_seed(self):
        ics = [0.1, 0.2, -0.05, 0.15, 0.25, 0.05]
        a = bootstrap_ic(ics, n_boot=200, seed=42)
        b = bootstrap_ic(ics, n_boot=200, seed=42)
        assert a == b

    def test_strongly_positive_ic_is_significant(self):
        ics = [0.25, 0.28, 0.22, 0.3, 0.26, 0.24, 0.27]
        res = bootstrap_ic(ics, n_boot=500, seed=7)
        assert res["ok"] is True
        assert res["p_le_zero"] < 0.05
        assert res["significant"] is True
        assert res["ci_low"] > 0

    def test_ic_centered_on_zero_is_not_significant(self):
        ics = [0.3, -0.28, 0.25, -0.32, 0.2, -0.22]
        res = bootstrap_ic(ics, n_boot=500, seed=7)
        assert res["p_le_zero"] > 0.05
        assert res["significant"] is False

    def test_needs_two_periods(self):
        assert bootstrap_ic([0.2])["ok"] is False


class _StubModel:
    """predict = 第一维特征（信号方向可人为控制），fits 只记录样本数。"""

    features = list(GBM_FEATURES)

    def __init__(self, sign: float = 1.0):
        self.sign = sign
        self.fitted = []

    def fit(self, train, valid):
        self.fitted.append(len(train))
        return self

    def predict(self, df):
        return df[self.features[0]].to_numpy() * self.sign


def _frame(n_days: int = 260, n_codes: int = 40, seed: int = 3) -> pd.DataFrame:
    """构造一个"特征与未来收益正相关"的玩具截面。"""
    rng = np.random.default_rng(seed)
    dates = _dates(n_days)
    codes = [f"{i:06d}" for i in range(n_codes)]
    rows = []
    for d in dates:
        skill = rng.normal(size=n_codes)
        for j, c in enumerate(codes):
            row = {"code": c, "date": d, "close": 10.0 + skill[j]}
            for f in GBM_FEATURES:
                row[f] = float(skill[j] + rng.normal(scale=0.1))
            row["fwd"] = 0.02 * skill[j] + rng.normal(scale=0.01)
            row["target"] = 0.0
            rows.append(row)
    df = pd.DataFrame(rows)
    df["target"] = df.groupby("date")["fwd"].rank(pct=True)
    return df


class TestWalkForwardLoop:
    cfg = WalkForwardConfig(step=20, train_days=120, valid_days=40, embargo=20, min_train_rows=100, n_boot=100)

    def test_produces_one_ic_per_period(self):
        df = _frame()
        report = walk_forward(df, self.cfg, model_factory=lambda: _StubModel())
        assert report["ok"] is True
        assert report["ic"]["n_periods"] >= 3
        assert report["ic"]["mean"] > 0, "特征与收益正相关时 IC 应为正"

    def test_backward_looking_model_gets_negative_ic(self):
        df = _frame()
        report = walk_forward(df, self.cfg, model_factory=lambda: _StubModel(sign=-1.0))
        assert report["ic"]["mean"] < 0

    def test_short_window_is_skipped_not_crashed(self):
        df = _frame(n_days=140)
        cfg = WalkForwardConfig(step=20, train_days=120, valid_days=40, embargo=20, min_train_rows=100)
        report = walk_forward(df, cfg, model_factory=lambda: _StubModel())
        # 只有 140 天、warmup=140 → 没有可用期
        assert report["ok"] is False
        assert "不足" in report.get("error", "") or "没有任何一期" in report.get("error", "")

    def test_periods_carry_window_and_counts(self):
        df = _frame()
        report = walk_forward(df, self.cfg, model_factory=lambda: _StubModel())
        first = report["periods"][0]
        assert first["n_train"] >= self.cfg.min_train_rows
        assert first["n_names"] == 40
        assert "~" in first["train_range"]

    def test_signal_day_without_horizon_is_explained(self):
        """数据末端的信号日缺少 horizon 个交易日后的收盘价, 应跳过并说明原因。"""
        df = _frame()
        tail = sorted(df["date"].unique())[-20:]
        df.loc[df["date"].isin(tail), ["fwd", "target"]] = np.nan
        report = walk_forward(df, self.cfg, model_factory=lambda: _StubModel())
        skipped = [p for p in report["periods"] if p.get("skipped")]
        assert skipped, "末端信号日应被跳过, 而不是产出 nan IC"
        assert any("超出数据末端" in p["reason"] for p in skipped)


def test_scan_funnel_and_backtest_methodology_fields():
    """漏斗/口径字段是"静默过滤"的可见化: 结构存在即可被前端和测试消费。"""
    from src.scanner.signals import ScanResult
    from src.web.schemas import ScanResponse

    result = ScanResult(
        scan_time="2026-11-28T15:00:00",
        total_stocks=5603,
        signals_found=1200,
        signals=[],
        summary={"金叉": 800},
        top_signals=[],
        diagnostics={"codes": 5603, "no_data": 3, "error": 0, "scanned": 5600, "with_signals": 1200},
    )
    assert result.to_dict()["diagnostics"]["scanned"] == 5600

    resp = ScanResponse(success=True, total_stocks=5603, funnel={"codes": 5603, "returned": 20})
    assert resp.to_dict()["funnel"]["returned"] == 20
    assert ScanResponse(success=True).to_dict()["funnel"] == {}

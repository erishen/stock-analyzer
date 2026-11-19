"""LightGBM 横截面排名模型（选股排序）。

方法论（与 scripts/ml_factor_mining.py 对齐，并提升为可复用模块）：
  - 样本: 每个股票日一条记录, 特征为技术指标(横截面排名归一化)
  - 目标: 未来 horizon 日收益的当日横截面排名(百分位) —— 关心选股排序而非点值
  - 切分: train/valid/test 完全样本外, 尾部各留 ~1 个月 embargo 防 20 日目标泄漏
  - 早停: 以 valid 集 RankIC 为目标(直接优化关心的指标)
  - 评估: 日度 RankIC(IC均值/ICIR/t值), 十分位组合单调性, Top-N 组合含费回测 vs 随机/等权

已知局限:
  - ST 过滤基于当前名称, 历史 ST 状态无法回溯
  - 中途退市股票按最后可得收盘价退出
  - 无滑点假设
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.common import (
    GBM_FEATURES,
    add_cross_sectional_ranks,
    add_target_rank,
    compute_forward_return,
    daily_rankic,
    filter_universe,
    load_analysis_data,
    report_path,
    require_ml,
    save_json_report,
)

# 默认切分（train/valid 尾部各留 ~1 个月 embargo，目标窗口不跨切分点）
DEFAULT_TRAIN_END = "2023-11-30"
DEFAULT_VALID_END = "2024-11-30"
DEFAULT_TEST_START = "2025-01-01"

DEFAULT_PARAMS: dict = {
    "objective": "regression",
    "metric": "None",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 2000,  # 金融噪声大，强正则
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "num_threads": 4,
    "verbosity": -1,
}


class GBMRankModel:
    """LightGBM 横截面排名模型封装。"""

    def __init__(
        self,
        features: list[str] | None = None,
        horizon: int = 20,
        params: dict | None = None,
    ):
        self.features = list(features or GBM_FEATURES)
        self.horizon = horizon
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.booster = None
        self.best_iteration = 0
        self.feature_names: list[str] = []

    def _make_ic_feval(self, valid_dates: np.ndarray, valid_fwd: np.ndarray):
        """LightGBM 自定义评估: 以 valid 集日度 RankIC 为早停指标。"""

        def feval(preds: np.ndarray, _dataset) -> tuple[str, float, bool]:
            v = pd.DataFrame({"p": preds, "f": valid_fwd, "d": valid_dates})
            v["pr"] = v.groupby("d")["p"].rank()
            v["fr"] = v.groupby("d")["f"].rank()
            ic = (
                v.groupby("d")
                .apply(
                    lambda g: g["pr"].corr(g["fr"]) if len(g) >= 30 else np.nan,
                    include_groups=False,
                )
                .mean()
            )
            return "rankic", float(ic), True

        return feval

    def fit(self, train: pd.DataFrame, valid: pd.DataFrame) -> GBMRankModel:
        """训练模型，以 valid 集 RankIC 早停。train/valid 需含 features + target。"""
        lgb = require_ml("lightgbm")
        dtrain = lgb.Dataset(train[self.features], train["target"], feature_name=self.features)
        dvalid = lgb.Dataset(valid[self.features], valid["target"], reference=dtrain, free_raw_data=False)
        self.booster = lgb.train(
            self.params,
            dtrain,
            num_boost_round=1000,
            valid_sets=[dvalid],
            feval=self._make_ic_feval(valid["date"].values, valid["fwd"].values),
            callbacks=[lgb.early_stopping(80, verbose=False), lgb.log_evaluation(50)],
        )
        self.best_iteration = int(self.booster.best_iteration)
        self.feature_names = list(self.features)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """对给定特征 DataFrame 输出排名分（越高越看好）。"""
        if self.booster is None:
            raise RuntimeError("模型未训练，请先调用 fit()")
        return self.booster.predict(df[self.features], num_iteration=self.best_iteration)

    def feature_importance(self, importance_type: str = "gain") -> list[tuple[str, float]]:
        """特征重要性（默认按 gain）。"""
        if self.booster is None:
            return []
        imp = self.booster.feature_importance(importance_type=importance_type)
        ranked = sorted(
            ({f: float(g) for f, g in zip(self.features, imp, strict=False)}).items(),
            key=lambda x: -x[1],
        )
        return ranked


def backtest_topn(
    test: pd.DataFrame,
    rebalance_dates: list[str],
    top_n: int = 10,
    initial_capital: float = 100_000.0,
    comm_rate: float = 0.0003,
    stamp_rate: float = 0.001,
    min_comm: float = 5.0,
    seed: int | None = None,
) -> tuple[float, dict]:
    """每 horizon 个交易日调仓，选预测 Top-N（或随机 N）等权持有，含费。

    seed 非 None 时为随机基线。返回 (终期权益, 统计)。
    """
    rng = np.random.default_rng(seed) if seed is not None else None
    capital = initial_capital
    period_rets: list[float] = []
    n_periods = 0

    for i, t in enumerate(rebalance_dates):
        day = test[test["date"] == t].dropna(subset=["fwd"])
        if len(day) < top_n:
            continue
        if rng is not None:
            picked = day.sample(n=top_n, random_state=seed + i)["code"].tolist()
        else:
            picked = day.nlargest(top_n, "pred")["code"].tolist()

        start_capital = capital
        pos_value = capital / len(picked)
        gross, costs = 0.0, 0.0
        for c in picked:
            r = float(day.loc[day["code"] == c, "fwd"].iloc[0])
            buy_cost = max(pos_value * comm_rate, min_comm)
            sell_amt = pos_value * (1 + r)
            sell_cost = max(sell_amt * comm_rate, min_comm) + sell_amt * stamp_rate
            gross += pos_value * (1 + r)
            costs += buy_cost + sell_cost
        capital = gross - costs
        period_rets.append(capital / start_capital - 1)
        n_periods += 1
        if capital <= 0:
            break

    stats = {
        "periods": n_periods,
        "final_capital": round(capital, 0),
        "total_return_pct": round((capital / initial_capital - 1) * 100, 1),
        "avg_period_return_pct": round(float(np.mean(period_rets)) * 100, 3) if period_rets else None,
    }
    return capital, stats


def equal_weight_baseline(
    test: pd.DataFrame,
    rebalance_dates: list[str],
    initial_capital: float = 100_000.0,
    comm_rate: float = 0.0003,
    stamp_rate: float = 0.001,
) -> dict:
    """全市场等权基线（费率近似，不含最低佣金——大分散下不适用）。"""
    capital = initial_capital
    cost_rate = comm_rate * 2 + stamp_rate
    for t in rebalance_dates:
        day = test[test["date"] == t].dropna(subset=["fwd"])
        if day.empty:
            continue
        capital *= 1 + float(day["fwd"].mean()) - cost_rate
    return {
        "final_capital": round(capital, 0),
        "total_return_pct": round((capital / initial_capital - 1) * 100, 1),
    }


def evaluate_deciles(test: pd.DataFrame, rebalance_dates: list[str]) -> dict:
    """十分位组合平均期收益%（D1=预测最差, D10=预测最好）。"""
    rows = []
    for t in rebalance_dates:
        day = test[test["date"] == t].dropna(subset=["fwd"]).copy()
        if len(day) < 100:
            continue
        day["decile"] = pd.qcut(day["pred"], 10, labels=False, duplicates="drop") + 1
        g = day.groupby("decile")["fwd"].mean()
        for d, r in g.items():
            rows.append({"date": t, "decile": int(d), "fwd": float(r)})
    if not rows:
        return {}
    dec = pd.DataFrame(rows)
    table = {f"D{int(d)}": round(v * 100, 3) for d, v in dec.groupby("decile")["fwd"].mean().items()}
    mono = all(table[f"D{i}"] <= table[f"D{j}"] for i, j in [(1, 5), (5, 10)] if f"D{i}" in table and f"D{j}" in table)
    return {"decile_mean_fwd_pct": table, "monotonic": bool(mono)}


def run_gbm(args, progress_callback=None) -> None:
    """CLI 入口：训练 LightGBM 排名模型并输出样本外评估报告。

    Args:
        args: argparse.Namespace (同 CLI ml-gbm 参数)
        progress_callback: 可选回调 (stage: str, done: int, total: int)，供 Web 后台任务上报阶段。
    """

    def _cb(stage: str, done: int = 0, total: int = 0):
        if progress_callback:
            with contextlib.suppress(Exception):
                progress_callback(stage, done, total)

    model = GBMRankModel(horizon=args.horizon, params={"num_threads": args.num_threads})
    feats = model.features

    _cb("加载数据")
    print(">>> 加载数据...", file=sys.stderr, flush=True)
    df = load_analysis_data(feats, args.start_year, args.end_year, args.db)
    df = compute_forward_return(df, args.horizon)
    _cb("特征工程")
    print(">>> 特征工程（ST/低价过滤 + 横截面排名归一化）...", file=sys.stderr, flush=True)
    df = filter_universe(df, args.min_price)
    df = add_cross_sectional_ranks(df, feats)
    df = add_target_rank(df)

    train_end = args.train_end or DEFAULT_TRAIN_END
    valid_end = args.valid_end or DEFAULT_VALID_END
    test_start = args.test_start or DEFAULT_TEST_START
    train = df[(df["date"] <= train_end) & df["target"].notna()]
    valid = df[(df["date"] > train_end) & (df["date"] <= valid_end) & df["target"].notna()]
    test = df[(df["date"] >= test_start) & df["fwd"].notna()].copy()
    if train.empty or valid.empty or test.empty:
        raise SystemExit(
            f"切分后有空集 (train {len(train)} / valid {len(valid)} / test {len(test)})。"
            f"请检查 --start-year/--end-year 与 --train-end/--valid-end/--test-start 是否覆盖数据范围"
            f"（--end-year 为不含上界；数据仅到 {df['date'].max()}）"
        )
    print(f"  切分: train {len(train):,} / valid {len(valid):,} / test {len(test):,}", file=sys.stderr, flush=True)

    _cb("训练")
    print(">>> 训练 LightGBM (早停指标: valid RankIC)...", file=sys.stderr, flush=True)
    model.fit(train, valid)

    _cb("评估")
    print(">>> 样本外评估...", file=sys.stderr, flush=True)
    test["pred"] = model.predict(test)
    ic = daily_rankic(test).dropna()
    ic_stats = {
        "mean_ic": round(float(ic.mean()), 4),
        "ic_std": round(float(ic.std()), 4),
        "icir": round(float(ic.mean() / ic.std()), 4),
        "t_stat": round(float(ic.mean() / ic.std() * np.sqrt(len(ic))), 2),
        "positive_rate": round(float((ic > 0).mean()), 4),
        "n_days": len(ic),
    }

    all_dates = sorted(test["date"].unique())
    rebalance = all_dates[:: args.horizon][:-1]
    _ml_capital, ml_stats = backtest_topn(test, rebalance, args.top_n)
    _rand_capital, rand_stats = backtest_topn(test, rebalance, args.top_n, seed=42)
    ew_stats = equal_weight_baseline(test, rebalance)
    decile = evaluate_deciles(test, rebalance)

    top_feats = model.feature_importance("gain")[:15]

    report = {
        "config": {
            "model": "lightgbm_rank",
            "horizon_days": args.horizon,
            "features": len(model.features),
            "train": f"{args.start_year}-01-01~{train_end}",
            "valid": f"2024-01-01~{valid_end}",
            "test": f"{test_start}~{args.end_year - 1}-12-31",
            "best_iteration": model.best_iteration,
            "top_n": args.top_n,
            "min_price": args.min_price,
        },
        "rankic": ic_stats,
        "decile": decile,
        "backtest": {
            "ml_topn": ml_stats,
            "random_n": rand_stats,
            "equal_weight": ew_stats,
        },
        "feature_importance_top15": top_feats,
        "limitations": [
            "ST过滤基于当前名称, 无法回溯历史ST状态",
            "中途退市股票按最后可得收盘价退出",
            "无滑点假设, 实盘Top-N组合冲击成本会更高",
        ],
    }
    out = report_path(args.output, "ml_gbm_report.json")
    save_json_report(report, out)
    _cb("完成")
    print(
        f"\nRankIC: {ic_stats['mean_ic']:+.4f} | ICIR {ic_stats['icir']:+.3f} "
        f"| t值 {ic_stats['t_stat']:+.1f} | 正率 {ic_stats['positive_rate']:.1%} ({ic_stats['n_days']}日)"
    )
    print(f"Top-{args.top_n} 含费回测: {ml_stats['total_return_pct']:+.1f}%")

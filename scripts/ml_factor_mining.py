"""v2.0 ML 因子挖掘: LightGBM 横截面排名模型

方法论:
  - 样本: 每个股票日一条记录, 特征为当日 51 个技术指标(横截面排名归一化, 消除量纲与市场状态影响)
  - 目标: 未来 20 日收益的当日横截面排名(百分位) — 我们关心的是选股排序而非点值预测
  - 切分: train 2020-01~2023-11 / valid 2024-01~2024-11 / test 2025-01~2026-08 (完全样本外)
    train/valid 尾部各留 ~1 个月 embargo, 防止 20 日目标跨越切分点造成泄漏
  - 早停: 以 valid 集 RankIC 为目标(直接优化我们关心的指标)
  - 评估: 日度 RankIC 序列(IC均值/ICIR/t值), 十分位组合单调性, Top-10 组合含费回测 vs 等权/随机基线

已知局限(诚实记录):
  - ST 过滤基于当前名称, 历史上 ST 状态变化无法回溯
  - 中途退市股票按最后可得收盘价退出(实际退市损失可能更大)
  - 无滑点假设
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import lightgbm as lgb

from config import get_stock_analysis_db_path

HORIZON = 20  # 预测 horizon = 持有期
TRAIN_END = "2023-11-30"  # embargo: 目标窗口不跨入 2024
VALID_END = "2024-11-30"  # embargo: 目标窗口不跨入 2025
TEST_START = "2025-01-01"
TOP_N = 10
INITIAL_CAPITAL = 100_000.0
COMM_RATE, STAMP_RATE, MIN_COMM = 0.0003, 0.001, 5.0

FEATURES = [
    "close",
    "change_percent",
    "amplitude",
    "turnover_rate",
    "volume",
    "amount",
    "rsi",
    "macd_hist",
    "kdj_k",
    "kdj_d",
    "kdj_j",
    "williams_r",
    "momentum_5d",
    "momentum_10d",
    "momentum_20d",
    "roc_10",
    "roc_20",
    "volatility_5d",
    "volatility_10d",
    "volatility_20d",
    "boll_position",
    "boll_width",
    "atr_ratio",
    "close_ma5_ratio",
    "close_ma10_ratio",
    "close_ma20_ratio",
    "close_ma60_ratio",
    "high_low_ratio",
    "upper_shadow",
    "lower_shadow",
    "body_size",
    "obv_signal",
]


def load_names() -> dict[str, str]:
    cache = PROJECT_ROOT / "data" / "stock_info_cache.json"
    names: dict[str, str] = {}
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        for k, v in raw.items():
            code = k[-6:]  # 兼容 sh600000 / 600000 两种键
            names.setdefault(code, v)
    return names


def is_st(name: str) -> bool:
    return "ST" in name.upper() or "退" in name


def load_data() -> pd.DataFrame:
    """分年加载 + 降内存 + 计算未来收益"""
    db = Path(get_stock_analysis_db_path())
    import sqlite3

    cols = ", ".join(["code", "date", *FEATURES])  # close 已在 FEATURES 中
    chunks = []
    with sqlite3.connect(str(db)) as conn:
        for y in range(2020, 2027):
            df = pd.read_sql_query(
                f"SELECT {cols} FROM stock_analysis WHERE date >= '{y}-01-01' AND date < '{y + 1}-01-01'",
                conn,
            )
            if df.empty:
                continue
            num_cols = list(dict.fromkeys(["close", *FEATURES]))
            df[num_cols] = df[num_cols].astype("float32")
            chunks.append(df)
            print(f"  加载 {y}: {len(df):,} 行", file=sys.stderr, flush=True)
    df = pd.concat(chunks, ignore_index=True)
    df.sort_values(["code", "date"], kind="stable", ignore_index=True, inplace=True)

    # 未来 HORIZON 期收益(按行数计, 与既有回测口径一致; 每股尾部为 NaN)
    df["fwd"] = (df.groupby("code")["close"].shift(-HORIZON) / df["close"] - 1).astype("float32")
    return df


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """ST/低价过滤 → 特征横截面排名归一化 → 目标=未来收益排名"""
    names = load_names()
    df["name"] = df["code"].map(names).fillna("")
    n0 = len(df)
    df = df[(~df["name"].map(is_st)) & (df["close"] >= 2.0)].copy()
    print(f"  ST/低价过滤: {n0:,} -> {len(df):,}", file=sys.stderr, flush=True)

    # 特征排名归一化(分两批, 控内存): 当日横截面内的百分位
    half = len(FEATURES) // 2
    for batch in (FEATURES[:half], FEATURES[half:]):
        df[batch] = df.groupby("date")[batch].rank(pct=True).astype("float32")

    # 目标: 未来收益的当日排名百分位(NaN 尾部在切分后剔除)
    df["target"] = df.groupby("date")["fwd"].rank(pct=True).astype("float32")
    return df


def daily_rankic(frame: pd.DataFrame) -> pd.Series:
    """按日计算 Spearman(pred, fwd) — 双重 rank 后的 Pearson 相关"""

    def _ic(g: pd.DataFrame) -> float:
        if len(g) < 30:
            return np.nan
        pr = g["pred"].rank()
        fr = g["fwd"].rank()
        if pr.std() == 0 or fr.std() == 0:
            return np.nan
        return float(np.corrcoef(pr, fr)[0, 1])

    return frame.groupby("date").apply(_ic, include_groups=False)


def make_ic_feval(valid_dates: np.ndarray, valid_fwd: np.ndarray):
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


def backtest_topn(
    test: pd.DataFrame, rebalance_dates: list[str], top_n: int = TOP_N, seed: int | None = None
) -> tuple[float, dict]:
    """每 HORIZON 个交易日调仓, 选预测 Top-N(或随机 N)等权持有, 含费。
    seed 非 None 时为随机基线。返回 (终期权益, 统计)。"""
    rng = np.random.default_rng(seed) if seed is not None else None
    capital = INITIAL_CAPITAL
    period_rets, n_periods = [], 0

    for i, t in enumerate(rebalance_dates):
        day = test[test["date"] == t].dropna(subset=["fwd"])
        if len(day) < top_n:
            continue
        if rng is not None:
            picked = day.sample(n=top_n, random_state=seed + i)["code"].tolist()
        else:
            picked = day.nlargest(top_n, "pred")["code"].tolist()

        # 等权分配资金, 按各自未来收益结算, 计入双边费用(佣金+卖出印花)
        start_capital = capital
        pos_value = capital / len(picked)
        gross, costs = 0.0, 0.0
        for c in picked:
            r = float(day.loc[day["code"] == c, "fwd"].iloc[0])
            buy_cost = max(pos_value * COMM_RATE, MIN_COMM)
            sell_amt = pos_value * (1 + r)
            sell_cost = max(sell_amt * COMM_RATE, MIN_COMM) + sell_amt * STAMP_RATE
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
        "total_return_pct": round((capital / INITIAL_CAPITAL - 1) * 100, 1),
        "avg_period_return_pct": round(float(np.mean(period_rets)) * 100, 3) if period_rets else None,
    }
    return capital, stats


def equal_weight_baseline(test: pd.DataFrame, rebalance_dates: list[str]) -> dict:
    """全市场等权(费率近似, 不含最低佣金 — 大分散下不适用)"""
    capital = INITIAL_CAPITAL
    cost_rate = COMM_RATE * 2 + STAMP_RATE  # 每期全额换手
    for t in rebalance_dates:
        day = test[test["date"] == t].dropna(subset=["fwd"])
        if day.empty:
            continue
        r = float(day["fwd"].mean())
        capital *= 1 + r - cost_rate
    return {
        "final_capital": round(capital, 0),
        "total_return_pct": round((capital / INITIAL_CAPITAL - 1) * 100, 1),
    }


def main() -> None:
    print(">>> 加载数据...", file=sys.stderr, flush=True)
    df = load_data()
    print(">>> 特征工程...", file=sys.stderr, flush=True)
    df = prepare(df)

    train = df[(df["date"] <= TRAIN_END) & df["target"].notna()]
    valid = df[(df["date"] > TRAIN_END) & (df["date"] <= VALID_END) & df["target"].notna()]
    test = df[(df["date"] >= TEST_START) & df["fwd"].notna()].copy()
    print(
        f"  切分: train {len(train):,} / valid {len(valid):,} / test {len(test):,}",
        file=sys.stderr,
        flush=True,
    )

    print(">>> 训练 LightGBM (早停指标: valid RankIC)...", file=sys.stderr, flush=True)
    dtrain = lgb.Dataset(train[FEATURES], train["target"], feature_name=FEATURES)
    dvalid = lgb.Dataset(valid[FEATURES], valid["target"], reference=dtrain, free_raw_data=False)
    params = {
        "objective": "regression",
        "metric": "None",
        "learning_rate": 0.05,
        "num_leaves": 63,
        "min_data_in_leaf": 2000,  # 金融噪声大, 强正则
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "lambda_l2": 1.0,
        "num_threads": 4,
        "verbosity": -1,
    }
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=1000,
        valid_sets=[dvalid],
        feval=make_ic_feval(valid["date"].values, valid["fwd"].values),
        callbacks=[lgb.early_stopping(80, verbose=True), lgb.log_evaluation(50)],
    )

    print(">>> 样本外评估 (2025-01 ~ 2026-08)...", file=sys.stderr, flush=True)
    test["pred"] = booster.predict(test[FEATURES], num_iteration=booster.best_iteration)
    ic = daily_rankic(test).dropna()

    # --- 组合回测: 每 HORIZON 个交易日调仓 ---
    all_dates = sorted(test["date"].unique())
    rebalance = all_dates[::HORIZON][:-1]  # 末段不足 HORIZON 天的丢弃
    ml_capital, ml_stats = backtest_topn(test, rebalance)
    _rand_capital, rand_stats = backtest_topn(test, rebalance, seed=42)
    ew_stats = equal_weight_baseline(test, rebalance)

    # --- 十分位分析 ---
    decile_rows = []
    for t in rebalance:
        day = test[test["date"] == t].dropna(subset=["fwd"]).copy()
        if len(day) < 100:
            continue
        day["decile"] = pd.qcut(day["pred"], 10, labels=False, duplicates="drop") + 1
        g = day.groupby("decile")["fwd"].mean()
        for d, r in g.items():
            decile_rows.append({"date": t, "decile": int(d), "fwd": float(r)})
    dec = pd.DataFrame(decile_rows)
    decile_table = {f"D{int(d)}": round(v * 100, 3) for d, v in dec.groupby("decile")["fwd"].mean().items()}

    # --- 特征重要性 ---
    imp = booster.feature_importance(importance_type="gain")
    top_feats = sorted(({f: float(g) for f, g in zip(FEATURES, imp, strict=False)}).items(), key=lambda x: -x[1])[:15]

    # --- 汇总输出 ---
    ic_stats = {
        "mean_ic": round(float(ic.mean()), 4),
        "ic_std": round(float(ic.std()), 4),
        "icir": round(float(ic.mean() / ic.std()), 4),
        "t_stat": round(float(ic.mean() / ic.std() * np.sqrt(len(ic))), 2),
        "positive_rate": round(float((ic > 0).mean()), 4),
        "n_days": len(ic),
    }

    print(f"\n{'=' * 60}")
    print(f"📊 ML 因子挖掘 · 样本外结果 (test {TEST_START} ~ 2026-08)")
    print(f"{'=' * 60}")
    print(
        f"RankIC: 均值 {ic_stats['mean_ic']:+.4f} | ICIR {ic_stats['icir']:+.3f} "
        f"| t值 {ic_stats['t_stat']:+.1f} | 正率 {ic_stats['positive_rate']:.1%} ({ic_stats['n_days']}日)"
    )
    print("\n十分位组合平均期收益% (D1=预测最差, D10=预测最好):")
    print("  " + "  ".join(f"{k}:{v:+.2f}" for k, v in decile_table.items()))
    mono = all(
        decile_table[f"D{i}"] <= decile_table[f"D{j}"]
        for i, j in [(1, 5), (5, 10)]
        if f"D{i}" in decile_table and f"D{j}" in decile_table
    )
    print(f"  单调性: {'D1<D5<D10 ✓' if mono else '不完全单调 ✗'}")
    print(f"\n组合回测 (Top-{TOP_N}, {len(rebalance)}期, 含费, 10万本金):")
    print(f"  ML Top-10 : {ml_stats['total_return_pct']:+.1f}%  (期末 {ml_capital:,.0f})")
    print(f"  随机 10 只: {rand_stats['total_return_pct']:+.1f}%")
    print(f"  全市场等权: {ew_stats['total_return_pct']:+.1f}%")
    print("\nTop-15 特征重要性(gain):")
    for f, g in top_feats:
        print(f"  {f:<20} {g:>10,.0f}")

    report = {
        "config": {
            "horizon_days": HORIZON,
            "features": len(FEATURES),
            "train": f"2020-01~{TRAIN_END}",
            "valid": f"2024-01~{VALID_END}",
            "test": f"{TEST_START}~2026-08",
            "best_iteration": booster.best_iteration,
        },
        "rankic": ic_stats,
        "decile_mean_fwd_pct": decile_table,
        "backtest": {
            "ml_top10": ml_stats,
            "random10": rand_stats,
            "equal_weight": ew_stats,
        },
        "feature_importance_top15": top_feats,
        "limitations": [
            "ST过滤基于当前名称, 无法回溯历史ST状态",
            "中途退市股票按最后可得收盘价退出",
            "无滑点假设, 实盘Top10组合冲击成本会更高",
        ],
    }
    out = PROJECT_ROOT / "output" / "reports" / "ml_factor_mining.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 已保存: {out}")


if __name__ == "__main__":
    main()

"""滚动样本外验证(walk-forward): 每 step 个交易日重训一次, 逐期算 RankIC。

为什么需要它: `gbm_rank.py` 是"训一次、测一段"的单一切分, 只能回答"这段测试期
灵不灵", 回答不了"换个年份还灵不灵"。滚动重训把样本外切成若干期, 每期都有独立的
IC, 才能看出稳定性——以及"平均 IC 是不是靠某一期撑着"。

口径(与 lume 原型对齐, 见 rhyc/stock-algo-lume 的 `walk_forward`):
  - 信号日 t 只用 <= t 的数据训练; 训练窗口末端与 t 之间留 ``embargo`` 个交易日,
    避免 20 日标签跨越切分点;
  - 训练窗口末尾切出 ``valid_days`` 做早停, 同样与 t 留出 embargo;
  - IC 只用未来收益做**评估**, 从不进入训练或权重;
  - bootstrap 固定种子, 单尾经验 p 值 (n₀+1)/(B+1), 可复现。

已知局限(写进报告): 期数少时检验功效很低; ST 用当前名称; 退市按最后收盘价退出。
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
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
    save_json_report,
)


@dataclass
class WalkForwardConfig:
    """滚动验证参数。"""

    horizon: int = 20  # 标签/持有天数
    step: int = 20  # 重训与调仓间隔(交易日)
    train_days: int = 750  # 训练窗口长度(交易日, ~3 年)
    valid_days: int = 120  # 训练窗口末尾的验证段(早停用)
    embargo: int = 20  # 训练末端与信号日之间留空
    top_n: int = 10
    min_train_rows: int = 5000
    n_boot: int = 500
    seed: int = 20261128
    max_periods: int | None = None


def build_periods(
    dates: list[str],
    config: WalkForwardConfig,
) -> list[dict]:
    """把交易日切成滚动期: 每期给出信号日 + 训练/验证窗口的日期边界。

    边界都按**交易日索引**计算(不是日历日), 保证窗口内样本数可控。
    """
    out: list[dict] = []
    warmup = config.train_days + config.embargo
    for k in range(warmup, len(dates), max(1, config.step)):
        signal_day = dates[k]
        train_end_idx = k - config.embargo
        train_start_idx = max(0, train_end_idx - config.train_days)
        valid_end_idx = train_end_idx
        valid_start_idx = max(train_start_idx + 1, valid_end_idx - config.valid_days)
        out.append(
            {
                "signal_day": signal_day,
                "train_start": dates[train_start_idx],
                "train_end": dates[train_end_idx],
                "valid_start": dates[valid_start_idx],
                "valid_end": dates[valid_end_idx],
            }
        )
    if config.max_periods:
        out = out[-config.max_periods :]
    return out


def aggregate_ic(ics: list[float]) -> dict:
    """IC 序列汇总: 均值/标准差/ICIR/正率/t 值。"""
    clean = [float(x) for x in ics if x is not None and np.isfinite(x)]
    n = len(clean)
    if n == 0:
        return {"n_periods": 0, "mean": None, "std": None, "icir": None, "positive_rate": None, "t_stat": None}
    arr = np.asarray(clean, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if n > 1 else 0.0
    return {
        "n_periods": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "icir": round(mean / std, 4) if std > 0 else None,
        "positive_rate": round(float((arr > 0).mean()), 4),
        "t_stat": round(mean / std * np.sqrt(n), 2) if std > 0 else None,
    }


def bootstrap_ic(ics: list[float], n_boot: int = 500, seed: int = 20261128) -> dict:
    """IC 均值的 bootstrap 置信区间与单尾 p 值。

    重采样只针对 IC 序列本身, 不回头改训练/权重。p 值用 (n₀+1)/(B+1),
    即"重采样后有 B 次均值 <= 0"的经验概率, 避免 p=0 的不可能性。
    """
    clean = [float(x) for x in ics if x is not None and np.isfinite(x)]
    n = len(clean)
    if n < 2:
        return {"ok": False, "error": "IC 期数不足 2, 无法做显著性检验"}
    rng = np.random.default_rng(seed)
    arr = np.asarray(clean, dtype=float)
    means = rng.choice(arr, size=(max(1, n_boot), n), replace=True).mean(axis=1)
    n_le_zero = int((means <= 0).sum())
    return {
        "ok": True,
        "n_periods": n,
        "n_boot": n_boot,
        "seed": seed,
        "ic_mean": round(float(arr.mean()), 4),
        "ci_low": round(float(np.percentile(means, 2.5)), 4),
        "ci_high": round(float(np.percentile(means, 97.5)), 4),
        "p_le_zero": round((n_le_zero + 1) / (n_boot + 1), 4),
        "significant": bool((n_le_zero + 1) / (n_boot + 1) < 0.05),
        "note": "置信区间只反映期数不确定性; 期数少时功效很低",
    }


def walk_forward(
    df: pd.DataFrame,
    config: WalkForwardConfig | None = None,
    model_factory=None,
    progress=None,
) -> dict:
    """在已构造好特征/标签的 DataFrame 上跑滚动样本外验证。

    Args:
        df: 含 code/date/close/features/fwd/target 的样本(由 prepare_samples 产出)
        config: 窗口参数
        model_factory: 返回未训练模型的可调用对象(默认 GBMRankModel);
            模型需提供 fit(train, valid) / predict(df), 便于测试注入桩模型
        progress: 可选回调 fn(stage, done, total)
    """
    config = config or WalkForwardConfig()
    dates = sorted(df["date"].unique())
    periods = build_periods(dates, config)
    if not periods:
        return {"ok": False, "error": "数据不足以形成任何一个滚动期"}

    if model_factory is None:
        from ml.gbm_rank import GBMRankModel

        model_factory = GBMRankModel

    rows: list[dict] = []
    ics: list[float] = []
    preds_frames: list[pd.DataFrame] = []

    for i, p in enumerate(periods):
        if progress:
            progress("train", i, len(periods))
        train = df[
            (df["date"] >= p["train_start"]) & (df["date"] <= p["train_end"]) & df["target"].notna()
        ]
        valid = df[
            (df["date"] >= p["valid_start"]) & (df["date"] <= p["valid_end"]) & df["target"].notna()
        ]
        signal = df[(df["date"] == p["signal_day"]) & df["fwd"].notna()].copy()
        if len(train) < config.min_train_rows or valid.empty or len(signal) < 30:
            if signal.empty:
                # 信号日的前向收益要等到 horizon 个交易日后才有收盘价, 数据末端之前无法评估
                reason = (
                    f"信号日 {p['signal_day']} 的前向收益需 {config.horizon} 个交易日后收盘价, "
                    f"超出数据末端 {df['date'].max()}"
                )
            else:
                reason = f"train={len(train)} valid={len(valid)} names={len(signal)}"
            rows.append({"signal_day": p["signal_day"], "skipped": True, "reason": reason})
            continue

        model = model_factory()
        model.fit(train, valid)
        signal["pred"] = model.predict(signal)

        ic_series = daily_rankic(signal).dropna()
        ic = float(ic_series.iloc[0]) if len(ic_series) else float("nan")
        if np.isfinite(ic):
            ics.append(ic)
        rows.append(
            {
                "signal_day": p["signal_day"],
                "train_range": f"{p['train_start']}~{p['train_end']}",
                "n_train": len(train),
                "n_names": len(signal),
                "ic": round(ic, 4) if np.isfinite(ic) else None,
            }
        )
        preds_frames.append(signal[["code", "date", "pred", "fwd", "close"]])

    if not ics:
        return {"ok": False, "error": "没有任何一期产出有效 IC", "periods": rows}

    # Top-N 含费回测复用同一批信号日的预测(与 gbm_rank 的口径一致)
    evaluation: dict = {}
    if preds_frames:
        from ml.gbm_rank import backtest_topn, equal_weight_baseline

        test = pd.concat(preds_frames, ignore_index=True)
        rebalance = sorted(test["date"].unique())
        _, ml_stats = backtest_topn(test, rebalance, config.top_n)
        _, rand_stats = backtest_topn(test, rebalance, config.top_n, seed=config.seed % 1000)
        evaluation = {
            "ml_topn": ml_stats,
            "random_n": rand_stats,
            "equal_weight": equal_weight_baseline(test, rebalance),
            "rebalance_days": len(rebalance),
        }

    ic_stats = aggregate_ic(ics)
    boot = bootstrap_ic(ics, config.n_boot, config.seed)

    return {
        "ok": True,
        "config": asdict(config),
        "periods": rows,
        "ic": ic_stats,
        "bootstrap": boot,
        "evaluation": evaluation,
        "limitations": [
            "期数少时显著性检验功效很低, 短窗口的「显著」未必能外推",
            "ST 过滤基于当前名称, 历史 ST 状态无法回溯",
            "退市股票按最后可得收盘价退出, 仍有幸存者偏差",
            "IC 量级偏高时先怀疑特征/口径与数据区间 regime, 单因子(如换手率)本就有 0.3 量级的截面相关性, 不等于可持续 alpha",
            f"训练窗口 {config.train_days} 个交易日、验证 {config.valid_days} 个、embargo {config.embargo} 个",
        ],
    }


def prepare_samples(
    start_year: int = 2020,
    end_year: int = 2027,
    horizon: int = 20,
    min_price: float = 2.0,
    db_path: str | None = None,
) -> pd.DataFrame:
    """加载分析库 → 未来收益标签 → 过滤 → 横截面排名 (与 gbm_rank 同一套预处理)。"""
    df = load_analysis_data(list(GBM_FEATURES), start_year, end_year, db_path)
    df = compute_forward_return(df, horizon)
    df = filter_universe(df, min_price)
    df = add_cross_sectional_ranks(df, list(GBM_FEATURES))
    df = add_target_rank(df)
    return df


def run_walk_forward(args, progress_callback=None) -> dict:
    """CLI 入口: 跑滚动验证并落盘报告。"""
    config = WalkForwardConfig(
        horizon=args.horizon,
        step=args.step,
        train_days=args.train_days,
        valid_days=args.valid_days,
        embargo=args.embargo,
        top_n=args.top_n,
        n_boot=args.boot,
        seed=args.seed,
        max_periods=getattr(args, "max_periods", None),
    )

    def _progress(stage: str, done: int = 0, total: int = 0):
        if progress_callback:
            progress_callback(stage, done, total)

    _progress("加载数据")
    df = prepare_samples(args.start_year, args.end_year, args.horizon, args.min_price, args.db)
    print(
        f"  样本: {len(df):,} 行 / {df['code'].nunique():,} 只 / {df['date'].min()}~{df['date'].max()}",
        file=sys.stderr,
        flush=True,
    )

    report = walk_forward(df, config, progress=_progress)
    report["generated_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    report["data"] = {
        "rows": len(df),
        "codes": df["code"].nunique(),
        "first_day": str(df["date"].min()),
        "last_day": str(df["date"].max()),
    }

    out = report_path(args.output, "ml_walkforward_report.json")
    save_json_report(report, out)
    _progress("完成")

    if report.get("ok"):
        ic = report["ic"]
        print(
            f"\n滚动样本外: {ic['n_periods']} 期 | IC 均值 {ic['mean']:+.4f} | ICIR {ic['icir']:+.2f} "
            f"| IC>0 占比 {ic['positive_rate']:.1%}"
        )
        b = report["bootstrap"]
        print(f"bootstrap: 95% CI [{b['ci_low']:+.3f}, {b['ci_high']:+.3f}] p={b['p_le_zero']:.3f}")
    else:
        print(f"\n滚动验证失败: {report.get('error')}")
    return report


__all__ = [
    "WalkForwardConfig",
    "aggregate_ic",
    "bootstrap_ic",
    "build_periods",
    "prepare_samples",
    "run_walk_forward",
    "walk_forward",
]

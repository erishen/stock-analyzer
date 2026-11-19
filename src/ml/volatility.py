"""GARCH(1,1) 波动率建模：单股条件波动率估计与预测。

方法:
  - 输入: 单股日对数收益序列(从 stock_analysis.db 加载, 可选窗口截取)
  - 模型: arch.arch_model(returns*100, vol='GARCH', p=1, q=1) —— 乘 100 改善数值稳定性
  - 输出: 模型参数(omega/alpha/beta, 持续性 alpha+beta)、当前条件波动率、
          未来 horizon 日波动率预测、年化波动率, 并与 30 日已实现波动率对比

用途: 波动率聚类与均值回归是 A 股定价的重要特征; GARCH 条件波动率可辅助仓位管理
      (如高波动降仓) 与波动率择时, 也可为后续风险模型提供输入。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_stock_analysis_db_path
from ml.common import project_root, report_path, require_ml, resolve_stock_code, save_json_report

TRADING_DAYS = 252


def load_stock_returns(code: str, window: int = 500, db_path: str | None = None) -> pd.Series:
    """加载单股日对数收益序列（最近 window 个交易日，升序）。"""
    real_code = resolve_stock_code(code, db_path)
    if real_code is None:
        raise ValueError(f"未找到股票 {code} 的数据")
    db = Path(db_path or get_stock_analysis_db_path())
    with sqlite3.connect(str(db)) as conn:
        df = pd.read_sql_query(
            "SELECT date, close FROM stock_analysis WHERE code = ? ORDER BY date DESC LIMIT ?",
            conn,
            params=(real_code, window),
        )
    if df.empty:
        raise ValueError(f"未找到股票 {code} 的数据")
    df = df.iloc[::-1].reset_index(drop=True)
    close = df["close"].astype("float64")
    close.index = pd.to_datetime(df["date"])
    ret = np.log(close / close.shift(1)).dropna()
    return ret.rename("log_return")


class GARCHVolatility:
    """GARCH(1,1) 波动率模型封装。"""

    def __init__(self, horizon: int = 5, dist: str = "normal", p: int = 1, q: int = 1):
        self.horizon = horizon
        self.dist = dist
        self.p = p
        self.q = q
        self.model = None
        self.res = None

    def fit(self, returns: pd.Series) -> GARCHVolatility:
        """拟合 GARCH。returns 为小数对数收益。"""
        require_ml("arch")
        from arch import arch_model

        # 乘 100 进入百分比尺度, 改善数值稳定性, 结果需 /100 还原
        self.model = arch_model(
            returns.to_numpy() * 100.0,
            vol="GARCH",
            p=self.p,
            q=self.q,
            dist=self.dist,
            rescale=False,
        )
        self.res = self.model.fit(disp="off")
        return self

    def _params(self) -> dict[str, float]:
        p = self.res.params
        omega = float(p["omega"]) / 100.0**2  # 还原到小数尺度
        alpha = float(p.get("alpha[1]", 0.0))
        beta = float(p.get("beta[1]", 0.0))
        return {"omega": omega, "alpha": alpha, "beta": beta, "persistence": alpha + beta}

    def current_conditional_vol(self) -> float:
        """最新条件波动率（小数）。"""
        return float(np.sqrt(self.res.conditional_volatility[-1])) / 100.0

    def forecast_vol(self) -> float:
        """未来 horizon 日平均条件波动率（小数）。"""
        fc = self.res.forecast(horizon=self.horizon, method="simulation")
        var = float(fc.variance.values[-1, : self.horizon].mean())
        return float(np.sqrt(var)) / 100.0

    def annualized_vol(self, scale: int = TRADING_DAYS) -> float:
        """年化条件波动率（小数）。"""
        return self.current_conditional_vol() * np.sqrt(scale)

    def realized_vol_30d(self, returns: pd.Series) -> float:
        """最近 30 日已实现年化波动率（小数，对比基准）。"""
        r = returns.tail(30)
        if len(r) < 10:
            return float("nan")
        return float(r.std() * np.sqrt(TRADING_DAYS))

    def summary(self, returns: pd.Series) -> dict:
        """模型摘要（含参数、当前/预测/年化/已实现波动率、信息准则）。"""
        p = self._params()
        return {
            "params": {k: round(v, 6) for k, v in p.items()},
            "dist": self.dist,
            "horizon_days": self.horizon,
            "current_conditional_vol_pct": round(self.current_conditional_vol() * 100, 3),
            "forecast_vol_pct": round(self.forecast_vol() * 100, 3),
            "annualized_vol_pct": round(self.annualized_vol() * 100, 2),
            "realized_vol_30d_pct": round(self.realized_vol_30d(returns) * 100, 2),
            "aic": round(float(self.res.aic), 2),
            "bic": round(float(self.res.bic), 2),
        }


def plot_garch(
    returns: pd.Series,
    model: GARCHVolatility,
    code: str,
    out_path: Path,
) -> Path:
    """绘制收益 + 条件波动率（含预测段）。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from utils.font_config import setup_chinese_font

    setup_chinese_font()

    cond_vol = pd.Series(model.res.conditional_volatility / 100.0, index=returns.index)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    ax1.plot(returns.index, returns.to_numpy(), lw=0.7, color="#4C72B0")
    ax1.set_title(f"{code} 日对数收益 & GARCH(1,1) 条件波动率")
    ax1.set_ylabel("log return")
    ax1.grid(alpha=0.3)

    ax2.plot(cond_vol.index, cond_vol.to_numpy(), lw=1.0, color="#C44E52", label="GARCH σ")
    # 已实现 30 日波动
    rv = returns.rolling(30).std()
    ax2.plot(rv.index, rv.to_numpy(), lw=0.8, color="#55A868", alpha=0.8, label="30d realized σ")
    ax2.set_ylabel("volatility")
    ax2.legend()
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def compute_garch_report(
    code: str,
    window: int = 300,
    horizon: int = 5,
    dist: str = "normal",
    db_path: str | None = None,
    with_series: bool = False,
) -> dict:
    """对单股拟合 GARCH(1,1) 返回报告 dict（不落盘）。

    供 Web (/api/ml/garch) 复用。with_series=True 时附带条件波动率与收益序列供前端画图。
    未找到股票抛 ValueError。
    """
    returns = load_stock_returns(code, window, db_path)
    model = GARCHVolatility(horizon=horizon, dist=dist).fit(returns)
    report = {
        "model": "garch",
        "success": True,
        "code": code,
        "window_days": window,
        "summary": model.summary(returns),
    }
    if with_series:
        cond_vol = model.res.conditional_volatility / 100.0
        report["series"] = {
            "dates": [d.strftime("%Y-%m-%d") for d in returns.index],
            "conditional_vol_pct": [round(float(v) * 100, 4) for v in cond_vol],
            "log_return": [round(float(v), 5) for v in returns.to_numpy()],
        }
    return report


def run_garch(args) -> None:
    """CLI 入口：对单股拟合 GARCH(1,1) 并输出波动率预测报告。"""
    require_ml("arch")
    print(f">>> 加载 {args.code} 日收益 (最近 {args.window} 日)...", file=sys.stderr, flush=True)
    returns = load_stock_returns(args.code, args.window, args.db)
    print(f"  样本: {len(returns)} 个交易日", file=sys.stderr, flush=True)

    model = GARCHVolatility(horizon=args.horizon, dist=args.dist)
    model.fit(returns)
    summary = model.summary(returns)

    report = {
        "model": "garch",
        "code": args.code,
        "window_days": args.window,
        "summary": summary,
    }
    out = report_path(args.output, f"ml_garch_{args.code}.json")
    save_json_report(report, out)

    if not args.no_chart:
        chart = project_root() / "output" / "charts" / f"ml_garch_{args.code}.png"
        plot_garch(returns, model, args.code, chart)
        print(f"📈 已保存图表: {chart}", file=sys.stderr)

    s = summary
    print(
        f"\nGARCH(1,1) {args.code}: ω={s['params']['omega']:.6f} α={s['params']['alpha']:.3f} "
        f"β={s['params']['beta']:.3f} 持续性={s['params']['persistence']:.3f}"
    )
    print(
        f"条件波动率: 当前 {s['current_conditional_vol_pct']:.3f}% | "
        f"未来{args.horizon}日 {s['forecast_vol_pct']:.3f}% | 年化 {s['annualized_vol_pct']:.2f}%"
    )
    print(f"已实现 30 日年化: {s['realized_vol_30d_pct']:.2f}% (对比基准)")

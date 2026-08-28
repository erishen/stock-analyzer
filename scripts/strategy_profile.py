"""四策略完整画像: 统一回测 + 等权基准 + 分年度收益 + 交易成本 + 综合排名"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import get_stock_analysis_db_path
from strategy.backtest import run_backtest
from strategy.comparison import compare_strategies

db = Path(get_stock_analysis_db_path())
HOLDING = 20  # 统一持有天数(动量新默认)

STRATEGIES = ["momentum", "mean_reversion", "trend_following", "multi_factor"]
NAMES = {
    "momentum": "动量策略",
    "mean_reversion": "均值回归",
    "trend_following": "趋势跟踪",
    "multi_factor": "多因子",
}

results = {}
for st in STRATEGIES:
    print(f"\n>>> 回测 {NAMES[st]} (holding={HOLDING})...", file=sys.stderr)
    results[st] = run_backtest(db_path=db, strategy_type=st, holding_days=HOLDING)


# --- 分年度收益 (从 equity_curve) ---
def yearly_returns(equity_curve):
    by_year = {}
    for p in equity_curve:
        y = p["date"][:4]
        by_year[y] = p["equity"]  # 每年最后一个值
    years = sorted(by_year)
    out, prev = {}, None
    for y in years:
        if prev is not None:
            out[y] = (by_year[y] / prev - 1) * 100
        prev = by_year[y]
    return out


yearly = {st: yearly_returns(r.equity_curve) for st, r in results.items()}

# --- 输出 ---
hdr = f"{'指标':<14}{'动量':>10}{'均值回归':>10}{'趋势跟踪':>10}{'多因子':>10}"
print(f"\n{'=' * 62}")
print(f"📊 四策略完整画像 (2020-01 ~ 2026-08, 持有{HOLDING}天, 全市场{len(results['momentum'].trades) and ''}含费)")
print(f"{'=' * 62}\n{hdr}\n{'-' * 62}")
rows = [
    ("总收益%", lambda r: r.total_return * 100),
    ("年化收益%", lambda r: r.annualized_return * 100),
    ("最大回撤%", lambda r: r.max_drawdown * 100),
    ("夏普", lambda r: r.sharpe_ratio),
    ("索提诺", lambda r: r.sortino_ratio),
    ("卡玛", lambda r: r.calmar_ratio),
    ("波动率%", lambda r: r.volatility * 100),
    ("胜率%", lambda r: r.win_rate * 100),
    ("盈亏比", lambda r: r.profit_factor),
    ("交易次数", lambda r: r.total_trades),
    ("交易成本¥", lambda r: r.total_trading_cost),
]
for label, fn in rows:
    vals = [fn(results[st]) for st in STRATEGIES]
    print(f"{label:<14}" + "".join(f"{v:>10.2f}" for v in vals))

print(f"\n{'=' * 62}\n📅 分年度收益%\n{'-' * 62}")
all_years = sorted({y for d in yearly.values() for y in d})
print(f"{'年份':<14}" + "".join(f"{NAMES[st]:>10}" for st in STRATEGIES))
for y in all_years:
    print(f"{y:<14}" + "".join(f"{yearly[st].get(y, float('nan')):>10.1f}" for st in STRATEGIES))

# --- 综合排名 (项目内置打分) ---
comparison = compare_strategies(list(results.values()))
print(f"\n{'=' * 62}\n🏆 综合排名 (收益/夏普/回撤/胜率加权)")
for i, (name, score) in enumerate(comparison.overall_ranking, 1):
    print(f"   {i}. {name:<12} 得分 {score:.1f}")
print(f"   最高收益: {comparison.best_return} | 最高夏普: {comparison.best_sharpe}")
print(f"   最低回撤: {comparison.best_drawdown} | 最高胜率: {comparison.best_win_rate}")

# --- 保存 JSON 画像 ---
profile = {
    "config": {"holding_days": HOLDING, "db": str(db), "period": "2020-01~2026-08"},
    "strategies": {st: results[st].to_dict() for st in STRATEGIES},
    "yearly_returns_pct": yearly,
    "ranking": [
        {"rank": i + 1, "strategy": n, "score": round(s, 1)} for i, (n, s) in enumerate(comparison.overall_ranking)
    ],
}
out = PROJECT_ROOT / "output" / "reports" / "strategy_profile.json"
out.write_text(json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(f"\n💾 画像已保存: {out}")

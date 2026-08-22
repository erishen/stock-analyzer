"""均值回归 + 质量过滤 改良版验证

假设: 全市场均值回归亏钱的原因是买入了一篮子垃圾股(低流动性/高波动/低价/崩盘中)。
验证: 在 RSI 超卖入场基础上逐级开启质量过滤, 观察收益变化。

过滤器(基于 2024 年 RSI<30 样本分布定阈值):
  liq   amount >= 5000万   (砍掉流动性最差的 ~35%)
  price close >= 5元        (P25, 排除低价退市风险区)
  vol   volatility_20d <= 0.035  (P80, 排除最妖的 20%)
  trend close/ma60 >= 0.75 (低于长期均线25%以上 = 崩盘中, 不接飞刀)
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pandas as pd

from config import get_stock_analysis_db_path
from strategy.backtest import BacktestEngine, MeanReversionStrategy

HOLDING = 20


class CachedEngine(BacktestEngine):
    """加载质量列 + 缓存, 避免多配置重复加载 700 万条"""

    def get_all_stock_data(self) -> dict[str, pd.DataFrame]:
        if getattr(self, "_cache", None) is None:
            query = """
                SELECT code, date, close, high, low, open, volume,
                       rsi, macd, macd_signal, ma5, ma10, ma20,
                       boll_upper, boll_lower,
                       amount, volatility_20d, ma60, close_ma60_ratio
                FROM stock_analysis
                ORDER BY code, date
            """
            df = pd.read_sql_query(query, self.conn)
            df["date"] = pd.to_datetime(df["date"])
            self._cache = {code: g.reset_index(drop=True) for code, g in df.groupby("code")}
        return self._cache


class QualityMeanReversion(MeanReversionStrategy):
    """均值回归 + 质量过滤(可开关)"""

    def __init__(self, liq=False, price=False, vol=False, trend=False, **kwargs):
        super().__init__(**kwargs)
        self.f_liq = liq
        self.f_price = price
        self.f_vol = vol
        self.f_trend = trend

    def select_stocks(self, all_data, date_idx, date, stock_names=None):
        selected = []
        for code, df in all_data.items():
            if stock_names and self.is_excluded(stock_names.get(code, "")):
                continue
            date_rows = df[df["date"] == date]
            if date_rows.empty:
                continue
            try:
                row = date_rows.iloc[0]
                close_price = float(row.get("close", 0) or 0)
                if close_price < self.min_price:
                    continue

                if self.f_price and close_price < 5.0:
                    continue
                if self.f_liq:
                    amount = float(row.get("amount", 0) or 0)
                    if amount < 50_000_000:
                        continue
                if self.f_vol:
                    vol20 = float(row.get("volatility_20d", 0) or 1)
                    if vol20 > 0.035:
                        continue
                if self.f_trend:
                    ma60_ratio = float(row.get("close_ma60_ratio", 1) or 1)
                    if ma60_ratio < 0.75:
                        continue

                rsi = row.get("rsi", 50) or 50
                if rsi < self.rsi_oversold:
                    selected.append((code, rsi))
            except Exception:
                continue

        selected.sort(key=lambda x: x[1])
        return selected[: self.max_stocks]


def yearly_returns(equity_curve):
    by_year = {}
    for p in equity_curve:
        by_year[p["date"][:4]] = p["equity"]
    years = sorted(by_year)
    out, prev = {}, None
    for y in years:
        if prev is not None:
            out[y] = round((by_year[y] / prev - 1) * 100, 1)
        prev = by_year[y]
    return out


CONFIGS = [
    ("基线(无过滤)", {}),
    ("+流动性", {"liq": True}),
    ("+价格", {"liq": True, "price": True}),
    ("+波动率", {"liq": True, "price": True, "vol": True}),
    ("全套", {"liq": True, "price": True, "vol": True, "trend": True}),
    ("仅趋势位置", {"trend": True}),
]

db = Path(get_stock_analysis_db_path())
engine = CachedEngine(db)
engine.connect()

results = {}
try:
    for name, filters in CONFIGS:
        print(f"\n>>> 回测: {name}", file=sys.stderr, flush=True)
        strategy = QualityMeanReversion(holding_days=HOLDING, **filters)
        results[name] = engine.run_backtest(strategy)
finally:
    engine.close()

# --- 对比表 ---
print(f"\n{'=' * 86}")
print(f"📊 均值回归 + 质量过滤 (持有{HOLDING}天, 全市场, 含费)")
print(f"{'=' * 86}")
print(f"{'配置':<12}{'总收益%':>9}{'年化%':>8}{'回撤%':>8}{'夏普':>7}{'胜率%':>7}{'盈亏比':>7}{'交易':>6}{'成本¥':>9}")
print("-" * 86)
for name, _ in CONFIGS:
    r = results[name]
    print(
        f"{name:<12}{r.total_return * 100:>9.1f}{r.annualized_return * 100:>8.1f}"
        f"{r.max_drawdown * 100:>8.1f}{r.sharpe_ratio:>7.2f}{r.win_rate * 100:>7.1f}"
        f"{r.profit_factor:>7.2f}{r.total_trades:>6}{r.total_trading_cost:>9,.0f}"
    )

print(f"\n{'=' * 86}\n📅 分年度收益%\n{'-' * 86}")
all_years = sorted({y for r in results.values() for y in yearly_returns(r.equity_curve)})
print(f"{'年份':<12}" + "".join(f"{n:>13}" for n, _ in CONFIGS))
for y in all_years:
    row = [yearly_returns(results[n].equity_curve).get(y, float("nan")) for n, _ in CONFIGS]
    print(f"{y:<12}" + "".join(f"{v:>13.1f}" for v in row))

# --- 保存 ---
out = {
    "config": {"holding_days": HOLDING, "period": "2020-01~2026-08", "universe": "全市场"},
    "filters": {
        "liq": "amount>=5000万", "price": "close>=5元",
        "vol": "volatility_20d<=0.035", "trend": "close/ma60>=0.75",
    },
    "results": {n: results[n].to_dict() for n, _ in CONFIGS},
    "yearly_returns_pct": {n: yearly_returns(results[n].equity_curve) for n, _ in CONFIGS},
}
path = PROJECT_ROOT / "output" / "reports" / "quality_meanrev.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(f"\n💾 已保存: {path}")

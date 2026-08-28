"""动量策略参数扫描: 市场宽度过滤 on/off × holding/lookback"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import get_stock_analysis_db_path
from strategy.backtest import BacktestEngine, MomentumStrategy

db = Path(get_stock_analysis_db_path())

combos = [
    # (holding, lookback, market_filter)
    (5, 20, False),  # 基线(旧行为)
    (5, 20, True),
    (10, 20, True),
    (20, 20, True),
    (20, 60, True),
]

print(
    f"{'hold':>5} {'look':>5} {'filter':>7} | {'收益%':>8} {'年化%':>7} {'回撤%':>7} {'夏普':>5} {'交易':>5} {'胜率%':>6}"
)
print("-" * 76)
for holding, lookback, mf in combos:
    strategy = MomentumStrategy(lookback_days=lookback, holding_days=holding, market_filter=mf)
    engine = BacktestEngine(db)
    engine.connect()
    r = engine.run_backtest(strategy, initial_capital=100000)
    engine.close()
    print(
        f"{holding:>5} {lookback:>5} {'on' if mf else 'off':>7} |"
        f" {r.total_return * 100:>8.2f} {r.annualized_return * 100:>7.2f} {r.max_drawdown * 100:>7.2f}"
        f" {r.sharpe_ratio:>5.2f} {r.total_trades:>5} {r.win_rate * 100:>6.2f}"
    )

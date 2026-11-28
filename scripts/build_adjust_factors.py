"""构建比例复权因子表(原始价 + 分红送转事件)。

行情源的 qfq 是减法复权且锚点随日期前移, 既不能落库也不能当因子用;
长周期总收益回测需要按比例复权的因子, 所以在这里自建一张表:

    data/stock_adjust_factors.db :: adjust_events(code, ex_date, div_per_share, share_ratio, ratio)

用法:
    uv run python scripts/build_adjust_factors.py            # 全市场
    uv run python scripts/build_adjust_factors.py --limit 50 # 抽样试跑
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.adjust import DEFAULT_FACTOR_DB, build_events, write_factor_db

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> int:
    ap = argparse.ArgumentParser(description="构建比例复权因子表")
    ap.add_argument("--db", default=str(ROOT / "data" / "stock_klines.db"), help="原始价库")
    ap.add_argument("--out", default=str(ROOT / DEFAULT_FACTOR_DB), help="因子库输出路径")
    ap.add_argument("--workers", type=int, default=6, help="并发线程数")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 只(调试用)")
    args = ap.parse_args()

    codes = None
    if args.limit:
        import sqlite3

        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        codes = [r[0] for r in conn.execute("SELECT DISTINCT code FROM stock_klines LIMIT ?", (args.limit,))]
        conn.close()

    events, stats = build_events(Path(args.db), codes=codes, workers=args.workers)
    total = write_factor_db(events, Path(args.out))
    print(json.dumps({"stats": stats, "rows_in_db": total, "out": args.out}, ensure_ascii=False, indent=2))
    return 0 if stats["events"] else 1


if __name__ == "__main__":
    sys.exit(main())

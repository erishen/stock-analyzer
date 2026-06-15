#!/usr/bin/env python3
"""
Demo 模式数据生成脚本
生成模拟股票数据到 SQLite 数据库，供 Demo 模式使用
"""

import sqlite3
import random
import math
from pathlib import Path

DEMO_STOCKS = [
    ("sh600000", "Demo银行", 15.0),
    ("sh600519", "Demo茅台", 180.0),
    ("sh600036", "Demo招行", 35.0),
    ("sz000001", "Demo平安", 12.0),
    ("sh601318", "Demo保险", 50.0),
    ("sh600030", "Demo证券", 20.0),
    ("sz002415", "Demo科技A", 45.0),
    ("sh600196", "Demo医药", 30.0),
    ("sh600887", "Demo食品", 28.0),
    ("sz300750", "Demo新能源", 60.0),
    ("sh600585", "Demo建材", 25.0),
    ("sz000002", "Demo地产", 10.0),
]


def generate_demo_db(output_path: Path | None = None) -> Path:
    if output_path is None:
        output_path = Path(__file__).parent.parent / "data" / "stock_analysis.db"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE stock_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL, close REAL, high REAL, low REAL,
            volume REAL, amount REAL,
            change_percent REAL,
            ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL,
            ma5_ratio REAL, ma10_ratio REAL, ma20_ratio REAL, ma60_ratio REAL,
            ema12 REAL, ema26 REAL, macd REAL, macd_signal REAL, macd_hist REAL,
            rsi REAL, boll_mid REAL, boll_upper REAL, boll_lower REAL,
            kdj_k REAL, kdj_d REAL, kdj_j REAL,
            atr REAL, obv REAL, williams_r REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("CREATE INDEX idx_code_date ON stock_analysis(code, date)")

    for code, name, base_price in DEMO_STOCKS:
        price = base_price
        prev_close = base_price
        volume_base = random.uniform(1e6, 1e7)
        obv = 0
        prices = []

        for day_offset in range(200):
            import datetime
            d = datetime.date(2025, 9, 1) + datetime.timedelta(days=day_offset)
            date = d.strftime("%Y.%m.%d")

            change = random.gauss(0, 0.02) + 0.0005
            if day_offset > 180:
                change += 0.003

            open_price = prev_close * (1 + random.gauss(0, 0.005))
            close = open_price * (1 + change)
            high = max(open_price, close) * (1 + abs(random.gauss(0, 0.01)))
            low = min(open_price, close) * (1 - abs(random.gauss(0, 0.01)))
            volume = volume_base * (1 + abs(random.gauss(0, 0.3)))
            amount = volume * (open_price + close) / 2
            change_percent = round((close - prev_close) / prev_close * 100, 4)

            prices.append(close)
            ma5 = sum(prices[-5:]) / min(5, len(prices)) if prices else close
            ma10 = sum(prices[-10:]) / min(10, len(prices)) if prices else close
            ma20 = sum(prices[-20:]) / min(20, len(prices)) if prices else close
            ma60 = sum(prices[-60:]) / min(60, len(prices)) if prices else close

            if close > prev_close:
                obv += volume
            elif close < prev_close:
                obv -= volume

            rsi = 50.0
            if len(prices) >= 14:
                gains = [max(prices[i] - prices[i-1], 0) for i in range(-13, 0)]
                losses = [max(prices[i-1] - prices[i], 0) for i in range(-13, 0)]
                avg_gain = sum(gains) / 14
                avg_loss = sum(losses) / 14
                if avg_loss == 0:
                    rsi = 100.0
                else:
                    rsi = 100 - 100 / (1 + avg_gain / avg_loss)

            boll_mid = ma20
            boll_std = math.sqrt(sum((p - ma20) ** 2 for p in prices[-20:]) / max(1, len(prices[-20:])))
            boll_upper = boll_mid + 2 * boll_std
            boll_lower = boll_mid - 2 * boll_std

            k_k = 50.0
            k_d = 50.0
            k_j = 50.0

            atr = (high - low) * random.uniform(0.5, 1.5)
            williams_r = random.uniform(-100, 0)

            cols = [
                "code", "date", "open", "close", "high", "low", "volume", "amount",
                "change_percent",
                "ma5", "ma10", "ma20", "ma60",
                "ma5_ratio", "ma10_ratio", "ma20_ratio", "ma60_ratio",
                "ema12", "ema26", "macd", "macd_signal", "macd_hist",
                "rsi", "boll_mid", "boll_upper", "boll_lower",
                "kdj_k", "kdj_d", "kdj_j",
                "atr", "obv", "williams_r",
            ]
            vals = [
                code, date,
                round(open_price, 2), round(close, 2), round(high, 2), round(low, 2),
                round(volume, 2), round(amount, 2), change_percent,
                round(ma5, 2), round(ma10, 2), round(ma20, 2), round(ma60, 2),
                round(close/ma5 - 1, 4) if ma5 else 0,
                round(close/ma10 - 1, 4) if ma10 else 0,
                round(close/ma20 - 1, 4) if ma20 else 0,
                round(close/ma60 - 1, 4) if ma60 else 0,
                round(close * 0.9, 2), round(close * 0.8, 2),
                round(close * 0.05, 4), round(close * 0.03, 4), round(close * 0.02, 4),
                round(rsi, 2),
                round(boll_mid, 2), round(boll_upper, 2), round(boll_lower, 2),
                round(k_k, 2), round(k_d, 2), round(k_j, 2),
                round(atr, 2), round(obv, 2), round(williams_r, 2),
            ]
            placeholders = ",".join("?" for _ in vals)
            cursor.execute(f"INSERT INTO stock_analysis ({','.join(cols)}) VALUES ({placeholders})", vals)

            prev_close = close

        print(f"  {code} ({name}): {day_offset+1} days, final ¥{prev_close:.2f}")

    conn.commit()
    conn.close()

    demo_stocks_dict = {code: name for code, name, _ in DEMO_STOCKS}
    cache = {
        "updated_at": "2025-09-01T00:00:00",
        "stocks": {
            code: {"code": code, "name": name, "industry": "模拟", "sector": "模拟行业", "market": "A股"}
            for code, name in demo_stocks_dict.items()
        },
    }
    cache_path = output_path.parent / "stock_info_cache.json"
    import json
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    db_size = output_path.stat().st_size
    cache_size = cache_path.stat().st_size
    print(f"\n✅ Demo DB: {output_path} ({db_size/1024:.1f} KB)")
    print(f"✅ Demo 股票信息: {cache_path} ({cache_size/1024:.1f} KB)")
    return output_path


if __name__ == "__main__":
    generate_demo_db()

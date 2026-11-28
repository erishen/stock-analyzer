"""全市场每日汇总表 `market_daily`。

为什么单独建表: 大盘图表/择时都要"每日一行"的市场统计, 但这些数字必须从
`stock_analysis`(700 万行 × 65 列) 现算。实测:
  - `/api/market/history` 取 90 天: 9~12s
  - 择时里 `GROUP BY date ... LIMIT 30`: 4.4s(而且没有下界, 每次扫全表)
两者都只是"按日聚合", 完全可以在 ETL 末尾增量维护成 1,430 行的窄表, 读起来毫秒级。

用法:
    refresh_market_summary(db_path)          # 全量重建(首次/口径变更后)
    refresh_market_summary(db_path, days=40) # 每日增量: 重算最近 40 个交易日
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

TABLE = "market_daily"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    date TEXT PRIMARY KEY,
    avg_close REAL,
    avg_ma5 REAL,
    avg_ma20 REAL,
    avg_change REAL,
    avg_rsi REAL,
    up_count INTEGER,
    down_count INTEGER,
    flat_count INTEGER,
    breadth REAL
)
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(_SCHEMA)


def refresh_market_summary(db_path: Path | str, days: int | None = None) -> int:
    """重建/增量刷新 `market_daily`, 返回写入行数。

    ``days`` 为空: 整表重建(首次构建或口径变更后);
    ``days`` 给定: 只重算最近 N 个交易日的行(每日 ETL 末尾调用, 秒级)。
    """
    with sqlite3.connect(str(db_path)) as conn:
        _ensure_schema(conn)

        if days is None:
            rows = conn.execute(
                """
                SELECT date,
                       AVG(close), AVG(ma5), AVG(ma20), AVG(change_percent), AVG(rsi),
                       SUM(CASE WHEN change_percent > 0 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN change_percent < 0 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN change_percent = 0 THEN 1 ELSE 0 END)
                FROM stock_analysis
                GROUP BY date
                ORDER BY date
                """
            ).fetchall()
            conn.execute(f"DELETE FROM {TABLE}")
        else:
            dates = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT date FROM stock_analysis ORDER BY date DESC LIMIT ?", (days,)
                ).fetchall()
            ]
            if not dates:
                return 0
            conn.executemany(f"DELETE FROM {TABLE} WHERE date = ?", [(d,) for d in dates])
            rows = []
            for d in dates:  # 逐日走 idx_analysis_date, 单日 ~0.07s
                row = conn.execute(
                    """
                    SELECT date,
                           AVG(close), AVG(ma5), AVG(ma20), AVG(change_percent), AVG(rsi),
                           SUM(CASE WHEN change_percent > 0 THEN 1 ELSE 0 END),
                           SUM(CASE WHEN change_percent < 0 THEN 1 ELSE 0 END),
                           SUM(CASE WHEN change_percent = 0 THEN 1 ELSE 0 END)
                    FROM stock_analysis
                    WHERE date = ?
                    GROUP BY date
                    """,
                    (d,),
                ).fetchone()
                if row:
                    rows.append(row)

        payload = []
        for date, close, ma5, ma20, chg, rsi, up, down, flat in rows:
            up, down, flat = int(up or 0), int(down or 0), int(flat or 0)
            effective = up + down
            # 全天全平盘时分母为 0 -> NULL, 而不是 0%。"0% 上涨"是误导性结论。
            breadth = (up / effective) if effective else None
            payload.append((date, close, ma5, ma20, chg, rsi, up, down, flat, breadth))

        conn.executemany(
            f"""
            INSERT OR REPLACE INTO {TABLE}
            (date, avg_close, avg_ma5, avg_ma20, avg_change, avg_rsi,
             up_count, down_count, flat_count, breadth)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            payload,
        )
        conn.commit()

    logger.info("market_daily 刷新完成: %d 行 (days=%s)", len(payload), days)
    return len(payload)


def table_ready(db_path: Path | str) -> bool:
    """汇总表是否存在且有数据(供 Web 端决定走快路径还是旧查询)。"""
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            return conn.execute(f"SELECT 1 FROM {TABLE} LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        return False

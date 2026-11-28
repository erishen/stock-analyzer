"""PIT(point-in-time) 标的池: 用行情自身推导"某一天真正存在并可交易"的代码集合。

为什么需要它:
  1) 库里只有**当前在市**的标的, 历史回放若用"今天的股票列表", 等于让策略提前知道
     谁活到了最后 —— 典型幸存者偏差;
  2) 期间新上市的标的(本库 2021-2026 有 1,659 只)在上市日之前根本不该出现在候选池;
  3) 退市/长期停牌标的(``last_date < 数据末端``)在停牌之后也不该继续被买入。

做法: 把每只标的的 ``first_date`` / ``last_date`` 落成一张 ``code_lifecycle`` 表
(5,600 行的窄表, 毫秒级查询), 之后任何"某日标的池"都从这张表取,
而不是从静态名单或"当前代码全集"取。

局限(必须在报告里如实写出): 已经彻底退市、行情源不再返回的标的,
本库根本没有它们的行, lifecycle 表也补不出来。因此这里能量化的是
"曾经在市、后来在库内停止更新"的那部分(实测 44 只), 真正的退市缺口只能
用``survivorship_report`` 里的 ``residual_bias_note`` 声明, 不能假装已消除。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_KLINES_DB = "data/stock_klines.db"
LIFECYCLE_TABLE = "code_lifecycle"


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    # 与库内其它表一致: 不用 WAL(OrbStack/FUSE 下 -wal 会坏库)
    conn.execute("PRAGMA journal_mode=delete")
    return conn


def rebuild_lifecycle(db_path: str | Path = DEFAULT_KLINES_DB) -> dict:
    """从 ``stock_klines`` 重建 ``code_lifecycle`` 表。

    Returns:
        ``{"codes": n, "table": ..., "first_day": ..., "last_day": ...}``
    """
    conn = _connect(db_path)
    try:
        first_day, last_day, n_rows = conn.execute(
            "SELECT MIN(date), MAX(date), COUNT(*) FROM stock_klines"
        ).fetchone()
        conn.execute(f"DROP TABLE IF EXISTS {LIFECYCLE_TABLE}")
        conn.execute(
            f"""
            CREATE TABLE {LIFECYCLE_TABLE} AS
            SELECT code, MIN(date) AS first_date, MAX(date) AS last_date, COUNT(*) AS n_days
            FROM stock_klines
            GROUP BY code
            """
        )
        conn.execute(f"CREATE INDEX idx_lifecycle_dates ON {LIFECYCLE_TABLE}(first_date, last_date)")
        conn.commit()
        codes = conn.execute(f"SELECT COUNT(*) FROM {LIFECYCLE_TABLE}").fetchone()[0]
        logger.info("code_lifecycle 重建: %s 只 / %s 行 / %s~%s", codes, n_rows, first_day, last_day)
        return {
            "codes": int(codes),
            "rows": int(n_rows),
            "first_day": first_day,
            "last_day": last_day,
            "table": LIFECYCLE_TABLE,
        }
    finally:
        conn.close()


def has_lifecycle(db_path: str | Path = DEFAULT_KLINES_DB) -> bool:
    """lifecycle 表是否已建(未建时调用方应回退到旧路径并提示重跑)。"""
    if not Path(db_path).exists():
        return False
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (LIFECYCLE_TABLE,),
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def universe_as_of(date: str, db_path: str | Path = DEFAULT_KLINES_DB) -> list[str]:
    """某交易日真实存在的标的(``first_date <= date <= last_date``)。

    lifecycle 表不存在时返回空列表, 由调用方显式回退(不静默当作"全市场")。
    """
    if not has_lifecycle(db_path):
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            f"SELECT code FROM {LIFECYCLE_TABLE} WHERE first_date <= ? AND last_date >= ? ORDER BY code",
            (date, date),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def lifecycle_frame(db_path: str | Path = DEFAULT_KLINES_DB):
    """lifecycle 表读成 DataFrame(需要 pandas; 仅分析路径用)。"""
    import pandas as pd

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(f"SELECT * FROM {LIFECYCLE_TABLE}", conn)
    finally:
        conn.close()


def survivorship_report(
    start: str | None = None,
    end: str | None = None,
    db_path: str | Path = DEFAULT_KLINES_DB,
) -> dict:
    """量化幸存者偏差: 窗口内新上市 / 中途停止更新 / 两端可交易标的数量。

    Args:
        start: 窗口起始日(默认数据首日)
        end: 窗口结束日(默认数据末日)
    """
    if not has_lifecycle(db_path):
        return {
            "ok": False,
            "error": f"缺少 {LIFECYCLE_TABLE} 表 (请先运行 make universe)",
        }
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        data_first, data_last = conn.execute(
            f"SELECT MIN(first_date), MAX(last_date) FROM {LIFECYCLE_TABLE}"
        ).fetchone()
        start = start or data_first
        end = end or data_last
        total = conn.execute(f"SELECT COUNT(*) FROM {LIFECYCLE_TABLE}").fetchone()[0]
        active_start = conn.execute(
            f"SELECT COUNT(*) FROM {LIFECYCLE_TABLE} WHERE first_date <= ? AND last_date >= ?",
            (start, start),
        ).fetchone()[0]
        active_end = conn.execute(
            f"SELECT COUNT(*) FROM {LIFECYCLE_TABLE} WHERE first_date <= ? AND last_date >= ?",
            (end, end),
        ).fetchone()[0]
        new_listings = conn.execute(
            f"SELECT COUNT(*) FROM {LIFECYCLE_TABLE} WHERE first_date > ? AND first_date <= ?",
            (start, end),
        ).fetchone()[0]
        stopped = conn.execute(
            f"SELECT code, last_date FROM {LIFECYCLE_TABLE} WHERE last_date < ? ORDER BY last_date",
            (end,),
        ).fetchall()
        # 窗口内新上市按年分布, 用来判断"静态名单当标的池"的偏差有多大
        by_year = conn.execute(
            f"""
            SELECT substr(first_date, 1, 4) AS y, COUNT(*)
            FROM {LIFECYCLE_TABLE}
            WHERE first_date > ? AND first_date <= ?
            GROUP BY y ORDER BY y
            """,
            (start, end),
        ).fetchall()
    finally:
        conn.close()

    stopped_codes = [c for c, _ in stopped]
    return {
        "ok": True,
        "start": start,
        "end": end,
        "data_first_day": data_first,
        "data_last_day": data_last,
        "total_codes": int(total),
        "active_at_start": int(active_start),
        "active_at_end": int(active_end),
        "new_listings": int(new_listings),
        "new_listings_by_year": {y: int(n) for y, n in by_year},
        "stopped_codes": len(stopped_codes),
        "stopped_sample": stopped_codes[:10],
        "coverage_pct": round(active_end / total * 100, 2) if total else 0.0,
        "residual_bias_note": (
            "库里只有当前在市标的, 彻底退市(行情源不再返回)的标的没有任何行, "
            "lifecycle 也补不出来; 上面 stopped_codes 只是「曾在库内、后来停止更新」的那部分。"
        ),
        "usage": (
            "选股/回测的候选池按日期取 universe_as_of(date), 不要用当前代码全集或静态名单; "
            "板块名单属静态快照, 回放历史时其归类视为窗口内不变。"
        ),
    }

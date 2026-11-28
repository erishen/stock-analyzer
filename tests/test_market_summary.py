"""market_daily 汇总表: 增量刷新与广度口径测试。

这张表的存在理由是性能(两个接口原来每次扫 700 万行), 但正确性同样关键:
广度在"全天全平盘"的日期必须留空(None), 不能落成 0%。
"""

import sqlite3

from src.data import market_summary


def _make_db(tmp_path, rows):
    db = tmp_path / "stock_analysis.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE stock_analysis (code TEXT, date TEXT, close REAL, ma5 REAL, ma20 REAL,"
        " change_percent REAL, rsi REAL)"
    )
    conn.executemany("INSERT INTO stock_analysis VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return db


def test_full_rebuild_and_breadth(tmp_path):
    db = _make_db(
        tmp_path,
        [
            ("sh600000", "2026-01-05", 10.0, 9.8, 9.5, 2.0, 55.0),
            ("sz000001", "2026-01-05", 12.0, 11.9, 11.5, -1.0, 45.0),
            ("sh600000", "2026-01-06", 10.1, 9.9, 9.6, 0.0, 56.0),
            ("sz000001", "2026-01-06", 12.1, 12.0, 11.6, 0.0, 46.0),
        ],
    )
    assert market_summary.refresh_market_summary(db) == 2
    assert market_summary.table_ready(db)

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT date, up_count, down_count, flat_count, breadth FROM market_daily ORDER BY date"
    ).fetchall()
    conn.close()

    assert rows[0] == ("2026-01-05", 1, 1, 0, 0.5)
    # 全平盘: 分母为 0 -> NULL, 不能写成 0
    assert rows[1] == ("2026-01-06", 0, 0, 2, None)


def test_incremental_refresh_keeps_history(tmp_path):
    db = _make_db(
        tmp_path,
        [
            ("sh600000", "2026-01-05", 10.0, 9.8, 9.5, 2.0, 55.0),
            ("sh600000", "2026-01-06", 10.1, 9.9, 9.6, 1.0, 56.0),
            ("sh600000", "2026-01-07", 10.2, 10.0, 9.7, -1.0, 54.0),
        ],
    )
    market_summary.refresh_market_summary(db)

    # 最后一天数据被重算(补数据/修正), 增量刷新只覆盖最近 2 天
    conn = sqlite3.connect(db)
    conn.execute("UPDATE stock_analysis SET change_percent = 5.0 WHERE date = '2026-01-07'")
    conn.commit()
    conn.close()

    market_summary.refresh_market_summary(db, days=2)

    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT date, avg_change FROM market_daily ORDER BY date").fetchall()
    conn.close()
    assert len(rows) == 3  # 历史行没被删
    assert rows[2][1] == 5.0


def test_table_ready_false_when_missing(tmp_path):
    assert not market_summary.table_ready(tmp_path / "missing.db")

"""coverage_guard 的逐票历史空洞体检(history_gaps)回归测试。

背景: 单日覆盖校验只看横截面, 某只票"中间成片缺交易日"完全看不出 ——
2026-11-28 复权口径重建时才发现 2,679 只票有此类空洞(最长 205 个交易日)。
"""

import sqlite3
import sys
from pathlib import Path

import pytest

_DATA_TOOLS = Path(__file__).resolve().parent.parent / "data_tools"
if _DATA_TOOLS.exists():
    sys.path.insert(0, str(_DATA_TOOLS))

cg = pytest.importorskip("coverage_guard", reason="data_tools/ 不存在(公开仓库)")

CAL = [f"2024-05-{d:02d}" for d in range(1, 21)]  # 20 个交易日


@pytest.fixture
def klines_db(tmp_path):
    db = tmp_path / "klines.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE stock_klines (code TEXT, date TEXT, close REAL)")
    rows = [("000001", d, 1.0) for d in CAL]  # 完整
    rows += [("600000", d, 1.0) for d in CAL if d not in CAL[7:13]]  # 中间连缺 6 天
    rows += [("000002", d, 1.0) for d in CAL if d not in CAL[2:5]]  # 连缺 3 天(噪音)
    rows += [("000003", d, 1.0) for d in CAL[10:]]  # 晚上市(不该算洞)
    conn.executemany("INSERT INTO stock_klines VALUES (?,?,?)", rows)
    conn.commit()
    conn.close()
    return db


def test_flags_only_long_gaps(klines_db):
    g = cg.history_gaps(klines_db, min_run=5, limit=100)
    assert g["calendar_days"] == len(CAL)
    assert g["checked"] == 4
    assert g["flagged_count"] == 1
    f = g["flagged"][0]
    assert f["code"] == "600000"
    assert f["longest_run"] == 6
    assert f["gap_start"] == CAL[7]
    assert f["gap_end"] == CAL[12]


def test_short_gap_and_late_listing_not_flagged(klines_db):
    g = cg.history_gaps(klines_db, min_run=4, limit=100)
    codes = [f["code"] for f in g["flagged"]]
    assert codes == ["600000"]  # 000002 只有 3 天连缺, 000003 是上市前


def test_limit_keeps_worst_first(klines_db):
    g = cg.history_gaps(klines_db, min_run=4, limit=1)
    assert len(g["flagged"]) == 1
    assert g["flagged"][0]["longest_run"] == 6

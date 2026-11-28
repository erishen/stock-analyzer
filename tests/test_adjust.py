"""比例复权因子(自建)的回归测试。

源端 qfq 是减法复权且锚点漂移, 不能落库也不能当因子用; 这里锁定自建因子的算法:
ratio = (prev_close - div) / (prev_close * (1 + 送转比例))
"""

from pathlib import Path

import pytest

from src.data.adjust import (
    AdjustEvent,
    apply_qfq,
    compute_events,
    load_events,
    qfq_closes,
    write_factor_db,
)

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
CLOSES = dict.fromkeys(DATES, 10.0)


def test_cash_dividend_only():
    evs = compute_events("000001", [("2024-01-05", 0.5, 0.0)], DATES, CLOSES)
    assert len(evs) == 1
    e = evs[0]
    assert e.ex_date == "2024-01-05"
    assert e.ratio == pytest.approx((10.0 - 0.5) / 10.0, abs=1e-6)
    assert e.div_per_share == 0.5


def test_share_ratio_bonus():
    evs = compute_events("000002", [("2024-01-05", 0.5, 1.0)], DATES, CLOSES)
    assert evs[0].ratio == pytest.approx((10.0 - 0.5) / (10.0 * 2), abs=1e-6)
    assert evs[0].share_ratio == 1.0


def test_prev_close_uses_last_trading_day_before_ex():
    closes = {**CLOSES, "2024-01-04": 12.0}
    evs = compute_events("000003", [("2024-01-05", 1.0, 0.0)], DATES, closes)
    assert evs[0].ratio == pytest.approx((12.0 - 1.0) / 12.0, abs=1e-6)


def test_skip_invalid_events():
    raw = [
        ("2023-12-29", 0.5, 0.0),  # 早于上市段
        ("2024-01-05", 0.0, 0.0),  # 没有派息也没有送转
        ("2024-01-05", 12.0, 0.0),  # 派息 >= 前收
    ]
    assert compute_events("000004", raw, DATES, CLOSES) == []


def test_apply_qfq_anchor_and_gap():
    evs = [AdjustEvent("000005", "2024-01-05", 0.5, 0.0, 0.95)]
    adj = apply_qfq(DATES, [CLOSES[d] for d in DATES], evs)
    assert adj[:3] == pytest.approx([9.5, 9.5, 9.5])
    assert adj[3:] == pytest.approx([10.0, 10.0])  # 除权当日及之后不动
    # 原始价在除权日"假跌 5%", 复权后不跌
    assert adj[3] / adj[2] == pytest.approx(10.0 / 9.5)


def test_apply_qfq_custom_anchor():
    evs = [AdjustEvent("000006", "2024-01-05", 0.5, 0.0, 0.95)]
    adj = apply_qfq(DATES, [CLOSES[d] for d in DATES], evs, anchor="2024-01-02")
    assert adj == pytest.approx([10.0] * len(DATES))  # 锚点之前的事件不生效


def test_multiple_events_all_applied():
    """多个除权事件必须逐个判断 —— 用 break 会漏掉"比 d 更晚"的事件(历史 bug)。"""
    dates = ["2024-01-02", "2024-01-03", "2024-05-06", "2024-09-02"]
    evs = [
        AdjustEvent("000009", "2024-01-03", 0.5, 0.0, 0.95),
        AdjustEvent("000009", "2024-05-06", 1.0, 0.0, 0.9),
        AdjustEvent("000009", "2024-09-02", 1.0, 0.0, 0.8),
    ]
    adj = apply_qfq(dates, [10.0] * 4, evs)
    assert adj[0] == pytest.approx(10.0 * 0.95 * 0.9 * 0.8)  # 三个事件都生效
    assert adj[1] == pytest.approx(10.0 * 0.9 * 0.8)  # 01-03 当日及之前不生效
    assert adj[2] == pytest.approx(10.0 * 0.8)  # 只剩 09-02 生效
    assert adj[3] == pytest.approx(10.0)  # 锚点日不动


def test_no_events_is_identity():
    adj = apply_qfq(DATES, [CLOSES[d] for d in DATES], [])
    assert adj == [CLOSES[d] for d in DATES]


def test_factor_db_full_rebuild_drops_stale(tmp_path):
    """重复构建必须整表重建 —— 否则上一轮成功、本轮抓取失败的票会留下陈旧事件。"""
    db = tmp_path / "factors.db"
    e1 = AdjustEvent("000001", "2024-01-03", 0.5, 0.0, 0.95)
    e2 = AdjustEvent("000002", "2024-02-05", 1.0, 0.0, 0.9)
    assert write_factor_db([e1, e2], db) == 2
    assert write_factor_db([e1], db) == 1
    assert set(load_events(db)) == {"000001"}


def test_factor_db_roundtrip(tmp_path):
    db = tmp_path / "factors.db"
    evs = [
        AdjustEvent("000007", "2024-01-05", 0.5, 0.0, 0.95),
        AdjustEvent("000007", "2025-06-20", 1.0, 0.0, 0.9),
    ]
    assert write_factor_db(evs, db) == 2
    loaded = load_events(db, ["000007"])["000007"]
    assert [e.ex_date for e in loaded] == ["2024-01-05", "2025-06-20"]
    assert loaded[0].ratio == 0.95


def test_qfq_closes_end_to_end(tmp_path):
    import sqlite3

    klines = tmp_path / "k.db"
    conn = sqlite3.connect(klines)
    conn.execute("CREATE TABLE stock_klines (code TEXT, date TEXT, close REAL)")
    conn.executemany("INSERT INTO stock_klines VALUES (?,?,?)", [("000008", d, CLOSES[d]) for d in DATES])
    conn.commit()
    conn.close()

    factor_db = tmp_path / "f.db"
    write_factor_db(compute_events("000008", [("2024-01-05", 0.5, 0.0)], DATES, CLOSES), factor_db)
    out = qfq_closes(Path(klines), Path(factor_db), "000008")
    assert [d for d, _ in out] == DATES
    assert out[-1][1] == 10.0  # 末根不动


def test_fhps_empty_result_is_no_events(monkeypatch):
    """东财返回 result:null 时 akshare 抛 TypeError —— 应视为"无分红记录"而非抓取失败。"""
    import akshare as ak

    from src.data.adjust import _fetch_raw_events

    def boom(symbol: str):
        raise TypeError("'NoneType' object is not subscriptable")

    monkeypatch.setattr(ak, "stock_fhps_detail_em", boom)
    assert _fetch_raw_events("002731") == []


def test_build_events_retries_transient_failure(tmp_path, monkeypatch):
    """单次抓取失败(限流/抖动)必须重试, 否则每次跑批都剩几只"失败"票。"""
    import sqlite3

    import src.data.adjust as mod

    db = tmp_path / "k.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE stock_klines (code TEXT, date TEXT, close REAL)")
    conn.execute("INSERT INTO stock_klines VALUES ('000010','2024-06-19',10.0)")
    conn.execute("INSERT INTO stock_klines VALUES ('000010','2024-06-20',9.5)")
    conn.commit()
    conn.close()

    calls = {"n": 0}

    def flaky(code: str):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("rate limited")
        return [("2024-06-20", 0.5, 0.0)]

    monkeypatch.setattr(mod, "_fetch_raw_events", flaky)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    events, stats = mod.build_events(db, codes=["000010"], workers=1)
    assert stats["failed"] == 0
    assert stats["with_events"] == 1
    assert len(events) == 1

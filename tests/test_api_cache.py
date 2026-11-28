"""Web 接口缓存 key 的数据版本语义测试。

历史教训: 缓存 key 只取分析库 MAX(date)。补空洞/重建期间 MAX(date) 可能不变,
于是复用了一份重建中途写入的半成品(行业接口返回 2024-01-02、只剩 1 个行业),
把脏结果当成最新数据展示。
"""

import sqlite3
import time

import pytest

from src.web import api_cache


@pytest.fixture
def db(tmp_path, monkeypatch):
    """最小分析库 + 指向它的缓存目录。"""
    path = tmp_path / "data" / "stock_analysis.db"
    path.parent.mkdir(parents=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE stock_analysis (code TEXT, date TEXT, close REAL)")
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?,?,?)",
        [("sh600519", "2026-11-27", 1472.36), ("sh600519", "2026-11-26", 1469.0)],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(api_cache, "_DB_PATH", path)
    return path


def test_key_only_changes_with_date(db):
    k1 = api_cache.make_key("sector", {})
    assert api_cache.make_key("sector", {}) == k1
    assert "2026-11-27" in k1


def test_key_changes_when_db_rewritten_same_max_date(db):
    """MAX(date) 不变但库被重写: key 必须变化, 否则会吃半成品缓存。"""
    k1 = api_cache.make_key("sector", {})
    time.sleep(1.05)  # mtime 秒级精度
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM stock_analysis")
    conn.execute("INSERT INTO stock_analysis VALUES ('sh600519','2026-11-27',1472.36)")
    conn.commit()
    conn.close()
    assert api_cache.make_key("sector", {}) != k1


def test_run_cached_recomputes_after_rewrite(db, tmp_path):
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"n": calls["n"]}

    assert api_cache.run_cached("sector", {}, compute) == {"n": 1}
    assert api_cache.run_cached("sector", {}, compute) == {"n": 1}  # 命中
    assert calls["n"] == 1

    time.sleep(1.05)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE stock_analysis SET close = 1470 WHERE date='2026-11-26'")
    conn.commit()
    conn.close()

    assert api_cache.run_cached("sector", {}, compute) == {"n": 2}  # 重写后重算
    assert calls["n"] == 2


def test_run_cached_survives_corrupt_file(db):
    key = api_cache.make_key("sector", {})
    (api_cache.cache_dir() / f"{key}.json").write_text("{not json", encoding="utf-8")
    assert api_cache.run_cached("sector", {}, lambda: {"ok": True}) == {"ok": True}


def test_clean_old_caches(tmp_path, db):
    d = api_cache.cache_dir()
    old = d / "old.json"
    old.write_text("{}", encoding="utf-8")
    import os

    os.utime(old, (time.time() - 20 * 86400, time.time() - 20 * 86400))
    assert api_cache.clean_old_caches(14) == 1
    assert not old.exists()

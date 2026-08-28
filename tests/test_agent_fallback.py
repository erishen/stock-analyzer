"""无 LLM 兜底(fallback)的单元测试: 命中意图返回真实数据, 未命中返回 None。

不依赖 LLM 凭证, 直接对 fallback 模块做自包含验证。
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest


def _load_fallback():
    """直接按文件路径加载 fallback 模块, 避免触发 agent 包重依赖。"""
    p = Path(__file__).parent.parent / "src" / "agent" / "fallback.py"
    spec = importlib.util.spec_from_file_location("agent_fallback_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def demo_db(tmp_path):
    """临时 stock_analysis 表 + 名称缓存, 模拟 seed 产物。"""
    db = tmp_path / "stock_analysis.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE stock_analysis ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, date TEXT, "
        "close REAL, change_percent REAL, rsi REAL)"
    )
    rows = [
        ("sh600000", "2026-03-18", 10.0, 1.2, 55.0),
        ("sh600519", "2026-03-18", 180.0, 3.1, 72.0),
        ("sh600036", "2026-03-18", 35.0, -2.0, 28.0),
        ("sh600000", "2026-03-19", 10.5, 5.0, 60.0),
        ("sh600519", "2026-03-19", 185.0, -1.0, 65.0),
        ("sh600036", "2026-03-19", 34.0, -3.5, 25.0),
        ("sz300750", "2026-03-19", 28.0, 2.0, 75.0),
        ("sh601318", "2026-03-19", 50.0, 0.5, 29.0),
    ]
    conn.executemany(
        "INSERT INTO stock_analysis(code,date,close,change_percent,rsi) VALUES(?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    # 名称缓存: seed 写到 db 同目录
    cache = {
        "stocks": {
            "sh600000": {"name": "Demo银行"},
            "sh600519": {"name": "Demo茅台"},
            "sh600036": {"name": "Demo招行"},
            "sz300750": {"name": "Demo新能源"},
            "sh601318": {"name": "Demo保险"},
        }
    }
    (tmp_path / "stock_info_cache.json").write_text(
        __import__("json").dumps(cache, ensure_ascii=False)
    )
    return str(db), str(tmp_path)


def test_detect_intent(demo_db):
    fb = _load_fallback()
    assert fb.detect_intent("今天涨幅最大的 10 只股票有哪些？")["kind"] == "top_gainers"
    assert fb.detect_intent("跌幅最大的10只股票")["kind"] == "top_losers"
    assert fb.detect_intent("当前 RSI 超买的股票有哪些？")["kind"] == "rsi_overbought"
    assert fb.detect_intent("RSI 超卖的股票有哪些？")["kind"] == "rsi_oversold"
    assert fb.detect_intent("帮我分析一下大盘整体走势") is None


def test_top_gainers_returns_sorted_real_data(demo_db):
    fb = _load_fallback()
    db, proj = demo_db
    r = fb.run_fallback(db, proj, "今天涨幅最大的 10 只股票有哪些？")
    assert r is not None
    assert r["success"] is True
    assert r["row_count"] == 5  # 2026-03-19 共 5 行
    # 按 change_percent 降序
    chgs = [row["change_percent"] for row in r["rows"]]
    assert chgs == sorted(chgs, reverse=True)
    # 中文名正确解析(去前缀键也能命中)
    names = {row["code"]: row["name"] for row in r["rows"]}
    assert names["sh600000"] == "Demo银行"
    assert names["sz300750"] == "Demo新能源"
    # 前端所需字段齐全
    assert r["chart"]["type"] == "bar"
    assert r["followups"]


def test_rsi_oversold_filters(demo_db):
    fb = _load_fallback()
    db, proj = demo_db
    r = fb.run_fallback(db, proj, "RSI 超卖的股票有哪些？")
    assert r["success"] is True
    # 仅 RSI < 30 的 sh600036(25) / sh601318(29) 命中
    codes = {row["code"] for row in r["rows"]}
    assert "sh600036" in codes
    assert "sh601318" in codes
    assert "sh600519" not in codes  # rsi 65


def test_unmatched_returns_none(demo_db):
    fb = _load_fallback()
    db, proj = demo_db
    assert fb.run_fallback(db, proj, "帮我分析一下大盘整体走势") is None


def test_table_without_turnover_column_ok(demo_db):
    """真实 seed 表无 turnover_rate, 兜底 SQL 不应引用它(此前 LLM 路径曾误用)。"""
    fb = _load_fallback()
    db, proj = demo_db
    r = fb.run_fallback(db, proj, "涨幅最大的股票")
    assert r is not None
    assert "turnover_rate" not in r["sql"]

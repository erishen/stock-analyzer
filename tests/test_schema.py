"""agent/schema 的股票名<->代码映射与中文名预翻译单测。

用一个临时 data/stock_info_cache.json 驱动, 不触碰真实数据文件。
"""

import json

import pytest

from agent import schema


@pytest.fixture()
def project(tmp_path):
    """构造临时 project_root, 写入一份含市场前缀的股票信息缓存。"""
    root = tmp_path / "proj"
    (root / "data").mkdir(parents=True)
    cache = {
        "stocks": {
            "sh600519": {"name": "贵州茅台"},
            "sz000858": {"name": "五粮液"},
            "sh600000": {"name": "浦发银行"},
            "bj830799": {"name": "*ST某北交所"},
        }
    }
    (root / "data" / "stock_info_cache.json").write_text(
        json.dumps(cache, ensure_ascii=False), encoding="utf-8"
    )
    return str(root)


def test_load_name_code_strips_prefix(project):
    c2n, n2c = schema.load_name_code(project)
    assert c2n["600519"] == "贵州茅台"
    assert n2c["贵州茅台"] == "600519"
    assert "sh600519" not in c2n  # 市场前缀被剥离


def test_code_from_name_exact(project):
    assert schema.code_from_name(project, "贵州茅台") == "600519"


def test_code_from_name_fuzzy_strips_suffix(project):
    # 输入带「股份」后缀, 规范化后命中「贵州茅台股份」
    assert schema.code_from_name(project, "浦发银行股份有限公司") == "600000"


def test_code_from_name_unknown_returns_input(project):
    assert schema.code_from_name(project, "不存在的股票") == "不存在的股票"


def test_translate_stock_names(project):
    out = schema.translate_stock_names(project, "今天贵州茅台涨幅怎么样？五粮液呢")
    assert "贵州茅台(代码600519)" in out
    assert "五粮液(代码000858)" in out


def test_translate_avoids_double_annotation(project):
    # 长名优先且单遍替换: 不应出现"贵州茅台(代码600519)600519"这种二次命中
    out = schema.translate_stock_names(project, "贵州茅台涨了吗")
    assert out.count("600519") == 1
    assert "贵州茅台(代码600519)" in out


def test_load_name_code_missing_file(tmp_path):
    c2n, n2c = schema.load_name_code(str(tmp_path))
    assert c2n == {} and n2c == {}


import sqlite3 as _sqlite3  # noqa: E402
from pathlib import Path as _Path  # noqa: E402


@pytest.fixture()
def partial_db(tmp_path):
    """故意缺少 amplitude/turnover_rate/change_amount 的瘦表, 模拟 demo seed。"""
    db = tmp_path / "partial.db"
    conn = _sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE stock_analysis ("
        "id INTEGER, code TEXT, date TEXT, open REAL, close REAL, high REAL, low REAL,"
        "volume REAL, amount REAL, change_percent REAL, rsi REAL)"
    )
    conn.execute(
        "INSERT INTO stock_analysis VALUES (1,'600519','2026-08-21',1700,1710,1720,1690,1000,1.7e9,1.2,65)"
    )
    conn.commit()
    conn.close()
    return str(db)


def test_describe_schema_only_lists_existing_columns(partial_db):
    """声明了但表缺失的列(amplitude/turnover_rate/change_amount)不得出现在 schema 文本。"""
    desc = schema.describe_schema(".", partial_db)
    assert "turnover_rate" not in desc
    assert "amplitude" not in desc
    assert "change_amount" not in desc
    # 真实存在的列应当出现
    assert "change_percent" in desc
    assert "rsi" in desc


def test_describe_schema_no_fabricated_columns(partial_db):
    """更严格: schema 列出的每一个 `- col:` 都必须真实存在于 PRAGMA。"""
    import re

    conn = _sqlite3.connect(partial_db)
    real = {r[1] for r in conn.execute("PRAGMA table_info(stock_analysis)")}
    conn.close()
    desc = schema.describe_schema(".", partial_db)
    mentioned = set(re.findall(r"^\s*- (\w+):", desc, re.M))
    assert mentioned <= real

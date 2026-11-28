"""PIT 标的池 / 幸存者偏差的口径测试。

验证的是"某日标的池来自行情实际存在性"这件事本身, 因此用临时 sqlite 构造
极小的行情库, 不碰真实 4.5G 数据。
"""

import sqlite3
from pathlib import Path

import pytest

from data.universe import (
    has_lifecycle,
    rebuild_lifecycle,
    survivorship_report,
    universe_as_of,
)


@pytest.fixture
def klines_db(tmp_path: Path) -> Path:
    """三只标的: A 全程在市, B 中途上市, C 中途停止更新。"""
    db = tmp_path / "stock_klines.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE stock_klines (
            code TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume REAL
        )
        """
    )
    rows = [
        ("600000", "2024-01-02"), ("600000", "2024-06-28"), ("600000", "2025-01-02"),
        ("600036", "2024-01-02"), ("600036", "2024-06-28"), ("600036", "2025-01-02"),
        ("300750", "2024-06-03"), ("300750", "2024-06-28"), ("300750", "2025-01-02"),
        ("000001", "2024-01-02"), ("000001", "2024-06-28"),
    ]
    conn.executemany(
        "INSERT INTO stock_klines (code, date, open, high, low, close, volume) "
        "VALUES (?, ?, 10, 10, 10, 10, 100)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def test_lifecycle_counts(klines_db):
    info = rebuild_lifecycle(klines_db)
    assert info["codes"] == 4
    assert info["first_day"] == "2024-01-02"
    assert info["last_day"] == "2025-01-02"
    assert has_lifecycle(klines_db)


def test_universe_as_of_excludes_not_yet_listed_and_stopped(klines_db):
    rebuild_lifecycle(klines_db)
    # 2024-06-28: 四只都在(300750 已上市, 000001 还没停)
    assert universe_as_of("2024-06-28", klines_db) == ["000001", "300750", "600000", "600036"]
    # 2024-01-02: 300750 未上市
    assert "300750" not in universe_as_of("2024-01-02", klines_db)
    # 2025-01-02: 000001 已停止更新
    assert "000001" not in universe_as_of("2025-01-02", klines_db)


def test_universe_as_of_without_lifecycle_returns_empty(klines_db):
    # 未建表时不静默当作"全市场", 而是返回空让调用方显式回退
    assert has_lifecycle(klines_db) is False
    assert universe_as_of("2024-06-28", klines_db) == []


def test_survivorship_report_numbers(klines_db):
    rebuild_lifecycle(klines_db)
    report = survivorship_report("2024-01-02", "2025-01-02", klines_db)
    assert report["ok"] is True
    assert report["total_codes"] == 4
    assert report["active_at_start"] == 3  # 300750 未上市
    assert report["active_at_end"] == 3  # 000001 已停止
    assert report["new_listings"] == 1
    assert report["new_listings_by_year"] == {"2024": 1}
    assert report["stopped_codes"] == 1
    assert report["stopped_sample"] == ["000001"]
    assert "彻底退市" in report["residual_bias_note"]


def test_survivorship_report_requires_lifecycle(klines_db):
    report = survivorship_report("2024-01-02", "2025-01-02", klines_db)
    assert report["ok"] is False
    assert "make universe" in report["error"]


def test_sector_rotation_filters_by_pit_universe(klines_db, tmp_path):
    """板块静态名单里的"未上市标的"必须被过滤掉, 且结果带快照元信息。"""
    from strategy.sector_rotation import SectorRotationAnalyzer

    rebuild_lifecycle(klines_db)
    analysis_db = tmp_path / "stock_analysis.db"
    conn = sqlite3.connect(analysis_db)
    conn.execute(
        """
        CREATE TABLE stock_analysis (
            code TEXT, date TEXT, change_percent REAL, volume REAL,
            close REAL, ma5 REAL, ma20 REAL
        )
        """
    )
    conn.executemany(
        "INSERT INTO stock_analysis (code, date, change_percent, volume, close, ma5, ma20) "
        "VALUES (?, ?, ?, 1e6, 10, 10, 9)",
        [
            ("sh600000", "2024-01-02", 1.0),
            ("sh600036", "2024-01-02", 2.0),
            ("sz300750", "2024-01-02", 3.0),  # 该日尚未上市
        ],
    )
    conn.commit()
    conn.close()

    analyzer = SectorRotationAnalyzer()
    analyzer.sector_mapping = {"测试板块": ["sh600000", "sh600036", "sz300750"]}
    info = analyzer.calculate_sector_metrics("测试板块", analysis_db, "2024-01-02")
    assert info is not None
    assert "sz300750" not in info.stocks
    assert info.avg_return == pytest.approx(0.015)

    meta = analyzer.snapshot_meta("2024-01-02", analysis_db)
    assert meta["universe_pit"] == "code_lifecycle"
    assert meta["universe_size"] == 3
    assert "静态" in meta["membership_source"]


def test_sector_analysis_result_carries_snapshot():
    from strategy.sector_rotation import SectorAnalysisResult

    result = SectorAnalysisResult(
        date="2024-01-02",
        sectors=[],
        rotations=[],
        top_sectors=[],
        bottom_sectors=[],
        market_breadth=0.0,
        snapshot={"universe_pit": "code_lifecycle"},
    )
    assert result.to_dict()["snapshot"]["universe_pit"] == "code_lifecycle"

"""data_tools/daily_update.py 的回归测试(定时任务的数据更新路径)。

data_tools/ 是本地工具、不入公开仓库(.gitignore), 所以该目录缺失时整体跳过,
保证公开仓库 `pytest` 仍然全绿。

覆盖三个曾经踩过的坑:
  1. 拉取起始日期格式: 数据源只认 YYYYMMDD, 传带横杠的会被误解析成全量拉取;
  2. 存在性分类: 源库裸 6 位 code 与分析库带前缀 code 比对前必须归一化;
  3. 失败计数: _fetch_one 的第三个返回值语义是「是否失败」, 不能当成 ok 用。
"""

import sys
from pathlib import Path

import pytest

_DATA_TOOLS = Path(__file__).resolve().parent.parent / "data_tools"
if _DATA_TOOLS.exists():
    sys.path.insert(0, str(_DATA_TOOLS))

daily_update = pytest.importorskip("daily_update", reason="data_tools/ 不存在(公开仓库)")


# ---------- Bug 3: 起始日期格式 ----------


def test_to_compact_date():
    assert daily_update.to_compact_date("2026-10-15") == "20261015"
    assert daily_update.to_compact_date("20261015") == "20261015"


def test_build_fetch_jobs_converts_to_compact():
    actives = [("600241", "2026-10-15"), ("000012", "2026-10-14")]
    assert daily_update.build_fetch_jobs(actives) == [
        ("600241", "20261015"),
        ("000012", "20261014"),
    ]


# ---------- Bug 2: 存在性分类(裸 code vs 带前缀 code) ----------


def test_classify_by_existence_normalizes_prefix():
    existing = {"sh600241", "sz000012"}
    inc, full = daily_update.classify_by_existence(["600241", "000012", "600025"], existing)
    assert inc == ["600241", "000012"]
    assert full == ["600025"]


def test_classify_by_existence_preserves_bare_codes():
    # 返回的仍是源库原始(裸) code, 供 ETL 按源库 code 抽取数据
    inc, full = daily_update.classify_by_existence(["688175"], set())
    assert inc == []
    assert full == ["688175"]


# ---------- Bug 1: 失败计数(第三个返回值是「是否失败」) ----------


def test_parallel_fetch_failure_accounting(monkeypatch, tmp_path):
    def fake_fetch_one(args):
        code = args[0]
        if code == "bad":
            return code, 0, True  # 失败
        return code, 3, False  # 成功, 3 行

    monkeypatch.setattr(daily_update, "_fetch_one", fake_fetch_one)
    jobs = [("good1", "20260101"), ("bad", "20260101"), ("good2", "20260101")]
    rows, failed = daily_update.parallel_fetch(jobs, tmp_path / "unused.db", "20261016", workers=2)
    assert rows == 6
    assert failed == ["bad"]

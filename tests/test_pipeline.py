"""agent/pipeline 的 Text2SQL 全链路单测。

用假的 LLM(monkeypatch agent.llm.chat_json)驱动「生成->执行->作答」,
在临时 SQLite 上验证成功路径与失败自纠错路径, 不触网、不动真实数据。
"""

import sqlite3

import pytest

from agent import pipeline


@pytest.fixture()
def project(tmp_path):
    """临时 project_root: 用于描述 schema, 不需要真实缓存文件。"""
    return str(tmp_path / "proj")


@pytest.fixture()
def db_path(tmp_path):
    """临时 stock_analysis 表, 含两行样例行有真实查询。"""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE stock_analysis (code TEXT, date TEXT, close REAL, change_percent REAL)"
    )
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?,?,?,?)",
        [
            ("600519", "2026-08-21", 1272.83, -1.45),
            ("600519", "2026-08-20", 1291.55, 0.61),
        ],
    )
    conn.commit()
    conn.close()
    return str(path)


def _sql_callback(calls):
    """从 SQL 生成/作答两条路径的调用里挑出 return dict。"""

    def fake_chat_json(msgs, **kwargs):
        joined = "".join(m.get("content", "") for m in msgs)
        if "请用中文回答" in joined:
            return {
                "answer": "测试回答: 共查到数据。",
                "chart": {"type": "none"},
                "questions": ["追问一", "追问二", "长于四位", "X"],  # "X" 单字符过短应被过滤
            }
        if "只输出 JSON" in joined:
            calls[0] += 1
            return {
                "sql": "SELECT code, close FROM stock_analysis LIMIT 3",
                "reasoning": "取最近收盘价",
            }
        raise AssertionError(f"未知提示词: {joined[:80]}")

    return fake_chat_json


def test_run_question_success(monkeypatch, db_path, project):
    calls = [0]
    monkeypatch.setattr("agent.llm.chat_json", _sql_callback(calls))

    res = pipeline.run_question(db_path, project, "贵州茅台近期走势如何？", history=[])
    assert res["success"] is True
    assert res["rows"][0]["code"] == "600519"
    assert res["answer"].startswith("测试回答")
    # 动态追问: 短于4字被过滤
    assert res["followups"] == ["追问一", "追问二", "长于四位"]
    assert res["chart"] is None  # type=none
    # 阶段名
    assert any(e["name"] == "text2sql" for e in res["events"])


def test_run_question_self_corrects_bad_sql(monkeypatch, db_path, project):
    calls = [0]
    REAL = "SELECT code, close FROM stock_analysis LIMIT 3"

    def fake_chat_json(msgs, **kwargs):
        joined = "".join(m.get("content", "") for m in msgs)
        if "请用中文回答" in joined:
            return {"answer": "ok", "chart": {"type": "none"}, "questions": []}
        if "只输出 JSON" in joined:
            calls[0] += 1
            # 第一次给非法写语句, 触发只读校验失败自纠错
            sql = "DELETE FROM stock_analysis" if calls[0] == 1 else REAL
            return {"sql": sql, "reasoning": "r"}
        raise AssertionError(f"未知提示词: {joined[:80]}")

    monkeypatch.setattr("agent.llm.chat_json", fake_chat_json)
    res = pipeline.run_question(db_path, project, "测试问题")
    assert res["success"] is True
    assert res["rows"][0]["code"] == "600519"
    # 记录过一次自纠错
    assert any(e["name"] == "sql_fix" for e in res["events"])


def test_run_question_fails_after_all_attempts(monkeypatch, db_path, project):
    def always_bad(msgs, **kwargs):
        joined = "".join(m.get("content", "") for m in msgs)
        if "只输出 JSON" in joined:
            return {"sql": "DELETE FROM stock_analysis", "reasoning": "r"}
        raise AssertionError(f"未知提示词: {joined[:80]}")

    monkeypatch.setattr("agent.llm.chat_json", always_bad)
    res = pipeline.run_question(db_path, project, "测试问题")
    assert res["success"] is False
    assert "只读校验" in res["message"] or "多次尝试" in res["message"]

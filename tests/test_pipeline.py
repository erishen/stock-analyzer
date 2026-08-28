"""agent/pipeline 的 Text2SQL 全链路单测。

用假的 LLM(monkeypatch agent.llm.chat_json)驱动「生成->执行->作答」,
在临时 SQLite 上验证成功路径与失败自纠错路径, 不触网、不动真实数据。
"""

import sqlite3

import pytest

from agent import pipeline


@pytest.fixture(autouse=True)
def _fake_llm_key(monkeypatch):
    """现有用例通过 monkeypatch agent.llm.chat_json 模拟已配置的 LLM。

    run_question 在无凭证时会走兜底/报错分支、不再调用 chat_json, 会让这些用例失效;
    这里注入一个 dummy key, 使「已配置 LLM」这一前置条件成立。
    """
    monkeypatch.setenv("LLM_API_KEY", "test-key-for-pipeline-tests")


@pytest.fixture()
def project(tmp_path):
    """临时 project_root: 用于描述 schema, 不需要真实缓存文件。"""
    return str(tmp_path / "proj")


@pytest.fixture()
def db_path(tmp_path):
    """临时 stock_analysis 表, 含两行样例行有真实查询(含 rsi, 供兜底 SQL 使用)。"""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE stock_analysis (code TEXT, date TEXT, close REAL, change_percent REAL, rsi REAL)")
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?,?,?,?,?)",
        [
            ("600519", "2026-08-21", 1272.83, -1.45, 40.0),
            ("600519", "2026-08-20", 1291.55, 0.61, 55.0),
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


def test_run_question_fallback_no_key(monkeypatch, db_path, project):
    """无 LLM 凭证 + 命中常见意图(涨幅 TOP) -> 走兜底, 直接返回真实数据, 不调 LLM。"""
    monkeypatch.setattr("agent.llm.get_llm_config", lambda: {"api_key": ""})
    res = pipeline.run_question(db_path, project, "今天涨幅最大的 10 只股票有哪些？")
    assert res["success"] is True
    assert res["row_count"] >= 1
    # 命中兜底分支(非 text2sql 全链路)
    assert any(e["name"] == "fallback" for e in res["events"])
    # 返回结构含前端所需字段
    assert res["chart"] and res["chart"]["type"] == "bar"
    assert res["followups"]
    assert "最新交易日" in res["answer"]


def test_run_question_no_llm_key_unmatched(monkeypatch, db_path, project):
    """无 LLM 凭证 + 未命中兜底意图 -> 返回可操作的 no_llm_key 错误, 而非笼统失败。"""
    monkeypatch.setattr("agent.llm.get_llm_config", lambda: {"api_key": ""})
    res = pipeline.run_question(db_path, project, "帮我分析一下大盘整体走势")
    assert res["success"] is False
    assert res.get("error_code") == "no_llm_key"
    assert "LLM" in res["message"]

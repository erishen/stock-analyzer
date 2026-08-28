"""Text2SQL 管线: 生成 -> 只读校验 -> 执行 -> (失败自纠错) -> 基于结果作答/出图。

复刻 work/harness/datapulse 的方法: 生成与作答两个阶段各自有独立的重试预算;
查询走只读校验, 保证任一环节模型出错都不会读写数据库。
"""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any

from . import fallback as agent_fallback
from . import llm, sqlsafety
from . import schema as sa_schema

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3   # SQL 生成/执行自纠错轮数
MAX_ANSWER_TRIES = 3  # 作答独立重试
MAX_ROWS = sqlsafety.MAX_LIMIT  # 与 sqlsafety 校验上限保持一致


class QueryFailedError(RuntimeError):
    pass


def _generate_sql(
    question: str,
    schema_text: str,
    history: list[dict],
    error: str | None = None,
    sql: str | None = None,
) -> dict:
    msgs = llm.messages()
    msgs.append({"role": "user", "content": schema_text})
    prompt = (
        "请根据上面的表结构, 为下面的问题写一条只读 SQL(SQLite 方言)。\n\n"
        "规则:\n"
        "1. 只允许一条只读 SELECT 查询, 禁止写操作。\n"
        "2. 聚合列务必加别名, 如 AS cnt / total / avg_ret。\n"
        "3. 必须加 LIMIT(常见 20, 最多 200)。\n"
        "4. date 是字符串 'YYYY-MM-DD', 比较用字符串比较(如 date >= '2026-01-01')。\n"
        "5. 最新数据日期请以 schema 中给出的最大日期为准。\n"
        "6. 只用表里明确存在的字段, 拿不准就先用 SELECT * LIMIT 3 探一下。\n"
    )
    if error:
        prompt += f"\n你上一次生成的 SQL 未通过校验或执行失败, 请修正。\n错误: {error}\n上次 SQL: {sql}\n"
    for h in history[-6:]:
        if h.get("role") in ("user", "assistant"):
            prompt += f"\n{h['role']}: {h.get('content', '')}"
    prompt += f"\n\n问题: {question}\n\n只输出 JSON: {{\"sql\": \"...\", \"reasoning\": \"...\"}}"
    msgs.append({"role": "user", "content": prompt})
    try:
        plan = llm.chat_json(msgs)
    except Exception as e:
        raise QueryFailedError(f"SQL 生成失败: {e}") from e
    plan = plan or {}
    if not plan.get("sql"):
        raise QueryFailedError("模型未返回 SQL 语句")
    return plan


def _execute(db_path: str, sql: str) -> dict[str, Any]:
    ok, err = sqlsafety.validate_readonly(sql)
    if not ok:
        raise QueryFailedError(f"只读校验未通过: {err}")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
    rows, truncated = sqlsafety.enforce_max_rows(rows, MAX_ROWS)
    columns = list(rows[0].keys()) if rows else []
    return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}


def _finalize(
    question: str,
    sql: str,
    columns: list[str],
    rows: list[dict],
    history: list[dict],
) -> dict:
    msgs = llm.messages()
    msgs.append({"role": "system",
                 "content": "你是严谨的A股分析助手, 基于真实查询结果用中文作答。"
                            "回答要具体、有结论, 不编造数据。若结果包含列可用于可视化, 给出 chart 建议。"
                            "最后结合本次结果给出 2-3 个用户可以继续追问的问题(followups)。"})
    user = (
        f"问题: {question}\n\n执行的 SQL:\n{sql}\n\n查询结果(列: {', '.join(columns)}):\n"
    )
    for i, r in enumerate(rows[:40]):
        user += f"{i + 1}. {r}\n"
    if len(rows) > 40:
        user += f"... 共 {len(rows)} 行, 已略去部分\n"
    user += (
        "\n请用中文回答: 先给结论, 再说依据和关键数字。"
        "若数据适合做图, 额外给出 chart 对象 "
        "(格式: {\"type\": \"bar|line|pie\", \"title\": \"...\", \"x\": \"列名\", \"y\": [\"列名\"]}), "
        "不适合则给 {\"type\": \"none\"}。\n"
        "另请给出 questions: 针对本次结果的 2-3 条简短中文追问(不是重复问题, 引导用户深入分析/对比/看细节)。\n"
        "只输出 JSON: {\"answer\": \"...\", \"chart\": {...}, \"questions\": [\"追问1\", \"追问2\", \"追问3\"]}"
    )
    msgs.append({"role": "user", "content": user})
    try:
        out = llm.chat_json(msgs)
    except Exception as e:
        raise QueryFailedError(f"作答失败: {e}") from e
    out = out or {}
    answer = (out.get("answer") or "").strip()
    if not answer:
        raise QueryFailedError("模型未返回作答文本")
    chart = out.get("chart")
    chart = {**chart, "dataset": rows[:100]} if isinstance(chart, dict) and chart.get("type") not in ("none",) else None
    # 动态追问: 容错解析, 只保留简短非空中文, 最多 3 条
    followups: list[str] = []
    raw_fu = out.get("questions", out.get("followups", []))
    if isinstance(raw_fu, str):
        raw_fu = [raw_fu]
    if isinstance(raw_fu, list):
        for item in raw_fu:
            if isinstance(item, str):
                t = item.strip()
            elif isinstance(item, dict):
                t = str(item.get("question") or item.get("text") or item.get("q") or "").strip()
            else:
                t = ""
            if 2 <= len(t) <= 80 and t not in followups:
                followups.append(t)
            if len(followups) >= 3:
                break
    return {"answer": answer, "chart": chart, "followups": followups}


def run_question(
    db_path: str,
    project_root: str,
    question: str,
    history: list[dict] | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """执行一次 Text2SQL 问答, 返回结构化结果。

    context: 可选的附加上下文(如模拟仓持仓快照), 会注入到生成提示词。
    """
    history = history or []

    # 未配置 LLM 凭证时(如公开 Demo 部署), 优先走确定性兜底, 让常见结构化问题
    # (涨幅/跌幅 TOP N、RSI 超买/超卖) 也能返回真实数据, 而不是报"查询失败"。
    # 兜底未命中时给出可操作的错误提示, 引导用户去配置凭证。
    if not llm.get_llm_config().get("api_key"):
        fb = agent_fallback.run_fallback(db_path, project_root, question)
        if fb is not None:
            return fb
        return {
            "success": False,
            "error_code": "no_llm_key",
            "message": (
                "未配置 LLM 凭证，AI 选股无法调用大模型。"
                "本地：在「设置」中填写 API Key；"
                "云端部署：在环境变量设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 后重新部署。"
            ),
            "events": [],
        }

    schema_text = sa_schema.describe_schema(project_root, db_path)
    if context:
        schema_text += "\n\n【额外背景 - 用户当前模拟仓持仓, 供你分析时参考】\n" + context
    events: list[dict] = []

    # 把问题里的股票中文名标注上代码, 减少 LLM 生成/作答时对股票代码的瞎猜
    question = sa_schema.translate_stock_names(project_root, question)

    last_error: str | None = None
    last_sql: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            plan = _generate_sql(question, schema_text, history, last_error, last_sql)
            last_sql = plan.get("sql")
            ok, verr = sqlsafety.validate_readonly(last_sql)
            if not ok:
                raise QueryFailedError(f"只读校验未通过: {verr}")
            data = _execute(db_path, last_sql)
            # 若查询结果含 code 列, 实时补充中文名(来自 stock_info_cache.json), 便于展示与作答
            if any(c == "code" for c in data["columns"]):
                c2n, _ = sa_schema.load_name_code(project_root)
                if c2n:
                    enriched: list[dict] = []
                    for r in data["rows"]:
                        nr = dict(r)
                        if "code" in nr and "name" not in nr:
                            # c2n 的键已去市场前缀(sh/sz/bj), 查表前需对齐
                            raw_code = str(nr["code"])
                            clean = re.sub(r"^(sh|sz|bj)", "", raw_code)
                            nr["name"] = c2n.get(clean, nr["code"])
                        enriched.append(nr)
                    if enriched:
                        data["rows"] = enriched
                        if "name" not in data["columns"]:
                            data["columns"] = ["name"] + data["columns"]
            events.append({
                "name": "text2sql",
                "attempt": attempt,
                "sql": last_sql,
                "reasoning": plan.get("reasoning", ""),
                "row_count": data["row_count"],
            })
            answer_err: str | None = None
            for _ in range(MAX_ANSWER_TRIES):
                try:
                    fin = _finalize(question, last_sql, data["columns"], data["rows"], history)
                    return {
                        "success": True,
                        "sql": last_sql,
                        "reasoning": plan.get("reasoning", ""),
                        "columns": data["columns"],
                        "rows": data["rows"],
                        "row_count": data["row_count"],
                        "truncated": data["truncated"],
                        "answer": fin["answer"],
                        "chart": fin["chart"],
                        "followups": fin.get("followups", []),
                        "events": events,
                    }
                except QueryFailedError as e:
                    answer_err = str(e)
            raise QueryFailedError(f"作答阶段失败: {answer_err}")
        except QueryFailedError as e:
            last_error = str(e)
            events.append({"name": "sql_fix", "attempt": attempt + 1, "error": last_error})

    return {"success": False, "message": f"多次尝试后仍未成功: {last_error}", "events": events}

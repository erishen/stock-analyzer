"""无 LLM 兜底: 对常见结构化问题(涨幅/跌幅排行、RSI 超买/超卖)直接跑只读 SQL 作答。

用于未配置 LLM 凭证的部署(如公开 Demo), 让预设的「今日涨幅 TOP10」等问题也能返回真实数据,
而不是报"查询失败"。

设计原则:
- 只有在「命中已知意图」时才返回结果; 未命中返回 None, 由调用方继续走 LLM 路径。
- 只读: 只发 SELECT, 不写库。
- 自包含: 仅依赖标准库 + sqlite3, 不 import 任何需要 LLM/第三方依赖的模块。
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

# 预编译意图正则(按优先级排列; 命中第一个即采用)
_INTENTS: list[tuple[str, re.Pattern[str]]] = [
    ("top_gainers", re.compile(r"涨幅最大|涨得最多|涨幅前|涨幅排行|涨幅榜|领涨|涨得最好|涨幅top|涨幅排名")),
    ("top_losers", re.compile(r"跌幅最大|跌得最多|跌幅前|跌幅排行|跌幅榜|领跌|跌得最狠|跌幅top|跌幅排名")),
    ("rsi_overbought", re.compile(r"rsi\s*超买|超买")),
    ("rsi_oversold", re.compile(r"rsi\s*超卖|超卖")),
]

# 各意图默认排序字段与过滤条件
_SPEC: dict[str, dict[str, str]] = {
    "top_gainers": {"order": "ORDER BY change_percent DESC", "where": ""},
    "top_losers": {"order": "ORDER BY change_percent ASC", "where": ""},
    "rsi_overbought": {"order": "ORDER BY rsi DESC", "where": "AND rsi > 70"},
    "rsi_oversold": {"order": "ORDER BY rsi ASC", "where": "AND rsi < 30"},
}


def _extract_n(question: str, default: int = 10) -> int:
    """从问句中抽取数量 N (如「10 只」「TOP10」), 缺省 10, 夹在 [1,200]。"""
    m = re.search(r"(\d+)\s*只", question)
    if not m:
        m = re.search(r"top\s*(\d+)", question, re.I)
    if m:
        return max(1, min(int(m.group(1)), 200))
    return default


def detect_intent(question: str) -> dict[str, Any] | None:
    """识别已知结构化意图; 未命中返回 None。"""
    if not question or not question.strip():
        return None
    for kind, rx in _INTENTS:
        if rx.search(question):
            return {"kind": kind, "n": _extract_n(question)}
    return None


def _latest_date(db_path: str) -> str | None:
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20) as conn:
            return conn.execute("SELECT MAX(date) FROM stock_analysis").fetchone()[0]
    except Exception:
        return None


def _load_names(db_path: str, project_root: str) -> dict[str, str]:
    """加载 code->中文名 映射。

    seed 把缓存写在 db 同目录; sa_schema 读 project_root/data。两处都试, 提高健壮性。
    """
    candidates = [
        Path(db_path).parent / "stock_info_cache.json",
        Path(project_root) / "data" / "stock_info_cache.json",
    ]
    for p in candidates:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        stocks = (data.get("stocks") or {}) if isinstance(data, dict) else {}
        mapping: dict[str, str] = {}
        for code, info in stocks.items():
            name = (info or {}).get("name", "")
            if not name:
                continue
            raw = str(code)
            mapping[raw] = name  # 原始键(如 sh600000)
            clean = re.sub(r"^(sh|sz|bj)", "", raw)
            if clean:
                mapping[clean] = name  # 去前缀键(如 600000)
        if mapping:
            return mapping
    return {}


def _build_rows(db_path: str, spec: dict[str, Any]) -> tuple[str, list[str], list[dict]]:
    kind = spec["kind"]
    n = spec["n"]
    s = _SPEC[kind]
    sql = (
        "SELECT code, date, close, change_percent, rsi "
        f"FROM stock_analysis "
        f"WHERE date = (SELECT MAX(date) FROM stock_analysis) {s['where']} "
        f"{s['order']} LIMIT {n}"
    )
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(sql).fetchall()]
    columns = ["name", "code", "date", "close", "change_percent", "rsi"]
    return sql, columns, rows


def _followups(kind: str) -> list[str]:
    if kind == "top_gainers":
        return ["跌幅最大的 10 只股票有哪些？", "当前 RSI 超买的股票有哪些？", "这些股票的 K 线走势偏多还是偏空？"]
    if kind == "top_losers":
        return ["涨幅最大的 10 只股票有哪些？", "当前 RSI 超卖的股票有哪些？", "这些股票是否出现止跌信号？"]
    if kind == "rsi_overbought":
        return ["涨幅最大的 10 只股票有哪些？", "RSI 超卖的股票有哪些？", "这些超买股 MACD 是否同步顶背离？"]
    return ["涨幅最大的 10 只股票有哪些？", "RSI 超买的股票有哪些？", "我的持仓现在表现如何？"]


def run_fallback(db_path: str, project_root: str, question: str) -> dict[str, Any] | None:
    """命中已知意图时返回结构化结果(与 agent_pipeline.run_question 的返回结构一致);
    未命中或执行失败返回 None。"""
    spec = detect_intent(question)
    if spec is None:
        return None
    latest = _latest_date(db_path)
    if not latest:
        return None

    names = _load_names(db_path, project_root)
    try:
        sql, columns, rows = _build_rows(db_path, spec)
    except Exception:
        return None

    kind = spec["kind"]
    if not rows:
        answer = (
            f"在最新交易日（{latest}）未找到符合条件的股票。\n\n"
            "> 数据来自演示库（模拟生成），仅用于功能演示。"
        )
        chart = None
    else:
        # 注入中文名(放在第一列)
        for r in rows:
            r["name"] = names.get(str(r["code"]), r["code"])
        top, bottom = rows[0], rows[-1]
        if kind in ("top_gainers", "top_losers"):
            label = "涨幅" if kind == "top_gainers" else "跌幅"
            answer = (
                f"最新交易日（{latest}）样本内{label}最大的 {len(rows)} 只股票如下：\n"
                f"- 居首：{top['name']}（{top['code']}），{label} {top['change_percent']}%\n"
                f"- 末位：{bottom['name']}（{bottom['code']}），{label} {bottom['change_percent']}%\n\n"
                "> 数据来自演示库（模拟生成），仅用于功能演示。"
            )
            yfield = "change_percent"
            title = f"最新交易日{'涨幅' if kind == 'top_gainers' else '跌幅'} TOP{len(rows)}"
        else:
            cond = "超买(>70)" if kind == "rsi_overbought" else "超卖(<30)"
            answer = (
                f"最新交易日（{latest}）RSI{cond}的股票共 {len(rows)} 只：\n"
                f"- 居首：{top['name']}（{top['code']}），RSI {top['rsi']}\n\n"
                "> 数据来自演示库（模拟生成），仅用于功能演示。"
            )
            yfield = "rsi"
            title = f"最新交易日 RSI{cond} TOP{len(rows)}"
        chart = {"type": "bar", "title": title, "x": "name", "y": [yfield], "dataset": rows}

    return {
        "success": True,
        "sql": sql,
        "reasoning": "无 LLM 兜底：命中常见结构化意图，直接跑只读 SQL，无需调用大模型。",
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": False,
        "answer": answer,
        "chart": chart,
        "followups": _followups(kind),
        "events": [{"name": "fallback", "intent": kind, "row_count": len(rows)}],
    }

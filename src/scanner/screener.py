"""
Custom Rule Screener for Stock Analyzer.
自定义规则选股器 - 基于技术指标字段做 AND 条件筛选(全部满足才命中)。

字段白名单与中文注释复用 agent/schema.COLUMN_HINTS; 用户可挑任意技术字段
配合运算符(> < >= <= = !=)与数值, 从前一天每只股票的最近一行数据中筛选。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from data.asset import ASSET_FIELDS

logger = logging.getLogger(__name__)

# 数值运算符白名单
OPS = (">", "<", ">=", "<=", "=", "!=")

# 不允许作为条件的标识列
_ID_COLS = {"id", "code", "date", "created_at"}


class ScreenerCondition:
    """单条筛选手条件: field op value (全部 AND 匹配)"""

    def __init__(self, field: str = "", op: str = ">", value: float = 0.0):
        self.field = field
        self.op = op
        self.value = value

    @staticmethod
    def from_dict(d: dict) -> ScreenerCondition:
        return ScreenerCondition(
            field=str(d.get("field") or "").strip(),
            op=str(d.get("op") or ">").strip(),
            value=float(d.get("value", 0) or 0),
        )


def _field_labels(db_path: Path) -> dict[str, str]:
    """内省 stock_analysis 数值字段, 返回 {column: 中文注释}。"""
    from agent.schema import COLUMN_HINTS

    labels: dict[str, str] = {}
    with sqlite3.connect(db_path) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(stock_analysis)").fetchall()]
    for c in cols:
        if c in _ID_COLS:
            continue
        labels[c] = COLUMN_HINTS.get(c, c)
    return labels


def _asset_fields() -> dict[str, str]:
    """资产 vs 技术字段分组标签: 返回 {field: '资产' | '技术'}。"""
    from data.asset import ASSET_FIELDS

    return {f: "资产" for f in ASSET_FIELDS}


def list_fields(db_path: Path) -> list[dict[str, str]]:
    """返回可选字段列表 [{field, label, group}], 供前端下拉使用。"""
    base = [
        {"field": f, "label": l, "group": "技术"}
        for f, l in _field_labels(db_path).items()
    ]
    asset = [
        {"field": f, "label": l, "group": "资产"}
        for f, l in ASSET_FIELDS.items()
    ]
    return base + asset


def _build_filter(cols: list[str], conds: list[ScreenerCondition]) -> tuple[list[tuple], tuple]:
    """
    校验条件并生成 Python filter 闭包。
    返回 (valid_conditions, filter_table)。field 白名单校验, value 转 float。
    """
    valid: list[ScreenerCondition] = []
    colset = set(cols)

    def _fn(row: dict) -> bool:
        for c in valid:
            raw = row.get(c.field)
            if raw is None:
                return False
            try:
                v = float(raw)
            except (TypeError, ValueError):
                return False
            if c.op == ">" and not (v > c.value):
                return False
            if c.op == "<" and not (v < c.value):
                return False
            if c.op == ">=" and not (v >= c.value):
                return False
            if c.op == "<=" and not (v <= c.value):
                return False
            if c.op == "=" and v != c.value:
                return False
            if c.op == "!=" and v == c.value:
                return False
        return True

    for c in conds:
        if not c.field or c.field not in colset:
            raise ValueError(f"未知字段: {c.field}")
        if c.op not in OPS:
            raise ValueError(f"不支持的运算符: {c.op}")
        valid.append(c)
    return valid, _fn


def scan(
    db_path: Path,
    conditions: list[ScreenerCondition] | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_field: str = "change_percent",
    sort_dir: str = "desc",
) -> dict:
    """
    按 AND 条件筛选全市场(每只股票取最近一天数据)。
    返回 {total, date, items:[{code,name,...最新字段}]}。
    limit/offset 用于分页: items 取 [offset, offset+limit)。
    """
    from data import get_stock_name

    conditions = conditions or []

    # 加载资产快照(code -> 资产字段dict), 与技术字段合并后统一筛选
    asset_map: dict[str, dict] = {}
    try:
        from data.asset import load_snapshot

        asset_snap = load_snapshot()
        asset_map = {a["code"]: a for a in asset_snap.get("items", [])}
    except Exception:
        asset_map = {}

    with sqlite3.connect(db_path) as conn:
        stock_cols = [r[1] for r in conn.execute("PRAGMA table_info(stock_analysis)").fetchall()]
        # 实际校验改用合并后的字段集合(技术 + 资产)
        merged_cols = set(stock_cols) | set(ASSET_FIELDS.keys())
        _build_filter(list(merged_cols), conditions)  # 校验 field 合法/op 合法

        # 每只股票最近一行(可能暂停上市导致各股最新日期不同)
        rows = conn.execute(
            """
            SELECT s.* FROM stock_analysis s
            JOIN (
                SELECT code, MAX(date) AS d FROM stock_analysis GROUP BY code
            ) m ON s.code = m.code AND s.date = m.d
            """
        ).fetchall()

    items: list[dict] = []
    for r in rows:
        row = dict(zip(stock_cols, r, strict=True))
        code = row.get("code", "")
        # 合并资产字段
        asset = asset_map.get(code)
        if asset:
            for f in ASSET_FIELDS:
                row[f] = asset.get(f)
        # 用合并字段做 AND 过滤
        if conditions and not _filter_conds(conditions, row):
            continue
        row.pop("id", None)
        row.pop("created_at", None)
        row["name"] = get_stock_name(code)
        items.append(row)

    if sort_field and sort_field in merged_cols:
        reverse = sort_dir == "desc"
        items.sort(key=lambda x: _safe_num(x.get(sort_field)), reverse=reverse)

    return {
        "total": len(items),
        "date": rows[0][stock_cols.index("date")] if rows else "",
        "items": items[offset : offset + limit],
    }


def _filter_conds(conds: list[ScreenerCondition], row: dict) -> bool:
    """对已合并的 row dict 应用全部 AND 条件。"""
    for c in conds:
        raw = row.get(c.field)
        if raw is None:
            return False
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return False
        if c.op == ">" and not (v > c.value):
            return False
        if c.op == "<" and not (v < c.value):
            return False
        if c.op == ">=" and not (v >= c.value):
            return False
        if c.op == "<=" and not (v <= c.value):
            return False
        if c.op == "=" and v != c.value:
            return False
        if c.op == "!=" and v == c.value:
            return False
    return True


def _safe_num(v):
    try:
        return float(v) if v is not None else float("-inf")
    except (TypeError, ValueError):
        return float("-inf")

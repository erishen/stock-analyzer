"""SQL 只读安全校验: 只放行单条只读查询, 禁止任何写操作, 强制 LIMIT。

对应 DataPulse 的只读安全设计 —— Agent 永远只能查, 不能改数据。
"""

from __future__ import annotations

import re

_SUPERFLUOUS_TAIL = re.compile(r"\s*;[\s;]*$")
_SQL_COMMENT = re.compile(r"--.*?$|/\*.*?\*/", re.S | re.M)
_WORD = re.compile(r"[A-Za-z_]\w*")
_LEAD_KEYWORD = re.compile(r"^\s*(SELECT|WITH|VALUES|EXPLAIN)\b", re.I)

# 单次查询可返回的行数上限, 与 pipeline.MAX_ROWS 保持一致
MAX_LIMIT = 200

# 任何语句中出现即拒绝的危险关键字
_BLOCKED = [
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "truncate",
    "attach",
    "detach",
    "vacuum",
    "pragma",
    "reindex",
    "commit",
    "rollback",
    "delete",
    "writefile",
    "load_extension",
]
# 常与提权/读取文件相关, 直接拒绝
_BLOCKED_FUNCS = ["glob(", "load_extension", "readfile", "writefile"]


def sanitize_statement(sql: str) -> str:
    """剥掉注释、去空白、去尾部多余分号, 返回规范化的单条语句。"""
    s = _SQL_COMMENT.sub(" ", sql)
    s = _SUPERFLUOUS_TAIL.sub("", s)
    # 去掉最外层可能的首个分号前的残余(只允许单条)
    return s.strip()


def _pos(text: str) -> int:
    """按行给出错误提示用的位置。"""
    return 0


def validate_readonly(sql: str) -> tuple[bool, str]:
    """校验是否为安全的只读单条查询。返回 (ok, error)。"""
    stmt = sql
    if not stmt or not stmt.strip():
        return False, "SQL 为空"

    stmt = sanitize_statement(stmt)
    # 规范化大小写统一检测
    lower = stmt.lower()

    # 1) 必须是一条: 去掉注释/结尾分号后, 内部不能再出现分号
    body = _SUPERFLUOUS_TAIL.sub("", stmt).strip()
    if ";" in body:
        return False, "只允许单条查询, 发现多余分号"
    # 2) 必须以 SELECT / WITH 开头 (只读)
    if not _LEAD_KEYWORD.match(stmt):
        return False, "非只读语句: 必须以 SELECT 或 WITH 开头"
    # 3) 危险关键字
    for kw in _BLOCKED:
        if re.search(rf"\b{kw}\b", lower):
            return False, f"检测到危险关键字 {kw.upper()}"
    for f in _BLOCKED_FUNCS:
        if f in lower:
            return False, f"检测到被禁止的函数 {f}"
    # 4) 强制 LIMIT
    if not re.search(r"\blimit\s+\d+", lower):
        return False, "查询必须包含 LIMIT n"
    n = re.search(r"limit\s+(\d+)", lower)
    if n and int(n.group(1)) > MAX_LIMIT:
        return False, f"LIMIT 不能超过 {MAX_LIMIT}"
    # 5) 禁止子查询里偷偷写文件的 pragma / 双分号已被拦截
    return True, ""


def enforce_max_rows(rows: list, limit: int = 200) -> tuple[list, bool]:
    """截断结果集, 返回 (截断后, 是否截断)。"""
    if len(rows) <= limit:
        return rows, False
    return rows[:limit], True

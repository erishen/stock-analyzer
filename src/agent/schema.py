"""stock_analysis 表的 schema 内省与中文注释, 供 Text2SQL 生成提示词使用。

同时提供股票中文名 <=> code 的映射(基于 data/stock_info_cache.json), 方便 Agent
把用户口中的「贵州茅台」翻译成 SQL 里的 code 条件。
"""

from __future__ import annotations

import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

# 关键列的中文注释, 提示模型如何处理数值含义与涨跌方向
COLUMN_HINTS: dict[str, str] = {
    "code": "股票代码, 如 '600519'(6/0/3开头为A股, 8/4开头为北交所), 查询务必加引号",
    "date": "交易日, 字符串格式 'YYYY-MM-DD'",
    "open": "开盘价", "close": "收盘价", "high": "最高价", "low": "最低价",
    "volume": "成交量(手)", "amount": "成交额(元)",
    "amplitude": "振幅%", "change_percent": "日涨跌幅%(正=上涨)", "turnover_rate": "换手率%",
    "ma5": "5日均线", "ma10": "10日均线", "ma20": "20日均线", "ma60": "60日均线",
    "close_ma5_ratio": "收盘价/MA5, >1 在5日线上方",
    "close_ma20_ratio": "收盘价/MA20, >1 在20日线上方(中期偏多)",
    "ema12": "12日指数均线", "ema26": "26日指数均线",
    "macd": "MACD 快线 DIF", "macd_signal": "MACD 慢线 DEA",
    "macd_hist": "MACD 柱(MACD-DEA), 红涨绿跌", "macd_cross": "1=金叉, -1=死叉, 0=无",
    "rsi": "RSI(0-100), >70 超买, <30 超卖", "rsi_overbought": "RSI 超买标记(1/0)",
    "rsi_oversold": "RSI 超卖标记(1/0)",
    "boll_mid": "布林中轨(20日均线)", "boll_upper": "布林上轨", "boll_lower": "布林下轨",
    "boll_width": "布林带宽度", "boll_position": "收盘价在布林带中的位置(0-1)",
    "kdj_k": "KDJ K值", "kdj_d": "KDJ D值", "kdj_j": "KDJ J值", "kdj_cross": "1=金叉, -1=死叉",
    "atr": "真实波幅", "atr_ratio": "ATR/收盘价(波动幅度占比)",
    "obv": "能量潮", "obv_ma10": "OBV 10日均线", "obv_signal": "OBV 信号(1/-1/0)",
    "williams_r": "威廉指标(-100~0)", "williams_overbought": "超买标记", "williams_oversold": "超卖标记",
    "momentum_5d": "5日动量(涨跌幅%)", "momentum_10d": "10日动量%", "momentum_20d": "20日动量%",
    "roc_10": "10日变动率%", "roc_20": "20日变动率%",
    "pct_change": "区间涨跌幅%",
    "volatility_5d": "5日波动率", "volatility_10d": "10日波动率", "volatility_20d": "20日波动率",
    "high_low_ratio": "最高/最低比", "close_open_ratio": "收盘/开盘比",
    "upper_shadow": "上影线长", "lower_shadow": "下影线长", "body_size": "K线实体长度",
}

BASE_COLS = [
    "code", "date", "open", "close", "high", "low", "volume", "amount",
    "amplitude", "change_percent", "change_amount", "turnover_rate",
]


def _stock_info_path(project_root: Path) -> Path:
    return project_root / "data" / "stock_info_cache.json"


@lru_cache(maxsize=1)
def load_name_code(project_root: str) -> tuple[dict[str, str], dict[str, str]]:
    """返回 (code_to_name, name_to_code)。失败时返回空映射。

    code 统一去掉 sh/sz/bj 市场前缀, 与 stock_analysis 主表内存储的纯6位保持一致。
    """
    p = _stock_info_path(Path(project_root))
    if not p.exists():
        return {}, {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        stocks = data.get("stocks", {}) if isinstance(data, dict) else {}
        c2n, n2c = {}, {}
        for code, info in stocks.items():
            name = (info or {}).get("name", "")
            clean = re.sub(r"^(sh|sz|bj)", "", code)
            if not clean or not name:
                continue
            c2n[clean] = name
            n2c[name] = clean  # 同名覆盖取最后一个
        return c2n, n2c
    except Exception:  # pragma: no cover
        return {}, {}


def code_from_name(project_root: str, name: str) -> str:
    """中文名 -> code。支持精确匹配与常见命名的模糊匹配, 找不到原样返回。"""
    name = (name or "").strip()
    if not name:
        return name
    c2n, n2c = load_name_code(project_root)
    if name in n2c:
        return n2c[name]

    # 规范化: 去掉空白与常见后缀, 便于模糊匹配
    def _norm(s: str) -> str:
        s = re.sub(r"\s+", "", s)
        for suf in ("集团有限公司", "股份有限公司", "股份有限公司", "集团", "股份", "有限", "公司", "*ST", "ST"):
            s = s.replace(suf, "")
        return s

    target = _norm(name)
    if target:
        # 1) 规范化后精确匹配
        for code, n in c2n.items():
            if _norm(n) == target:
                return code
        # 2) 包含匹配: 输入是股票名的子串或反之
        for code, n in c2n.items():
            if n and (target in n or n in target):
                return code
    return name


def translate_stock_names(project_root: str, text: str) -> str:
    """把句子里能识别的股票中文名替换为 code, 减少 LLM 生成 SQL 时的瞎猜。

    例如「今天贵州茅台涨幅」-> 「今天贵州茅台(代码600519)涨幅」。
    用一次编译的交替正则单遍替换, 长名优先, 避免子串二次命中与顺序错乱。
    """
    if not text:
        return text
    c2n, _ = load_name_code(project_root)
    if not c2n:
        return text

    # 长度去重 -> 按长度降序
    uniq: dict[str, str] = {}
    for code, n in c2n.items():
        cur = uniq.get(n)
        if cur is None or code < cur:
            uniq[n] = code
    names = sorted(uniq.keys(), key=len, reverse=True)

    # 一次编译的交替正则, 单遍替换 (长名在前, re 对同一位置取首个匹配分支)
    pattern = re.compile("|".join(re.escape(n) for n in names))
    def _rep(m):
        return f"{m.group(0)}(代码{uniq[m.group(0)]})"
    return pattern.sub(_rep, text)


@lru_cache(maxsize=4)
def describe_schema(project_root: str, db_path: str) -> str:
    """内省表结构与数据概览, 生成给模型看的中文 schema 文本。

    结果缓存(maxsize=4): 字段结构静态, 仅日期/条数随 ETL 更新而滞后(最多到下次
    缓存失效或每日 ETL 后清缓存); 对 Text2SQL 生成影响很小, 换取高频问答时省去重复 DB 内省。
    """
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("PRAGMA table_info(stock_analysis)")
        cols = [r[1] for r in cur.fetchall()]
        row = conn.execute(
            "SELECT COUNT(DISTINCT code), COUNT(*), MIN(date), MAX(date) "
            "FROM stock_analysis"
        ).fetchone()
    stock_count, total_rows, min_date, max_date = row

    indicator_cols = [c for c in cols if c not in BASE_COLS and c not in ("id", "created_at")]
    known = [(c, COLUMN_HINTS.get(c)) for c in indicator_cols]

    lines: list[str] = []
    lines.append("【数据表】 stock_analysis —— A股日频行情与技术指标, 每行 = 某只股票某一天的数据。")
    lines.append(f"共 {stock_count} 只股票, {total_rows:,} 条记录, 日期范围 {min_date} ~ {max_date}。")
    lines.append("")
    lines.append("常用字段:")
    for c in BASE_COLS:
        hint = COLUMN_HINTS.get(c, "")
        lines.append(f"  - {c}: {hint}")
    lines.append("")
    lines.append("技术指标字段(选股/诊断时可用):")
    used = 0
    for c, hint in known:
        if hint:
            lines.append(f"  - {c}: {hint}")
            used += 1
    lines.append(f"(共列出 {used} 个已注释指标字段)")
    lines.append("")
    lines.append("查询建议:")
    lines.append("  - code 用单引号, 例如 WHERE code='600519'")
    lines.append("  - 股票用中文名提及时, 先自行换算为代码(如 贵州茅台=600519), 用 code 条件查询")
    lines.append("  - 时间序列查询默认给最近一个/几个交易日, 数据最大日期为 " + str(max_date))
    lines.append("  - 需要股票名称时, 可用常见映射: 贵州茅台=600519, 五粮液=000858, "
                 "宁德时代=300750, 比亚迪=002594, 平安银行=000001, 贵州茅台=600519")
    return "\n".join(lines)


def stock_name(code: str, project_root: str) -> str:
    c2n, _ = load_name_code(project_root)
    return c2n.get(code, code)

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

# 演示库把真实标的脱敏为 DemoXX 占位名, 但用户/LLM 仍习惯用真实名(如"茅台""贵州茅台")提问。
# 这里提供「真实名(含常见简称) -> 演示库代码」的别名表, 让自然语言查询能命中演示数据,
# 而展示名仍保持 DemoXX 脱敏风格(不改 seed 数据)。键为脱敏占位名, 值为该占位名对应的真实名别名列表。
DEMO_REALNAME_ALIASES: dict[str, list[str]] = {
    "sh600000": ["浦发银行", "浦发", "上海浦东发展银行"],
    "sh600519": ["贵州茅台", "茅台", "茅台酒"],
    "sh600036": ["招商银行", "招行", "招商"],
    "sz000001": ["平安银行", "平安", "深圳平安银行"],
    "sh601318": ["中国平安", "平安保险", "平安保险集团"],
    "sh600030": ["中信证券", "中信", "中信证券股份"],
    "sz002415": ["海康威视", "海康", "杭州海康威视"],
    "sh600196": ["复星医药", "复星", "上海复星医药"],
    "sh600887": ["伊利股份", "伊利", "内蒙古伊利"],
    "sz300750": ["宁德时代", "宁德", "CATL", "宁德时代新能源"],
    "sh600585": ["海螺水泥", "海螺", "安徽海螺水泥"],
    "sz000002": ["万科", "万科A", "万科企业", "深圳万科"],
}

# 关键列的中文注释, 提示模型如何处理数值含义与涨跌方向
COLUMN_HINTS: dict[str, str] = {
    "code": "股票代码, 如 '600519'(6/0/3开头为A股, 8/4开头为北交所), 查询务必加引号",
    "date": "交易日, 字符串格式 'YYYY-MM-DD'",
    "open": "开盘价",
    "close": "收盘价",
    "high": "最高价",
    "low": "最低价",
    "volume": "成交量(手)",
    "amount": "成交额(元)",
    "amplitude": "振幅%",
    "change_percent": "日涨跌幅%(正=上涨)",
    "turnover_rate": "换手率%",
    "ma5": "5日均线",
    "ma10": "10日均线",
    "ma20": "20日均线",
    "ma60": "60日均线",
    "ma5_ratio": "收盘价/MA5, >1 在5日线上方",
    "ma10_ratio": "收盘价/MA10",
    "ma20_ratio": "收盘价/MA20, >1 在20日线上方(中期偏多)",
    "ma60_ratio": "收盘价/MA60",
    "close_ma5_ratio": "收盘价/MA5, >1 在5日线上方",
    "close_ma20_ratio": "收盘价/MA20, >1 在20日线上方(中期偏多)",
    "ema12": "12日指数均线",
    "ema26": "26日指数均线",
    "macd": "MACD 快线 DIF",
    "macd_signal": "MACD 慢线 DEA",
    "macd_hist": "MACD 柱(MACD-DEA), 红涨绿跌",
    "macd_cross": "1=金叉, -1=死叉, 0=无",
    "rsi": "RSI(0-100), >70 超买, <30 超卖",
    "rsi_overbought": "RSI 超买标记(1/0)",
    "rsi_oversold": "RSI 超卖标记(1/0)",
    "boll_mid": "布林中轨(20日均线)",
    "boll_upper": "布林上轨",
    "boll_lower": "布林下轨",
    "boll_width": "布林带宽度",
    "boll_position": "收盘价在布林带中的位置(0-1)",
    "kdj_k": "KDJ K值",
    "kdj_d": "KDJ D值",
    "kdj_j": "KDJ J值",
    "kdj_cross": "1=金叉, -1=死叉",
    "atr": "真实波幅",
    "atr_ratio": "ATR/收盘价(波动幅度占比)",
    "obv": "能量潮",
    "obv_ma10": "OBV 10日均线",
    "obv_signal": "OBV 信号(1/-1/0)",
    "williams_r": "威廉指标(-100~0)",
    "williams_overbought": "超买标记",
    "williams_oversold": "超卖标记",
    "momentum_5d": "5日动量(涨跌幅%)",
    "momentum_10d": "10日动量%",
    "momentum_20d": "20日动量%",
    "roc_10": "10日变动率%",
    "roc_20": "20日变动率%",
    "pct_change": "区间涨跌幅%",
    "volatility_5d": "5日波动率",
    "volatility_10d": "10日波动率",
    "volatility_20d": "20日波动率",
    "high_low_ratio": "最高/最低比",
    "close_open_ratio": "收盘/开盘比",
    "upper_shadow": "上影线长",
    "lower_shadow": "下影线长",
    "body_size": "K线实体长度",
}

BASE_COLS = [
    "code",
    "date",
    "open",
    "close",
    "high",
    "low",
    "volume",
    "amount",
    "change_percent",
]
# 注: BASE_COLS 仅作为「常用字段」的推荐展示顺序。实际输出时 describe_schema 会
# 以真实表结构(PRAGMA)为准过滤, 表不存在的列(如 amplitude/turnover_rate/change_amount)
# 不会被列给 LLM, 避免误导其生成非法 SQL。


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
    """中文名 -> 完整代码(带 sh/sz/bj 前缀)。支持精确匹配与常见命名的模糊匹配, 找不到原样返回。"""
    name = (name or "").strip()
    if not name:
        return name
    # 优先走 中文名 -> 完整代码 映射(含占位名与真实名别名, 返回带前缀代码)
    mapping = _name_to_fullcode_map(project_root)
    if name in mapping:
        return mapping[name]

    # 规范化: 去掉空白与常见后缀, 便于模糊匹配
    def _norm(s: str) -> str:
        s = re.sub(r"\s+", "", s)
        for suf in ("集团有限公司", "股份有限公司", "股份有限公司", "集团", "股份", "有限", "公司", "*ST", "ST"):
            s = s.replace(suf, "")
        return s

    target = _norm(name)
    if target:
        # 1) 规范化后精确匹配(占位名)
        for n, code in mapping.items():
            if n.startswith("Demo") and _norm(n) == target:
                return code
        # 2) 包含匹配: 输入是股票名的子串或反之
        for n, code in mapping.items():
            if n.startswith("Demo") and n and (target in _norm(n) or _norm(n) in target):
                return code
        # 3) 演示库真实名别名匹配(如"茅台"/"贵州茅台" -> sh600519)
        for code, aliases in DEMO_REALNAME_ALIASES.items():
            if target == _norm(aliases[0]) or any(target in _norm(a) or _norm(a) in target for a in aliases):
                return code
    return name


def _name_to_fullcode_map(project_root: str) -> dict[str, str]:
    """构造 中文名(占位名/真实名别名) -> 完整代码(带 sh/sz/bj 前缀) 的映射。

    注意: 必须返回带前缀的完整代码(如 sh600519), 因为 stock_analysis 主表 code 列
    存的就是带前缀格式; 若返回去前缀的 600519, LLM 生成 WHERE code='600519' 会查不到。
    """
    p = _stock_info_path(Path(project_root))
    fullcode_by_name: dict[str, str] = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            stocks = data.get("stocks", {}) if isinstance(data, dict) else {}
            for code, info in stocks.items():
                name = (info or {}).get("name", "")
                if name and code not in fullcode_by_name:
                    fullcode_by_name[name] = code
        except Exception:  # pragma: no cover
            pass
    # 注入真实名别名(覆盖演示库脱敏占位名场景)
    for code, aliases in DEMO_REALNAME_ALIASES.items():
        for a in aliases:
            if a not in fullcode_by_name:
                fullcode_by_name[a] = code
    return fullcode_by_name


def translate_stock_names(project_root: str, text: str) -> str:
    """把句子里能识别的股票中文名替换为完整 code, 减少 LLM 生成 SQL 时的瞎猜。

    例如「今天贵州茅台涨幅」-> 「今天贵州茅台(代码sh600519)涨幅」。
    用一次编译的交替正则单遍替换, 长名优先, 避免子串二次命中与顺序错乱。

    同时支持演示库的真实名别名(如"茅台"/"贵州茅台" -> sh600519), 让自然语言查询能命中
    脱敏后的 DemoXX 数据; 替换时保留用户原话(真实名), 标注的 code 为带前缀的完整代码,
    与 stock_analysis 主表 code 列格式一致, 确保 LLM 生成的 SQL 能命中。
    """
    if not text:
        return text
    mapping = _name_to_fullcode_map(project_root)
    if not mapping:
        return text

    # 占位名(DemoXX) 与真实名别名 都可能命中; 长名优先, 避免"茅台"抢在"贵州茅台"之前
    names = sorted(mapping.keys(), key=len, reverse=True)

    # 一次编译的交替正则, 单遍替换 (长名在前, re 对同一位置取首个匹配分支)
    pattern = re.compile("|".join(re.escape(n) for n in names))

    def _rep(m):
        return f"{m.group(0)}(代码{mapping[m.group(0)]})"

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
        row = conn.execute("SELECT COUNT(DISTINCT code), COUNT(*), MIN(date), MAX(date) FROM stock_analysis").fetchone()
    stock_count, total_rows, min_date, max_date = row

    indicator_cols = [c for c in cols if c not in BASE_COLS and c not in ("id", "created_at")]
    known = [(c, COLUMN_HINTS.get(c)) for c in indicator_cols]

    lines: list[str] = []
    lines.append("【数据表】 stock_analysis —— A股日频行情与技术指标, 每行 = 某只股票某一天的数据。")
    lines.append(f"共 {stock_count} 只股票, {total_rows:,} 条记录, 日期范围 {min_date} ~ {max_date}。")
    lines.append("")
    lines.append("常用字段:")
    for c in BASE_COLS:
        if c not in cols:
            continue  # 仅列出表真实存在的列, 避免把 schema 描述里声明但表结构缺失的列(如 turnover_rate)误导 LLM 生成非法 SQL
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
    lines.append(
        "  - code 用单引号且带市场前缀, 例如 WHERE code='sh600519' (注意: 表内 code 列存的是带 sh/sz/bj 前缀的完整代码)"
    )
    lines.append("  - 股票用中文名提及时, 问题中已被标注为 '真实名(代码sh600519)' 形式, 直接用其中的带前缀代码查询")
    lines.append("  - 时间序列查询默认给最近一个/几个交易日, 数据最大日期为 " + str(max_date))
    lines.append(
        "  - 需要股票名称时, 可用常见映射: 贵州茅台=sh600519, 五粮液=sz000858, "
        "宁德时代=sz300750, 比亚迪=sz002594, 平安银行=sz000001"
    )
    lines.append("")
    lines.append(
        "注意: 本演示库股票 name 字段为脱敏占位名(如 'Demo茅台'/'Demo银行'), "
        "不要按真实名(茅台/贵州茅台)用 name 字段 LIKE 匹配, 一律用带前缀的 code 条件查询"
        "(如 WHERE code='sh600519'); 用户问题中已标注完整代码, 直接照搬即可。"
    )
    return "\n".join(lines)


def stock_name(code: str, project_root: str) -> str:
    c2n, _ = load_name_code(project_root)
    return c2n.get(code, code)

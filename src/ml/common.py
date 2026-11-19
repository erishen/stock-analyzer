"""共享工具：数据加载、特征工程、横截面排名归一化、评估指标。

所有 ML 模块（LightGBM / Isolation Forest / K-Means / GARCH）共用：
  - 从 stock_analysis.db 加载 51 指标分析库
  - ST / 低价过滤（基于名称缓存 + 价格阈值）
  - 横截面排名归一化（消除量纲与市场状态影响）
  - 未来收益计算、日度 RankIC 指标

设计原则：
  - 重计算在函数内完成，模块级不依赖 lightgbm / sklearn / arch（惰性导入）
  - 所有 pandas groupby.apply 均带 include_groups=False（pandas>=2.0）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_stock_analysis_db_path

# 默认横截面排名特征（与 scripts/ml_factor_mining.py 口径一致）
RANK_FEATURES: list[str] = [
    "close",
    "change_percent",
    "amplitude",
    "turnover_rate",
    "volume",
    "amount",
    "rsi",
    "macd_hist",
    "kdj_k",
    "kdj_d",
    "kdj_j",
    "williams_r",
    "momentum_5d",
    "momentum_10d",
    "momentum_20d",
    "roc_10",
    "roc_20",
    "volatility_5d",
    "volatility_10d",
    "volatility_20d",
    "boll_position",
    "boll_width",
    "atr_ratio",
    "close_ma5_ratio",
    "close_ma10_ratio",
    "close_ma20_ratio",
    "close_ma60_ratio",
    "high_low_ratio",
    "upper_shadow",
    "lower_shadow",
    "body_size",
    "obv_signal",
]

# 各模型默认特征子集（可被 CLI 覆盖）
GBM_FEATURES = RANK_FEATURES
ANOMALY_FEATURES = [
    "change_percent",
    "amplitude",
    "turnover_rate",
    "volume",
    "amount",
    "rsi",
    "macd_hist",
    "kdj_j",
    "williams_r",
    "boll_position",
    "boll_width",
    "atr_ratio",
    "volatility_20d",
]
CLUSTER_FEATURES = [
    "change_percent",
    "amplitude",
    "turnover_rate",
    "rsi",
    "macd_hist",
    "kdj_k",
    "williams_r",
    "momentum_10d",
    "momentum_20d",
    "volatility_10d",
    "volatility_20d",
    "boll_position",
    "boll_width",
    "atr_ratio",
    "close_ma5_ratio",
    "close_ma20_ratio",
    "close_ma60_ratio",
]


def project_root() -> Path:
    """项目根目录（src/ml/../..）。"""
    return Path(__file__).resolve().parent.parent.parent


def load_names() -> dict[str, str]:
    """加载股票名称缓存（兼容 sh600000 / 600000 两种键）。"""
    cache = project_root() / "data" / "stock_info_cache.json"
    names: dict[str, str] = {}
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        for k, v in raw.items():
            code = str(k)[-6:]
            names.setdefault(code, v)
    return names


def is_st(name: str) -> bool:
    """是否 ST / 退市股（按名称关键词启发式判断）。"""
    return "ST" in name.upper() or "退" in name


def load_analysis_data(
    features: list[str],
    start_year: int = 2020,
    end_year: int = 2027,
    db_path: str | None = None,
) -> pd.DataFrame:
    """分年加载分析库并降内存。

    返回列：code, date, *features（float32 降内存）。按 code/date 稳定排序。
    """
    db = Path(db_path or get_stock_analysis_db_path())
    import sqlite3

    cols = ", ".join(["code", "date", *features])
    chunks: list[pd.DataFrame] = []
    with sqlite3.connect(str(db)) as conn:
        for y in range(start_year, end_year):
            df = pd.read_sql_query(
                f"SELECT {cols} FROM stock_analysis WHERE date >= '{y}-01-01' AND date < '{y + 1}-01-01'",
                conn,
            )
            if df.empty:
                continue
            df[list(dict.fromkeys(features))] = df[list(dict.fromkeys(features))].astype("float32")
            chunks.append(df)
            print(f"  加载 {y}: {len(df):,} 行", file=sys.stderr, flush=True)
    df = pd.concat(chunks, ignore_index=True)
    df.sort_values(["code", "date"], kind="stable", ignore_index=True, inplace=True)
    return df


def compute_forward_return(df: pd.DataFrame, horizon: int = 20) -> pd.DataFrame:
    """按行数计算未来 horizon 期收益（与既有回测口径一致；尾部为 NaN）。"""
    df = df.copy()
    df["fwd"] = (df.groupby("code")["close"].shift(-horizon) / df["close"] - 1).astype("float32")
    return df


def filter_universe(df: pd.DataFrame, min_price: float = 2.0) -> pd.DataFrame:
    """ST / 低价过滤。需要 df 含 code（名称映射在函数内补）。"""
    names = load_names()
    df = df.copy()
    df["name"] = df["code"].map(names).fillna("")
    n0 = len(df)
    df = df[(~df["name"].map(is_st)) & (df["close"] >= min_price)].copy()
    print(f"  ST/低价过滤: {n0:,} -> {len(df):,}", file=sys.stderr, flush=True)
    return df


def add_cross_sectional_ranks(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """按日做特征横截面排名百分位归一化（分两批控内存）。"""
    df = df.copy()
    half = len(features) // 2
    for batch in (features[:half], features[half:]):
        df[batch] = df.groupby("date")[batch].rank(pct=True).astype("float32")
    return df


def add_target_rank(df: pd.DataFrame) -> pd.DataFrame:
    """目标 = 未来收益的当日横截面排名百分位（选股排序问题）。"""
    df = df.copy()
    df["target"] = df.groupby("date")["fwd"].rank(pct=True).astype("float32")
    return df


def daily_rankic(frame: pd.DataFrame, pred: str = "pred", fwd: str = "fwd") -> pd.Series:
    """按日计算 Spearman(pred, fwd) —— 双重 rank 后 Pearson 相关。"""

    def _ic(g: pd.DataFrame) -> float:
        if len(g) < 30:
            return np.nan
        pr = g[pred].rank()
        fr = g[fwd].rank()
        if pr.std() == 0 or fr.std() == 0:
            return np.nan
        return float(np.corrcoef(pr, fr)[0, 1])

    return frame.groupby("date").apply(_ic, include_groups=False)


def save_json_report(obj: Any, path: Path) -> Path:
    """写 JSON 报告并返回路径。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 已保存: {path}", file=sys.stderr)
    return path


def report_path(output: str | None, default_name: str) -> Path:
    """解析报告输出路径。

    - output 为 None: 使用默认 output/reports/<default_name>
    - output 为相对路径: 相对项目根目录（避免与 output/reports 重复拼接）
    - output 为绝对路径: 原样使用
    """
    if output:
        p = Path(output)
        return p if p.is_absolute() else project_root() / p
    return project_root() / "output" / "reports" / default_name


def latest_date(db_path: str | None = None) -> str | None:
    """获取分析库最新交易日期。"""
    import sqlite3

    db = Path(db_path or get_stock_analysis_db_path())
    with sqlite3.connect(str(db)) as conn:
        row = conn.execute("SELECT MAX(date) FROM stock_analysis").fetchone()
    return row[0] if row else None


def resolve_stock_code(code: str, db_path: str | None = None) -> str | None:
    """把用户输入的 6 位代码解析为分析库中的真实代码（可能带 sh/sz/bj 前缀）。

    依次尝试: 精确匹配 -> sh/sz/bj 前缀 -> LIKE %code% 兜底。
    """
    import sqlite3

    db = Path(db_path or get_stock_analysis_db_path())
    with sqlite3.connect(str(db)) as conn:
        if conn.execute("SELECT 1 FROM stock_analysis WHERE code = ? LIMIT 1", (code,)).fetchone():
            return code
        for prefix in ("sh", "sz", "bj"):
            cand = f"{prefix}{code}"
            if conn.execute("SELECT 1 FROM stock_analysis WHERE code = ? LIMIT 1", (cand,)).fetchone():
                return cand
        row = conn.execute(
            "SELECT DISTINCT code FROM stock_analysis WHERE code LIKE ? LIMIT 1", (f"%{code}",)
        ).fetchone()
        return row[0] if row else None


def load_latest_cross_section(features: list[str], date: str, db_path: str | None = None) -> pd.DataFrame:
    """加载某交易日的全市场横截面（code/name + features），用于异常检测与聚类。"""
    import sqlite3

    db = Path(db_path or get_stock_analysis_db_path())
    cols = ", ".join(["code", "date", *features])
    with sqlite3.connect(str(db)) as conn:
        df = pd.read_sql_query(
            f"SELECT {cols} FROM stock_analysis WHERE date = ?",
            conn,
            params=(date,),
        )
    names = load_names()
    df["name"] = df["code"].map(names).fillna("")
    df = df[~df["name"].map(is_st)].reset_index(drop=True)
    return df


def require_ml(package: str) -> Any:
    """惰性导入 ML 依赖，给出可读错误提示。"""
    try:
        if package == "lightgbm":
            import lightgbm as mod
        elif package == "sklearn":
            import sklearn as mod
        elif package == "arch":
            import arch as mod
        else:
            raise ImportError(package)
        return mod
    except ImportError as exc:  # pragma: no cover - 依赖缺失提示
        raise RuntimeError(f"缺少 ML 依赖 {package!r}。请先安装: uv sync --extra ml") from exc

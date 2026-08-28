"""换手率补算

背景: K 线数据源均不提供换手率 (腾讯 K 线源无此字段, 东财源被 TLS 拦截, 新浪源无此字段),
导致 stock_klines / stock_analysis 的 turnover_rate 全为 0。

方案: 腾讯实时快照接口 (qt.gtimg.cn) 批量返回每只股票的:
    字段[38] 换手率(当日), 字段[44] 流通市值(亿)
由 流通市值/现价 得流通股本, 历史换手率 = volume(股) / 流通股本 × 100。

注意: 历史回填用当前流通股本近似 (流通股本仅在增发/解禁时变化, 对多数股票影响小)。

被三处调用:
    scripts/backfill_turnover.py  历史一次性回填
    data_tools/update_task.py     Web 端更新任务 (拉取后、ETL 前; 需 WEB_ENABLE_UPDATE=1)
    data_tools/daily_update.py   cron 每日增量
"""

import contextlib
import re
import sqlite3
import time
from pathlib import Path

import requests

QT_URL = "https://qt.gtimg.cn/q="
BATCH = 50
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def market_prefix(code: str) -> str:
    """裸代码 -> 腾讯市场前缀"""
    if code.startswith(("43", "83", "87", "92")):
        return "bj"
    if code.startswith("6"):
        return "sh"
    return "sz"


def fetch_snapshots(codes: list[str], progress_cb=None) -> dict[str, dict]:
    """批量拉腾讯实时快照, 返回 {code: {price, turnover, float_shares}}

    快照字段: [3]现价 [38]换手率% [44]流通市值(亿)
    停牌/异常股票 (price=0 或流通市值为 0) 不入结果。
    """
    result: dict[str, dict] = {}
    session = requests.Session()
    total_batches = (len(codes) + BATCH - 1) // BATCH

    for bi in range(total_batches):
        batch = codes[bi * BATCH : (bi + 1) * BATCH]
        symbols = ",".join(f"{market_prefix(c)}{c}" for c in batch)
        try:
            r = session.get(QT_URL + symbols, headers=HEADERS, timeout=10)
            text = r.content.decode("gbk", errors="ignore")
            for m in re.finditer(r'v_(?:sh|sz|bj)(\d{6})="([^"]*)"', text):
                fields = m.group(2).split("~")
                if len(fields) < 45:
                    continue
                try:
                    price = float(fields[3])
                    turnover = float(fields[38])
                    float_mv = float(fields[44])  # 亿元
                except ValueError:
                    continue
                if price > 0 and float_mv > 0:
                    result[m.group(1)] = {
                        "price": price,
                        "turnover": turnover,
                        "float_shares": float_mv * 1e8 / price,
                    }
        except Exception:
            continue  # 单批失败跳过, 调用方可重试
        if progress_cb and (bi + 1) % 10 == 0:
            progress_cb(bi + 1, total_batches)
        time.sleep(0.15)

    return result


def patch_db_turnover(
    db_path: Path,
    snapshots: dict[str, dict],
    only_date: str | None = None,
    table: str = "stock_klines",
) -> int:
    """给单个库补换手率

    - only_date=None: 补该股所有 turnover_rate=0 的行 (历史回填)
    - only_date='2026-08-20': 只补指定日期 (增量场景)
    - table: klines 库用 stock_klines, 分析库用 stock_analysis (列结构一致)
    返回更新行数。
    """
    updated = 0
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("CREATE TEMP TABLE _fs(code TEXT PRIMARY KEY, fs REAL)")
        conn.executemany(
            "INSERT OR IGNORE INTO _fs(code, fs) VALUES (?, ?)",
            [(c, s["float_shares"]) for c, s in snapshots.items()],
        )
        date_cond = "AND date = ?" if only_date else ""
        date_args = (only_date,) if only_date else ()
        cursor = conn.execute(
            f"""
            UPDATE {table}
            SET turnover_rate = volume / (SELECT fs FROM _fs WHERE _fs.code = {table}.code) * 100
            WHERE turnover_rate = 0
              AND code IN (SELECT code FROM _fs)
              {date_cond}
            """,
            date_args,
        )
        updated = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
        conn.execute("DROP TABLE _fs")
    return updated


def patch_turnover(
    klines_db: Path,
    analysis_db: Path | None = None,
    codes: list[str] | None = None,
    only_date: str | None = None,
    progress_cb=None,
) -> dict:
    """补换手率入口

    - codes=None: 对库中全部股票操作 (回填); 否则只处理指定代码 (增量)
    - analysis_db 传入时同步补分析库 (仅回填场景需要; 增量场景由 ETL 从 klines 复制)
    返回 {snapshots: 获取数, klines_updated: 行数, analysis_updated: 行数}
    """
    conn = sqlite3.connect(str(klines_db))
    try:
        if codes is None:
            rows = conn.execute("SELECT DISTINCT code FROM stock_klines").fetchall()
            codes = [r[0] for r in rows]
    finally:
        conn.close()

    if not codes:
        return {"snapshots": 0, "klines_updated": 0, "analysis_updated": 0}

    snapshots = fetch_snapshots(codes, progress_cb=progress_cb)
    if not snapshots:
        return {"snapshots": 0, "klines_updated": 0, "analysis_updated": 0}

    klines_updated = patch_db_turnover(klines_db, snapshots, only_date=only_date, table="stock_klines")
    analysis_updated = 0
    if analysis_db is not None and analysis_db.exists():
        with contextlib.suppress(sqlite3.Error):
            analysis_updated = patch_db_turnover(analysis_db, snapshots, only_date=only_date, table="stock_analysis")

    return {
        "snapshots": len(snapshots),
        "klines_updated": klines_updated,
        "analysis_updated": analysis_updated,
    }

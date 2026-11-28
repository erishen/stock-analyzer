"""比例复权因子: 由原始价 + 分红送转事件自建。

为什么不用行情源的 `qfq`: 腾讯 `stock_zh_a_hist_tx` 与东财 `stock_zh_a_hist`
给的前复权都是**减法(等额)复权**(`qfq = 原始价 - 累计分红`), 且锚点是"最新交易日",
同一条历史隔天再拉数值就变。这种口径既不适合落库, 也表达不了送股/转股
(价格差为常数无法描述股本变化, 遇 1 送 2 这类事件直接失真)。

所以库里只存原始价, 需要复权收益时用这里的比例因子:
    ``qfq(d) = raw(d) * prod(ratio_e for e in events if e.ex_date > d)``
其中 ``ratio_e = (prev_close - div_per_share) / (prev_close * (1 + share_ratio))``,
``prev_close`` 取除权前最后一个交易日的原始收盘价。
"""

from __future__ import annotations

import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_FACTOR_DB = "data/stock_adjust_factors.db"


@dataclass(frozen=True)
class AdjustEvent:
    """一次除权除息事件。"""

    code: str
    ex_date: str
    div_per_share: float  # 每股现金分红(税前, 元)
    share_ratio: float  # 每股送转比例(送股+转股, 每 1 股新增的股数)
    ratio: float  # 理论"除权后/除权前"价格比, 落在 (0, 1]
    source: str = "eastmoney"


def _prev_close(dates: list[str], closes: dict[str, float], ex_date: str) -> float | None:
    """除权前最后一个交易日的收盘价(原始价)。"""
    lo, hi = 0, len(dates)
    while lo < hi:  # 二分找第一个 >= ex_date 的位置
        mid = (lo + hi) // 2
        if dates[mid] < ex_date:
            lo = mid + 1
        else:
            hi = mid
    return closes.get(dates[lo - 1]) if lo > 0 else None


def compute_events(
    code: str,
    raw_events: list[tuple[str, float, float]],
    dates: list[str],
    closes: dict[str, float],
) -> list[AdjustEvent]:
    """把"分红明细"换算成复权事件。

    Args:
        raw_events: [(除权除息日, 每股现金分红, 每股送转比例), ...]
        dates: 该票在库内的交易日(升序)
        closes: {交易日: 原始收盘价}
    """
    out: list[AdjustEvent] = []
    for ex_date, div, share in raw_events:
        if not dates or ex_date < dates[0] or ex_date > dates[-1]:
            continue
        if div <= 0 and share <= 0:
            continue
        prev = _prev_close(dates, closes, ex_date)
        if not prev or prev <= 0:
            continue
        if div >= prev:
            logger.debug(f"{code} {ex_date}: 分红 {div} >= 前收 {prev}, 跳过该事件")
            continue
        ratio = (prev - div) / (prev * (1 + share))
        if ratio <= 0:
            continue
        out.append(
            AdjustEvent(
                code=code,
                ex_date=ex_date,
                div_per_share=round(div, 4),
                share_ratio=round(share, 6),
                ratio=round(ratio, 6),
            )
        )
    return out


def apply_qfq(
    dates: list[str],
    closes: list[float],
    events: list[AdjustEvent],
    anchor: str | None = None,
) -> list[float]:
    """把原始价折算成比例前复权价。

    ``anchor`` 为空时锚点是最后一根(与行情软件一致: 最新价不动)。
    返回长度与入参一致。
    """
    if not events:
        return list(closes)
    ordered = sorted(events, key=lambda e: e.ex_date)
    cutoff = anchor or dates[-1]
    out: list[float] = []
    for d, c in zip(dates, closes, strict=False):
        f = 1.0
        for e in ordered:
            # 注意不能用 break: 事件按 ex_date 升序, 一旦遇到"已过去的"事件
            # 后面还有更晚(即对 d 仍然生效)的事件, 必须逐个判断。
            if e.ex_date <= d or e.ex_date > cutoff:
                continue
            f *= e.ratio
        out.append(c * f)
    return out


def _fetch_raw_events(code: str) -> list[tuple[str, float, float]]:
    """东财分红送配明细 -> [(除权除息日, 每股派息, 每股送转)]。"""
    import akshare as ak
    import pandas as pd

    try:
        df = ak.stock_fhps_detail_em(symbol=code)
    except TypeError:
        # 东财对"无分红送配记录"的票返回 result:null, akshare 未做判空直接下标 -> TypeError。
        # 这类票没有除权事件, 返回空表是正确结果, 不能计入"抓取失败"(否则每次跑都报同样 168 只)。
        return []
    if df is None or df.empty:
        return []
    out = []
    for _, row in df.iterrows():
        ex = row.get("除权除息日")
        if pd.isna(ex):
            continue

        def num(key: str, _row=row) -> float:
            v = _row.get(key)
            return 0.0 if pd.isna(v) else float(v)

        out.append(
            (
                pd.to_datetime(ex).strftime("%Y-%m-%d"),
                num("现金分红-现金分红比例") / 10,  # 每 10 股 -> 每 1 股
                (num("送转股份-送股比例") + num("送转股份-转股比例")) / 10,
            )
        )
    return out


def _series(klines_db: Path, code: str) -> tuple[list[str], dict[str, float]]:
    conn = sqlite3.connect(f"file:{klines_db}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT date, close FROM stock_klines WHERE code=? ORDER BY date", (code,)).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows], {r[0]: r[1] for r in rows}


def build_events(
    klines_db: Path,
    codes: list[str] | None = None,
    workers: int = 6,
    progress_every: int = 500,
) -> tuple[list[AdjustEvent], dict]:
    """批量构建复权事件。网络密集(每只票一次分红查询), 用线程池并发。"""
    if codes is None:
        conn = sqlite3.connect(f"file:{klines_db}?mode=ro", uri=True)
        try:
            codes = [r[0] for r in conn.execute("SELECT DISTINCT code FROM stock_klines")]
        finally:
            conn.close()

    stats = {
        "codes": len(codes),
        "with_events": 0,
        "no_events": 0,
        "events": 0,
        "failed": 0,
        "failed_codes": [],
    }
    prepared = {}
    for code in codes:  # 本地读一遍序列, 避免工作线程各自连库
        prepared[code] = _series(klines_db, code)

    def one(code: str):
        # 东财对并发请求会偶发限流(短时返回非 JSON/超时), 单次失败不代表无数据,
        # 重试 2 次可把 8 线程跑批的失败率从 1%~2% 降到 0。
        last: Exception | None = None
        for attempt in range(3):
            try:
                raw = _fetch_raw_events(code)
                break
            except Exception as e:  # 单票失败不拖垮全局
                last = e
                if attempt < 2:
                    time.sleep(0.4 * (attempt + 1))
        else:
            return code, [], f"{type(last).__name__}"
        dates, closes = prepared[code]
        return code, compute_events(code, raw, dates, closes), None

    events: list[AdjustEvent] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, (_code, evs, err) in enumerate(ex.map(one, codes), 1):
            if err:
                stats["failed"] += 1
                stats["failed_codes"].append(_code)
            elif evs:
                stats["with_events"] += 1
                stats["events"] += len(evs)
                events.extend(evs)
            else:
                stats["no_events"] += 1  # 源端无分红送配记录(新股/从未分红), 非失败
            if progress_every and i % progress_every == 0:
                logger.info(f"  复权事件构建 {i}/{len(codes)}: 事件 {stats['events']}, 失败 {stats['failed']}")
    return events, stats


def write_factor_db(events: list[AdjustEvent], out_db: Path) -> int:
    """把事件写入独立库(不改动 klines/analysis, 避免动 4.5G 大库)。"""
    out_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(out_db))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS adjust_events (
                code TEXT NOT NULL,
                ex_date TEXT NOT NULL,
                div_per_share REAL NOT NULL,
                share_ratio REAL NOT NULL,
                ratio REAL NOT NULL,
                source TEXT DEFAULT 'eastmoney',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, ex_date)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_code ON adjust_events(code)")
        # 全量重建语义: 先清空。此前只做 INSERT OR REPLACE, 上一轮存在、本轮失败
        # (或源端已删除)的票会留下陈旧事件, 因子表与当日分红数据悄悄不一致。
        conn.execute("DELETE FROM adjust_events")
        conn.executemany(
            """
            INSERT OR REPLACE INTO adjust_events
            (code, ex_date, div_per_share, share_ratio, ratio, source)
            VALUES (?,?,?,?,?,?)
            """,
            [(e.code, e.ex_date, e.div_per_share, e.share_ratio, e.ratio, e.source) for e in events],
        )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM adjust_events").fetchone()[0]
    finally:
        conn.close()


def load_events(db: Path, codes: list[str] | None = None) -> dict[str, list[AdjustEvent]]:
    """从因子库读回 {code: [AdjustEvent]}。"""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        sql = "SELECT code, ex_date, div_per_share, share_ratio, ratio, source FROM adjust_events"
        args: tuple = ()
        if codes:
            sql += f" WHERE code IN ({','.join('?' * len(codes))})"
            args = tuple(codes)
        rows = conn.execute(sql + " ORDER BY code, ex_date", args).fetchall()
    finally:
        conn.close()
    by_code: dict[str, list[AdjustEvent]] = {}
    for code, ex, div, share, ratio, src in rows:
        by_code.setdefault(code, []).append(
            AdjustEvent(code=code, ex_date=ex, div_per_share=div, share_ratio=share, ratio=ratio, source=src)
        )
    return by_code


def qfq_closes(klines_db: Path, factor_db: Path, code: str) -> list[tuple[str, float]]:
    """便捷入口: 返回该票的比例前复权 [(date, qfq_close)]。"""
    dates, closes = _series(klines_db, code)
    events = load_events(factor_db, [code]).get(code, [])
    return list(zip(dates, apply_qfq(dates, [closes[d] for d in dates], events), strict=False))

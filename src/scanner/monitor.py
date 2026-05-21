"""
Real-time Signal Monitor Module.
实时信号监控模块 - 监控当前市场信号
"""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import get_stock_analysis_db_path

logger = logging.getLogger(__name__)


@dataclass
class LiveSignal:
    """实时信号"""

    code: str
    name: str
    signal_type: str
    price: float
    change_percent: float
    volume: float
    rsi: float
    macd: float
    ma5: float
    ma20: float
    date: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "signal_type": self.signal_type,
            "price": round(self.price, 2),
            "change_percent": round(self.change_percent, 2),
            "volume": self.volume,
            "rsi": round(self.rsi, 2),
            "macd": round(self.macd, 4),
            "ma5": round(self.ma5, 2),
            "ma20": round(self.ma20, 2),
            "date": self.date,
            "score": round(self.score, 2),
        }


@dataclass
class MarketSummary:
    """市场概览"""

    date: str
    total_stocks: int
    up_count: int
    down_count: int
    flat_count: int
    avg_change: float
    max_up: tuple[str, str, float]
    max_down: tuple[str, str, float]
    oversold_count: int
    overbought_count: int
    golden_cross_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "total_stocks": self.total_stocks,
            "up_count": self.up_count,
            "down_count": self.down_count,
            "flat_count": self.flat_count,
            "up_ratio": round(self.up_count / self.total_stocks * 100, 2)
            if self.total_stocks > 0
            else 0,
            "avg_change": round(self.avg_change, 2),
            "max_up": {"code": self.max_up[0], "name": self.max_up[1], "change": self.max_up[2]},
            "max_down": {
                "code": self.max_down[0],
                "name": self.max_down[1],
                "change": self.max_down[2],
            },
            "oversold_count": self.oversold_count,
            "overbought_count": self.overbought_count,
            "golden_cross_count": self.golden_cross_count,
        }


def get_latest_date(db_path: Path) -> str | None:
    """获取最新日期"""
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute("SELECT MAX(date) FROM stock_analysis")
        result = cursor.fetchone()
    return result[0] if result else None


def get_market_summary(db_path: Path) -> MarketSummary:
    """获取市场概览"""
    latest_date = get_latest_date(db_path)
    if not latest_date:
        raise ValueError("数据库中没有数据")

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN change_percent > 0 THEN 1 ELSE 0 END) as up_count,
                SUM(CASE WHEN change_percent < 0 THEN 1 ELSE 0 END) as down_count,
                AVG(change_percent) as avg_change
            FROM stock_analysis
            WHERE date = ?
            """,
            (latest_date,),
        )
        row = cursor.fetchone()
        total, up_count, down_count, avg_change = row
        flat_count = total - up_count - down_count

        cursor = conn.execute(
            """
            SELECT code, change_percent
            FROM stock_analysis
            WHERE date = ?
            ORDER BY change_percent DESC
            LIMIT 1
            """,
            (latest_date,),
        )
        max_up_row = cursor.fetchone()
        max_up = (max_up_row[0], max_up_row[0], max_up_row[1]) if max_up_row else ("", "", 0)

        cursor = conn.execute(
            """
            SELECT code, change_percent
            FROM stock_analysis
            WHERE date = ?
            ORDER BY change_percent ASC
            LIMIT 1
            """,
            (latest_date,),
        )
        max_down_row = cursor.fetchone()
        max_down = (
            (max_down_row[0], max_down_row[0], max_down_row[1]) if max_down_row else ("", "", 0)
        )

        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM stock_analysis
            WHERE date = ? AND rsi IS NOT NULL AND rsi < 30
            """,
            (latest_date,),
        )
        oversold_count = cursor.fetchone()[0]

        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM stock_analysis
            WHERE date = ? AND rsi IS NOT NULL AND rsi > 70
            """,
            (latest_date,),
        )
        overbought_count = cursor.fetchone()[0]

        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM stock_analysis
            WHERE date = ? AND macd > macd_signal AND macd_signal > 0
            """,
            (latest_date,),
        )
        golden_cross_count = cursor.fetchone()[0]

    return MarketSummary(
        date=latest_date,
        total_stocks=total,
        up_count=up_count,
        down_count=down_count,
        flat_count=flat_count,
        avg_change=avg_change or 0,
        max_up=max_up,
        max_down=max_down,
        oversold_count=oversold_count,
        overbought_count=overbought_count,
        golden_cross_count=golden_cross_count,
    )


def get_live_signals(
    db_path: Path,
    signal_type: str = "all",
    limit: int = 20,
) -> list[LiveSignal]:
    """
    获取实时信号

    Args:
        db_path: 数据库路径
        signal_type: 信号类型 (all, oversold, overbought, golden_cross, ma_cross)
        limit: 返回数量

    Returns:
        信号列表
    """
    latest_date = get_latest_date(db_path)
    if not latest_date:
        return []

    conditions = ["date = ?"]
    params: list[Any] = [latest_date]

    if signal_type == "oversold":
        conditions.append("rsi < 30")
    elif signal_type == "overbought":
        conditions.append("rsi > 70")
    elif signal_type == "golden_cross":
        conditions.append("macd > macd_signal AND macd_signal > 0")
    elif signal_type == "ma_cross":
        conditions.append("ma5 > ma20 AND ma5 > 0")

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT code, close, change_percent, volume, rsi, macd, ma5, ma20
        FROM stock_analysis
        WHERE {where_clause}
        ORDER BY
            CASE
                WHEN rsi < 30 THEN 30 - rsi
                WHEN rsi > 70 THEN rsi - 70
                ELSE 0
            END DESC,
            ABS(macd) DESC
        LIMIT ?
    """
    params.append(limit)

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    signals = []
    for row in rows:
        code, close, change, volume, rsi, macd, ma5, ma20 = row

        if rsi and rsi < 30:
            sig_type = "RSI超卖"
            score = 30 - rsi
        elif rsi and rsi > 70:
            sig_type = "RSI超买"
            score = rsi - 70
        elif macd and macd > 0:
            sig_type = "MACD金叉"
            score = macd * 100
        elif ma5 and ma20 and ma5 > ma20:
            sig_type = "均线多头"
            score = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
        else:
            sig_type = "其他"
            score = 0

        signals.append(
            LiveSignal(
                code=code,
                name=code,
                signal_type=sig_type,
                price=close or 0,
                change_percent=change or 0,
                volume=volume or 0,
                rsi=rsi or 50,
                macd=macd or 0,
                ma5=ma5 or 0,
                ma20=ma20 or 0,
                date=latest_date,
                score=score,
            )
        )

    return signals


def print_market_monitor(db_path: Path):
    """打印市场监控信息"""
    logger.info("\n" + "=" * 60)
    logger.info("📊 市场实时监控")
    logger.info("=" * 60)

    try:
        summary = get_market_summary(db_path)

        logger.info(f"\n📅 日期: {summary.date}")
        logger.info("\n📈 市场概况:")
        logger.info(f"   总股票数: {summary.total_stocks}")
        logger.info(
            f"   上涨: {summary.up_count} ({summary.up_count / summary.total_stocks * 100:.1f}%)"
        )
        logger.info(
            f"   下跌: {summary.down_count} ({summary.down_count / summary.total_stocks * 100:.1f}%)"
        )
        logger.info(f"   平盘: {summary.flat_count}")
        logger.info(f"   平均涨跌: {summary.avg_change:+.2f}%")

        logger.info("\n🏆 涨跌幅榜:")
        logger.info(f"   最大涨幅: {summary.max_up[1]} ({summary.max_up[2]:+.2f}%)")
        logger.info(f"   最大跌幅: {summary.max_down[1]} ({summary.max_down[2]:+.2f}%)")

        logger.info("\n📊 技术信号:")
        logger.info(f"   RSI 超卖 (<30): {summary.oversold_count}")
        logger.info(f"   RSI 超买 (>70): {summary.overbought_count}")
        logger.info(f"   MACD 金叉: {summary.golden_cross_count}")

        logger.info("\n🔍 RSI 超卖信号 (潜在反弹机会):")
        signals = get_live_signals(db_path, "oversold", 10)
        if signals:
            logger.info(
                f"{'代码':<12} {'名称':<10} {'价格':<10} {'涨跌%':<10} {'RSI':<8} {'得分':<8}"
            )
            logger.info("-" * 65)
            for s in signals:
                logger.info(
                    f"{s.code:<12} {s.name[:8]:<10} {s.price:<10.2f} {s.change_percent:+.2f}%     {s.rsi:<8.1f} {s.score:<8.1f}"
                )
        else:
            logger.info("   暂无超卖信号")

        logger.info("\n🔍 MACD 金叉信号:")
        signals = get_live_signals(db_path, "golden_cross", 10)
        if signals:
            logger.info(
                f"{'代码':<12} {'名称':<10} {'价格':<10} {'涨跌%':<10} {'MACD':<10} {'得分':<8}"
            )
            logger.info("-" * 65)
            for s in signals:
                logger.info(
                    f"{s.code:<12} {s.name[:8]:<10} {s.price:<10.2f} {s.change_percent:+.2f}%     {s.macd:<10.4f} {s.score:<8.1f}"
                )
        else:
            logger.info("   暂无金叉信号")

    except Exception as e:
        logger.error(f"❌ 获取市场数据失败: {e}")


def run_monitor(db_path: Path | None = None) -> dict[str, Any]:
    """运行市场监控"""
    project_root = Path(__file__).parent.parent.parent
    project_root / "data"
    db_path = db_path or get_stock_analysis_db_path()

    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    print_market_monitor(db_path)

    return {
        "summary": get_market_summary(db_path).to_dict(),
        "oversold_signals": [s.to_dict() for s in get_live_signals(db_path, "oversold", 20)],
        "golden_cross_signals": [
            s.to_dict() for s in get_live_signals(db_path, "golden_cross", 20)
        ],
    }

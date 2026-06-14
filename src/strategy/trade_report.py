"""
Trade Report Module.
交易报告模块 - 生成详细的交易分析报告
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TradeStatistics:
    """交易统计"""

    total_trades: int
    winning_trades: int
    losing_trades: int
    even_trades: int
    win_rate: float
    avg_profit: float
    avg_loss: float
    avg_holding_days: float
    max_profit_trade: float
    max_loss_trade: float
    profit_factor: float
    expectancy: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "even_trades": self.even_trades,
            "win_rate": round(self.win_rate * 100, 2),
            "avg_profit": round(self.avg_profit * 100, 2),
            "avg_loss": round(self.avg_loss * 100, 2),
            "avg_holding_days": round(self.avg_holding_days, 1),
            "max_profit_trade": round(self.max_profit_trade * 100, 2),
            "max_loss_trade": round(self.max_loss_trade * 100, 2),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy": round(self.expectancy * 100, 2),
        }


@dataclass
class MonthlyPerformance:
    """月度表现"""

    month: str
    trades: int
    wins: int
    losses: int
    return_pct: float
    win_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "return_pct": round(self.return_pct * 100, 2),
            "win_rate": round(self.win_rate * 100, 2),
        }


@dataclass
class StockPerformance:
    """个股表现"""

    code: str
    name: str
    trades: int
    wins: int
    losses: int
    total_profit: float
    win_rate: float
    avg_return: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "total_profit": round(self.total_profit * 100, 2),
            "win_rate": round(self.win_rate * 100, 2),
            "avg_return": round(self.avg_return * 100, 2),
        }


@dataclass
class TradeReport:
    """交易报告"""

    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    statistics: TradeStatistics
    monthly_performance: list[MonthlyPerformance]
    top_winners: list[dict]
    top_losers: list[dict]
    stock_performance: list[StockPerformance]
    holding_distribution: dict[str, int]
    weekday_performance: dict[str, dict]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": round(self.initial_capital, 2),
            "final_capital": round(self.final_capital, 2),
            "total_return": round(self.total_return * 100, 2),
            "statistics": self.statistics.to_dict(),
            "monthly_performance": [m.to_dict() for m in self.monthly_performance],
            "top_winners": self.top_winners,
            "top_losers": self.top_losers,
            "stock_performance": [s.to_dict() for s in self.stock_performance[:20]],
            "holding_distribution": self.holding_distribution,
            "weekday_performance": self.weekday_performance,
        }


def generate_trade_report(backtest_result: Any) -> TradeReport:
    """
    生成交易报告

    Args:
        backtest_result: 回测结果

    Returns:
        交易报告
    """
    trades = backtest_result.trades

    if not trades:
        return TradeReport(
            strategy_name=backtest_result.strategy_name,
            start_date=backtest_result.start_date,
            end_date=backtest_result.end_date,
            initial_capital=backtest_result.initial_capital,
            final_capital=backtest_result.final_capital,
            total_return=backtest_result.total_return,
            statistics=TradeStatistics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                even_trades=0,
                win_rate=0,
                avg_profit=0,
                avg_loss=0,
                avg_holding_days=0,
                max_profit_trade=0,
                max_loss_trade=0,
                profit_factor=0,
                expectancy=0,
            ),
            monthly_performance=[],
            top_winners=[],
            top_losers=[],
            stock_performance=[],
            holding_distribution={},
            weekday_performance={},
        )

    winning_trades = [t for t in trades if t.profit > 0]
    losing_trades = [t for t in trades if t.profit < 0]
    even_trades = [t for t in trades if t.profit == 0]

    total_profit = sum(t.profit_percent for t in winning_trades) if winning_trades else 0
    total_loss = sum(t.profit_percent for t in losing_trades) if losing_trades else 0

    avg_profit = total_profit / len(winning_trades) if winning_trades else 0
    avg_loss = total_loss / len(losing_trades) if losing_trades else 0

    avg_holding_days = sum(t.holding_days for t in trades) / len(trades)

    max_profit_trade = max((t.profit_percent for t in trades), default=0)
    max_loss_trade = min((t.profit_percent for t in trades), default=0)

    profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float("inf")

    win_rate = len(winning_trades) / len(trades) if trades else 0
    expectancy = (win_rate * avg_profit) + ((1 - win_rate) * avg_loss)

    statistics = TradeStatistics(
        total_trades=len(trades),
        winning_trades=len(winning_trades),
        losing_trades=len(losing_trades),
        even_trades=len(even_trades),
        win_rate=win_rate,
        avg_profit=avg_profit,
        avg_loss=avg_loss,
        avg_holding_days=avg_holding_days,
        max_profit_trade=max_profit_trade,
        max_loss_trade=max_loss_trade,
        profit_factor=profit_factor,
        expectancy=expectancy,
    )

    monthly_data = {}
    for t in trades:
        month = t.entry_date[:7]
        if month not in monthly_data:
            monthly_data[month] = {"trades": [], "profits": []}
        monthly_data[month]["trades"].append(t)
        monthly_data[month]["profits"].append(t.profit_percent)

    monthly_performance = []
    for month in sorted(monthly_data.keys()):
        data = monthly_data[month]
        trades_in_month = data["trades"]
        wins = sum(1 for t in trades_in_month if t.profit > 0)
        losses = sum(1 for t in trades_in_month if t.profit < 0)
        return_pct = sum(data["profits"])
        win_rate_m = wins / len(trades_in_month) if trades_in_month else 0

        monthly_performance.append(
            MonthlyPerformance(
                month=month,
                trades=len(trades_in_month),
                wins=wins,
                losses=losses,
                return_pct=return_pct,
                win_rate=win_rate_m,
            )
        )

    sorted_trades = sorted(trades, key=lambda t: t.profit_percent, reverse=True)
    top_winners = [
        {
            "code": t.code,
            "name": t.name,
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "profit_pct": round(t.profit_percent * 100, 2),
            "holding_days": t.holding_days,
        }
        for t in sorted_trades[:10]
    ]

    top_losers = [
        {
            "code": t.code,
            "name": t.name,
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "profit_pct": round(t.profit_percent * 100, 2),
            "holding_days": t.holding_days,
        }
        for t in sorted_trades[-10:][::-1]
    ]

    stock_data = {}
    for t in trades:
        if t.code not in stock_data:
            stock_data[t.code] = {"name": t.name, "trades": [], "profits": []}
        stock_data[t.code]["trades"].append(t)
        stock_data[t.code]["profits"].append(t.profit_percent)

    stock_performance = []
    for code, data in stock_data.items():
        trades_for_stock = data["trades"]
        wins = sum(1 for t in trades_for_stock if t.profit > 0)
        losses = sum(1 for t in trades_for_stock if t.profit < 0)
        total_profit = sum(data["profits"])
        win_rate_s = wins / len(trades_for_stock) if trades_for_stock else 0
        avg_return = total_profit / len(trades_for_stock) if trades_for_stock else 0

        stock_performance.append(
            StockPerformance(
                code=code,
                name=data["name"],
                trades=len(trades_for_stock),
                wins=wins,
                losses=losses,
                total_profit=total_profit,
                win_rate=win_rate_s,
                avg_return=avg_return,
            )
        )

    stock_performance.sort(key=lambda x: x.total_profit, reverse=True)

    holding_dist = {}
    for t in trades:
        days = t.holding_days
        bucket = f"{(days // 5) * 5 + 1}-{(days // 5) * 5 + 5}"
        holding_dist[bucket] = holding_dist.get(bucket, 0) + 1

    weekday_data = {}
    for t in trades:
        try:
            entry_date = datetime.strptime(t.entry_date, "%Y-%m-%d")
            weekday = entry_date.strftime("%A")
            if weekday not in weekday_data:
                weekday_data[weekday] = {"trades": 0, "wins": 0, "total_return": 0}
            weekday_data[weekday]["trades"] += 1
            if t.profit > 0:
                weekday_data[weekday]["wins"] += 1
            weekday_data[weekday]["total_return"] += t.profit_percent
        except KeyError:
            pass

        except Exception:
            pass

    weekday_performance = {
        day: {
            "trades": data["trades"],
            "win_rate": round(data["wins"] / data["trades"] * 100, 2) if data["trades"] > 0 else 0,
            "avg_return": round(data["total_return"] / data["trades"] * 100, 2) if data["trades"] > 0 else 0,
        }
        for day, data in weekday_data.items()
    }

    return TradeReport(
        strategy_name=backtest_result.strategy_name,
        start_date=backtest_result.start_date,
        end_date=backtest_result.end_date,
        initial_capital=backtest_result.initial_capital,
        final_capital=backtest_result.final_capital,
        total_return=backtest_result.total_return,
        statistics=statistics,
        monthly_performance=monthly_performance,
        top_winners=top_winners,
        top_losers=top_losers,
        stock_performance=stock_performance,
        holding_distribution=holding_dist,
        weekday_performance=weekday_performance,
    )


def print_trade_report(report: TradeReport):
    """打印交易报告"""
    logger.info("\n" + "=" * 70)
    logger.info(f"📋 交易分析报告 - {report.strategy_name}")
    logger.info("=" * 70)

    logger.info(f"\n📅 回测区间: {report.start_date} ~ {report.end_date}")
    logger.info(f"💰 初始资金: {report.initial_capital:,.0f} 元")
    logger.info(f"💰 最终资金: {report.final_capital:,.0f} 元")
    logger.info(f"📈 总收益率: {report.total_return * 100:+.2f}%")

    stats = report.statistics
    logger.info("\n📊 交易统计:")
    logger.info(f"   总交易次数: {stats.total_trades}")
    logger.info(f"   盈利交易: {stats.winning_trades} ({stats.win_rate:.1f}%)")
    logger.info(f"   亏损交易: {stats.losing_trades}")
    logger.info(f"   持平交易: {stats.even_trades}")
    logger.info(f"   平均盈利: {stats.avg_profit:+.2f}%")
    logger.info(f"   平均亏损: {stats.avg_loss:.2f}%")
    logger.info(f"   盈亏比: {stats.profit_factor:.2f}")
    logger.info(f"   期望收益: {stats.expectancy:+.2f}%")
    logger.info(f"   平均持仓: {stats.avg_holding_days:.1f} 天")
    logger.info(f"   最大单笔盈利: {stats.max_profit_trade:+.2f}%")
    logger.info(f"   最大单笔亏损: {stats.max_loss_trade:.2f}%")

    if report.monthly_performance:
        logger.info("\n📅 月度表现:")
        logger.info(f"{'月份':<10} {'交易':<8} {'胜率':<10} {'收益率':<12}")
        logger.info("-" * 45)
        for m in report.monthly_performance[-6:]:
            logger.info(f"{m.month:<10} {m.trades:<8} {m.win_rate * 100:.1f}%      {m.return_pct * 100:+.2f}%")

    if report.top_winners:
        logger.info("\n🏆 盈利 Top 10:")
        logger.info(f"{'代码':<12} {'名称':<10} {'买入日期':<12} {'收益率':<10} {'持仓天数':<8}")
        logger.info("-" * 60)
        for t in report.top_winners:
            logger.info(
                f"{t['code']:<12} {t['name'][:8]:<10} {t['entry_date']:<12} {t['profit_pct']:+.2f}%     {t['holding_days']:<8}"
            )

    if report.top_losers:
        logger.info("\n📉 亏损 Top 10:")
        logger.info(f"{'代码':<12} {'名称':<10} {'买入日期':<12} {'收益率':<10} {'持仓天数':<8}")
        logger.info("-" * 60)
        for t in report.top_losers:
            logger.info(
                f"{t['code']:<12} {t['name'][:8]:<10} {t['entry_date']:<12} {t['profit_pct']:.2f}%      {t['holding_days']:<8}"
            )

    if report.stock_performance:
        logger.info("\n📈 个股表现 Top 10:")
        logger.info(f"{'代码':<12} {'名称':<10} {'交易次数':<10} {'胜率':<10} {'总收益':<12}")
        logger.info("-" * 60)
        for s in report.stock_performance[:10]:
            logger.info(
                f"{s.code:<12} {s.name[:8]:<10} {s.trades:<10} {s.win_rate * 100:.1f}%      {s.total_profit * 100:+.2f}%"
            )

    if report.holding_distribution:
        logger.info("\n⏱️ 持仓天数分布:")
        for bucket in sorted(report.holding_distribution.keys()):
            count = report.holding_distribution[bucket]
            bar = "█" * (count // 5 + 1)
            logger.info(f"   {bucket} 天: {bar} ({count})")

    if report.weekday_performance:
        logger.info("\n📆 按买入日分析:")
        logger.info(f"{'星期':<12} {'交易次数':<10} {'胜率':<10} {'平均收益':<12}")
        logger.info("-" * 50)
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for day in weekday_order:
            if day in report.weekday_performance:
                data = report.weekday_performance[day]
                logger.info(f"{day:<12} {data['trades']:<10} {data['win_rate']:.1f}%      {data['avg_return']:+.2f}%")


def save_trade_report(report: TradeReport, output_path: Path):
    """保存交易报告"""
    import json

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

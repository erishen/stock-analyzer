"""
Backtest Visualization Module.
回测可视化模块 - 生成资金曲线图、收益分布图等
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from utils.font_config import setup_chinese_font

logger = logging.getLogger(__name__)


@dataclass
class BacktestChartData:
    """回测图表数据"""

    strategy_name: str
    equity_curve: list[dict]
    trades: list[dict]
    initial_capital: float
    final_capital: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float

    @classmethod
    def from_json(cls, json_path: Path) -> "BacktestChartData":
        """从 JSON 文件加载"""
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            strategy_name=data.get("strategy_name", "Unknown"),
            equity_curve=data.get("equity_curve", []),
            trades=data.get("trades", []),
            initial_capital=data.get("initial_capital", 100000),
            final_capital=data.get("final_capital", 100000),
            total_return=data.get("total_return", 0),
            max_drawdown=data.get("max_drawdown", 0),
            sharpe_ratio=data.get("sharpe_ratio", 0),
            win_rate=data.get("win_rate", 0),
        )


def plot_equity_curve(
    chart_data: BacktestChartData,
    output_path: Path | None = None,
    show_stats: bool = True,
) -> Path:
    """绘制资金曲线图"""
    setup_chinese_font()

    _fig, ax = plt.subplots(figsize=(14, 7))

    dates = [datetime.strptime(e["date"], "%Y-%m-%d") for e in chart_data.equity_curve]
    equities = [e["equity"] for e in chart_data.equity_curve]

    ax.plot(dates, equities, "b-", linewidth=1.5, label="账户权益")
    ax.axhline(y=chart_data.initial_capital, color="gray", linestyle="--", alpha=0.5, label="初始资金")

    peak = chart_data.initial_capital
    for i, equity in enumerate(equities):
        if equity > peak:
            peak = equity
        if peak > 0:
            drawdown = (peak - equity) / peak
            if drawdown > 0.1:
                ax.axvspan(dates[i], dates[min(i + 1, len(dates) - 1)], alpha=0.1, color="red")

    ax.fill_between(
        dates,
        chart_data.initial_capital,
        equities,
        where=[e >= chart_data.initial_capital for e in equities],
        alpha=0.3,
        color="green",
        label="盈利区域",
    )
    ax.fill_between(
        dates,
        chart_data.initial_capital,
        equities,
        where=[e < chart_data.initial_capital for e in equities],
        alpha=0.3,
        color="red",
        label="亏损区域",
    )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.xticks(rotation=45)

    ax.set_xlabel("日期", fontsize=12)
    ax.set_ylabel("账户权益 (元)", fontsize=12)
    ax.set_title(f"{chart_data.strategy_name} 策略资金曲线", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    if show_stats:
        stats_text = (
            f"总收益率: {chart_data.total_return:.2f}%\n"
            f"最大回撤: {chart_data.max_drawdown:.2f}%\n"
            f"夏普比率: {chart_data.sharpe_ratio:.2f}\n"
            f"胜率: {chart_data.win_rate:.2f}%"
        )
        props = dict(boxstyle="round", facecolor="wheat", alpha=0.8)
        ax.text(
            0.02,
            0.98,
            stats_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=props,
        )

    plt.tight_layout()

    if output_path is None:
        output_path = Path("output/charts/equity_curve.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path


def plot_trade_distribution(
    chart_data: BacktestChartData,
    output_path: Path | None = None,
) -> Path:
    """绘制交易收益分布图"""
    setup_chinese_font()

    _fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    profits = [t["profit_percent"] * 100 for t in chart_data.trades if t.get("profit_percent")]

    if not profits:
        axes[0].text(0.5, 0.5, "无交易数据", ha="center", va="center", fontsize=14)
        axes[1].text(0.5, 0.5, "无交易数据", ha="center", va="center", fontsize=14)
    else:
        ax1 = axes[0]
        _n, bins, patches = ax1.hist(profits, bins=30, edgecolor="black", alpha=0.7)

        for i, patch in enumerate(patches):
            if bins[i] < 0:
                patch.set_facecolor("red")
            else:
                patch.set_facecolor("green")

        ax1.axvline(x=0, color="black", linestyle="--", linewidth=2)
        ax1.axvline(
            x=np.mean(profits),
            color="blue",
            linestyle="-",
            linewidth=2,
            label=f"平均: {np.mean(profits):.2f}%",
        )

        ax1.set_xlabel("收益率 (%)", fontsize=12)
        ax1.set_ylabel("交易次数", fontsize=12)
        ax1.set_title("交易收益分布", fontsize=14, fontweight="bold")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        ax2 = axes[1]
        holding_days = [t["holding_days"] for t in chart_data.trades if t.get("holding_days")]
        if holding_days:
            ax2.hist(
                holding_days,
                bins=range(1, max(holding_days) + 2),
                edgecolor="black",
                alpha=0.7,
                color="steelblue",
            )
            ax2.set_xlabel("持有天数", fontsize=12)
            ax2.set_ylabel("交易次数", fontsize=12)
            ax2.set_title("持有天数分布", fontsize=14, fontweight="bold")
            ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path is None:
        output_path = Path("output/charts/trade_distribution.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path


def plot_monthly_returns(
    chart_data: BacktestChartData,
    output_path: Path | None = None,
) -> Path:
    """绘制月度收益图"""
    setup_chinese_font()

    if not chart_data.equity_curve:
        return Path("")

    monthly_returns = {}
    prev_equity = chart_data.equity_curve[0]["equity"]

    for e in chart_data.equity_curve[1:]:
        date = datetime.strptime(e["date"], "%Y-%m-%d")
        month_key = date.strftime("%Y-%m")
        current_equity = e["equity"]

        if month_key not in monthly_returns:
            monthly_returns[month_key] = {"start": prev_equity, "end": current_equity}
        else:
            monthly_returns[month_key]["end"] = current_equity

        prev_equity = current_equity

    months = sorted(monthly_returns.keys())
    returns = []
    for m in months:
        data = monthly_returns[m]
        ret = (data["end"] - data["start"]) / data["start"] * 100 if data["start"] > 0 else 0
        returns.append(ret)

    _fig, ax = plt.subplots(figsize=(14, 6))

    colors = ["green" if r >= 0 else "red" for r in returns]
    bars = ax.bar(months, returns, color=colors, edgecolor="black", alpha=0.7)

    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xlabel("月份", fontsize=12)
    ax.set_ylabel("收益率 (%)", fontsize=12)
    ax.set_title(f"{chart_data.strategy_name} 月度收益", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")

    plt.xticks(rotation=45)

    for bar, ret in zip(bars, returns, strict=False):
        height = bar.get_height()
        ax.annotate(
            f"{ret:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3 if height >= 0 else -12),
            textcoords="offset points",
            ha="center",
            va="bottom" if height >= 0 else "top",
            fontsize=8,
        )

    plt.tight_layout()

    if output_path is None:
        output_path = Path("output/charts/monthly_returns.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path


def plot_drawdown(
    chart_data: BacktestChartData,
    output_path: Path | None = None,
) -> Path:
    """绘制回撤曲线图"""
    setup_chinese_font()

    if not chart_data.equity_curve:
        return Path("")

    _fig, ax = plt.subplots(figsize=(14, 5))

    dates = [datetime.strptime(e["date"], "%Y-%m-%d") for e in chart_data.equity_curve]
    equities = [e["equity"] for e in chart_data.equity_curve]

    peak = equities[0]
    drawdowns = []
    for equity in equities:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 100
        drawdowns.append(dd)

    ax.fill_between(dates, 0, [-d for d in drawdowns], color="red", alpha=0.5)
    ax.plot(dates, [-d for d in drawdowns], "r-", linewidth=1)

    ax.axhline(
        y=-chart_data.max_drawdown,
        color="darkred",
        linestyle="--",
        label=f"最大回撤: {chart_data.max_drawdown:.2f}%",
    )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.xticks(rotation=45)

    ax.set_xlabel("日期", fontsize=12)
    ax.set_ylabel("回撤 (%)", fontsize=12)
    ax.set_title(f"{chart_data.strategy_name} 回撤曲线", fontsize=14, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path is None:
        output_path = Path("output/charts/drawdown.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path


def generate_backtest_report(
    json_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """生成完整的回测可视化报告"""
    chart_data = BacktestChartData.from_json(json_path)

    if output_dir is None:
        output_dir = Path("output/charts")

    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {}

    paths["equity_curve"] = plot_equity_curve(chart_data, output_dir / f"{chart_data.strategy_name.lower()}_equity.png")

    paths["trade_distribution"] = plot_trade_distribution(
        chart_data, output_dir / f"{chart_data.strategy_name.lower()}_distribution.png"
    )

    paths["monthly_returns"] = plot_monthly_returns(
        chart_data, output_dir / f"{chart_data.strategy_name.lower()}_monthly.png"
    )

    paths["drawdown"] = plot_drawdown(chart_data, output_dir / f"{chart_data.strategy_name.lower()}_drawdown.png")

    return paths


def visualize_backtest(
    backtest_result_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """可视化回测结果的便捷函数"""
    if backtest_result_path is None:
        backtest_result_path = Path("output/reports/backtest_report.json")

    if not backtest_result_path.exists():
        logger.error(f"❌ 回测报告不存在: {backtest_result_path}")
        return {}

    logger.info("\n📊 生成回测可视化报告...")

    paths = generate_backtest_report(backtest_result_path, output_dir)

    logger.info(f"✅ 已生成 {len(paths)} 个图表:")
    for path in paths.values():
        logger.info(f"   - {path}")

    return paths

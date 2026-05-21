"""
CLI Utilities for Stock Analyzer.
命令行工具 - 提供彩色输出、进度条、交互式选择等功能
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

console = Console()


class ColorScheme:
    COLORS: ClassVar[dict[str, str]] = {
        "bullish": "green",
        "bearish": "red",
        "neutral": "yellow",
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "highlight": "magenta",
    }

    @classmethod
    def colorize(cls, text: str, color_type: str) -> Text:
        color = cls.COLORS.get(color_type, "white")
        return Text(text, style=color)


@dataclass
class OutputConfig:
    show_progress: bool = True
    color_output: bool = True
    verbose: bool = False
    json_output: bool = False


def print_header(title: str, subtitle: str = ""):
    content = f"[bold]{title}[/bold]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(content, border_style="blue"))


def print_section(title: str):
    console.print(f"\n[bold cyan]{'=' * 20}[/bold cyan]")
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print(f"[bold cyan]{'=' * 20}[/bold cyan]\n")


def print_success(message: str):
    console.print(f"[green]✅ {message}[/green]")


def print_error(message: str):
    console.print(f"[red]❌ {message}[/red]")


def print_warning(message: str):
    console.print(f"[yellow]⚠️ {message}[/yellow]")


def print_info(message: str):
    console.print(f"[blue]ℹ️ {message}[/blue]")


def print_signal_table(signals: list[dict[str, Any]], title: str = "信号列表"):
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("代码", style="cyan", width=12)
    table.add_column("名称", style="white", width=10)
    table.add_column("信号类型", style="yellow", width=15)
    table.add_column("强度", width=6)
    table.add_column("得分", justify="right", width=8)
    table.add_column("价格", justify="right", width=10)
    table.add_column("涨跌幅", justify="right", width=10)

    for s in signals:
        signal_type = s.get("signal_type", "")
        is_bullish = any(x in signal_type for x in ["金叉", "上穿", "超卖", "突破下轨", "上升"])
        is_bearish = any(x in signal_type for x in ["死叉", "下穿", "超买", "突破上轨", "下降"])

        if is_bullish:
            signal_style = "green"
        elif is_bearish:
            signal_style = "red"
        else:
            signal_style = "yellow"

        strength = s.get("strength", "中")
        if strength == "强":
            strength_style = "bold green"
        elif strength == "弱":
            strength_style = "dim red"
        else:
            strength_style = "yellow"

        change = s.get("change_percent", 0)
        change_str = f"{change:+.2f}%"
        change_style = "green" if change >= 0 else "red"

        table.add_row(
            s.get("code", ""),
            s.get("name", "")[:8],
            Text(signal_type, style=signal_style),
            Text(strength, style=strength_style),
            f"{s.get('score', 0):.1f}",
            f"{s.get('price', 0):.2f}",
            Text(change_str, style=change_style),
        )

    console.print(table)


def print_backtest_result(result: dict[str, Any]):
    print_section("回测结果")

    metrics_table = Table(show_header=False, box=None)
    metrics_table.add_column("指标", style="cyan")
    metrics_table.add_column("值", style="white", justify="right")

    total_return = result.get("total_return", 0)
    return_style = "green" if total_return >= 0 else "red"
    metrics_table.add_row("总收益率", Text(f"{total_return * 100:.2f}%", style=return_style))
    metrics_table.add_row("年化收益", f"{result.get('annualized_return', 0) * 100:.2f}%")
    metrics_table.add_row("最大回撤", f"{result.get('max_drawdown', 0) * 100:.2f}%")
    metrics_table.add_row("夏普比率", f"{result.get('sharpe_ratio', 0):.2f}")
    metrics_table.add_row("胜率", f"{result.get('win_rate', 0) * 100:.2f}%")

    console.print(metrics_table)


def create_progress_bar(description: str = "处理中") -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def progress_iterate(
    items: list[Any],
    process_func: Callable[[Any], Any],
    description: str = "处理中",
) -> list[Any]:
    results = []
    with create_progress_bar(description) as progress:
        task = progress.add_task(description, total=len(items))
        for item in items:
            try:
                result = process_func(item)
                if result is not None:
                    results.append(result)
            except Exception:
                pass
            progress.advance(task)
    return results


def interactive_select(
    choices: list[str],
    title: str = "请选择",
) -> str | None:
    try:
        import questionary

        return questionary.select(title, choices=choices).ask()
    except ImportError:
        print_warning("交互式选择需要安装 questionary: pip install questionary")
        return None


def interactive_multiselect(
    choices: list[str],
    title: str = "请选择 (多选)",
) -> list[str] | None:
    try:
        import questionary

        return questionary.checkbox(title, choices=choices).ask()
    except ImportError:
        print_warning("交互式选择需要安装 questionary: pip install questionary")
        return None


def interactive_confirm(title: str, default: bool = False) -> bool:
    try:
        import questionary

        return questionary.confirm(title, default=default).ask()
    except ImportError:
        return default


def interactive_text(title: str, default: str = "") -> str:
    try:
        import questionary

        return questionary.text(title, default=default).ask() or ""
    except ImportError:
        return default


def print_summary_box(title: str, items: list[tuple[str, Any]], style: str = "blue"):
    content = ""
    for label, value in items:
        if isinstance(value, float):
            content += f"[cyan]{label}:[/cyan] {value:.2f}\n"
        elif isinstance(value, int):
            content += f"[cyan]{label}:[/cyan] {value:,}\n"
        else:
            content += f"[cyan]{label}:[/cyan] {value}\n"
    console.print(Panel(content.strip(), title=title, border_style=style))


def format_number(value: float, decimals: int = 2) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f}M"
    elif abs(value) >= 1_000:
        return f"{value / 1_000:.{decimals}f}K"
    else:
        return f"{value:.{decimals}f}"


def format_percent(value: float, decimals: int = 2) -> str:
    return f"{value * 100:+.{decimals}f}%"


def format_price(value: float) -> str:
    if value >= 100:
        return f"{value:.2f}"
    elif value >= 10:
        return f"{value:.3f}"
    else:
        return f"{value:.4f}"

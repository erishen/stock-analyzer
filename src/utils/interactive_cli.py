"""
Interactive CLI for Stock Analyzer.
交互式命令行界面 - 提供菜单驱动的交互体验
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import get_stock_analysis_db_path

console = Console()


class InteractiveCLI:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_stock_analysis_db_path()
        self.running = True

    def run(self):
        self._show_welcome()
        while self.running:
            try:
                self._show_main_menu()
            except KeyboardInterrupt:
                self._exit()
                break

    def _show_welcome(self):
        console.clear()
        console.print(
            Panel.fit(
                "[bold cyan]Stock Analyzer[/bold cyan]\n"
                "[dim]股票数据分析工具 v0.1.0[/dim]\n\n"
                "[yellow]提示: 使用方向键选择，Enter 确认[/yellow]",
                border_style="cyan",
            )
        )

    def _show_main_menu(self):
        try:
            import questionary
        except ImportError:
            console.print("[red]请安装 questionary: pip install questionary[/red]")
            return

        action = questionary.select(
            "请选择操作",
            choices=[
                questionary.Choice("📊 数据管理", value="data"),
                questionary.Choice("🔍 信号扫描", value="scan"),
                questionary.Choice("📈 策略回测", value="backtest"),
                questionary.Choice("🏆 选股评分", value="score"),
                questionary.Choice("📋 准确率分析", value="accuracy"),
                questionary.Choice("🌐 启动 Web 服务", value="web"),
                questionary.Choice("⚙️ 设置", value="settings"),
                questionary.Choice("❌ 退出", value="exit"),
            ],
        ).ask()

        if action is None or action == "exit":
            self._exit()
        elif action == "data":
            self._data_menu()
        elif action == "scan":
            self._scan_menu()
        elif action == "backtest":
            self._backtest_menu()
        elif action == "score":
            self._score_menu()
        elif action == "accuracy":
            self._accuracy_menu()
        elif action == "web":
            self._start_web()
        elif action == "settings":
            self._settings_menu()

    def _data_menu(self):
        try:
            import questionary
        except ImportError:
            return

        action = questionary.select(
            "数据管理",
            choices=[
                questionary.Choice("📥 同步数据", value="sync"),
                questionary.Choice("🔄 运行 ETL", value="etl"),
                questionary.Choice("📊 查看统计", value="stats"),
                questionary.Choice("📤 导出数据", value="export"),
                questionary.Choice("⬅️ 返回", value="back"),
            ],
        ).ask()

        if action == "sync":
            self._run_sync()
        elif action == "etl":
            self._run_etl()
        elif action == "stats":
            self._show_stats()
        elif action == "export":
            self._export_data()

    def _scan_menu(self):
        try:
            import questionary
        except ImportError:
            return

        signal_types = questionary.checkbox(
            "选择信号类型 (空选择=全部)",
            choices=[
                "MACD金叉",
                "MACD死叉",
                "KDJ金叉",
                "KDJ死叉",
                "MA5上穿MA20",
                "MA5下穿MA20",
                "RSI超卖",
                "RSI超买",
                "突破布林上轨",
                "跌破布林下轨",
                "成交量异动",
                "上升趋势",
                "下降趋势",
            ],
        ).ask()

        min_score = questionary.text(
            "最低得分 (默认 0)",
            default="0",
        ).ask()

        output_file = questionary.text(
            "输出文件路径 (可选)",
            default="",
        ).ask()

        self._run_scan(signal_types, float(min_score or 0), output_file)

    def _backtest_menu(self):
        try:
            import questionary
        except ImportError:
            return

        strategy = questionary.select(
            "选择策略",
            choices=[
                questionary.Choice("📈 动量策略", value="momentum"),
                questionary.Choice("🔄 均值回归", value="mean_reversion"),
                questionary.Choice("📊 趋势跟踪", value="trend_following"),
                questionary.Choice("🎯 多因子策略", value="multi_factor"),
            ],
        ).ask()

        holding_days = int(
            questionary.text(
                "持有天数",
                default="5",
            ).ask()
            or "5"
        )

        capital = float(
            questionary.text(
                "初始资金",
                default="100000",
            ).ask()
            or "100000"
        )

        compare_benchmark = questionary.confirm(
            "是否与基准对比?",
            default=False,
        ).ask()

        self._run_backtest(strategy, holding_days, capital, compare_benchmark)

    def _score_menu(self):
        try:
            import questionary
        except ImportError:
            return

        top_n = int(
            questionary.text(
                "返回前 N 只股票",
                default="50",
            ).ask()
            or "50"
        )

        output_file = questionary.text(
            "输出文件路径 (可选)",
            default="",
        ).ask()

        self._run_score(top_n, output_file)

    def _accuracy_menu(self):
        try:
            import questionary
        except ImportError:
            return

        holding_days = int(
            questionary.text(
                "持有天数",
                default="5",
            ).ask()
            or "5"
        )

        self._run_accuracy(holding_days)

    def _settings_menu(self):
        try:
            import questionary
        except ImportError:
            return

        action = questionary.select(
            "设置",
            choices=[
                questionary.Choice("📁 设置数据库路径", value="db_path"),
                questionary.Choice("⬅️ 返回", value="back"),
            ],
        ).ask()

        if action == "db_path":
            new_path = questionary.text(
                "数据库路径",
                default=str(self.db_path),
            ).ask()
            if new_path:
                self.db_path = Path(new_path)
                console.print(f"[green]数据库路径已更新: {self.db_path}[/green]")

    def _run_sync(self):
        console.print("\n[cyan]正在同步数据...[/cyan]")

        from data import run_sync

        result = run_sync()
        if result.get("success"):
            console.print("[green]✅ 数据同步成功[/green]")
        else:
            console.print(f"[red]❌ 同步失败: {result.get('error')}[/red]")

    def _run_etl(self):
        console.print("\n[cyan]正在运行 ETL...[/cyan]")

        from etl import run_etl

        result = run_etl()
        console.print(f"[green]✅ ETL 完成: {result.records_processed} 条记录[/green]")

    def _show_stats(self):
        import sqlite3

        if not self.db_path.exists():
            console.print(f"[red]❌ 数据库不存在: {self.db_path}[/red]")
            return

        with sqlite3.connect(str(self.db_path)) as conn:
            table = Table(title="数据统计")
            table.add_column("指标", style="cyan")
            table.add_column("值", style="white")

            cursor = conn.execute("SELECT COUNT(DISTINCT code) FROM stock_analysis")
            stock_count = cursor.fetchone()[0]
            table.add_row("股票数量", f"{stock_count:,}")

            cursor = conn.execute("SELECT COUNT(*) FROM stock_analysis")
            total_records = cursor.fetchone()[0]
            table.add_row("总记录数", f"{total_records:,}")

            cursor = conn.execute("SELECT MIN(date), MAX(date) FROM stock_analysis")
            row = cursor.fetchone()
            table.add_row("日期范围", f"{row[0]} ~ {row[1]}")

        console.print(table)

    def _export_data(self):
        console.print("[yellow]导出功能开发中...[/yellow]")

    def _run_scan(self, signal_types: list[str], min_score: float, output_file: str):
        console.print("\n[cyan]正在扫描市场...[/cyan]")

        from scanner import run_scan

        result = run_scan(db_path=self.db_path, min_score=min_score)

        console.print("\n[green]✅ 扫描完成[/green]")
        console.print(f"   扫描股票: {result.total_stocks:,}")
        console.print(f"   发现信号: {result.signals_found:,}")

        if result.top_signals:
            from .cli_utils import print_signal_table

            print_signal_table([s.to_dict() for s in result.top_signals[:20]])

        if output_file:
            import json

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            console.print(f"[green]💾 结果已保存到: {output_file}[/green]")

    def _run_backtest(
        self, strategy: str, holding_days: int, capital: float, compare_benchmark: bool
    ):
        console.print("\n[cyan]正在运行回测...[/cyan]")

        from strategy import run_backtest as run_strategy_backtest

        result = run_strategy_backtest(
            db_path=self.db_path,
            strategy_type=strategy,
            holding_days=holding_days,
            initial_capital=capital,
        )

        from .cli_utils import print_backtest_result

        print_backtest_result(result.to_dict())

    def _run_score(self, top_n: int, output_file: str):
        console.print("\n[cyan]正在计算评分...[/cyan]")

        from scorer import run_scoring

        report = run_scoring(db_path=self.db_path, top_n=top_n)

        console.print("\n[green]✅ 评分完成[/green]")
        console.print(f"   评分股票: {report.total_stocks:,}")

        if report.top_stocks:
            table = Table(title=f"Top {len(report.top_stocks)} 推荐股票")
            table.add_column("排名", style="cyan")
            table.add_column("代码", style="white")
            table.add_column("名称", style="white")
            table.add_column("得分", justify="right")
            table.add_column("建议", style="yellow")

            for s in report.top_stocks[:20]:
                table.add_row(
                    str(s.rank),
                    s.code,
                    s.name[:8],
                    f"{s.total_score:.1f}",
                    s.recommendation,
                )

            console.print(table)

        if output_file:
            import json

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
            console.print(f"[green]💾 结果已保存到: {output_file}[/green]")

    def _run_accuracy(self, holding_days: int):
        console.print("\n[cyan]正在分析准确率...[/cyan]")

        from scanner import run_accuracy_analysis

        report = run_accuracy_analysis(db_path=self.db_path, holding_days=holding_days)

        console.print("\n[green]✅ 分析完成[/green]")
        console.print(f"   总信号数: {report.total_signals_analyzed:,}")
        console.print(f"   总体胜率: {report.overall_win_rate * 100:.2f}%")

        if report.signal_performances:
            table = Table(title="各信号表现")
            table.add_column("信号类型", style="cyan")
            table.add_column("数量", justify="right")
            table.add_column("胜率", justify="right")
            table.add_column("平均收益", justify="right")

            for p in report.signal_performances:
                table.add_row(
                    p.signal_type.value,
                    str(p.total_signals),
                    f"{p.win_rate * 100:.2f}%",
                    f"{p.avg_return * 100:+.2f}%",
                )

            console.print(table)

    def _start_web(self):
        console.print("\n[cyan]正在启动 Web 服务...[/cyan]")

        from web import run_server

        console.print("[green]🌐 Web 服务已启动: http://127.0.0.1:8000[/green]")
        run_server(host="127.0.0.1", port=8000)

    def _exit(self):
        console.print("\n[dim]感谢使用 Stock Analyzer! 👋[/dim]")
        self.running = False


def run_interactive(db_path: Path | None = None):
    cli = InteractiveCLI(db_path)
    cli.run()

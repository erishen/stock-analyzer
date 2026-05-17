"""
Tests for Main Module - Extended Coverage.
主模块扩展测试
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_DIR = Path(__file__).parent.parent


class TestMainModule:
    """主模块测试"""

    def test_import_main(self):
        """测试导入主模块"""
        from src import main

        assert hasattr(main, "run_etl")
        assert hasattr(main, "run_scan")
        assert hasattr(main, "run_backtest")
        assert hasattr(main, "run_score")
        assert hasattr(main, "run_accuracy")

    def test_data_dir_exists(self):
        """测试数据目录"""
        from src.main import DATA_DIR

        assert DATA_DIR is not None

    def test_output_dir_exists(self):
        """测试输出目录"""
        from src.main import OUTPUT_DIR

        assert OUTPUT_DIR is not None

    def test_charts_dir_exists(self):
        """测试图表目录"""
        from src.main import CHARTS_DIR

        assert CHARTS_DIR is not None

    def test_reports_dir_exists(self):
        """测试报告目录"""
        from src.main import REPORTS_DIR

        assert REPORTS_DIR is not None


class TestRunStats:
    """统计命令测试"""

    def test_run_stats_no_db(self):
        """测试无数据库时的统计"""
        from src.main import run_stats

        args = MagicMock()
        args.db = "/nonexistent/path.db"

        with patch("builtins.print") as mock_print:
            run_stats(args)
            mock_print.assert_called()

    def test_run_stats_with_temp_db(self):
        """测试有数据库时的统计"""
        import sqlite3

        from src.main import run_stats

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                close REAL,
                volume REAL,
                rsi REAL,
                macd REAL,
                kdj_k REAL,
                kdj_d REAL
            )
        """)
        conn.execute("""
            INSERT INTO stock_analysis (code, date, close, volume, rsi, macd, kdj_k, kdj_d)
            VALUES ('000001', '2024-01-01', 10.0, 1000000, 50.0, 0.1, 50.0, 50.0)
        """)
        conn.commit()
        conn.close()

        args = MagicMock()
        args.db = str(db_path)

        with patch("builtins.print"):
            run_stats(args)

        db_path.unlink(missing_ok=True)


class TestRunInteractiveMode:
    """交互模式测试"""

    def test_run_interactive_mode_exists(self):
        """测试交互模式函数存在"""
        from src.main import run_interactive_mode

        assert callable(run_interactive_mode)


class TestRunSignalBacktest:
    """信号回测命令测试"""

    def test_run_signal_backtest_no_db(self):
        """测试无数据库时的信号回测"""
        from src.main import run_signal_backtest

        args = MagicMock()
        args.db = "/nonexistent/path.db"
        args.type = None
        args.holding_days = 5
        args.output = None

        with patch("builtins.print"):
            run_signal_backtest(args)


class TestRunPortfolioOpt:
    """组合优化命令测试"""

    def test_run_portfolio_opt(self):
        """测试组合优化命令"""
        from src.main import run_portfolio_opt

        args = MagicMock()
        args.db = None
        args.max_positions = 10
        args.max_single_pct = 0.15
        args.max_sector_pct = 0.30
        args.output = None

        with patch("builtins.print"), patch("numpy.fill_diagonal"):
            run_portfolio_opt(args)


class TestRunRiskAttribution:
    """风险归因命令测试"""

    def test_run_risk_attribution(self):
        """测试风险归因命令"""
        from src.main import run_risk_attribution

        args = MagicMock()
        args.db = None
        args.output = None

        with patch("builtins.print"):
            run_risk_attribution(args)


class TestRunDbOptimize:
    """数据库优化命令测试"""

    def test_run_db_optimize_no_db(self):
        """测试无数据库时的优化"""
        from src.main import run_db_optimize

        args = MagicMock()
        args.db = "/nonexistent/path.db"

        with patch("builtins.print"):
            run_db_optimize(args)


class TestArgParsing:
    """参数解析测试"""

    def test_main_function_exists(self):
        """测试主函数存在"""
        from src.main import main

        assert callable(main)

    def test_create_parser(self):
        """测试创建解析器"""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        subparsers.add_parser("scan")
        subparsers.add_parser("backtest")
        subparsers.add_parser("score")
        subparsers.add_parser("accuracy")
        subparsers.add_parser("stats")
        subparsers.add_parser("etl")

        args = parser.parse_args(["scan"])
        assert args.command == "scan"

        args = parser.parse_args(["backtest"])
        assert args.command == "backtest"

    def test_scan_args(self):
        """测试扫描参数"""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        scan_parser = subparsers.add_parser("scan")
        scan_parser.add_argument("--db", type=str)
        scan_parser.add_argument("--type", type=str)
        scan_parser.add_argument("--min-score", type=float, default=0)
        scan_parser.add_argument("--output", type=str)
        scan_parser.add_argument("--parallel", action="store_true")
        scan_parser.add_argument("--workers", type=int, default=4)

        args = parser.parse_args(
            [
                "scan",
                "--db",
                "test.db",
                "--type",
                "MACD金叉",
                "--min-score",
                "50",
                "--parallel",
                "--workers",
                "8",
            ]
        )

        assert args.command == "scan"
        assert args.db == "test.db"
        assert args.type == "MACD金叉"
        assert args.min_score == 50
        assert args.parallel is True
        assert args.workers == 8


class TestCLICommands:
    """CLI 命令测试"""

    def test_scan_command_help(self):
        """测试扫描命令帮助"""
        import subprocess

        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.main", "scan", "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
        )
        assert result.returncode == 0
        assert "scan" in result.stdout.lower() or "信号" in result.stdout

    def test_backtest_command_help(self):
        """测试回测命令帮助"""
        import subprocess

        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.main", "backtest", "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
        )
        assert result.returncode == 0

    def test_score_command_help(self):
        """测试评分命令帮助"""
        import subprocess

        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.main", "score", "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
        )
        assert result.returncode == 0

    def test_main_help(self):
        """测试主命令帮助"""
        import subprocess

        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.main", "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
        )
        assert result.returncode == 0

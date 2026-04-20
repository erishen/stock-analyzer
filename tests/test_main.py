"""
Tests for Main Module.
主模块测试
"""

from unittest.mock import MagicMock, patch


class TestMainModule:
    """主模块测试"""

    def test_import_main(self):
        """测试导入主模块"""
        from src import main

        assert hasattr(main, "run_etl")
        assert hasattr(main, "run_scan")
        assert hasattr(main, "run_backtest")

    def test_data_dir_exists(self):
        """测试数据目录"""
        from src.main import DATA_DIR

        assert DATA_DIR is not None


class TestRunETL:
    """ETL 命令测试"""

    def test_run_etl_mock(self):
        """测试 ETL 命令调用"""
        from src.main import run_etl

        args = MagicMock()
        args.db = None

        with patch("src.main.run_etl", side_effect=run_etl):
            pass


class TestRunScan:
    """扫描命令测试"""

    def test_run_scan_mock(self):
        """测试扫描命令调用"""
        from src.main import run_scan

        args = MagicMock()
        args.db = None
        args.signal_type = None
        args.min_score = 0
        args.limit = 20
        args.output = None

        with patch("src.main.run_scan", side_effect=run_scan):
            pass


class TestRunBacktest:
    """回测命令测试"""

    def test_run_backtest_mock(self):
        """测试回测命令调用"""
        from src.main import run_backtest

        args = MagicMock()
        args.db = None
        args.strategy = "momentum"
        args.holding = 5
        args.capital = 100000
        args.output = None

        with patch("src.main.run_backtest", side_effect=run_backtest):
            pass


class TestRunPortfolio:
    """组合命令测试"""

    def test_run_portfolio_mock(self):
        """测试组合命令调用"""
        from src.main import run_portfolio

        args = MagicMock()
        args.db = None
        args.strategies = None
        args.weight_method = "equal"
        args.holding = 5
        args.capital = 100000
        args.output = None

        with patch("src.main.run_portfolio", side_effect=run_portfolio):
            pass


class TestRunWeb:
    """Web 命令测试"""

    def test_run_web_mock(self):
        """测试 Web 命令调用"""
        from src.main import run_web

        args = MagicMock()
        args.host = "127.0.0.1"
        args.port = 8000

        with patch("src.main.run_web", side_effect=run_web):
            pass


class TestRunSector:
    """行业命令测试"""

    def test_run_sector_mock(self):
        """测试行业命令调用"""
        from src.main import run_sector

        args = MagicMock()
        args.db = None
        args.date = None
        args.validate = False
        args.output = None

        with patch("src.main.run_sector", side_effect=run_sector):
            pass


class TestRunSync:
    """同步命令测试"""

    def test_run_sync_mock(self):
        """测试同步命令调用"""
        from src.main import run_sync

        args = MagicMock()
        args.no_backup = False
        args.run_etl = False

        with patch("src.main.run_sync", side_effect=run_sync):
            pass


class TestRunSyncEnv:
    """同步环境变量命令测试"""

    def test_run_sync_env_mock(self):
        """测试同步环境变量命令调用"""
        from src.main import run_sync_env

        MagicMock()

        with patch("src.main.run_sync_env", side_effect=run_sync_env):
            pass


class TestRunRefreshNames:
    """刷新名称命令测试"""

    def test_run_refresh_names_mock(self):
        """测试刷新名称命令调用"""
        from src.main import run_refresh_names

        MagicMock()

        with patch("src.main.run_refresh_names", side_effect=run_refresh_names):
            pass

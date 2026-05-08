"""
Tests for Stock Analyzer.
股票分析器测试
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from analyze_stocks import StockAnalyzer


class TestStockAnalyzerInit:
    """测试股票分析器初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        analyzer = StockAnalyzer()
        assert analyzer.db_path is not None
        assert analyzer.conn is None
        assert analyzer.df is None

    def test_init_custom_path(self):
        """测试自定义路径初始化"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        analyzer = StockAnalyzer(db_path=db_path)
        assert analyzer.db_path == db_path

        Path(db_path).unlink(missing_ok=True)

    def test_init_use_analysis_db(self):
        """测试使用分析数据库"""
        analyzer = StockAnalyzer(use_analysis_db=True)
        assert "stock_analysis.db" in analyzer.db_path

    def test_init_use_asset_lens_db(self):
        """测试使用 asset_lens 数据库"""
        analyzer = StockAnalyzer(use_analysis_db=False)
        assert "asset_lens.db" in analyzer.db_path


class TestStockAnalyzerConnection:
    """测试数据库连接"""

    def test_connect_db_success(self):
        """测试成功连接"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        analyzer = StockAnalyzer(db_path=db_path)
        analyzer.connect_db()

        assert analyzer.conn is not None

        analyzer.conn.close()
        Path(db_path).unlink(missing_ok=True)

    def test_connect_db_not_found(self):
        """测试数据库不存在"""
        analyzer = StockAnalyzer(db_path="/nonexistent/path.db")

        with pytest.raises(FileNotFoundError):
            analyzer.connect_db()


class TestStockAnalyzerLoadData:
    """测试数据加载"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                close REAL,
                volume REAL
            )
        """)

        for i in range(10):
            conn.execute(
                """
                INSERT INTO stock_analysis (code, date, close, volume)
                VALUES (?, ?, ?, ?)
                """,
                ("000001", f"2024-01-{i + 1:02d}", 10.0 + i, 1000000),
            )

        conn.commit()
        conn.close()

        yield db_path

        db_path.unlink(missing_ok=True)

    def test_load_data_basic(self, temp_db):
        """测试基本数据加载"""
        analyzer = StockAnalyzer(db_path=str(temp_db))
        df = analyzer.load_data()

        assert df is not None
        assert len(df) == 10
        assert "code" in df.columns
        assert "date" in df.columns

    def test_load_data_with_limit(self, temp_db):
        """测试带限制的数据加载"""
        analyzer = StockAnalyzer(db_path=str(temp_db))
        df = analyzer.load_data(limit=5)

        assert len(df) == 5

    def test_load_data_with_codes(self, temp_db):
        """测试指定代码的数据加载"""
        conn = sqlite3.connect(str(temp_db))
        conn.execute(
            """
            INSERT INTO stock_analysis (code, date, close, volume)
            VALUES (?, ?, ?, ?)
            """,
            ("000002", "2024-01-01", 20.0, 2000000),
        )
        conn.commit()
        conn.close()

        analyzer = StockAnalyzer(db_path=str(temp_db))
        df = analyzer.load_data(codes=["000001"])

        assert all(df["code"] == "000001")


class TestStockAnalyzerGetStockList:
    """测试获取股票列表"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                close REAL,
                volume REAL
            )
        """)

        for code in ["000001", "000002", "000003"]:
            conn.execute(
                """
                INSERT INTO stock_analysis (code, date, close, volume)
                VALUES (?, ?, ?, ?)
                """,
                (code, "2024-01-01", 10.0, 1000000),
            )

        conn.commit()
        conn.close()

        yield db_path

        db_path.unlink(missing_ok=True)

    def test_get_stock_list(self, temp_db):
        """测试获取股票列表"""
        analyzer = StockAnalyzer(db_path=str(temp_db))
        codes = analyzer.get_stock_list()

        assert len(codes) == 3
        assert "000001" in codes
        assert "000002" in codes
        assert "000003" in codes


class TestStockAnalyzerGetStockData:
    """测试获取单只股票数据"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                close REAL,
                volume REAL
            )
        """)

        for i in range(30):
            conn.execute(
                """
                INSERT INTO stock_analysis (code, date, close, volume)
                VALUES (?, ?, ?, ?)
                """,
                ("000001", f"2024-01-{i + 1:02d}", 10.0 + i * 0.1, 1000000 + i * 10000),
            )

        conn.commit()
        conn.close()

        yield db_path

        db_path.unlink(missing_ok=True)

    def test_get_stock_data_default_days(self, temp_db):
        """测试默认天数获取"""
        analyzer = StockAnalyzer(db_path=str(temp_db))
        df = analyzer.get_stock_data("000001")

        assert len(df) == 30

    def test_get_stock_data_custom_days(self, temp_db):
        """测试自定义天数获取"""
        analyzer = StockAnalyzer(db_path=str(temp_db))
        df = analyzer.get_stock_data("000001", days=10)

        assert len(df) == 10


class TestStockAnalyzerCalculateMA:
    """测试移动平均线计算"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                close REAL,
                volume REAL
            )
        """)

        for i in range(30):
            conn.execute(
                """
                INSERT INTO stock_analysis (code, date, close, volume)
                VALUES (?, ?, ?, ?)
                """,
                ("000001", f"2024-01-{i + 1:02d}", 10.0 + i * 0.1, 1000000),
            )

        conn.commit()
        conn.close()

        yield db_path

        db_path.unlink(missing_ok=True)

    def test_calculate_moving_average(self, temp_db):
        """测试移动平均线"""
        analyzer = StockAnalyzer(db_path=str(temp_db))
        analyzer.load_data()

        with patch("matplotlib.pyplot.savefig"):
            with patch("matplotlib.pyplot.close"):
                analyzer.calculate_moving_average(window=5, top_n=1)


class TestStockAnalyzerPlotting:
    """测试绘图功能"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE stock_analysis (
                id INTEGER PRIMARY KEY,
                code TEXT,
                date TEXT,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL
            )
        """)

        for i in range(30):
            conn.execute(
                """
                INSERT INTO stock_analysis (code, date, open, close, high, low, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "000001",
                    f"2024-01-{i + 1:02d}",
                    10.0 + i,
                    10.0 + i + 0.5,
                    10.0 + i + 1.0,
                    10.0 + i - 0.5,
                    1000000 + i * 10000,
                ),
            )

        conn.commit()
        conn.close()

        yield db_path

        db_path.unlink(missing_ok=True)

    def test_plot_price_trend(self, temp_db):
        """测试价格趋势图"""
        analyzer = StockAnalyzer(db_path=str(temp_db))

        with patch("matplotlib.pyplot.savefig"):
            with patch("matplotlib.pyplot.close"):
                analyzer.load_data()
                analyzer.plot_price_trend(top_n=1)

    def test_plot_volume_trend(self, temp_db):
        """测试成交量趋势图"""
        analyzer = StockAnalyzer(db_path=str(temp_db))

        with patch("matplotlib.pyplot.savefig"):
            with patch("matplotlib.pyplot.close"):
                analyzer.load_data()
                analyzer.plot_volume_trend(top_n=1)

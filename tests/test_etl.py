"""
Tests for ETL Pipeline.
ETL 管道测试
"""

import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etl.pipeline import (
    DataExtractor,
    DataLoader,
    DataTransformer,
    ETLConfig,
    ETLPipeline,
)


@pytest.fixture
def sample_kline_data():
    """创建示例 K 线数据"""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    data = {
        "code": ["sh600000"] * 100,
        "date": dates,
        "open": np.random.uniform(10, 20, 100),
        "close": np.random.uniform(10, 20, 100),
        "high": np.random.uniform(15, 25, 100),
        "low": np.random.uniform(5, 15, 100),
        "volume": np.random.uniform(100000, 500000, 100),
        "amount": np.random.uniform(1000000, 5000000, 100),
        "amplitude": np.random.uniform(1, 5, 100),
        "change_percent": np.random.uniform(-5, 5, 100),
        "change_amount": np.random.uniform(-1, 1, 100),
        "turnover_rate": np.random.uniform(0.5, 5, 100),
    }
    return pd.DataFrame(data)


@pytest.fixture
def temp_source_db(sample_kline_data):
    """创建临时源数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    sample_kline_data.to_sql("stock_klines", conn, if_exists="replace", index=False)
    conn.close()

    yield db_path

    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def temp_target_db():
    """创建临时目标数据库路径"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    if db_path.exists():
        db_path.unlink()


class TestDataExtractor:
    """数据提取器测试"""

    def test_extract_stock_data(self, temp_source_db):
        """测试提取股票数据"""
        extractor = DataExtractor(temp_source_db)
        extractor.connect()

        codes = extractor.get_stock_codes()
        assert len(codes) == 1
        assert codes[0] == "sh600000"

        df = extractor.extract_stock_data("sh600000")
        assert len(df) == 100
        assert "close" in df.columns

        extractor.close()

    def test_get_stock_count(self, temp_source_db):
        """测试获取股票数量"""
        extractor = DataExtractor(temp_source_db)
        extractor.connect()

        count = extractor.get_stock_count()
        assert count == 1

        extractor.close()

    def test_get_total_records(self, temp_source_db):
        """测试获取总记录数"""
        extractor = DataExtractor(temp_source_db)
        extractor.connect()

        total = extractor.get_total_records()
        assert total == 100

        extractor.close()


class TestDataTransformer:
    """数据转换器测试"""

    def test_transform_basic(self, sample_kline_data):
        """测试基本数据转换"""
        config = ETLConfig(
            source_db=Path("dummy"),
            target_db=Path("dummy"),
        )
        transformer = DataTransformer(config)

        df = transformer.transform(sample_kline_data)

        assert len(df) == 100
        assert str(df["date"].dtype).startswith("datetime64")

    def test_calculate_ma(self, sample_kline_data):
        """测试移动平均线计算"""
        config = ETLConfig(
            source_db=Path("dummy"),
            target_db=Path("dummy"),
            calculate_indicators=True,
        )
        transformer = DataTransformer(config)

        df = transformer.transform(sample_kline_data)

        assert "ma5" in df.columns
        assert "ma10" in df.columns
        assert "ma20" in df.columns
        assert "ma60" in df.columns

    def test_calculate_macd(self, sample_kline_data):
        """测试 MACD 计算"""
        config = ETLConfig(
            source_db=Path("dummy"),
            target_db=Path("dummy"),
            calculate_indicators=True,
        )
        transformer = DataTransformer(config)

        df = transformer.transform(sample_kline_data)

        assert "macd" in df.columns
        assert "macd_signal" in df.columns
        assert "macd_hist" in df.columns

    def test_calculate_rsi(self, sample_kline_data):
        """测试 RSI 计算"""
        config = ETLConfig(
            source_db=Path("dummy"),
            target_db=Path("dummy"),
            calculate_indicators=True,
        )
        transformer = DataTransformer(config)

        df = transformer.transform(sample_kline_data)

        assert "rsi" in df.columns
        assert df["rsi"].max() <= 100
        assert df["rsi"].min() >= 0

    def test_calculate_boll(self, sample_kline_data):
        """测试布林带计算"""
        config = ETLConfig(
            source_db=Path("dummy"),
            target_db=Path("dummy"),
            calculate_indicators=True,
        )
        transformer = DataTransformer(config)

        df = transformer.transform(sample_kline_data)

        assert "boll_upper" in df.columns
        assert "boll_lower" in df.columns
        assert "boll_mid" in df.columns

    def test_calculate_kdj(self, sample_kline_data):
        """测试 KDJ 计算"""
        config = ETLConfig(
            source_db=Path("dummy"),
            target_db=Path("dummy"),
            calculate_indicators=True,
        )
        transformer = DataTransformer(config)

        df = transformer.transform(sample_kline_data)

        assert "kdj_k" in df.columns
        assert "kdj_d" in df.columns
        assert "kdj_j" in df.columns

    def test_no_indicators(self, sample_kline_data):
        """测试不计算技术指标"""
        config = ETLConfig(
            source_db=Path("dummy"),
            target_db=Path("dummy"),
            calculate_indicators=False,
        )
        transformer = DataTransformer(config)

        df = transformer.transform(sample_kline_data)

        assert "ma5" not in df.columns
        assert "macd" not in df.columns


class TestDataLoader:
    """数据加载器测试"""

    def test_create_tables(self, temp_target_db):
        """测试创建表"""
        loader = DataLoader(temp_target_db)
        loader.connect()

        conn = sqlite3.connect(str(temp_target_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert "stock_analysis" in tables
        assert "etl_logs" in tables

        loader.close()

    def test_load_stock_data(self, temp_target_db, sample_kline_data):
        """测试加载股票数据"""
        config = ETLConfig(
            source_db=Path("dummy"),
            target_db=Path("dummy"),
            calculate_indicators=True,
        )
        transformer = DataTransformer(config)
        loader = DataLoader(temp_target_db)
        loader.connect()

        transformed_df = transformer.transform(sample_kline_data)
        count = loader.load_stock_data(transformed_df)

        assert count == 100

        conn = sqlite3.connect(str(temp_target_db))
        df = pd.read_sql_query("SELECT * FROM stock_analysis", conn)
        conn.close()

        assert len(df) == 100

        loader.close()


class TestETLPipeline:
    """ETL 管道测试"""

    def test_run_pipeline(self, temp_source_db, temp_target_db):
        """测试运行 ETL 管道"""
        config = ETLConfig(
            source_db=temp_source_db,
            target_db=temp_target_db,
            min_data_days=10,
        )

        pipeline = ETLPipeline(config)
        result = pipeline.run()

        assert result.stocks_processed == 1
        assert result.records_extracted == 100
        assert result.records_loaded > 0
        assert len(result.errors) == 0

    def test_get_statistics(self, temp_source_db, temp_target_db):
        """测试获取统计信息"""
        config = ETLConfig(
            source_db=temp_source_db,
            target_db=temp_target_db,
        )

        pipeline = ETLPipeline(config)
        pipeline.run()

        stats = pipeline.get_statistics()

        assert stats["stock_count"] == 1
        assert stats["total_records"] > 0

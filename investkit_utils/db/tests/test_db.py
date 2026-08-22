"""db 模块测试"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


class TestConstants:
    def test_excluded_keywords_not_empty(self):
        from investkit_utils.db.constants import EXCLUDED_KEYWORDS

        assert len(EXCLUDED_KEYWORDS) > 0
        assert "ST" in EXCLUDED_KEYWORDS

    def test_is_excluded_stock_with_st(self):
        from investkit_utils.db.constants import is_excluded_stock

        assert is_excluded_stock("ST平安") is True
        assert is_excluded_stock("*ST华业") is True
        assert is_excluded_stock("退市股") is True

    def test_is_excluded_stock_normal(self):
        from investkit_utils.db.constants import is_excluded_stock

        assert is_excluded_stock("贵州茅台") is False
        assert is_excluded_stock("中国平安") is False

    def test_is_excluded_stock_disabled(self):
        from investkit_utils.db.constants import is_excluded_stock

        assert is_excluded_stock("ST平安", exclude_st=False) is False


class TestPaths:
    def test_data_dir_exists(self):
        from investkit_utils.db.paths import DATA_DIR

        assert DATA_DIR.name == "data"

    def test_get_db_path_default(self):
        from investkit_utils.db.paths import get_db_path

        result = get_db_path()
        assert isinstance(result, Path)
        assert result.name == "asset_lens.db"

    def test_get_db_path_custom_name(self):
        from investkit_utils.db.paths import get_db_path

        result = get_db_path("test.db")
        assert result.name == "test.db"

    def test_get_asset_lens_db_path(self):
        from investkit_utils.db.paths import get_asset_lens_db_path

        result = get_asset_lens_db_path()
        assert isinstance(result, Path)
        assert "asset_lens" in str(result)

    def test_get_stock_analysis_db_path(self):
        from investkit_utils.db.paths import get_stock_analysis_db_path

        result = get_stock_analysis_db_path()
        assert isinstance(result, Path)
        assert "stock_analysis" in str(result)

    def test_get_stock_klines_db_path(self):
        from investkit_utils.db.paths import get_stock_klines_db_path

        result = get_stock_klines_db_path()
        assert isinstance(result, Path)
        assert "stock_klines" in str(result)

    def test_ensure_data_dir(self):
        from investkit_utils.db.paths import ensure_data_dir

        result = ensure_data_dir()
        assert result.exists()

    def test_env_var_override(self):
        from investkit_utils.db.paths import get_db_path

        original = os.environ.get("INVESTKIT_DB_PATH")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.environ["INVESTKIT_DB_PATH"] = tmpdir
                result = get_db_path("custom.db")
                assert tmpdir in str(result)
                assert result.name == "custom.db"
        finally:
            if original is None:
                os.environ.pop("INVESTKIT_DB_PATH", None)
            else:
                os.environ["INVESTKIT_DB_PATH"] = original


class TestConnection:
    def test_db_connection_context_manager(self):
        from investkit_utils.db.connection import db_connection

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_file = f.name
        try:
            with db_connection(Path(db_file)) as conn:
                assert isinstance(conn, sqlite3.Connection)
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
                cursor = conn.execute("SELECT COUNT(*) FROM test")
                assert cursor.fetchone()[0] == 0
        finally:
            os.unlink(db_file)

    def test_db_transaction_success(self):
        from investkit_utils.db.connection import db_connection

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_file = f.name
        try:
            with db_connection(Path(db_file)) as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
                conn.execute("INSERT INTO test VALUES (1)")
            with db_connection(Path(db_file)) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM test")
                assert cursor.fetchone()[0] == 1
        finally:
            os.unlink(db_file)

    def test_db_transaction_rollback(self):
        from investkit_utils.db.connection import db_connection

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_file = f.name
        try:
            with pytest.raises(RuntimeError):
                with db_connection(Path(db_file)) as conn:
                    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
                    raise RuntimeError("test error")
        finally:
            os.unlink(db_file)

    def test_db_transaction_deprecated(self):
        from investkit_utils.db.connection import db_transaction

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_file = f.name
        try:
            with pytest.warns(DeprecationWarning, match="db_transaction is deprecated"):
                with db_transaction(Path(db_file)) as conn:
                    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        finally:
            os.unlink(db_file)


class TestModels:
    @pytest.fixture
    def engine_session(self):
        from investkit_utils.db.models import init_database

        return init_database("sqlite:///:memory:")

    def test_base_exists(self):
        from investkit_utils.db.models import Base

        assert Base is not None

    def test_stockkline_model(self):
        from investkit_utils.db.models import StockKline

        kline = StockKline(
            code="sh600519",
            date="2024-01-15",
            open=1800.0,
            close=1810.0,
            high=1820.0,
            low=1790.0,
        )
        d = kline.to_dict()
        assert d["date"] == "2024-01-15"
        assert d["close"] == 1810.0

    def test_stockinfo_model(self):
        from investkit_utils.db.models import DBStockInfo

        info = DBStockInfo(code="sh600519", name="贵州茅台")
        assert info.code == "sh600519"
        assert info.name == "贵州茅台"

    def test_mlmodel_model(self):
        from investkit_utils.db.models import MLModel

        model = MLModel(name="test_model", model_type="lightgbm")
        assert model.name == "test_model"
        assert model.model_type == "lightgbm"

    def test_prediction_record_model(self):
        from investkit_utils.db.models import PredictionRecord

        record = PredictionRecord(
            code="sh600519",
            predict_date="2024-01-15",
            prediction=1,
            confidence=0.85,
        )
        assert record.code == "sh600519"
        assert record.prediction == 1

    def test_data_sync_log_model(self):
        from datetime import datetime

        from investkit_utils.db.models import DataSyncLog

        log = DataSyncLog(data_type="stock_klines", sync_start=datetime.now(), status="running")
        assert log.data_type == "stock_klines"
        assert log.status == "running"

    def test_north_industry_flow_model(self):
        from investkit_utils.db.models import NorthIndustryFlow

        flow = NorthIndustryFlow(date="2024-01-15", industry="银行", net_inflow=10000000)
        d = flow.to_dict()
        assert d["industry"] == "银行"
        assert d["net_inflow"] == 10000000

    def test_init_database_creates_tables(self, engine_session):
        from sqlalchemy import inspect

        engine, _ = engine_session
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "stock_klines" in tables
        assert "stock_info" in tables

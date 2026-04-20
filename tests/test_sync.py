"""
Tests for Data Sync Module.
数据同步模块测试
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.data.sync import (
    get_db_info,
    run_sync,
    sync_from_external_db,
)


@pytest.fixture
def temp_source_db():
    """创建临时源数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE stock_klines (
            code TEXT,
            date TEXT,
            open REAL,
            close REAL,
            high REAL,
            low REAL,
            volume REAL
        )
    """)

    test_data = [
        ("000001", "2024-01-01", 10.0, 10.5, 10.8, 9.9, 1000000),
        ("000001", "2024-01-02", 10.5, 10.3, 10.6, 10.2, 1200000),
        ("000002", "2024-01-01", 20.0, 20.5, 20.8, 19.9, 2000000),
    ]
    conn.executemany(
        "INSERT INTO stock_klines VALUES (?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


@pytest.fixture
def temp_target_dir():
    """创建临时目标目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestSyncFromExternalDb:
    """测试数据库同步"""

    def test_sync_no_source(self, temp_target_dir):
        """测试未指定源路径"""
        result = sync_from_external_db(source_path=None, target_path=temp_target_dir / "test.db")
        assert result["success"] is False
        assert "未指定" in result["message"]

    def test_sync_source_not_exists(self, temp_target_dir):
        """测试源文件不存在"""
        result = sync_from_external_db(
            source_path="/nonexistent/path.db",
            target_path=temp_target_dir / "test.db",
        )
        assert result["success"] is False
        assert "不存在" in result["message"]

    def test_sync_success(self, temp_source_db, temp_target_dir):
        """测试同步成功"""
        target_path = temp_target_dir / "target.db"
        result = sync_from_external_db(
            source_path=temp_source_db,
            target_path=target_path,
            backup=False,
        )

        assert result["success"] is True
        assert result["source_size"] > 0
        assert result["target_size"] > 0
        assert target_path.exists()

    def test_sync_with_backup(self, temp_source_db, temp_target_dir):
        """测试带备份的同步"""
        target_path = temp_target_dir / "target.db"

        target_path.write_bytes(b"dummy")

        result = sync_from_external_db(
            source_path=temp_source_db,
            target_path=target_path,
            backup=True,
        )

        assert result["success"] is True
        assert result["backup_created"] is True
        assert result["backup_path"] is not None

        backup_path = Path(result["backup_path"])
        assert backup_path.exists()
        backup_path.unlink(missing_ok=True)

    def test_sync_no_backup(self, temp_source_db, temp_target_dir):
        """测试不带备份的同步"""
        target_path = temp_target_dir / "target.db"

        target_path.write_bytes(b"dummy")

        result = sync_from_external_db(
            source_path=temp_source_db,
            target_path=target_path,
            backup=False,
        )

        assert result["success"] is True
        assert result["backup_created"] is False

    def test_sync_with_env_variable(self, temp_source_db, temp_target_dir):
        """测试通过环境变量指定源路径"""
        target_path = temp_target_dir / "target.db"

        with patch.dict(os.environ, {"SYNC_DB_SOURCE": str(temp_source_db)}):
            result = sync_from_external_db(
                source_path=None,
                target_path=target_path,
            )

        assert result["success"] is True


class TestGetDbInfo:
    """测试获取数据库信息"""

    def test_get_info_no_path(self):
        """测试未指定路径"""
        info = get_db_info(source_path=None)
        assert info["path"] is None
        assert info["exists"] is False

    def test_get_info_not_exists(self):
        """测试文件不存在"""
        info = get_db_info(source_path="/nonexistent/path.db")
        assert info["exists"] is False

    def test_get_info_success(self, temp_source_db):
        """测试获取信息成功"""
        info = get_db_info(source_path=temp_source_db)

        assert info["exists"] is True
        assert info["size"] > 0
        assert "stock_klines" in info["tables"]
        assert info["stock_count"] == 2
        assert info["kline_count"] == 3
        assert info["last_update"] == "2024-01-02"

    def test_get_info_with_env_variable(self, temp_source_db):
        """测试通过环境变量获取信息"""
        with patch.dict(os.environ, {"SYNC_DB_SOURCE": str(temp_source_db)}):
            info = get_db_info(source_path=None)

        assert info["exists"] is True

    def test_get_info_no_stock_klines_table(self):
        """测试没有 stock_klines 表"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE other_table (id INTEGER)")
        conn.commit()
        conn.close()

        info = get_db_info(source_path=db_path)

        assert info["exists"] is True
        assert info["stock_count"] == 0
        assert info["kline_count"] == 0

        db_path.unlink(missing_ok=True)


class TestRunSync:
    """测试运行同步"""

    def test_run_sync_no_source(self):
        """测试未指定源"""
        with patch.dict(os.environ, {}, clear=True):
            result = run_sync(source_path=None)
        assert result["success"] is False

    def test_run_sync_source_not_exists(self):
        """测试源不存在"""
        result = run_sync(source_path="/nonexistent/path.db")
        assert result["success"] is False

    def test_run_sync_success(self, temp_source_db, temp_target_dir):
        """测试同步成功"""
        result = run_sync(
            source_path=temp_source_db,
            backup=False,
        )

        assert result["success"] is True

"""
Tests for Data Sync Module.
数据同步模块测试
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestSyncEnvFromExternal:
    """测试环境变量同步"""

    def test_no_source_path(self):
        """测试未指定源路径"""
        with patch.dict(os.environ, {}, clear=True):
            from src.data.sync_env import sync_env_from_external

            result = sync_env_from_external()
            assert result["success"] is False
            assert "未指定源文件路径" in result["error"]

    def test_source_not_found(self):
        """测试源文件不存在"""
        from src.data.sync_env import sync_env_from_external

        result = sync_env_from_external("/nonexistent/path/.env")
        assert result["success"] is False
        assert "不存在" in result["error"]

    def test_sync_success(self):
        """测试同步成功"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_env = Path(tmpdir) / ".env"
            source_env.write_text("TEST_KEY=test_value\nAPI_KEY=secret123\n")

            from src.data.sync_env import sync_env_from_external

            result = sync_env_from_external(source_env)
            assert result["success"] is True
            assert "TEST_KEY" in result["keys"]
            assert "API_KEY" in result["keys"]

    def test_sync_with_env_variable(self):
        """测试通过环境变量指定源路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_env = Path(tmpdir) / ".env"
            source_env.write_text("KEY1=value1\n")

            with patch.dict(os.environ, {"SYNC_ENV_SOURCE": str(source_env)}):
                from src.data.sync_env import sync_env_from_external

                result = sync_env_from_external()
                assert result["success"] is True
                assert "KEY1" in result["keys"]


class TestRunSyncEnv:
    """测试运行环境变量同步"""

    def test_run_sync_env_success(self):
        """测试成功运行"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_env = Path(tmpdir) / ".env"
            source_env.write_text("KEY1=value1\nKEY2=value2\n")

            from src.data.sync_env import run_sync_env

            result = run_sync_env(source_env)
            assert result["success"] is True
            assert len(result["keys"]) == 2

    def test_run_sync_env_failure(self):
        """测试失败情况"""
        from src.data.sync_env import run_sync_env

        result = run_sync_env("/nonexistent/.env")
        assert result["success"] is False

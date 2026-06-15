"""InvestKit 配置模块测试"""

import os
import tempfile
from pathlib import Path

import pytest

from investkit_utils.config import (
    Config,
    ConfigLoader,
    clear_config_cache,
    get_config,
    reload_config,
    set_config_path,
)
from investkit_utils.config.models import (
    AppConfig,
    Environment,
    LoggingConfig,
    LoggingFormat,
)
from investkit_utils.utils.data_utils import deep_merge


class TestConfigModels:
    def test_app_config_defaults(self):
        config = AppConfig()
        assert config.name == "investkit-app"
        assert config.version == "1.0.0"
        assert config.debug is False
        assert config.environment == Environment.DEVELOPMENT

    def test_logging_config_defaults(self):
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == LoggingFormat.JSON
        assert config.output.console is True
        assert config.output.file is False

    def test_logging_config_invalid_level(self):
        with pytest.raises(ValueError):
            LoggingConfig(level="INVALID")

    def test_config_defaults(self):
        config = Config()
        assert config.app.name == "investkit-app"
        assert config.database.type.value == "sqlite"
        assert config.cache.enabled is True
        assert config.llm.default_provider.value == "ollama"


class TestConfigLoader:
    def test_load_from_file(self):
        config_path = Path(__file__).parent / "config.base.yaml"
        if config_path.exists():
            config = ConfigLoader.load_from_file(config_path)
            assert config is not None
            assert config.app.name == "investkit"

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load_from_file("nonexistent.yaml")

    def test_substitute_env_vars(self):
        os.environ["TEST_VAR"] = "test_value"
        data = {"app": {"name": "${TEST_VAR}"}}
        result = ConfigLoader._substitute_env_vars(data)
        assert result["app"]["name"] == "test_value"
        del os.environ["TEST_VAR"]

    def test_substitute_missing_env_var(self):
        data = {"app": {"name": "${MISSING_VAR}"}}
        result = ConfigLoader._substitute_env_vars(data)
        assert result["app"]["name"] == ""

    def test_deep_merge(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 10}}
        result = deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 10
        assert result["b"]["d"] == 3


class TestConfigFunctions:
    def setup_method(self):
        clear_config_cache()

    def test_get_config_default(self):
        config = get_config()
        assert config is not None
        assert isinstance(config, Config)

    def test_get_config_cached(self):
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config(self):
        config1 = get_config()
        config2 = reload_config()
        assert config1 is not config2

    def test_set_config_path(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("app:\n  name: test-app\n")
            f.flush()
            set_config_path(f.name)
            clear_config_cache()
            config = get_config()
            assert config.app.name == "test-app"
            os.unlink(f.name)


class TestConfigMerge:
    def test_merge_configs(self):
        base = Config()
        override = {"app": {"name": "merged-app", "debug": True}}
        merged = base.merge(override)
        assert merged.app.name == "merged-app"
        assert merged.app.debug is True

    def test_merge_with_config_object(self):
        base = Config()
        override = Config(app=AppConfig(name="override-app"))
        merged = base.merge(override)
        assert merged.app.name == "override-app"

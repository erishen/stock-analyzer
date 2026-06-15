import os
import tempfile
from pathlib import Path

import pytest

from investkit_utils.config.loader import (
    ConfigLoader,
    clear_config_cache,
    get_config,
    reload_config,
    set_config_path,
)
from investkit_utils.config.models import (
    AppConfig,
    CacheConfig,
    CacheType,
    Config,
    DatabaseConfig,
    DatabaseType,
    Environment,
    LLMConfig,
    LLMProvider,
    LoggingConfig,
    LoggingFormat,
)


class TestConfigLoaderEnvVars:
    def test_substitute_nested(self):
        os.environ["TEST_HOST"] = "myhost"
        data = {"db": {"host": "${TEST_HOST}", "port": 5432}}
        result = ConfigLoader._substitute_env_vars(data)
        assert result["db"]["host"] == "myhost"
        assert result["db"]["port"] == 5432
        del os.environ["TEST_HOST"]

    def test_substitute_list(self):
        os.environ["TEST_ITEM"] = "item1"
        data = {"items": ["${TEST_ITEM}", "static"]}
        result = ConfigLoader._substitute_env_vars(data)
        assert result["items"][0] == "item1"
        del os.environ["TEST_ITEM"]

    def test_substitute_non_string(self):
        data = {"num": 42, "flag": True}
        result = ConfigLoader._substitute_env_vars(data)
        assert result["num"] == 42
        assert result["flag"] is True

    def test_load_from_files_merge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            override = Path(tmpdir) / "override.yaml"
            base.write_text("app:\n  name: base\n  debug: false\n")
            override.write_text("app:\n  debug: true\n")
            config = ConfigLoader.load_from_files(base, override)
            assert config.app.name == "base"
            assert config.app.debug is True

    def test_load_from_files_skip_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            base.write_text("app:\n  name: test\n")
            config = ConfigLoader.load_from_files(base, Path(tmpdir) / "missing.yaml")
            assert config.app.name == "test"


class TestConfigModelsExtended:
    def test_environment_enum(self):
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"

    def test_database_type_enum(self):
        assert DatabaseType.SQLITE.value == "sqlite"
        assert DatabaseType.POSTGRESQL.value == "postgresql"

    def test_cache_type_enum(self):
        assert CacheType.MEMORY.value == "memory"
        assert CacheType.REDIS.value == "redis"

    def test_llm_provider_enum(self):
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.OLLAMA.value == "ollama"

    def test_database_config_defaults(self):
        config = DatabaseConfig()
        assert config.type == DatabaseType.SQLITE
        assert config.sqlite.path == "data/app.db"
        assert config.pool.size == 5

    def test_cache_config_defaults(self):
        config = CacheConfig()
        assert config.enabled is True
        assert config.type == CacheType.MEMORY
        assert config.ttl == 3600

    def test_llm_config_defaults(self):
        config = LLMConfig()
        assert config.default_provider == LLMProvider.OLLAMA
        assert config.openai.model == "gpt-4"

    def test_config_extra_fields(self):
        config = Config(**{"custom_field": "custom_value"})
        assert config.custom_field == "custom_value"

    def test_config_merge(self):
        base = Config()
        merged = base.merge({"app": {"name": "merged"}})
        assert merged.app.name == "merged"

    def test_logging_config_level_normalization(self):
        config = LoggingConfig(level="info")
        assert config.level == "INFO"


class TestConfigFunctionsExtended:
    def setup_method(self):
        clear_config_cache()
        import investkit_utils.config.loader as loader_mod
        loader_mod._default_config_path = None

    def teardown_method(self):
        clear_config_cache()
        import investkit_utils.config.loader as loader_mod
        loader_mod._default_config_path = None

    def test_get_config_default(self):
        config = get_config()
        assert isinstance(config, Config)

    def test_reload_clears_cache(self):
        c1 = get_config()
        c2 = reload_config()
        assert c1 is not c2

    def test_set_config_path_and_load(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("app:\n  name: path-test\n")
            f.flush()
            set_config_path(f.name)
            clear_config_cache()
            config = get_config()
            assert config.app.name == "path-test"
            os.unlink(f.name)

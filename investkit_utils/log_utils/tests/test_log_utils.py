"""log_utils 模块测试"""

import json
import logging
import tempfile
from pathlib import Path


class TestLogConfig:
    def test_log_format_enum(self):
        from investkit_utils.config.models import LoggingFormat

        assert LoggingFormat.JSON.value == "json"
        assert LoggingFormat.TEXT.value == "text"

    def test_log_level_enum(self):
        from investkit_utils.log_utils.config import LogLevel

        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_logging_config_defaults(self):
        from investkit_utils.config.models import LoggingConfig, LoggingFormat

        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == LoggingFormat.JSON
        assert config.output.console is True
        assert config.output.file is False
        assert config.fields.include_timestamp is True
        assert config.fields.include_module is True
        assert config.fields.include_correlation_id is True

    def test_logging_config_custom(self):
        from investkit_utils.config.models import (
            LoggingConfig,
            LoggingFormat,
            LoggingOutputConfig,
        )

        config = LoggingConfig(
            level="DEBUG",
            format=LoggingFormat.TEXT,
            output=LoggingOutputConfig(
                console=False,
                file=True,
                path="/tmp/test.log",
            ),
        )
        assert config.level == "DEBUG"
        assert config.format == LoggingFormat.TEXT
        assert config.output.console is False
        assert config.output.file is True


class TestContext:
    def test_set_and_get_correlation_id(self):
        from investkit_utils.log_utils.context import get_correlation_id, set_correlation_id

        set_correlation_id("test-123")
        assert get_correlation_id() == "test-123"

    def test_default_correlation_id(self):
        from investkit_utils.log_utils.context import _correlation_id

        _correlation_id.set(None)
        from investkit_utils.log_utils.context import get_correlation_id

        assert get_correlation_id() is None

    def test_correlation_id_overwrite(self):
        from investkit_utils.log_utils.context import get_correlation_id, set_correlation_id

        set_correlation_id("first")
        set_correlation_id("second")
        assert get_correlation_id() == "second"


class TestFormatters:
    def test_json_formatter_basic(self):
        from investkit_utils.log_utils.formatters import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "hello"
        assert data["level"] == "INFO"
        assert "timestamp" in data

    def test_json_formatter_with_module(self):
        from investkit_utils.log_utils.formatters import JsonFormatter

        formatter = JsonFormatter(include_module=True)
        record = logging.LogRecord(
            name="test.module",
            level=logging.WARNING,
            pathname="test.py",
            lineno=42,
            msg="warning msg",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "module" in data
        assert "line" in data

    def test_json_formatter_without_module(self):
        from investkit_utils.log_utils.formatters import JsonFormatter

        formatter = JsonFormatter(include_module=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "module" not in data

    def test_json_formatter_with_correlation_id(self):
        from investkit_utils.log_utils.context import set_correlation_id
        from investkit_utils.log_utils.formatters import JsonFormatter

        set_correlation_id("corr-123")
        formatter = JsonFormatter(include_correlation_id=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data.get("correlation_id") == "corr-123"

    def test_text_formatter_basic(self):
        from investkit_utils.log_utils.formatters import TextFormatter

        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "hello" in output
        assert "INFO" in output

    def test_text_formatter_with_correlation_id(self):
        from investkit_utils.log_utils.context import set_correlation_id
        from investkit_utils.log_utils.formatters import TextFormatter

        set_correlation_id("corr-123")
        formatter = TextFormatter(include_correlation_id=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "corr-123"[:8] in output


class TestInvestKitLogger:
    def test_logger_creation(self):
        from investkit_utils.log_utils.logger import InvestKitLogger

        logger = InvestKitLogger("test")
        assert logger.name == "test"

    def test_info_with_data(self):
        from investkit_utils.log_utils.logger import InvestKitLogger

        logger = InvestKitLogger("test.data.info")
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info_with_data("test message", data={"key": "value"})
        logger.removeHandler(handler)

    def test_error_with_data(self):
        from investkit_utils.log_utils.logger import InvestKitLogger

        logger = InvestKitLogger("test.data.error")
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.error_with_data("error msg", data={"code": 500})
        logger.removeHandler(handler)

    def test_warning_with_data(self):
        from investkit_utils.log_utils.logger import InvestKitLogger

        logger = InvestKitLogger("test.data.warning")
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.warning_with_data("warning msg", data={"level": "warn"})
        logger.removeHandler(handler)

    def test_debug_with_data(self):
        from investkit_utils.log_utils.logger import InvestKitLogger

        logger = InvestKitLogger("test.data.debug")
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.debug_with_data("debug msg", data={"detail": "info"})
        logger.removeHandler(handler)


class TestLoggerManager:
    def test_configure_default(self):
        from investkit_utils.config.models import LoggingConfig
        from investkit_utils.log_utils.manager import LoggerManager

        LoggerManager.configure(LoggingConfig())
        assert LoggerManager._initialized is True
        assert LoggerManager._config.level == "INFO"

    def test_configure_custom(self):
        from investkit_utils.config.models import LoggingConfig, LoggingFormat
        from investkit_utils.log_utils.manager import LoggerManager

        config = LoggingConfig(level="DEBUG", format=LoggingFormat.TEXT)
        LoggerManager.configure(config)
        assert LoggerManager._config.level == "DEBUG"
        assert LoggerManager._config.format == LoggingFormat.TEXT

    def test_get_config(self):
        from investkit_utils.config.models import LoggingConfig
        from investkit_utils.log_utils.manager import LoggerManager

        LoggerManager.configure(LoggingConfig(level="WARNING"))
        config = LoggerManager.get_config()
        assert config.level == "WARNING"

    def test_get_logger(self):
        from investkit_utils.log_utils.logger import InvestKitLogger
        from investkit_utils.log_utils.manager import get_logger

        logger = get_logger("test.module")
        assert isinstance(logger, InvestKitLogger)

    def test_setup_logging(self):
        from investkit_utils.log_utils.manager import LoggerManager, setup_logging

        setup_logging(level="DEBUG", log_format="text")
        assert LoggerManager._config.level == "DEBUG"

    def test_setup_logging_with_file(self):
        from investkit_utils.log_utils.manager import LoggerManager, setup_logging

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "test.log")
            setup_logging(level="INFO", log_format="json", file_path=log_file)
            assert LoggerManager._config.output.file is True
            assert LoggerManager._config.output.path == log_file

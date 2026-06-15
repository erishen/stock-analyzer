import json
import logging

from investkit_utils.log_utils.context import get_correlation_id, set_correlation_id
from investkit_utils.log_utils.formatters import JsonFormatter, TextFormatter


class TestContext:
    def test_set_and_get(self):
        set_correlation_id("test-123")
        assert get_correlation_id() == "test-123"

    def test_default_is_none(self):
        set_correlation_id(None)
        assert get_correlation_id() is None

    def test_overwrite(self):
        set_correlation_id("first")
        set_correlation_id("second")
        assert get_correlation_id() == "second"


class TestJsonFormatter:
    def _make_record(self, msg="hello", level=logging.INFO, name="test"):
        return logging.LogRecord(
            name=name,
            level=level,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_basic_format(self):
        formatter = JsonFormatter()
        output = formatter.format(self._make_record())
        data = json.loads(output)
        assert data["message"] == "hello"
        assert data["level"] == "INFO"
        assert "timestamp" in data

    def test_with_module(self):
        formatter = JsonFormatter(include_module=True)
        output = formatter.format(self._make_record())
        data = json.loads(output)
        assert "module" in data
        assert "line" in data

    def test_without_module(self):
        formatter = JsonFormatter(include_module=False)
        output = formatter.format(self._make_record())
        data = json.loads(output)
        assert "module" not in data

    def test_with_correlation_id(self):
        set_correlation_id("corr-abc")
        formatter = JsonFormatter(include_correlation_id=True)
        output = formatter.format(self._make_record())
        data = json.loads(output)
        assert data.get("correlation_id") == "corr-abc"
        set_correlation_id(None)

    def test_without_correlation_id(self):
        set_correlation_id(None)
        formatter = JsonFormatter(include_correlation_id=True)
        output = formatter.format(self._make_record())
        data = json.loads(output)
        assert "correlation_id" not in data

    def test_without_correlation_id_flag(self):
        set_correlation_id("corr-abc")
        formatter = JsonFormatter(include_correlation_id=False)
        output = formatter.format(self._make_record())
        data = json.loads(output)
        assert "correlation_id" not in data
        set_correlation_id(None)

    def test_warning_level(self):
        formatter = JsonFormatter()
        output = formatter.format(self._make_record(level=logging.WARNING))
        data = json.loads(output)
        assert data["level"] == "WARNING"

    def test_unicode_message(self):
        formatter = JsonFormatter()
        output = formatter.format(self._make_record(msg="中文消息"))
        data = json.loads(output)
        assert data["message"] == "中文消息"


class TestTextFormatter:
    def _make_record(self, msg="hello", level=logging.INFO, name="test"):
        return logging.LogRecord(
            name=name,
            level=level,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_basic_format(self):
        formatter = TextFormatter()
        output = formatter.format(self._make_record())
        assert "hello" in output
        assert "INFO" in output

    def test_with_module(self):
        formatter = TextFormatter(include_module=True)
        output = formatter.format(self._make_record())
        assert "test" in output

    def test_without_module(self):
        formatter = TextFormatter(include_module=False)
        output = formatter.format(self._make_record())
        assert "hello" in output

    def test_with_correlation_id(self):
        set_correlation_id("corr-12345678")
        formatter = TextFormatter(include_correlation_id=True)
        output = formatter.format(self._make_record())
        assert "corr-123" in output
        set_correlation_id(None)

    def test_without_correlation_id(self):
        set_correlation_id(None)
        formatter = TextFormatter(include_correlation_id=True)
        output = formatter.format(self._make_record())
        assert "hello" in output

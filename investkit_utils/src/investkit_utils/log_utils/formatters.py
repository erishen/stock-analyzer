"""日志格式化器"""

import json
from datetime import UTC, datetime
from logging import Formatter, LogRecord
from typing import Any

from investkit_utils.log_utils.context import get_correlation_id


class JsonFormatter(Formatter):
    """JSON 格式日志格式化器"""

    def __init__(self, include_module: bool = True, include_correlation_id: bool = True):
        super().__init__()
        self.include_module = include_module
        self.include_correlation_id = include_correlation_id

    def format(self, record: LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        if self.include_module:
            log_data["module"] = record.module
            log_data["function"] = record.funcName
            log_data["line"] = record.lineno

        if self.include_correlation_id:
            cid = get_correlation_id()
            if cid:
                log_data["correlation_id"] = cid

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data") and record.extra_data:
            log_data["data"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(Formatter):
    """文本格式日志格式化器"""

    def __init__(self, include_module: bool = True, include_correlation_id: bool = True):
        self.include_module = include_module
        self.include_correlation_id = include_correlation_id
        super().__init__()

    def format(self, record: LogRecord) -> str:
        parts = [
            datetime.now(UTC).isoformat() + "Z",
            f"[{record.levelname:8}]",
        ]

        if self.include_module:
            parts.append(f"{record.name}:{record.module}:{record.lineno}")

        if self.include_correlation_id:
            cid = get_correlation_id()
            if cid:
                parts.append(f"[{cid[:8]}]")

        parts.append(record.getMessage())

        if record.exc_info:
            parts.append("\n" + self.formatException(record.exc_info))

        return " ".join(parts)

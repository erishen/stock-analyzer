"""日志配置"""

from enum import Enum

from investkit_utils.config.models import (
    LoggingFormat,
)

LogFormat = LoggingFormat


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

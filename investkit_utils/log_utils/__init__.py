"""
InvestKit 统一日志模块

提供统一的日志格式和配置，所有项目应使用此模块进行日志记录。

使用示例:
    from investkit_utils.log_utils import get_logger, setup_logging

    logger = get_logger(__name__)
    logger.info("操作成功", extra={"user_id": "123", "action": "login"})
"""

from investkit_utils.log_utils.config import (
    LogFormat,
    LoggingFormat,
    LogLevel,
)
from investkit_utils.config.models import LoggingConfig
from investkit_utils.log_utils.context import (
    get_correlation_id,
    set_correlation_id,
)
from investkit_utils.log_utils.logger import InvestKitLogger
from investkit_utils.log_utils.manager import (
    LoggerManager,
    get_logger,
    setup_logging,
)

__all__ = [
    "InvestKitLogger",
    "LogFormat",
    "LogLevel",
    "LoggerManager",
    "LoggingConfig",
    "LoggingFormat",
    "get_correlation_id",
    "get_logger",
    "set_correlation_id",
    "setup_logging",
]

"""
InvestKit 统一异常处理

提供统一的异常定义和处理机制。

使用示例:
    from investkit_utils.exceptions import InvestKitError, ValidationError

    raise ValidationError("无效的股票代码", field="stock_code", value="ABC")
"""

from investkit_utils.exceptions.base import (
    AuthenticationError,
    AuthorizationError,
    CacheError,
    ConfigurationError,
    DatabaseError,
    DataError,
    ExternalServiceError,
    InvestKitError,
    LLMError,
    MLModelError,
    NotFoundError,
    RateLimitError,
    TradingError,
    ValidationError,
)
from investkit_utils.exceptions.handlers import (
    handle_exception,
    raise_for_status,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "CacheError",
    "ConfigurationError",
    "DataError",
    "DatabaseError",
    "ExternalServiceError",
    "InvestKitError",
    "LLMError",
    "MLModelError",
    "NotFoundError",
    "RateLimitError",
    "TradingError",
    "ValidationError",
    "handle_exception",
    "raise_for_status",
]

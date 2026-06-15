"""基础异常类"""

from typing import Any


class InvestKitError(Exception):
    """
    InvestKit 基础异常类

    所有 InvestKit 异常都应继承此类。

    Attributes:
        message: 错误消息
        code: 错误代码
        status_code: HTTP 状态码
        details: 错误详情
    """

    default_message = "An error occurred"
    default_code = "UNKNOWN_ERROR"
    default_status_code = 500

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        status_code: int | None = None,
        field: str | None = None,
        value: Any | None = None,
        details: dict | None = None,
    ):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status_code
        self.field = field
        self.value = value
        self.details = details
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.field:
            result["error"]["field"] = self.field
        if self.value is not None:
            result["error"]["value"] = self.value
        if self.details:
            result["error"]["details"] = self.details
        return result

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationError(InvestKitError):
    """数据验证错误"""

    default_message = "Validation failed"
    default_code = "VALIDATION_ERROR"
    default_status_code = 400


class NotFoundError(InvestKitError):
    """资源未找到错误"""

    default_message = "Resource not found"
    default_code = "NOT_FOUND"
    default_status_code = 404


class AuthenticationError(InvestKitError):
    """认证错误"""

    default_message = "Authentication failed"
    default_code = "AUTHENTICATION_ERROR"
    default_status_code = 401


class AuthorizationError(InvestKitError):
    """授权错误"""

    default_message = "Permission denied"
    default_code = "AUTHORIZATION_ERROR"
    default_status_code = 403


class RateLimitError(InvestKitError):
    """速率限制错误"""

    default_message = "Rate limit exceeded"
    default_code = "RATE_LIMIT_EXCEEDED"
    default_status_code = 429


class ExternalServiceError(InvestKitError):
    """外部服务错误"""

    default_message = "External service error"
    default_code = "EXTERNAL_SERVICE_ERROR"
    default_status_code = 502


class DataError(InvestKitError):
    """数据错误"""

    default_message = "Data error"
    default_code = "DATA_ERROR"
    default_status_code = 422


class ConfigurationError(InvestKitError):
    """配置错误"""

    default_message = "Configuration error"
    default_code = "CONFIGURATION_ERROR"
    default_status_code = 500


class CacheError(InvestKitError):
    """缓存错误"""

    default_message = "Cache error"
    default_code = "CACHE_ERROR"
    default_status_code = 500


class DatabaseError(InvestKitError):
    """数据库错误"""

    default_message = "Database error"
    default_code = "DATABASE_ERROR"
    default_status_code = 500


class MLModelError(InvestKitError):
    """ML 模型错误"""

    default_message = "ML model error"
    default_code = "ML_MODEL_ERROR"
    default_status_code = 500


class LLMError(InvestKitError):
    """LLM 错误"""

    default_message = "LLM error"
    default_code = "LLM_ERROR"
    default_status_code = 500


class TradingError(InvestKitError):
    """交易错误"""

    default_message = "Trading error"
    default_code = "TRADING_ERROR"
    default_status_code = 500

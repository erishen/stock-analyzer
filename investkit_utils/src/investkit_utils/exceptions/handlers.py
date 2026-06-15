"""异常处理工具"""

from investkit_utils.exceptions.base import (
    AuthenticationError,
    AuthorizationError,
    DataError,
    ExternalServiceError,
    InvestKitError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


def handle_exception(exc: Exception) -> dict:
    """
    统一异常处理

    Args:
        exc: 异常对象

    Returns:
        错误响应字典
    """
    if isinstance(exc, InvestKitError):
        return exc.to_dict()

    return {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": str(exc),
        }
    }


def raise_for_status(status_code: int, message: str = "Request failed") -> None:
    """
    根据状态码抛出异常

    Args:
        status_code: HTTP 状态码
        message: 错误消息

    Raises:
        InvestKitError: 对应的异常
    """
    if 200 <= status_code < 300:
        return

    error_map = {
        400: ValidationError,
        401: AuthenticationError,
        403: AuthorizationError,
        404: NotFoundError,
        422: DataError,
        429: RateLimitError,
        502: ExternalServiceError,
    }

    error_class = error_map.get(status_code, InvestKitError)
    raise error_class(message=message, status_code=status_code)

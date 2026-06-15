"""日志上下文管理"""

from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(cid: str) -> None:
    """设置当前请求的关联 ID"""
    _correlation_id.set(cid)


def get_correlation_id() -> str | None:
    """获取当前请求的关联 ID"""
    return _correlation_id.get()

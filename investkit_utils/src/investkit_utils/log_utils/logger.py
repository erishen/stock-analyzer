"""自定义 Logger 类"""

from logging import DEBUG, ERROR, INFO, WARNING, Logger


class InvestKitLogger(Logger):
    """InvestKit 自定义 Logger"""

    def _log_with_extra(
        self, level: int, msg: str, args: tuple, exc_info=None, extra: dict | None = None, **kwargs
    ) -> None:
        if extra:
            if "extra_data" not in kwargs:
                kwargs["extra"] = {}
            kwargs["extra"]["extra_data"] = extra
        super()._log(level, msg, args, exc_info=exc_info, **kwargs)

    def info_with_data(self, msg: str, data: dict | None = None, **kwargs) -> None:
        """带数据的 INFO 日志"""
        self._log_with_extra(INFO, msg, (), extra=data, **kwargs)

    def error_with_data(self, msg: str, data: dict | None = None, **kwargs) -> None:
        """带数据的 ERROR 日志"""
        self._log_with_extra(ERROR, msg, (), extra=data, **kwargs)

    def warning_with_data(self, msg: str, data: dict | None = None, **kwargs) -> None:
        """带数据的 WARNING 日志"""
        self._log_with_extra(WARNING, msg, (), extra=data, **kwargs)

    def debug_with_data(self, msg: str, data: dict | None = None, **kwargs) -> None:
        """带数据的 DEBUG 日志"""
        self._log_with_extra(DEBUG, msg, (), extra=data, **kwargs)

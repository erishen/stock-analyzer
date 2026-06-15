"""日期时间工具"""

import re
from datetime import date, datetime, timedelta


def parse_date(value: str | date | datetime | None) -> date | None:
    """
    解析日期字符串

    Args:
        value: 日期字符串、date 或 datetime 对象

    Returns:
        date 对象或 None

    支持格式:
        - YYYY-MM-DD
        - YYYY/MM/DD
        - YYYYMMDD
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    value = str(value).strip()

    patterns = [
        (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
        (r"^\d{4}/\d{2}/\d{2}$", "%Y/%m/%d"),
        (r"^\d{8}$", "%Y%m%d"),
    ]

    for pattern, fmt in patterns:
        if re.match(pattern, value):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

    return None


def format_date(value: date | datetime | None, fmt: str = "%Y-%m-%d") -> str | None:
    """
    格式化日期

    Args:
        value: 日期对象
        fmt: 格式字符串

    Returns:
        格式化后的字符串
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime(fmt)


def get_trading_days(start_date: date, end_date: date) -> list[date]:
    """
    获取日期范围内的交易日（排除周末）

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        交易日列表
    """
    trading_days = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            trading_days.append(current)
        current += timedelta(days=1)
    return trading_days


def is_trading_day(d: date | None = None) -> bool:
    """
    判断是否为交易日（排除周末）

    Args:
        d: 日期，默认今天

    Returns:
        是否为交易日
    """
    if d is None:
        d = date.today()
    return d.weekday() < 5

"""数据验证器"""

import re
from decimal import Decimal, InvalidOperation


def validate_stock_code(code: str) -> bool:
    """
    验证股票代码格式

    Args:
        code: 股票代码

    Returns:
        是否有效
    """
    if not code:
        return False

    patterns = [
        r"^\d{6}$",
        r"^\d{6}\.[A-Z]{2}$",
        r"^[A-Z]{1,5}(\.[A-Z])?$",
    ]

    return any(re.match(p, code) for p in patterns)


def validate_amount(value: str | int | float | Decimal) -> bool:
    """
    验证金额

    Args:
        value: 金额值

    Returns:
        是否有效
    """
    try:
        amount = Decimal(str(value))
        return amount >= 0
    except (ValueError, TypeError, InvalidOperation):
        return False


def validate_percentage(value: str | int | float) -> bool:
    """
    验证百分比

    Args:
        value: 百分比值

    Returns:
        是否有效
    """
    try:
        pct = float(value)
        return -100 <= pct <= 100
    except (ValueError, TypeError):
        return False

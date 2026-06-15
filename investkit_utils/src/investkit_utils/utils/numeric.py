"""数值计算工具"""

from decimal import ROUND_HALF_UP, Decimal


def safe_divide(
    numerator: int | float | Decimal,
    denominator: int | float | Decimal,
    default: int | float | Decimal = 0,
) -> float:
    """
    安全除法，避免除零错误

    Args:
        numerator: 被除数
        denominator: 除数
        default: 默认值（除数为零时）

    Returns:
        计算结果
    """
    try:
        if float(denominator) == 0:
            return float(default)
        return float(numerator) / float(denominator)
    except (ValueError, TypeError, ZeroDivisionError):
        return float(default)


def round_to(value: int | float | Decimal, precision: int = 2) -> float:
    """
    精确四舍五入

    Args:
        value: 数值
        precision: 小数位数

    Returns:
        四舍五入后的值
    """
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP))


def percentage_change(
    old_value: int | float,
    new_value: int | float,
) -> float:
    """
    计算百分比变化

    Args:
        old_value: 旧值
        new_value: 新值

    Returns:
        百分比变化
    """
    if old_value == 0:
        return 0.0 if new_value == 0 else 100.0
    return round_to((new_value - old_value) / abs(old_value) * 100)

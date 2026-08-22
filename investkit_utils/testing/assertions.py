"""断言工具"""

from collections.abc import Callable
from typing import Any


def assert_dict_equal(actual: dict, expected: dict, ignore_keys: list | None = None) -> None:
    """
    断言字典相等（可忽略特定键）

    Args:
        actual: 实际字典
        expected: 期望字典
        ignore_keys: 忽略的键列表
    """
    ignore_keys = ignore_keys or []

    actual_filtered = {k: v for k, v in actual.items() if k not in ignore_keys}
    expected_filtered = {k: v for k, v in expected.items() if k not in ignore_keys}

    assert actual_filtered == expected_filtered, (
        f"Dicts not equal:\nActual: {actual_filtered}\nExpected: {expected_filtered}"
    )


def assert_almost_equal(actual: float, expected: float, tolerance: float = 1e-6) -> None:
    """
    断言浮点数近似相等

    Args:
        actual: 实际值
        expected: 期望值
        tolerance: 容差
    """
    assert abs(actual - expected) <= tolerance, f"Values not equal: {actual} != {expected}"


def assert_list_contains(lst: list, item: Any) -> None:
    """
    断言列表包含元素

    Args:
        lst: 列表
        item: 元素
    """
    assert item in lst, f"Item {item} not in list {lst}"


def assert_raises(exc_type: type, func: Callable, *args, **kwargs) -> None:
    """
    断言函数抛出异常

    Args:
        exc_type: 异常类型
        func: 函数
        args: 位置参数
        kwargs: 关键字参数
    """
    try:
        func(*args, **kwargs)
        raise AssertionError(f"Expected {exc_type.__name__} to be raised")
    except exc_type:
        pass

"""数据处理工具"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """深度合并两个字典

    Args:
        base: 基础字典
        override: 覆盖字典

    Returns:
        合并后的字典

    示例:
        >>> deep_merge({"a": 1, "b": {"c": 2}}, {"b": {"d": 3}})
        {"a": 1, "b": {"c": 2, "d": 3}}
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def flatten_dict(
    d: dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> dict[str, Any]:
    """扁平化字典

    Args:
        d: 字典
        parent_key: 父键前缀
        sep: 分隔符

    Returns:
        扁平化后的字典

    示例:
        >>> flatten_dict({"a": {"b": 1, "c": 2}})
        {"a.b": 1, "a.c": 2}
    """
    items: list[tuple[str, Any]] = []
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep).items())
        else:
            items.append((new_key, value))
    return dict(items)


def unflatten_dict(d: dict[str, Any], sep: str = ".") -> dict[str, Any]:
    """反扁平化字典

    Args:
        d: 扁平化的字典
        sep: 分隔符

    Returns:
        嵌套字典

    示例:
        >>> unflatten_dict({"a.b": 1, "a.c": 2})
        {"a": {"b": 1, "c": 2}}
    """
    result: dict[str, Any] = {}
    for key, value in d.items():
        parts = key.split(sep)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def chunk_list(lst: list[T], chunk_size: int) -> list[list[T]]:
    """将列表分块

    Args:
        lst: 列表
        chunk_size: 块大小

    Returns:
        分块后的列表

    示例:
        >>> chunk_list([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def unique_list(lst: list[T], key: str | None = None) -> list[T]:
    """列表去重 (保持顺序)

    Args:
        lst: 列表
        key: 用于去重的键 (如果是字典列表)

    Returns:
        去重后的列表

    示例:
        >>> unique_list([1, 2, 2, 3, 1])
        [1, 2, 3]
    """
    if key is None:
        seen = set()
        result = []
        for item in lst:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    else:
        seen = set()
        result = []
        for item in lst:
            if isinstance(item, dict) and key in item:
                k = item[key]
                if k not in seen:
                    seen.add(k)
                    result.append(item)
        return result


def group_by(lst: list[dict], key: str) -> dict[Any, list[dict]]:
    """按键分组

    Args:
        lst: 字典列表
        key: 分组键

    Returns:
        分组后的字典

    示例:
        >>> group_by([{"type": "a", "val": 1}, {"type": "b", "val": 2}], "type")
        {"a": [{"type": "a", "val": 1}], "b": [{"type": "b", "val": 2}]}
    """
    result: dict[Any, list[dict]] = {}
    for item in lst:
        if key in item:
            k = item[key]
            if k not in result:
                result[k] = []
            result[k].append(item)
    return result


def safe_get(d: dict, *keys: str, default: Any = None) -> Any:
    """安全获取嵌套字典值

    Args:
        d: 字典
        *keys: 键序列
        default: 默认值

    Returns:
        值或默认值

    示例:
        >>> safe_get({"a": {"b": {"c": 1}}}, "a", "b", "c")
        1
        >>> safe_get({"a": {"b": 1}}, "a", "x", "y", default=0)
        0
    """
    current = d
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def to_json_serializable(obj: Any) -> Any:
    """转换为 JSON 可序列化对象

    Args:
        obj: 任意对象

    Returns:
        JSON 可序列化的对象

    示例:
        >>> to_json_serializable({"date": date(2024, 1, 1)})
        {"date": "2024-01-01"}
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_serializable(item) for item in obj]
    if hasattr(obj, "__dict__"):
        return to_json_serializable(obj.__dict__)
    return str(obj)


def to_decimal(value: Any, precision: int = 2) -> Decimal:
    """转换为 Decimal

    Args:
        value: 任意值
        precision: 小数位数

    Returns:
        Decimal 对象

    示例:
        >>> to_decimal("123.456", 2)
        Decimal('123.46')
    """
    try:
        d = Decimal(str(value))
        return d.quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, InvalidOperation):
        return Decimal("0")


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    result = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        result[f.name] = _serialize_value(value)
    return result


class ToDictMixin:
    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return dataclass_to_dict(value)
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def batch_process(
    items: list[T],
    process_func: Callable[[T], Any],
    batch_size: int = 100,
    on_batch_complete: Callable[[int, int, int], None] | None = None,
) -> list[Any]:
    """批量处理

    Args:
        items: 项目列表
        process_func: 处理函数
        batch_size: 批次大小
        on_batch_complete: 批次完成回调

    Returns:
        处理结果列表

    示例:
        >>> batch_process([1, 2, 3, 4, 5], lambda x: x * 2, batch_size=2)
        [2, 4, 6, 8, 10]
    """
    results = []
    chunks = chunk_list(items, batch_size)

    for i, chunk in enumerate(chunks):
        batch_results = [process_func(item) for item in chunk]
        results.extend(batch_results)

        if on_batch_complete:
            on_batch_complete(i + 1, len(chunks), len(batch_results))

    return results

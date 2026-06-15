from investkit_utils.utils.data_utils import (
    ToDictMixin,
    batch_process,
    chunk_list,
    dataclass_to_dict,
    deep_merge,
    flatten_dict,
    group_by,
    safe_get,
    to_decimal,
    to_json_serializable,
    unflatten_dict,
    unique_list,
)
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class Color(Enum):
    RED = "red"
    BLUE = "blue"


@dataclass
class SampleItem(ToDictMixin):
    name: str
    value: int
    color: Color = Color.RED
    created: date | None = None


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"d": 4, "e": 5}}
        result = deep_merge(base, override)
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 4
        assert result["b"]["e"] == 5

    def test_base_not_modified(self):
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        deep_merge(base, override)
        assert "c" not in base["a"]

    def test_override_dict_with_non_dict(self):
        base = {"a": {"b": 1}}
        override = {"a": "replaced"}
        result = deep_merge(base, override)
        assert result["a"] == "replaced"


class TestFlattenDict:
    def test_simple(self):
        d = {"a": {"b": 1, "c": 2}}
        result = flatten_dict(d)
        assert result == {"a.b": 1, "a.c": 2}

    def test_nested_deep(self):
        d = {"a": {"b": {"c": 1}}}
        result = flatten_dict(d)
        assert result == {"a.b.c": 1}

    def test_custom_sep(self):
        d = {"a": {"b": 1}}
        result = flatten_dict(d, sep="_")
        assert result == {"a_b": 1}

    def test_empty(self):
        assert flatten_dict({}) == {}

    def test_no_nesting(self):
        d = {"a": 1, "b": 2}
        result = flatten_dict(d)
        assert result == {"a": 1, "b": 2}


class TestUnflattenDict:
    def test_simple(self):
        d = {"a.b": 1, "a.c": 2}
        result = unflatten_dict(d)
        assert result == {"a": {"b": 1, "c": 2}}

    def test_deep(self):
        d = {"a.b.c": 1}
        result = unflatten_dict(d)
        assert result == {"a": {"b": {"c": 1}}}

    def test_custom_sep(self):
        d = {"a_b": 1}
        result = unflatten_dict(d, sep="_")
        assert result == {"a": {"b": 1}}


class TestChunkList:
    def test_even(self):
        result = chunk_list([1, 2, 3, 4], 2)
        assert result == [[1, 2], [3, 4]]

    def test_uneven(self):
        result = chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_single_chunk(self):
        result = chunk_list([1, 2, 3], 10)
        assert result == [[1, 2, 3]]

    def test_empty(self):
        result = chunk_list([], 2)
        assert result == []


class TestUniqueList:
    def test_simple(self):
        result = unique_list([1, 2, 2, 3, 1])
        assert result == [1, 2, 3]

    def test_preserves_order(self):
        result = unique_list([3, 1, 2, 1, 3])
        assert result == [3, 1, 2]

    def test_with_key(self):
        data = [{"id": 1, "v": "a"}, {"id": 1, "v": "b"}, {"id": 2, "v": "c"}]
        result = unique_list(data, key="id")
        assert len(result) == 2
        assert result[0]["v"] == "a"

    def test_empty(self):
        assert unique_list([]) == []


class TestGroupBy:
    def test_basic(self):
        data = [{"type": "a", "v": 1}, {"type": "b", "v": 2}, {"type": "a", "v": 3}]
        result = group_by(data, "type")
        assert len(result["a"]) == 2
        assert len(result["b"]) == 1

    def test_missing_key(self):
        data = [{"type": "a", "v": 1}, {"v": 2}]
        result = group_by(data, "type")
        assert len(result) == 1

    def test_empty(self):
        assert group_by([], "key") == {}


class TestSafeGet:
    def test_deep_access(self):
        d = {"a": {"b": {"c": 1}}}
        assert safe_get(d, "a", "b", "c") == 1

    def test_missing_key(self):
        d = {"a": {"b": 1}}
        assert safe_get(d, "a", "x", "y", default=0) == 0

    def test_none_default(self):
        d = {"a": 1}
        assert safe_get(d, "b") is None

    def test_custom_default(self):
        d = {}
        assert safe_get(d, "x", default="missing") == "missing"


class TestToJsonSerializable:
    def test_date(self):
        result = to_json_serializable({"d": date(2024, 1, 1)})
        assert result["d"] == "2024-01-01"

    def test_datetime(self):
        result = to_json_serializable({"dt": datetime(2024, 1, 1, 12, 0)})
        assert "2024-01-01" in result["dt"]

    def test_decimal(self):
        result = to_json_serializable(Decimal("1.5"))
        assert result == 1.5

    def test_none(self):
        assert to_json_serializable(None) is None

    def test_list(self):
        result = to_json_serializable([1, "a", None])
        assert result == [1, "a", None]

    def test_nested(self):
        result = to_json_serializable({"a": [date(2024, 1, 1)]})
        assert result["a"][0] == "2024-01-01"


class TestToDecimal:
    def test_string(self):
        assert to_decimal("123.456", 2) == Decimal("123.46")

    def test_integer(self):
        assert to_decimal(100, 0) == Decimal("100")

    def test_invalid(self):
        assert to_decimal("abc") == Decimal("0")

    def test_none(self):
        assert to_decimal(None) == Decimal("0")


class TestDataclassToDict:
    def test_basic(self):
        item = SampleItem(name="test", value=42)
        result = dataclass_to_dict(item)
        assert result["name"] == "test"
        assert result["value"] == 42
        assert result["color"] == "red"

    def test_with_date(self):
        item = SampleItem(name="test", value=1, created=date(2024, 1, 1))
        result = dataclass_to_dict(item)
        assert result["created"] == "2024-01-01"


class TestToDictMixin:
    def test_to_dict(self):
        item = SampleItem(name="test", value=42)
        d = item.to_dict()
        assert d["name"] == "test"
        assert d["color"] == "red"


class TestBatchProcess:
    def test_basic(self):
        result = batch_process([1, 2, 3, 4, 5], lambda x: x * 2, batch_size=2)
        assert result == [2, 4, 6, 8, 10]

    def test_callback(self):
        calls = []
        batch_process([1, 2, 3], lambda x: x, batch_size=2, on_batch_complete=lambda b, t, n: calls.append((b, n)))
        assert len(calls) == 2
        assert calls[0] == (1, 2)
        assert calls[1] == (2, 1)

    def test_empty(self):
        result = batch_process([], lambda x: x)
        assert result == []

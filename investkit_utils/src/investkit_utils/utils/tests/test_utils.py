"""工具函数测试"""

import os
import tempfile
from datetime import date
from decimal import Decimal

from investkit_utils.utils import (
    calculate_cagr,
    calculate_compound_interest,
    calculate_irr,
    calculate_max_drawdown,
    calculate_position_size,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_win_rate,
    chunk_list,
    copy_file,
    deep_merge,
    ensure_dir,
    find_files,
    flatten_dict,
    format_file_size,
    get_file_info,
    get_latest_file,
    group_by,
    move_file,
    read_json,
    read_lines,
    read_text,
    safe_get,
    to_decimal,
    to_json_serializable,
    unflatten_dict,
    unique_list,
    write_json,
    write_text,
)


class TestFinancialCalculations:
    def test_calculate_irr(self):
        result = calculate_irr([-10000, 3000, 3000, 3000, 3000])
        assert result is not None
        assert 0.07 < result < 0.08

    def test_calculate_irr_empty(self):
        assert calculate_irr([]) is None

    def test_calculate_irr_positive_first(self):
        assert calculate_irr([100, 200]) is None

    def test_calculate_cagr(self):
        result = calculate_cagr(10000, 15000, 3)
        assert result is not None
        assert 0.14 < result < 0.15

    def test_calculate_cagr_zero_start(self):
        assert calculate_cagr(0, 100, 1) is None

    def test_calculate_sharpe_ratio(self):
        result = calculate_sharpe_ratio([0.1, 0.05, 0.08, -0.02, 0.12])
        assert result is not None

    def test_calculate_sharpe_ratio_empty(self):
        assert calculate_sharpe_ratio([]) is None

    def test_calculate_max_drawdown(self):
        result = calculate_max_drawdown([100, 110, 105, 95, 100, 90])
        assert 0.18 < result < 0.19

    def test_calculate_max_drawdown_empty(self):
        assert calculate_max_drawdown([]) == 0.0

    def test_calculate_win_rate(self):
        result = calculate_win_rate([(10, 12), (15, 14), (20, 25)])
        assert 0.66 < result < 0.67

    def test_calculate_win_rate_empty(self):
        assert calculate_win_rate([]) == 0.0

    def test_calculate_profit_factor(self):
        result = calculate_profit_factor([(10, 12), (15, 14), (20, 25)])
        assert result == 7.0

    def test_calculate_position_size(self):
        result = calculate_position_size(100000, 0.02, 50, 45)
        assert result == 400

    def test_calculate_compound_interest(self):
        result = calculate_compound_interest(10000, 0.05, 5)
        assert 12800 < result < 12900


class TestDataUtils:
    def test_deep_merge(self):
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}}
        result = deep_merge(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 3

    def test_flatten_dict(self):
        d = {"a": {"b": 1, "c": 2}}
        result = flatten_dict(d)
        assert result == {"a.b": 1, "a.c": 2}

    def test_unflatten_dict(self):
        d = {"a.b": 1, "a.c": 2}
        result = unflatten_dict(d)
        assert result == {"a": {"b": 1, "c": 2}}

    def test_chunk_list(self):
        result = chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_unique_list(self):
        result = unique_list([1, 2, 2, 3, 1])
        assert result == [1, 2, 3]

    def test_unique_list_with_key(self):
        data = [{"id": 1, "val": "a"}, {"id": 1, "val": "b"}, {"id": 2, "val": "c"}]
        result = unique_list(data, key="id")
        assert len(result) == 2

    def test_group_by(self):
        data = [{"type": "a", "val": 1}, {"type": "b", "val": 2}, {"type": "a", "val": 3}]
        result = group_by(data, "type")
        assert len(result["a"]) == 2
        assert len(result["b"]) == 1

    def test_safe_get(self):
        d = {"a": {"b": {"c": 1}}}
        assert safe_get(d, "a", "b", "c") == 1
        assert safe_get(d, "a", "x", "y", default=0) == 0

    def test_to_json_serializable(self):
        d = {"date": date(2024, 1, 1), "decimal": Decimal("1.5")}
        result = to_json_serializable(d)
        assert result["date"] == "2024-01-01"
        assert result["decimal"] == 1.5

    def test_to_decimal(self):
        assert to_decimal("123.456", 2) == Decimal("123.46")
        assert to_decimal("invalid") == Decimal("0")


class TestFileUtils:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_dir(self):
        dir_path = os.path.join(self.temp_dir, "subdir", "nested")
        ensure_dir(dir_path)
        assert os.path.exists(dir_path)

    def test_write_and_read_json(self):
        file_path = os.path.join(self.temp_dir, "test.json")
        data = {"key": "value", "number": 123}
        write_json(file_path, data)
        result = read_json(file_path)
        assert result == data

    def test_read_json_nonexistent(self):
        result = read_json("nonexistent.json", default={})
        assert result == {}

    def test_write_and_read_text(self):
        file_path = os.path.join(self.temp_dir, "test.txt")
        write_text(file_path, "Hello\nWorld")
        result = read_text(file_path)
        assert "Hello" in result

    def test_read_lines(self):
        file_path = os.path.join(self.temp_dir, "test.txt")
        write_text(file_path, "line1\nline2\nline3\n")
        result = read_lines(file_path)
        assert result == ["line1", "line2", "line3"]

    def test_get_file_info(self):
        file_path = os.path.join(self.temp_dir, "test.txt")
        write_text(file_path, "Hello World")
        info = get_file_info(file_path)
        assert info["name"] == "test.txt"
        assert info["size"] == 11

    def test_format_file_size(self):
        assert format_file_size(1024) == "1.00 KB"
        assert format_file_size(1048576) == "1.00 MB"

    def test_find_files(self):
        write_text(os.path.join(self.temp_dir, "a.txt"), "")
        write_text(os.path.join(self.temp_dir, "b.txt"), "")
        write_text(os.path.join(self.temp_dir, "c.csv"), "")
        files = find_files(self.temp_dir, "*.txt")
        assert len(files) == 2

    def test_copy_file(self):
        src = os.path.join(self.temp_dir, "src.txt")
        dst = os.path.join(self.temp_dir, "dst.txt")
        write_text(src, "content")
        assert copy_file(src, dst) is True
        assert read_text(dst) == "content"

    def test_move_file(self):
        src = os.path.join(self.temp_dir, "src.txt")
        dst = os.path.join(self.temp_dir, "dst.txt")
        write_text(src, "content")
        assert move_file(src, dst) is True
        assert not os.path.exists(src)
        assert read_text(dst) == "content"

    def test_get_latest_file(self):
        import time

        file1 = os.path.join(self.temp_dir, "a.txt")
        file2 = os.path.join(self.temp_dir, "b.txt")
        write_text(file1, "a")
        time.sleep(0.1)
        write_text(file2, "b")
        latest = get_latest_file(self.temp_dir, "*.txt")
        assert latest.name == "b.txt"

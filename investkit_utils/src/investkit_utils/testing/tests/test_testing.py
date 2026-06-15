"""InvestKit 测试工具模块测试"""

import pytest

from investkit_utils.testing.assertions import (
    assert_almost_equal,
    assert_dict_equal,
    assert_list_contains,
    assert_raises,
)
from investkit_utils.testing.data_generators import (
    generate_test_portfolio,
    generate_test_stock_data,
)


class TestAssertDictEqual:
    def test_equal_dicts(self):
        assert_dict_equal({"a": 1}, {"a": 1})

    def test_unequal_dicts_raises(self):
        with pytest.raises(AssertionError):
            assert_dict_equal({"a": 1}, {"a": 2})

    def test_ignore_keys(self):
        assert_dict_equal({"a": 1, "b": 2}, {"a": 1, "b": 3}, ignore_keys=["b"])

    def test_empty_dicts(self):
        assert_dict_equal({}, {})


class TestAssertAlmostEqual:
    def test_equal_values(self):
        assert_almost_equal(1.0, 1.0)

    def test_close_values(self):
        assert_almost_equal(1.0, 1.000001)

    def test_custom_tolerance(self):
        assert_almost_equal(1.0, 1.05, tolerance=0.1)

    def test_far_values_raises(self):
        with pytest.raises(AssertionError):
            assert_almost_equal(1.0, 2.0)


class TestAssertListContains:
    def test_contains(self):
        assert_list_contains([1, 2, 3], 2)

    def test_not_contains_raises(self):
        with pytest.raises(AssertionError):
            assert_list_contains([1, 2, 3], 4)


class TestAssertRaises:
    def test_raises_expected(self):
        assert_raises(ValueError, int, "abc")

    def test_no_raise_raises(self):
        with pytest.raises(AssertionError):
            assert_raises(ValueError, int, "123")


class TestDataGenerators:
    def test_generate_stock_data(self):
        data = generate_test_stock_data()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_generate_portfolio(self):
        portfolio = generate_test_portfolio()
        assert portfolio is not None

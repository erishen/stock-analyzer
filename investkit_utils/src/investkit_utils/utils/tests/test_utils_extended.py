"""Smoke tests for investkit_utils.utils untested sub-modules."""

from datetime import date, datetime

from investkit_utils.utils.datetime_utils import parse_date
from investkit_utils.utils.numeric import round_to, safe_divide
from investkit_utils.utils.retry import retry
from investkit_utils.utils.string_utils import mask_sensitive, truncate_string
from investkit_utils.utils.validators import validate_amount, validate_stock_code


class TestValidators:
    def test_validate_stock_code_a_share(self):
        assert validate_stock_code("000001") is True

    def test_validate_stock_code_with_suffix(self):
        assert validate_stock_code("000001.SZ") is True

    def test_validate_stock_code_us(self):
        assert validate_stock_code("AAPL") is True

    def test_validate_stock_code_empty(self):
        assert validate_stock_code("") is False

    def test_validate_stock_code_invalid(self):
        assert validate_stock_code("abc123xyz") is False

    def test_validate_amount_positive(self):
        assert validate_amount(100) is True

    def test_validate_amount_zero(self):
        assert validate_amount(0) is True

    def test_validate_amount_string(self):
        assert validate_amount("100.50") is True


class TestRetry:
    def test_retry_success_first_try(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_retry_success_after_failure(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        result = fail_then_succeed()
        assert result == "ok"
        assert call_count == 2


class TestStringUtils:
    def test_truncate_short_string(self):
        assert truncate_string("hello", max_length=10) == "hello"

    def test_truncate_long_string(self):
        result = truncate_string("a" * 100, max_length=10)
        assert len(result) == 10
        assert result.endswith("...")

    def test_mask_sensitive_short(self):
        result = mask_sensitive("ab", visible_chars=4)
        assert "*" in result

    def test_mask_sensitive_long(self):
        result = mask_sensitive("1234567890", visible_chars=4)
        assert result.startswith("1234")
        assert "*" in result


class TestDatetimeUtils:
    def test_parse_date_string(self):
        result = parse_date("2025-01-15")
        assert result == date(2025, 1, 15)

    def test_parse_date_slash_format(self):
        result = parse_date("2025/01/15")
        assert result == date(2025, 1, 15)

    def test_parse_date_compact(self):
        result = parse_date("20250115")
        assert result == date(2025, 1, 15)

    def test_parse_date_none(self):
        assert parse_date(None) is None

    def test_parse_date_date_object(self):
        d = date(2025, 1, 15)
        assert parse_date(d) == d

    def test_parse_date_datetime_object(self):
        dt = datetime(2025, 1, 15, 10, 30)
        result = parse_date(dt)
        assert isinstance(result, date)


class TestNumeric:
    def test_safe_divide_normal(self):
        assert safe_divide(10, 2) == 5.0

    def test_safe_divide_by_zero(self):
        assert safe_divide(10, 0) == 0.0

    def test_safe_divide_by_zero_custom_default(self):
        assert safe_divide(10, 0, default=-1) == -1.0

    def test_round_to_two_decimals(self):
        assert round_to(3.14159, precision=2) == 3.14

    def test_round_to_zero_decimals(self):
        assert round_to(3.7, precision=0) == 4.0

from decimal import Decimal

from investkit_utils.utils.validators import validate_amount, validate_percentage, validate_stock_code


class TestValidateStockCode:
    def test_a_share_plain(self):
        assert validate_stock_code("000001") is True

    def test_a_share_with_suffix(self):
        assert validate_stock_code("000001.SZ") is True
        assert validate_stock_code("600000.SH") is True

    def test_us_stock(self):
        assert validate_stock_code("AAPL") is True

    def test_us_stock_with_class(self):
        assert validate_stock_code("BRK.B") is True

    def test_empty_string(self):
        assert validate_stock_code("") is False

    def test_invalid_format(self):
        assert validate_stock_code("abc123xyz") is False

    def test_too_many_digits(self):
        assert validate_stock_code("0000001") is False

    def test_fewer_digits(self):
        assert validate_stock_code("00001") is False

    def test_lowercase_suffix(self):
        assert validate_stock_code("000001.sz") is False

    def test_long_us_ticker(self):
        assert validate_stock_code("GOOGL") is True


class TestValidateAmount:
    def test_positive_int(self):
        assert validate_amount(100) is True

    def test_zero(self):
        assert validate_amount(0) is True

    def test_positive_float(self):
        assert validate_amount(99.99) is True

    def test_negative(self):
        assert validate_amount(-1) is False

    def test_string_number(self):
        assert validate_amount("100.50") is True

    def test_decimal(self):
        assert validate_amount(Decimal("50.00")) is True

    def test_invalid_string(self):
        assert validate_amount("not_a_number") is False

    def test_none_value(self):
        assert validate_amount(None) is False

    def test_zero_string(self):
        assert validate_amount("0") is True

    def test_negative_string(self):
        assert validate_amount("-10") is False


class TestValidatePercentage:
    def test_valid_positive(self):
        assert validate_percentage(50) is True

    def test_valid_negative(self):
        assert validate_percentage(-50) is True

    def test_zero(self):
        assert validate_percentage(0) is True

    def test_boundary_100(self):
        assert validate_percentage(100) is True

    def test_boundary_minus_100(self):
        assert validate_percentage(-100) is True

    def test_over_100(self):
        assert validate_percentage(101) is False

    def test_under_minus_100(self):
        assert validate_percentage(-101) is False

    def test_float_value(self):
        assert validate_percentage(99.9) is True

    def test_string_value(self):
        assert validate_percentage("50") is True

    def test_invalid_string(self):
        assert validate_percentage("abc") is False

    def test_none_value(self):
        assert validate_percentage(None) is False

from decimal import Decimal

from investkit_utils.utils.numeric import percentage_change, round_to, safe_divide


class TestSafeDivide:
    def test_normal_division(self):
        assert safe_divide(10, 2) == 5.0

    def test_divide_by_zero(self):
        assert safe_divide(10, 0) == 0.0

    def test_custom_default(self):
        assert safe_divide(10, 0, default=-1) == -1.0

    def test_float_division(self):
        assert safe_divide(7.0, 2.0) == 3.5

    def test_decimal_division(self):
        result = safe_divide(Decimal("10"), Decimal("3"))
        assert abs(result - 3.3333333333333335) < 1e-10

    def test_zero_numerator(self):
        assert safe_divide(0, 5) == 0.0

    def test_negative_numbers(self):
        assert safe_divide(-10, 2) == -5.0

    def test_both_negative(self):
        assert safe_divide(-10, -2) == 5.0

    def test_invalid_input(self):
        assert safe_divide("abc", 2) == 0.0


class TestRoundTo:
    def test_two_decimals(self):
        assert round_to(3.14159, precision=2) == 3.14

    def test_zero_decimals(self):
        assert round_to(3.7, precision=0) == 4.0

    def test_round_up(self):
        assert round_to(3.145, precision=2) == 3.15

    def test_round_down(self):
        assert round_to(3.144, precision=2) == 3.14

    def test_default_precision(self):
        assert round_to(3.14159) == 3.14

    def test_negative_value(self):
        assert round_to(-3.14159, precision=2) == -3.14

    def test_integer_input(self):
        assert round_to(5, precision=2) == 5.0

    def test_decimal_input(self):
        assert round_to(Decimal("3.145"), precision=2) == 3.15

    def test_high_precision(self):
        assert round_to(3.14159265, precision=5) == 3.14159


class TestPercentageChange:
    def test_positive_change(self):
        result = percentage_change(100, 110)
        assert result == 10.0

    def test_negative_change(self):
        result = percentage_change(100, 90)
        assert result == -10.0

    def test_no_change(self):
        result = percentage_change(100, 100)
        assert result == 0.0

    def test_old_value_zero_new_zero(self):
        result = percentage_change(0, 0)
        assert result == 0.0

    def test_old_value_zero_new_nonzero(self):
        result = percentage_change(0, 50)
        assert result == 100.0

    def test_doubling(self):
        result = percentage_change(50, 100)
        assert result == 100.0

    def test_halving(self):
        result = percentage_change(100, 50)
        assert result == -50.0

    def test_negative_old_value(self):
        result = percentage_change(-100, -80)
        assert result == 20.0

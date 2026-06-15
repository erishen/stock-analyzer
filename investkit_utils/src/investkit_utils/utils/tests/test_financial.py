from investkit_utils.utils.financial import (
    calculate_cagr,
    calculate_compound_interest,
    calculate_irr,
    calculate_max_drawdown,
    calculate_position_size,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_win_rate,
)
import math


class TestCalculateIRR:
    def test_basic(self):
        result = calculate_irr([-10000, 3000, 3000, 3000, 3000])
        assert result is not None
        assert 0.07 < result < 0.08

    def test_empty(self):
        assert calculate_irr([]) is None

    def test_positive_first(self):
        assert calculate_irr([100, 200]) is None

    def test_single_negative(self):
        result = calculate_irr([-100, 110])
        assert result is not None
        assert 0.09 < result < 0.11

    def test_zero_flows(self):
        assert calculate_irr([0, 0, 0]) is None


class TestCalculateCAGR:
    def test_basic(self):
        result = calculate_cagr(10000, 15000, 3)
        assert result is not None
        assert 0.14 < result < 0.15

    def test_zero_start(self):
        assert calculate_cagr(0, 100, 1) is None

    def test_negative_start(self):
        assert calculate_cagr(-100, 200, 1) is None

    def test_zero_years(self):
        assert calculate_cagr(100, 200, 0) is None

    def test_one_year(self):
        result = calculate_cagr(100, 110, 1)
        assert result is not None
        assert abs(result - 0.1) < 0.001


class TestCalculateSharpeRatio:
    def test_basic(self):
        result = calculate_sharpe_ratio([0.1, 0.05, 0.08, -0.02, 0.12])
        assert result is not None

    def test_empty(self):
        assert calculate_sharpe_ratio([]) is None

    def test_zero_std(self):
        result = calculate_sharpe_ratio([0.05, 0.05, 0.05])
        assert result is None or abs(result) > 1e10

    def test_negative_returns(self):
        result = calculate_sharpe_ratio([-0.1, -0.2, -0.05])
        assert result is not None
        assert result < 0


class TestCalculateMaxDrawdown:
    def test_basic(self):
        result = calculate_max_drawdown([100, 110, 105, 95, 100, 90])
        assert 0.18 < result < 0.19

    def test_empty(self):
        assert calculate_max_drawdown([]) == 0.0

    def test_no_drawdown(self):
        result = calculate_max_drawdown([100, 110, 120, 130])
        assert result == 0.0

    def test_single_value(self):
        result = calculate_max_drawdown([100])
        assert result == 0.0

    def test_full_drawdown(self):
        result = calculate_max_drawdown([100, 0])
        assert result == 1.0


class TestCalculateWinRate:
    def test_basic(self):
        result = calculate_win_rate([(10, 12), (15, 14), (20, 25)])
        assert 0.66 < result < 0.67

    def test_empty(self):
        assert calculate_win_rate([]) == 0.0

    def test_all_wins(self):
        result = calculate_win_rate([(10, 12), (20, 25)])
        assert result == 1.0

    def test_all_losses(self):
        result = calculate_win_rate([(10, 8), (20, 15)])
        assert result == 0.0

    def test_breakeven(self):
        result = calculate_win_rate([(10, 10)])
        assert result == 0.0


class TestCalculateProfitFactor:
    def test_basic(self):
        result = calculate_profit_factor([(10, 12), (15, 14), (20, 25)])
        assert result == 7.0

    def test_empty(self):
        assert calculate_profit_factor([]) == 0.0

    def test_all_wins(self):
        result = calculate_profit_factor([(10, 12), (20, 25)])
        assert result == float("inf")

    def test_all_losses(self):
        result = calculate_profit_factor([(10, 8), (20, 15)])
        assert result == 0.0

    def test_mixed(self):
        result = calculate_profit_factor([(10, 12), (10, 8)])
        assert result == 1.0


class TestCalculatePositionSize:
    def test_basic(self):
        result = calculate_position_size(100000, 0.02, 50, 45)
        assert result == 400

    def test_no_stop_loss(self):
        result = calculate_position_size(100000, 0.02, 50)
        assert result == 2000

    def test_zero_capital(self):
        assert calculate_position_size(0, 0.02, 50) == 0.0

    def test_zero_price(self):
        assert calculate_position_size(100000, 0.02, 0) == 0.0

    def test_stop_loss_above_entry(self):
        result = calculate_position_size(100000, 0.02, 50, 55)
        assert result == 2000


class TestCalculateCompoundInterest:
    def test_basic(self):
        result = calculate_compound_interest(10000, 0.05, 5)
        assert 12800 < result < 12900

    def test_zero_rate(self):
        result = calculate_compound_interest(10000, 0, 5)
        assert result == 10000.0

    def test_annual_compound(self):
        result = calculate_compound_interest(10000, 0.1, 1, compounds_per_year=1)
        assert result == 11000.0

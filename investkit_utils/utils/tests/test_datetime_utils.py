from datetime import date, datetime

from investkit_utils.utils.datetime_utils import format_date, get_trading_days, is_trading_day, parse_date


class TestParseDate:
    def test_iso_format(self):
        assert parse_date("2025-01-15") == date(2025, 1, 15)

    def test_slash_format(self):
        assert parse_date("2025/01/15") == date(2025, 1, 15)

    def test_compact_format(self):
        assert parse_date("20250115") == date(2025, 1, 15)

    def test_none_input(self):
        assert parse_date(None) is None

    def test_date_object(self):
        d = date(2025, 1, 15)
        assert parse_date(d) == d

    def test_datetime_object(self):
        dt = datetime(2025, 1, 15, 10, 30)
        result = parse_date(dt)
        assert isinstance(result, date)
        assert result == date(2025, 1, 15)

    def test_invalid_string(self):
        assert parse_date("not-a-date") is None

    def test_partial_date(self):
        assert parse_date("2025-13-01") is None

    def test_whitespace_stripped(self):
        assert parse_date("  2025-01-15  ") == date(2025, 1, 15)

    def test_empty_string(self):
        assert parse_date("") is None


class TestFormatDate:
    def test_default_format(self):
        assert format_date(date(2025, 1, 15)) == "2025-01-15"

    def test_custom_format(self):
        assert format_date(date(2025, 1, 15), fmt="%Y/%m/%d") == "2025/01/15"

    def test_datetime_input(self):
        result = format_date(datetime(2025, 1, 15, 10, 30))
        assert result == "2025-01-15"

    def test_none_input(self):
        assert format_date(None) is None

    def test_compact_format(self):
        assert format_date(date(2025, 1, 15), fmt="%Y%m%d") == "20250115"


class TestGetTradingDays:
    def test_week_only(self):
        start = date(2025, 1, 6)
        end = date(2025, 1, 10)
        days = get_trading_days(start, end)
        assert len(days) == 5

    def test_includes_weekend(self):
        start = date(2025, 1, 6)
        end = date(2025, 1, 12)
        days = get_trading_days(start, end)
        assert len(days) == 5

    def test_same_day_weekday(self):
        d = date(2025, 1, 6)
        days = get_trading_days(d, d)
        assert len(days) == 1

    def test_same_day_weekend(self):
        d = date(2025, 1, 4)
        days = get_trading_days(d, d)
        assert len(days) == 0

    def test_start_after_end(self):
        start = date(2025, 1, 10)
        end = date(2025, 1, 6)
        days = get_trading_days(start, end)
        assert len(days) == 0


class TestIsTradingDay:
    def test_monday(self):
        assert is_trading_day(date(2025, 1, 6)) is True

    def test_friday(self):
        assert is_trading_day(date(2025, 1, 10)) is True

    def test_saturday(self):
        assert is_trading_day(date(2025, 1, 4)) is False

    def test_sunday(self):
        assert is_trading_day(date(2025, 1, 5)) is False

    def test_default_today(self):
        result = is_trading_day()
        assert isinstance(result, bool)

from investkit_utils.utils.string_utils import mask_sensitive, truncate_string


class TestTruncateString:
    def test_short_string_unchanged(self):
        assert truncate_string("hello", max_length=10) == "hello"

    def test_exact_length_unchanged(self):
        assert truncate_string("hello", max_length=5) == "hello"

    def test_long_string_truncated(self):
        result = truncate_string("a" * 100, max_length=10)
        assert len(result) == 10
        assert result.endswith("...")

    def test_custom_suffix(self):
        result = truncate_string("a" * 100, max_length=10, suffix="…")
        assert result.endswith("…")
        assert len(result) == 10

    def test_default_max_length(self):
        short = "hello"
        assert truncate_string(short) == short

    def test_empty_string(self):
        assert truncate_string("", max_length=10) == ""

    def test_suffix_longer_than_max_length(self):
        result = truncate_string("abc", max_length=2, suffix="...")
        assert "..." in result


class TestMaskSensitive:
    def test_long_string(self):
        result = mask_sensitive("1234567890", visible_chars=4)
        assert result.startswith("1234")
        assert result.endswith("******")

    def test_short_string(self):
        result = mask_sensitive("ab", visible_chars=4)
        assert all(c == "*" for c in result)
        assert len(result) == 2

    def test_exact_visible_chars(self):
        result = mask_sensitive("1234", visible_chars=4)
        assert result == "****"

    def test_one_more_than_visible_chars(self):
        result = mask_sensitive("12345", visible_chars=4)
        assert result.startswith("1234")
        assert result.endswith("*")

    def test_custom_mask_char(self):
        result = mask_sensitive("1234567890", visible_chars=4, mask_char="#")
        assert result.startswith("1234")
        assert result.endswith("######")

    def test_default_visible_chars(self):
        result = mask_sensitive("abcdefghij", visible_chars=4)
        assert result[:4] == "abcd"
        assert all(c == "*" for c in result[4:])

    def test_empty_string(self):
        result = mask_sensitive("", visible_chars=4)
        assert result == ""

    def test_single_char(self):
        result = mask_sensitive("x", visible_chars=4)
        assert result == "*"

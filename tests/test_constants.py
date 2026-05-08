
from constants import EXCLUDED_KEYWORDS, is_excluded_stock


class TestExcludedKeywords:
    def test_keywords_list(self):
        assert "ST" in EXCLUDED_KEYWORDS
        assert "退市" in EXCLUDED_KEYWORDS
        assert "停牌" in EXCLUDED_KEYWORDS
        assert len(EXCLUDED_KEYWORDS) == 9

    def test_is_excluded_st_stock(self):
        assert is_excluded_stock("*ST某某") is True
        assert is_excluded_stock("ST某某") is True
        assert is_excluded_stock("SST某某") is True
        assert is_excluded_stock("S*ST某某") is True

    def test_is_excluded_delisted(self):
        assert is_excluded_stock("某某退市") is True
        assert is_excluded_stock("某某退") is True

    def test_is_excluded_suspended(self):
        assert is_excluded_stock("某某停牌") is True

    def test_is_excluded_pt(self):
        assert is_excluded_stock("某某PT") is True

    def test_is_not_excluded_normal(self):
        assert is_excluded_stock("平安银行") is False
        assert is_excluded_stock("贵州茅台") is False
        assert is_excluded_stock("比亚迪") is False

    def test_is_not_excluded_when_disabled(self):
        assert is_excluded_stock("*ST某某", exclude_st=False) is False
        assert is_excluded_stock("某某退市", exclude_st=False) is False

    def test_is_excluded_empty_name(self):
        assert is_excluded_stock("") is False
        assert is_excluded_stock("", exclude_st=False) is False

    def test_is_excluded_partial_match(self):
        assert is_excluded_stock("st") is True
        assert is_excluded_stock("ST") is True

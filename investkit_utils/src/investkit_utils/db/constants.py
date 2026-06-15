EXCLUDED_KEYWORDS = ["ST", "st", "*ST", "SST", "S*ST", "退市", "退", "PT", "停牌"]


def is_excluded_stock(name: str, exclude_st: bool = True) -> bool:
    if not exclude_st:
        return False
    return any(keyword in name for keyword in EXCLUDED_KEYWORDS)

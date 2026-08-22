"""字符串工具"""


def truncate_string(s: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    截断字符串

    Args:
        s: 原字符串
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的字符串
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def mask_sensitive(s: str, visible_chars: int = 4, mask_char: str = "*") -> str:
    """
    敏感信息脱敏

    Args:
        s: 原字符串
        visible_chars: 可见字符数
        mask_char: 掩码字符

    Returns:
        脱敏后的字符串
    """
    if len(s) <= visible_chars:
        return mask_char * len(s)
    return s[:visible_chars] + mask_char * (len(s) - visible_chars)

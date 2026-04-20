"""
Matplotlib Font Configuration for Chinese Support.
Matplotlib 中文字体配置
"""

import platform

import matplotlib.pyplot as plt


def setup_chinese_font():
    """
    配置 matplotlib 支持中文显示

    根据操作系统自动选择合适的中文字体:
    - macOS: Arial Unicode MS, Heiti TC, Songti SC, STHeiti
    - Windows: Microsoft YaHei, SimHei, KaiTi
    - Linux: WenQuanYi Micro Hei, Noto Sans CJK
    """
    system = platform.system()

    if system == "Darwin":
        fonts = ["Arial Unicode MS", "Heiti TC", "Songti SC", "STHeiti", "PingFang HK"]
    elif system == "Windows":
        fonts = ["Microsoft YaHei", "SimHei", "KaiTi"]
    else:
        fonts = ["WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]

    for font in fonts:
        try:
            plt.rcParams["font.family"] = font
            plt.rcParams["axes.unicode_minus"] = False
            return font
        except Exception:
            continue

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False
    return "sans-serif"


def get_chinese_font():
    """获取当前可用的中文字体"""
    system = platform.system()

    if system == "Darwin":
        return "Arial Unicode MS"
    elif system == "Windows":
        return "Microsoft YaHei"
    else:
        return "WenQuanYi Micro Hei"


setup_chinese_font()

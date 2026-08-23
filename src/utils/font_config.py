"""
Matplotlib Font Configuration for Chinese Support.
Matplotlib 中文字体配置

设计要点（相比旧实现）:
- 旧实现盲设 plt.rcParams["font.family"] 为候选字体名，但从不校验该字体是否真的
  装在系统里；在缺少 CJK 字体的 headless/Docker/CI 环境下会静默回退成豆腐块。
- 新实现: 先枚举 matplotlib 已注册字体中真实可用的中文字体 -> 命中才设；
  均缺失时尝试注册 src/utils/fonts/ 下打包的 CJK 字体 -> 再不行才回退 sans-serif
  并输出一次 RuntimeWarning，明确告诉使用者中文可能显示为方框。
"""

import platform
import warnings
from pathlib import Path


def _available_font_names():
    """返回 matplotlib 字体管理器已注册字体的名称集合(小写)，用于判断候选字体是否真实可用。"""
    from matplotlib import font_manager

    return {f.name.lower() for f in font_manager.fontManager.ttflist}


def _platform_candidates():
    """按操作系统返回候选中文字体名(优先级从高到低)。"""
    system = platform.system()
    if system == "Darwin":
        return [
            "Arial Unicode MS",
            "Heiti TC",
            "Songti SC",
            "STHeiti",
            "PingFang HK",
            "PingFang SC",
        ]
    elif system == "Windows":
        return ["Microsoft YaHei", "SimHei", "KaiTi", "SimSun"]
    else:
        return [
            "WenQuanYi Micro Hei",
            "WenQuanYi Zen Hei",
            "Noto Sans CJK SC",
            "Noto Sans CJK JP",
            "Source Han Sans SC",
        ]


def setup_chinese_font():
    """
    配置 matplotlib 支持中文显示。

    返回最终选定的字体名（已成功设置）；若都不可用则返回 "sans-serif" 并警告。
    可重复调用（幂等）。

    注意: matplotlib 为重量级可选依赖(仅绘图/CLI 需要), 此处延迟导入,
    避免 web 启动链(仅装 fastapi+uvicorn 的 web extra)因缺少 matplotlib 而崩溃。
    """
    try:
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
    except Exception:
        # 无 matplotlib(如 web 部署): 跳过中文字体配置, 不阻断启动
        return None

    candidates = _platform_candidates()
    available = _available_font_names()

    # 1) 优先使用系统已安装且 matplotlib 已识别的中文字体
    for font in candidates:
        if font.lower() in available:
            plt.rcParams["font.family"] = font
            plt.rcParams["axes.unicode_minus"] = False
            return font

    # 2) 尝试注册打包的 CJK 字体（放在 src/utils/fonts/ 下，可选）
    bundled_dir = Path(__file__).parent / "fonts"
    if bundled_dir.is_dir():
        for fp in sorted(bundled_dir.glob("*.ttf")) + sorted(bundled_dir.glob("*.otf")):
            try:
                font_manager.fontManager.addfont(str(fp))
                name = font_manager.FontProperties(fname=str(fp)).get_name()
                plt.rcParams["font.family"] = name
                plt.rcParams["axes.unicode_minus"] = False
                return name
            except Exception:
                continue

    # 3) 兜底: 保留 sans-serif 回退（中文仍可能显示为方框，但至少不崩），并明确警告
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False
    warnings.warn(
        "未找到可用的中文字体，图表中的中文可能显示为方框(豆腐块)。"
        "请安装中文字体(如 macOS 的 Arial Unicode MS / Windows 的微软雅黑 / Linux 的 Noto Sans CJK)，"
        "或将 .ttf/.otf 字体放到 src/utils/fonts/ 下自动注册。",
        RuntimeWarning,
        stacklevel=2,
    )
    return "sans-serif"


def get_chinese_font():
    """获取当前实际可用的中文字体名（首次调用时探测，并缓存结果复用）。

    无 matplotlib 环境(如 web 部署)返回 None，调用方需自行容错。
    """
    global _chosen_font
    if _chosen_font is _UNSET:
        _chosen_font = setup_chinese_font() or None
    return _chosen_font


# 延迟探测标记: 避免在模块导入时(web 启动链)就触发 matplotlib 导入。
_UNSET = object()
_chosen_font = _UNSET

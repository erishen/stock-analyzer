"""可选的钉钉通知钩子（公开仓库安全：无 data_tools/ 时静默降级）。

公开仓库不含 ``data_tools/``（本地工具，见 .gitignore），其中才有 ``notify.py`` 与
webhook 配置。本模块按**文件路径**动态加载同仓的 ``data_tools/notify.py`` 来推送，
找不到就返回 ``(False, 原因)`` 且不抛异常——公开部署无此模块也照常运行。

本地 Docker 镜像会 ``COPY data_tools/``（见 Dockerfile），因此容器内的
「一键清仓」等操作具备钉钉推送能力；未配 ``STOCK_WEBHOOK_URL`` 时 notify 自身会跳过。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

# src/web/notify_hook.py -> parents[2] = apps/stock-analyzer
_DATA_TOOLS = Path(__file__).resolve().parents[2] / "data_tools"
_NOTIFY_PATH = _DATA_TOOLS / "notify.py"

_module: Any = None
_loaded = False


def _notify():
    """惰性加载 data_tools/notify.py（只加载一次）；不存在返回 None。"""
    global _module, _loaded
    if _loaded:
        return _module
    _loaded = True
    try:
        spec = importlib.util.spec_from_file_location("stock_data_tools_notify", _NOTIFY_PATH)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _module = mod
    except Exception:
        _module = None
    return _module


def configured() -> bool:
    """是否配置了 webhook（未配置/模块缺失 → False，调用方可据此跳过拼消息）。"""
    mod = _notify()
    try:
        return bool(mod and mod.configured())
    except Exception:
        return False


def send_markdown(text: str, title: str = "模拟仓") -> tuple[bool, str]:
    """推送 Markdown；notify 不可用/未配置时返回 ``(False, 原因)``，从不抛异常。"""
    mod = _notify()
    if mod is None:
        return False, "notify 不可用（无 data_tools/notify.py）"
    try:
        return mod.send_markdown(text, title=title)
    except Exception as e:
        return False, f"推送异常：{type(e).__name__}: {e}"

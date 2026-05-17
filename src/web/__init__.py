"""
Web Module for Stock Analyzer.
Web 模块 - 提供 Web 界面和 API
"""

from .api import app, run_server
from .schemas import (
    BacktestRequest,
    BacktestResponse,
    MarketTimingResponse,
    PortfolioRequest,
    PortfolioResponse,
    ScanRequest,
    ScanResponse,
    SectorResponse,
)

__all__ = [
    "BacktestRequest",
    "BacktestResponse",
    "MarketTimingResponse",
    "PortfolioRequest",
    "PortfolioResponse",
    "ScanRequest",
    "ScanResponse",
    "SectorResponse",
    "app",
    "run_server",
]

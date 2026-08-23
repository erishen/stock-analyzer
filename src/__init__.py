"""Stock Analyzer - 股票数据分析工具

注意: 不在包导入顶层加载 analyze_stocks(它依赖 matplotlib/pandas 等重依赖),
否则 web 启动链(仅装 fastapi+uvicorn 的 web extra)会因缺少这些依赖而崩溃。
StockAnalyzer 通过模块级 __getattr__ 惰性导入, 仅在实际使用时才加载。
"""

__all__ = ["StockAnalyzer"]


def __getattr__(name: str):
    if name == "StockAnalyzer":
        from .analyze_stocks import StockAnalyzer

        return StockAnalyzer
    raise AttributeError(f"module 'src' has no attribute {name!r}")

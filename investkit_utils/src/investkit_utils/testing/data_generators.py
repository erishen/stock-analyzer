"""测试数据生成"""

import random
from datetime import date, timedelta


def generate_test_stock_data(
    symbol: str = "000001",
    days: int = 30,
    start_price: float = 10.0,
    volatility: float = 0.02,
) -> list[dict]:
    """
    生成测试股票数据

    Args:
        symbol: 股票代码
        days: 天数
        start_price: 起始价格
        volatility: 波动率

    Returns:
        股票数据列表
    """
    data = []
    price = start_price
    base_date = date.today() - timedelta(days=days)

    for i in range(days):
        current_date = base_date + timedelta(days=i)
        change = random.uniform(-volatility, volatility)
        open_price = price
        close_price = price * (1 + change)
        high_price = max(open_price, close_price) * (1 + random.uniform(0, volatility / 2))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, volatility / 2))
        volume = random.randint(100000, 1000000)

        data.append(
            {
                "symbol": symbol,
                "date": current_date.isoformat(),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": volume,
            }
        )

        price = close_price

    return data


def generate_test_portfolio(
    symbols: list[str] | None = None,
    cash: float = 10000.0,
) -> dict:
    """
    生成测试投资组合

    Args:
        symbols: 股票代码列表
        cash: 现金

    Returns:
        投资组合字典
    """
    symbols = symbols or ["000001", "600000", "000002"]

    positions = []
    for symbol in symbols:
        quantity = random.randint(100, 1000)
        cost_price = random.uniform(10, 100)
        positions.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "cost_price": round(cost_price, 2),
            }
        )

    return {
        "name": "Test Portfolio",
        "positions": positions,
        "cash": cash,
    }

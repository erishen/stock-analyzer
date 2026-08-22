"""金融计算工具"""

from __future__ import annotations

from collections.abc import Iterable


def calculate_irr(
    cash_flows: Iterable[float],
    guess: float = 0.1,
    max_iterations: int = 1000,
    tolerance: float = 1e-6,
) -> float | None:
    """计算内部收益率 (IRR)

    使用牛顿迭代法求解使 NPV = 0 的折现率。

    Args:
        cash_flows: 现金流序列 (第一个为负数表示初始投资)
        guess: 初始猜测值
        max_iterations: 最大迭代次数
        tolerance: 收敛容差

    Returns:
        IRR 值 (年化收益率)，无法计算时返回 None

    示例:
        >>> calculate_irr([-10000, 3000, 3000, 3000, 3000])
        0.0771  # 约 7.71%
    """
    flows = list(cash_flows)
    if not flows or flows[0] >= 0:
        return None

    rate = guess

    for _ in range(max_iterations):
        npv = sum(cf / (1 + rate) ** i for i, cf in enumerate(flows))
        npv_derivative = sum(-i * cf / (1 + rate) ** (i + 1) for i, cf in enumerate(flows))

        if abs(npv_derivative) < 1e-10:
            break

        new_rate = rate - npv / npv_derivative

        if abs(new_rate - rate) < tolerance:
            return round(new_rate, 6)

        rate = new_rate

    return round(rate, 6) if -1 < rate < 10 else None


def calculate_cagr(
    start_value: float,
    end_value: float,
    years: float,
) -> float | None:
    """计算复合年增长率 (CAGR)

    Args:
        start_value: 起始值
        end_value: 结束值
        years: 年数

    Returns:
        CAGR 值 (小数形式)

    示例:
        >>> calculate_cagr(10000, 15000, 3)
        0.1447  # 约 14.47%
    """
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return None

    return (end_value / start_value) ** (1 / years) - 1


def calculate_sharpe_ratio(
    returns: Iterable[float],
    risk_free_rate: float = 0.03,
) -> float | None:
    """计算夏普比率

    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率 (年化)

    Returns:
        夏普比率

    示例:
        >>> calculate_sharpe_ratio([0.1, 0.05, 0.08, -0.02, 0.12])
        1.234
    """
    import math

    returns_list = list(returns)
    if not returns_list:
        return None

    n = len(returns_list)
    mean_return = sum(returns_list) / n

    variance = sum((r - mean_return) ** 2 for r in returns_list) / n
    std_dev = math.sqrt(variance)

    if std_dev == 0:
        return None

    return (mean_return - risk_free_rate) / std_dev


def calculate_max_drawdown(values: Iterable[float]) -> float:
    """计算最大回撤

    Args:
        values: 资产价值序列

    Returns:
        最大回撤 (正数)

    示例:
        >>> calculate_max_drawdown([100, 110, 105, 95, 100, 90])
        0.1818  # 约 18.18%
    """
    values_list = list(values)
    if not values_list:
        return 0.0

    max_value = values_list[0]
    max_drawdown = 0.0

    for value in values_list:
        if value > max_value:
            max_value = value

        drawdown = (max_value - value) / max_value if max_value > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)

    return round(max_drawdown, 4)


def calculate_win_rate(trades: Iterable[tuple[float, float]]) -> float:
    """计算胜率

    Args:
        trades: 交易序列 [(买入价, 卖出价), ...]

    Returns:
        胜率 (0-1)

    示例:
        >>> calculate_win_rate([(10, 12), (15, 14), (20, 25)])
        0.6667  # 约 66.67%
    """
    trades_list = list(trades)
    if not trades_list:
        return 0.0

    wins = sum(1 for buy, sell in trades_list if sell > buy)
    return round(wins / len(trades_list), 4)


def calculate_profit_factor(trades: Iterable[tuple[float, float]]) -> float:
    """计算盈亏比

    Args:
        trades: 交易序列 [(买入价, 卖出价), ...]

    Returns:
        盈亏比

    示例:
        >>> calculate_profit_factor([(10, 12), (15, 14), (20, 25)])
        3.5
    """
    trades_list = list(trades)
    if not trades_list:
        return 0.0

    total_profit = 0.0
    total_loss = 0.0

    for buy, sell in trades_list:
        pnl = sell - buy
        if pnl > 0:
            total_profit += pnl
        else:
            total_loss += abs(pnl)

    if total_loss == 0:
        return float("inf") if total_profit > 0 else 0.0

    return round(total_profit / total_loss, 2)


def calculate_position_size(
    total_capital: float,
    risk_per_trade: float = 0.02,
    entry_price: float = 0,
    stop_loss_price: float | None = None,
) -> float:
    """计算仓位大小

    Args:
        total_capital: 总资金
        risk_per_trade: 单笔风险比例 (默认 2%)
        entry_price: 入场价格
        stop_loss_price: 止损价格

    Returns:
        可购买数量

    示例:
        >>> calculate_position_size(100000, 0.02, 50, 45)
        400  # 可买 400 股
    """
    if total_capital <= 0 or entry_price <= 0:
        return 0.0

    risk_amount = total_capital * risk_per_trade

    if stop_loss_price and stop_loss_price < entry_price:
        risk_per_share = entry_price - stop_loss_price
        shares = risk_amount / risk_per_share
    else:
        shares = total_capital / entry_price

    return int(shares)


def calculate_compound_interest(
    principal: float,
    rate: float,
    years: int,
    compounds_per_year: int = 12,
) -> float:
    """计算复利

    Args:
        principal: 本金
        rate: 年利率 (小数形式)
        years: 年数
        compounds_per_year: 每年复利次数

    Returns:
        最终金额

    示例:
        >>> calculate_compound_interest(10000, 0.05, 5)
        12833.59
    """
    amount = principal * (1 + rate / compounds_per_year) ** (compounds_per_year * years)
    return round(amount, 2)

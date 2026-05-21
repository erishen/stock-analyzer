"""
Strategy Backtester for Stock Analyzer.
策略回测模块 - 验证交易策略的历史表现

支持策略:
- 动量策略: 基于涨跌幅动量选股
- 均值回归: RSI 超卖反弹
- 趋势跟踪: MA 均线策略
- 突破策略: 价格突破布林带
"""

import logging
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_stock_analysis_db_path
from constants import is_excluded_stock
from data import get_stock_info_fetcher, get_stock_name

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """交易记录"""

    code: str
    name: str
    entry_date: str
    entry_price: float
    exit_date: str = ""
    exit_price: float = 0.0
    shares: int = 0
    profit: float = 0.0
    profit_percent: float = 0.0
    holding_days: int = 0
    signal: str = ""
    commission: float = 0.0
    stamp_tax: float = 0.0
    total_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "entry_date": self.entry_date,
            "entry_price": round(self.entry_price, 2),
            "exit_date": self.exit_date,
            "exit_price": round(self.exit_price, 2),
            "shares": self.shares,
            "profit": round(self.profit, 2),
            "profit_percent": round(self.profit_percent, 2),
            "holding_days": self.holding_days,
            "signal": self.signal,
            "commission": round(self.commission, 2),
            "stamp_tax": round(self.stamp_tax, 2),
            "total_cost": round(self.total_cost, 2),
        }


@dataclass
class BacktestResult:
    """回测结果"""

    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_profit: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    trades: list[Trade]
    equity_curve: list[dict]
    total_commission: float = 0.0
    total_stamp_tax: float = 0.0
    total_trading_cost: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": round(self.initial_capital, 2),
            "final_capital": round(self.final_capital, 2),
            "total_return": round(self.total_return * 100, 2),
            "annualized_return": round(self.annualized_return * 100, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "win_rate": round(self.win_rate * 100, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_profit": round(self.avg_profit * 100, 2),
            "avg_loss": round(self.avg_loss * 100, 2),
            "profit_factor": round(self.profit_factor, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "volatility": round(self.volatility * 100, 2),
            "trades": [t.to_dict() for t in self.trades[:20]],
            "equity_curve": self.equity_curve,
            "total_commission": round(self.total_commission, 2),
            "total_stamp_tax": round(self.total_stamp_tax, 2),
            "total_trading_cost": round(self.total_trading_cost, 2),
        }


class MomentumStrategy:
    """动量策略"""

    def __init__(
        self,
        lookback_days: int = 20,
        top_n: int = 10,
        holding_days: int = 5,
        min_momentum: float = 0.0,
        max_momentum: float = 1.0,
        max_volatility: float = 0.15,
        min_price: float = 2.0,
        exclude_st: bool = True,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
    ):
        """
        初始化动量策略

        Args:
            lookback_days: 回看天数，计算动量的周期
            top_n: 选择动量最强的前 N 只股票
            holding_days: 持有天数
            min_momentum: 最小动量阈值 (避免选择下跌股票)
            max_momentum: 最大动量阈值 (避免追涨过头)
            max_volatility: 最大波动率阈值
            min_price: 最低价格过滤
            exclude_st: 是否排除 ST 股票
            stop_loss: 止损比例 (如 0.05 表示 5% 止损，0 表示不止损)
            take_profit: 止盈比例 (如 0.1 表示 10% 止盈，0 表示不止盈)
        """
        self.lookback_days = lookback_days
        self.top_n = top_n
        self.holding_days = holding_days
        self.min_momentum = min_momentum
        self.max_momentum = max_momentum
        self.max_volatility = max_volatility
        self.min_price = min_price
        self.exclude_st = exclude_st
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def calculate_momentum(self, df: pd.DataFrame, date_idx: int) -> float:
        """计算动量 (收益率)"""
        if date_idx < self.lookback_days:
            return 0.0

        start_price = df.iloc[date_idx - self.lookback_days]["close"]
        end_price = df.iloc[date_idx]["close"]

        if start_price <= 0:
            return 0.0

        return (end_price - start_price) / start_price

    def calculate_volatility(self, df: pd.DataFrame, date_idx: int, window: int = 20) -> float:
        """计算波动率"""
        if date_idx < window:
            return 1.0

        returns = df["close"].iloc[date_idx - window : date_idx].pct_change()
        return returns.std()

    def is_excluded(self, name: str) -> bool:
        return is_excluded_stock(name, self.exclude_st)

    def select_stocks(
        self,
        all_data: dict[str, pd.DataFrame],
        date_idx: int,
        date: str,
        stock_names: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]:
        """
        选择股票

        Returns:
            [(code, momentum), ...]
        """
        momentums = []

        for code, df in all_data.items():
            if stock_names and self.is_excluded(stock_names.get(code, "")):
                continue

            date_rows = df[df["date"] == date]
            if date_rows.empty:
                continue

            stock_idx = date_rows.index[0]
            if stock_idx < self.lookback_days:
                continue

            try:
                row = date_rows.iloc[0]
                close_price = float(row.get("close", 0) or 0)

                if close_price < self.min_price:
                    continue

                momentum = self.calculate_momentum(df, stock_idx)

                if momentum < self.min_momentum or momentum > self.max_momentum:
                    continue

                volatility = self.calculate_volatility(df, stock_idx)
                if volatility > self.max_volatility:
                    continue

                momentums.append((code, momentum))
            except Exception:
                continue

        momentums.sort(key=lambda x: x[1], reverse=True)
        return momentums[: self.top_n]


class MeanReversionStrategy:
    """均值回归策略 (RSI 超卖反弹)"""

    def __init__(
        self,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        holding_days: int = 5,
        max_stocks: int = 10,
        min_price: float = 2.0,
        exclude_st: bool = True,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
    ):
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.holding_days = holding_days
        self.max_stocks = max_stocks
        self.min_price = min_price
        self.exclude_st = exclude_st
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def is_excluded(self, name: str) -> bool:
        return is_excluded_stock(name, self.exclude_st)

    def select_stocks(
        self,
        all_data: dict[str, pd.DataFrame],
        date_idx: int,
        date: str,
        stock_names: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]:
        """选择 RSI 超卖的股票"""
        selected = []

        for code, df in all_data.items():
            if stock_names and self.is_excluded(stock_names.get(code, "")):
                continue

            date_rows = df[df["date"] == date]
            if date_rows.empty:
                continue

            try:
                row = date_rows.iloc[0]
                close_price = float(row.get("close", 0) or 0)
                if close_price < self.min_price:
                    continue

                rsi = row.get("rsi", 50) or 50
                if rsi < self.rsi_oversold:
                    selected.append((code, rsi))
            except Exception:
                continue

        selected.sort(key=lambda x: x[1])
        return selected[: self.max_stocks]


class TrendFollowingStrategy:
    """趋势跟踪策略 (布林带突破)"""

    def __init__(
        self,
        holding_days: int = 5,
        max_stocks: int = 10,
        min_price: float = 2.0,
        exclude_st: bool = True,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        use_ma_cross: bool = False,
    ):
        self.holding_days = holding_days
        self.max_stocks = max_stocks
        self.min_price = min_price
        self.exclude_st = exclude_st
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.use_ma_cross = use_ma_cross

    def is_excluded(self, name: str) -> bool:
        return is_excluded_stock(name, self.exclude_st)

    def select_stocks(
        self,
        all_data: dict[str, pd.DataFrame],
        date_idx: int,
        date: str,
        stock_names: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]:
        """选择突破布林带上轨或均线金叉的股票"""
        selected = []

        for code, df in all_data.items():
            if stock_names and self.is_excluded(stock_names.get(code, "")):
                continue

            date_rows = df[df["date"] == date]
            if date_rows.empty:
                continue

            try:
                row = date_rows.iloc[0]
                close_price = float(row.get("close", 0) or 0)
                if close_price < self.min_price:
                    continue

                boll_upper = row.get("boll_upper", 0) or 0
                row.get("boll_lower", 0) or 0
                ma5 = row.get("ma5", 0) or 0
                ma10 = row.get("ma10", 0) or 0
                ma20 = row.get("ma20", 0) or 0

                signal_score = 0

                if self.use_ma_cross:
                    if ma5 > ma10 > ma20:
                        signal_score = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
                else:
                    if close_price > boll_upper and boll_upper > 0:
                        signal_score = (close_price - boll_upper) / boll_upper * 100

                if signal_score > 0:
                    selected.append((code, signal_score))

            except Exception:
                continue

        selected.sort(key=lambda x: x[1], reverse=True)
        return selected[: self.max_stocks]


class MultiFactorStrategy:
    """多因子策略 (综合评分选股)"""

    def __init__(
        self,
        holding_days: int = 5,
        max_stocks: int = 10,
        min_price: float = 2.0,
        exclude_st: bool = True,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        trend_weight: float = 0.3,
        momentum_weight: float = 0.3,
        volatility_weight: float = 0.2,
        volume_weight: float = 0.2,
    ):
        self.holding_days = holding_days
        self.max_stocks = max_stocks
        self.min_price = min_price
        self.exclude_st = exclude_st
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trend_weight = trend_weight
        self.momentum_weight = momentum_weight
        self.volatility_weight = volatility_weight
        self.volume_weight = volume_weight

    def is_excluded(self, name: str) -> bool:
        return is_excluded_stock(name, self.exclude_st)

    def calculate_factors(self, df: pd.DataFrame, date_idx: int) -> dict:
        """计算因子得分"""
        if date_idx < 20:
            return {}

        row = df.iloc[date_idx]
        close = float(row.get("close", 0) or 0)
        ma5 = float(row.get("ma5", 0) or 0)
        ma10 = float(row.get("ma10", 0) or 0)
        ma20 = float(row.get("ma20", 0) or 0)
        float(row.get("rsi", 50) or 50)
        volume = float(row.get("volume", 0) or 0)

        trend_score = 0
        if ma5 > ma10 > ma20 and close > ma5:
            trend_score = (close - ma20) / ma20 * 100 if ma20 > 0 else 0

        momentum_score = 0
        if date_idx >= 20:
            returns = df["close"].iloc[date_idx - 20 : date_idx].pct_change().dropna()
            if len(returns) > 0:
                momentum_score = returns.sum() * 100

        volatility_score = 0
        if date_idx >= 20:
            returns = df["close"].iloc[date_idx - 20 : date_idx].pct_change().dropna()
            if len(returns) > 0:
                vol = returns.std()
                volatility_score = max(0, 10 - vol * 100)

        volume_score = 0
        if date_idx >= 5 and volume > 0:
            avg_volume = df["volume"].iloc[date_idx - 5 : date_idx].mean()
            if avg_volume > 0:
                volume_score = (volume / avg_volume - 1) * 10

        return {
            "trend": trend_score,
            "momentum": momentum_score,
            "volatility": volatility_score,
            "volume": volume_score,
        }

    def select_stocks(
        self,
        all_data: dict[str, pd.DataFrame],
        date_idx: int,
        date: str,
        stock_names: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]:
        """选择综合评分最高的股票"""
        selected = []

        for code, df in all_data.items():
            if stock_names and self.is_excluded(stock_names.get(code, "")):
                continue

            date_rows = df[df["date"] == date]
            if date_rows.empty:
                continue

            try:
                row = date_rows.iloc[0]
                close_price = float(row.get("close", 0) or 0)
                if close_price < self.min_price:
                    continue

                local_idx = df[df["date"] == date].index[0]
                factors = self.calculate_factors(df, local_idx)

                if not factors:
                    continue

                total_score = (
                    factors["trend"] * self.trend_weight
                    + factors["momentum"] * self.momentum_weight
                    + factors["volatility"] * self.volatility_weight
                    + factors["volume"] * self.volume_weight
                )

                if total_score > 0:
                    selected.append((code, total_score))

            except Exception:
                continue

        selected.sort(key=lambda x: x[1], reverse=True)
        return selected[: self.max_stocks]


class PositionManager:
    """仓位管理器"""

    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """凯利公式计算最优仓位"""
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0.1

        b = avg_win / abs(avg_loss)
        q = 1 - win_rate
        kelly = (win_rate * b - q) / b

        return max(0.05, min(kelly * 0.5, 0.2))

    @staticmethod
    def risk_parity(volatilities: dict[str, float]) -> dict[str, float]:
        """风险平价仓位分配"""
        if not volatilities:
            return {}

        inv_vols = {k: 1 / v for k, v in volatilities.items() if v > 0}
        total_inv_vol = sum(inv_vols.values())

        if total_inv_vol == 0:
            return {k: 1 / len(volatilities) for k in volatilities}

        return {k: v / total_inv_vol for k, v in inv_vols.items()}

    @staticmethod
    def equal_weight(n: int) -> float:
        """等权分配"""
        return 1.0 / n if n > 0 else 0.0


class DynamicStopLoss:
    """动态止损管理器"""

    def __init__(
        self,
        atr_multiplier: float = 2.0,
        trailing_stop: float = 0.0,
        max_hold_days: int = 20,
    ):
        self.atr_multiplier = atr_multiplier
        self.trailing_stop = trailing_stop
        self.max_hold_days = max_hold_days

    def calculate_atr_stop(
        self,
        entry_price: float,
        atr: float,
        highest_price: float | None = None,
    ) -> tuple[float, str]:
        """计算 ATR 止损价"""
        stop_price = entry_price - self.atr_multiplier * atr
        stop_type = "ATR止损"

        if self.trailing_stop > 0 and highest_price:
            trailing_stop_price = highest_price * (1 - self.trailing_stop)
            if trailing_stop_price > stop_price:
                stop_price = trailing_stop_price
                stop_type = "移动止损"

        return stop_price, stop_type

    def should_stop(
        self,
        current_price: float,
        entry_price: float,
        highest_price: float,
        atr: float,
        holding_days: int,
    ) -> tuple[bool, str]:
        """判断是否应该止损"""
        if holding_days >= self.max_hold_days:
            return True, "最大持仓天数"

        stop_price, stop_type = self.calculate_atr_stop(entry_price, atr, highest_price)

        if current_price <= stop_price:
            return True, stop_type

        return False, ""


class BacktestEngine:
    """回测引擎"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接数据库"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库不存在: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()

    def get_all_stock_data(self) -> dict[str, pd.DataFrame]:
        """获取所有股票数据"""
        query = """
            SELECT code, date, close, high, low, open, volume,
                   rsi, macd, macd_signal, ma5, ma10, ma20,
                   boll_upper, boll_lower
            FROM stock_analysis
            ORDER BY code, date
        """
        df = pd.read_sql_query(query, self.conn)
        df["date"] = pd.to_datetime(df["date"])

        all_data = {}
        for code, group in df.groupby("code"):
            all_data[code] = group.reset_index(drop=True)

        return all_data

    def get_date_range(self, all_data: dict[str, pd.DataFrame]) -> list[str]:
        """获取日期范围"""
        all_dates = set()
        for df in all_data.values():
            all_dates.update(df["date"].dt.strftime("%Y-%m-%d").tolist())

        return sorted(list(all_dates))

    def get_stock_names(self) -> dict[str, str]:
        """获取所有股票名称"""
        fetcher = get_stock_info_fetcher()
        codes = []
        try:
            df = pd.read_sql_query("SELECT DISTINCT code FROM stock_analysis", self.conn)
            codes = df["code"].tolist()
        except Exception:
            pass

        if codes:
            return fetcher.batch_get_names(codes)
        return {}

    def run_backtest(
        self,
        strategy: MomentumStrategy | MeanReversionStrategy,
        initial_capital: float = 100000.0,
        position_size: float = 0.1,
        commission_rate: float = 0.0003,
        stamp_tax_rate: float = 0.001,
        min_commission: float = 5.0,
    ) -> BacktestResult:
        """
        运行回测

        Args:
            strategy: 策略实例
            initial_capital: 初始资金
            position_size: 单只股票仓位比例
            commission_rate: 佣金费率 (默认万三)
            stamp_tax_rate: 印花税率 (默认千一，仅卖出)
            min_commission: 最低佣金 (默认5元)

        Returns:
            回测结果
        """
        all_data = self.get_all_stock_data()
        dates = self.get_date_range(all_data)
        stock_names = self.get_stock_names()

        capital = initial_capital
        equity_curve = []
        trades: list[Trade] = []
        holdings: dict[str, Trade] = {}
        total_commission = 0.0
        total_stamp_tax = 0.0

        holding_days = getattr(strategy, "holding_days", 5)

        def calc_commission(amount: float) -> float:
            return max(amount * commission_rate, min_commission)

        logger.info(f"\n📈 回测策略: {strategy.__class__.__name__}")
        logger.info(f"   初始资金: {initial_capital:,.0f}")
        logger.info(f"   回测区间: {dates[0]} ~ {dates[-1]}")
        logger.info(f"   佣金费率: {commission_rate * 100:.3f}% (最低{min_commission}元)")
        logger.info(f"   印花税率: {stamp_tax_rate * 100:.2f}% (仅卖出)")

        stop_loss = getattr(strategy, "stop_loss", 0.0)
        take_profit = getattr(strategy, "take_profit", 0.0)
        if stop_loss > 0:
            logger.info(f"   止损比例: {stop_loss * 100:.1f}%")
        if take_profit > 0:
            logger.info(f"   止盈比例: {take_profit * 100:.1f}%")

        for i, date in enumerate(dates):
            for code, trade in list(holdings.items()):
                if code not in all_data:
                    continue

                df = all_data[code]
                date_rows = df[df["date"] == date]

                if date_rows.empty:
                    continue

                trade.holding_days += 1
                current_price = float(date_rows.iloc[0]["close"])
                pnl_percent = (current_price - trade.entry_price) / trade.entry_price

                should_exit = False
                exit_reason = ""

                if stop_loss > 0 and pnl_percent <= -stop_loss:
                    should_exit = True
                    exit_reason = "止损"
                elif take_profit > 0 and pnl_percent >= take_profit:
                    should_exit = True
                    exit_reason = "止盈"

                if should_exit or trade.holding_days >= holding_days:
                    exit_price = current_price
                    trade.exit_date = date
                    trade.exit_price = exit_price
                    if exit_reason:
                        trade.signal = f"{trade.signal} ({exit_reason})"

                    sell_amount = exit_price * trade.shares
                    sell_commission = calc_commission(sell_amount)
                    sell_stamp_tax = sell_amount * stamp_tax_rate
                    sell_cost = sell_commission + sell_stamp_tax

                    trade.commission += sell_commission
                    trade.stamp_tax = sell_stamp_tax
                    trade.total_cost += sell_cost
                    total_commission += sell_commission
                    total_stamp_tax += sell_stamp_tax

                    trade.profit = (
                        exit_price - trade.entry_price
                    ) * trade.shares - trade.total_cost
                    trade.profit_percent = trade.profit / (trade.entry_price * trade.shares)

                    capital += sell_amount - sell_cost
                    trades.append(trade)
                    del holdings[code]

            if i % holding_days == 0:
                select_kwargs = {"all_data": all_data, "date_idx": i, "date": date}
                if isinstance(
                    strategy,
                    (
                        MomentumStrategy,
                        MeanReversionStrategy,
                        TrendFollowingStrategy,
                        MultiFactorStrategy,
                    ),
                ):
                    select_kwargs["stock_names"] = stock_names
                selected = strategy.select_stocks(**select_kwargs)

                for code, signal_value in selected:
                    if code in holdings:
                        continue

                    if code not in all_data:
                        continue

                    df = all_data[code]
                    date_rows = df[df["date"] == date]

                    if date_rows.empty:
                        continue

                    entry_price = float(date_rows.iloc[0]["close"])
                    position_value = capital * position_size
                    shares = int(position_value / entry_price)

                    if shares <= 0:
                        continue

                    buy_amount = entry_price * shares
                    buy_commission = calc_commission(buy_amount)

                    trade = Trade(
                        code=code,
                        name=get_stock_name(code),
                        entry_date=date,
                        entry_price=entry_price,
                        shares=shares,
                        signal=f"{signal_value:.4f}",
                        commission=buy_commission,
                        total_cost=buy_commission,
                    )
                    total_commission += buy_commission

                    holdings[code] = trade
                    capital -= buy_amount + buy_commission

            holdings_value = 0.0
            for h_code, h_trade in holdings.items():
                if h_code in all_data:
                    df = all_data[h_code]
                    date_rows = df[df["date"] == date]
                    if not date_rows.empty:
                        current_price = float(date_rows.iloc[0]["close"])
                        holdings_value += current_price * h_trade.shares

            total_equity = capital + holdings_value
            equity_curve.append(
                {
                    "date": date,
                    "equity": round(total_equity, 2),
                }
            )

        for trade in holdings.values():
            if trade.code in all_data:
                df = all_data[trade.code]
                if not df.empty:
                    last_price = float(df.iloc[-1]["close"])
                    trade.exit_price = last_price
                    trade.exit_date = df.iloc[-1]["date"].strftime("%Y-%m-%d")

                    sell_amount = last_price * trade.shares
                    sell_commission = max(sell_amount * commission_rate, min_commission)
                    sell_stamp_tax = sell_amount * stamp_tax_rate
                    sell_cost = sell_commission + sell_stamp_tax

                    trade.commission += sell_commission
                    trade.stamp_tax = sell_stamp_tax
                    trade.total_cost += sell_cost
                    total_commission += sell_commission
                    total_stamp_tax += sell_stamp_tax

                    trade.profit = (
                        last_price - trade.entry_price
                    ) * trade.shares - trade.total_cost
                    trade.profit_percent = trade.profit / (trade.entry_price * trade.shares)
                    capital += sell_amount - sell_cost
            trades.append(trade)

        return self._calculate_result(
            strategy.__class__.__name__,
            dates,
            initial_capital,
            equity_curve[-1]["equity"] if equity_curve else capital,
            trades,
            equity_curve,
            total_commission,
            total_stamp_tax,
        )

    def _calculate_result(
        self,
        strategy_name: str,
        dates: list[str],
        initial_capital: float,
        final_capital: float,
        trades: list[Trade],
        equity_curve: list[dict],
        total_commission: float = 0.0,
        total_stamp_tax: float = 0.0,
    ) -> BacktestResult:
        """计算回测结果"""
        total_return = (final_capital - initial_capital) / initial_capital

        days = (
            datetime.strptime(dates[-1], "%Y-%m-%d") - datetime.strptime(dates[0], "%Y-%m-%d")
        ).days
        annualized_return = (1 + total_return) ** (365 / max(days, 1)) - 1

        equities = [e["equity"] for e in equity_curve]
        peak = initial_capital
        max_drawdown = 0.0
        for equity in equities:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        winning_trades = [t for t in trades if t.profit > 0]
        losing_trades = [t for t in trades if t.profit <= 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0

        avg_profit = np.mean([t.profit_percent for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.profit_percent for t in losing_trades]) if losing_trades else 0

        total_profit = sum(t.profit_percent for t in winning_trades)
        total_loss = abs(sum(t.profit_percent for t in losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")

        returns = []
        for i in range(1, len(equities)):
            ret = (equities[i] - equities[i - 1]) / equities[i - 1]
            returns.append(ret)

        sharpe_ratio = 0.0
        sortino_ratio = 0.0
        calmar_ratio = 0.0
        volatility = 0.0

        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            volatility = std_return * np.sqrt(252)

            if std_return > 0:
                sharpe_ratio = avg_return / std_return * np.sqrt(252)

            negative_returns = [r for r in returns if r < 0]
            if negative_returns:
                downside_std = np.std(negative_returns)
                if downside_std > 0:
                    sortino_ratio = avg_return / downside_std * np.sqrt(252)

            if max_drawdown > 0:
                calmar_ratio = annualized_return / max_drawdown

        return BacktestResult(
            strategy_name=strategy_name,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            trades=trades,
            equity_curve=equity_curve,
            total_commission=total_commission,
            total_stamp_tax=total_stamp_tax,
            total_trading_cost=total_commission + total_stamp_tax,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            volatility=volatility,
        )


def run_backtest(
    db_path: Path | None = None,
    strategy_type: str = "momentum",
    lookback_days: int = 20,
    top_n: int = 10,
    holding_days: int = 5,
    initial_capital: float = 100000.0,
    min_momentum: float = 0.0,
    max_momentum: float = 1.0,
    max_volatility: float = 0.15,
    min_price: float = 2.0,
    exclude_st: bool = True,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    use_ma_cross: bool = False,
) -> BacktestResult:
    """
    运行回测的便捷函数

    Args:
        db_path: 数据库路径
        strategy_type: 策略类型 ("momentum", "mean_reversion", "trend_following", "multi_factor")
        lookback_days: 动量回看天数
        top_n: 选股数量
        holding_days: 持有天数
        initial_capital: 初始资金
        min_momentum: 最小动量阈值
        max_momentum: 最大动量阈值
        max_volatility: 最大波动率阈值
        min_price: 最低价格过滤
        exclude_st: 是否排除 ST 股票
        stop_loss: 止损比例
        take_profit: 止盈比例
        use_ma_cross: 趋势策略是否使用均线交叉

    Returns:
        回测结果
    """
    project_root = Path(__file__).parent.parent.parent
    project_root / "data"

    db_path = db_path or get_stock_analysis_db_path()

    engine = BacktestEngine(db_path)
    engine.connect()

    try:
        if strategy_type == "momentum":
            strategy = MomentumStrategy(
                lookback_days=lookback_days,
                top_n=top_n,
                holding_days=holding_days,
                min_momentum=min_momentum,
                max_momentum=max_momentum,
                max_volatility=max_volatility,
                min_price=min_price,
                exclude_st=exclude_st,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        elif strategy_type == "mean_reversion":
            strategy = MeanReversionStrategy(
                holding_days=holding_days,
                max_stocks=top_n,
                min_price=min_price,
                exclude_st=exclude_st,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        elif strategy_type == "trend_following":
            strategy = TrendFollowingStrategy(
                holding_days=holding_days,
                max_stocks=top_n,
                min_price=min_price,
                exclude_st=exclude_st,
                stop_loss=stop_loss,
                take_profit=take_profit,
                use_ma_cross=use_ma_cross,
            )
        elif strategy_type == "multi_factor":
            strategy = MultiFactorStrategy(
                holding_days=holding_days,
                max_stocks=top_n,
                min_price=min_price,
                exclude_st=exclude_st,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        else:
            raise ValueError(f"未知策略类型: {strategy_type}")

        return engine.run_backtest(strategy, initial_capital)
    finally:
        engine.close()

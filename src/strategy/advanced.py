"""
Advanced Trading Strategies for Stock Analyzer.
高级交易策略

支持策略:
- 突破策略: 价格突破、布林带突破、成交量突破
- 网格交易策略: 固定间隔网格、动态网格
- 配对交易策略: 协整配对、统计套利
- 事件驱动策略: 财报事件、分红事件
"""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from constants import is_excluded_stock


@dataclass
class GridLevel:
    """网格层级"""

    price: float
    shares: int
    is_buy: bool
    is_filled: bool = False


@dataclass
class PairInfo:
    """配对信息"""

    code1: str
    code2: str
    spread_mean: float
    spread_std: float
    hedge_ratio: float
    correlation: float


class BreakoutStrategy:
    """突破策略 - 价格突破、布林带突破、成交量突破"""

    def __init__(
        self,
        breakout_type: str = "price",
        lookback_days: int = 20,
        breakout_threshold: float = 0.02,
        volume_multiplier: float = 1.5,
        holding_days: int = 5,
        max_stocks: int = 10,
        min_price: float = 2.0,
        exclude_st: bool = True,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
    ):
        self.breakout_type = breakout_type
        self.lookback_days = lookback_days
        self.breakout_threshold = breakout_threshold
        self.volume_multiplier = volume_multiplier
        self.holding_days = holding_days
        self.max_stocks = max_stocks
        self.min_price = min_price
        self.exclude_st = exclude_st
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def is_excluded(self, name: str) -> bool:
        return is_excluded_stock(name, self.exclude_st)

    def detect_price_breakout(self, df: pd.DataFrame, idx: int) -> tuple[bool, float]:
        """检测价格突破"""
        if idx < self.lookback_days:
            return False, 0.0

        current_price = float(df.iloc[idx]["close"])
        high_prices = df.iloc[idx - self.lookback_days : idx]["high"]

        if len(high_prices) < self.lookback_days:
            return False, 0.0

        resistance = high_prices.max()
        breakout_pct = (current_price - resistance) / resistance

        if breakout_pct > self.breakout_threshold:
            return True, breakout_pct
        return False, 0.0

    def detect_bollinger_breakout(self, df: pd.DataFrame, idx: int) -> tuple[bool, float]:
        """检测布林带突破"""
        if idx < 20:
            return False, 0.0

        current_price = float(df.iloc[idx]["close"])
        boll_upper = float(df.iloc[idx].get("boll_upper", 0) or 0)

        if boll_upper <= 0:
            return False, 0.0

        if current_price > boll_upper:
            breakout_pct = (current_price - boll_upper) / boll_upper
            return True, breakout_pct
        return False, 0.0

    def detect_volume_breakout(self, df: pd.DataFrame, idx: int) -> tuple[bool, float]:
        """检测成交量突破"""
        if idx < self.lookback_days:
            return False, 0.0

        current_volume = float(df.iloc[idx].get("volume", 0) or 0)
        avg_volume = df.iloc[idx - self.lookback_days : idx]["volume"].mean()

        if avg_volume <= 0:
            return False, 0.0

        volume_ratio = current_volume / avg_volume

        if volume_ratio > self.volume_multiplier:
            current_price = float(df.iloc[idx]["close"])
            prev_price = float(df.iloc[idx - 1]["close"])
            price_change = (current_price - prev_price) / prev_price

            if price_change > 0:
                return True, volume_ratio
        return False, 0.0

    def select_stocks(
        self,
        all_data: dict[str, pd.DataFrame],
        date_idx: int,
        date: str,
        stock_names: dict[str, str] | None = None,
    ) -> list[tuple[str, float]]:
        """选择突破股票"""
        selected = []

        for code, df in all_data.items():
            if stock_names and self.is_excluded(stock_names.get(code, "")):
                continue

            date_rows = df[df["date"] == date]
            if date_rows.empty:
                continue

            try:
                stock_idx = date_rows.index[0]
                row = date_rows.iloc[0]
                close_price = float(row.get("close", 0) or 0)

                if close_price < self.min_price:
                    continue

                is_breakout = False
                strength = 0.0

                if self.breakout_type == "price":
                    is_breakout, strength = self.detect_price_breakout(df, stock_idx)
                elif self.breakout_type == "bollinger":
                    is_breakout, strength = self.detect_bollinger_breakout(df, stock_idx)
                elif self.breakout_type == "volume":
                    is_breakout, strength = self.detect_volume_breakout(df, stock_idx)
                elif self.breakout_type == "all":
                    price_break, price_str = self.detect_price_breakout(df, stock_idx)
                    boll_break, boll_str = self.detect_bollinger_breakout(df, stock_idx)
                    vol_break, vol_str = self.detect_volume_breakout(df, stock_idx)

                    if price_break or boll_break or vol_break:
                        is_breakout = True
                        strength = max(price_str, boll_str, vol_str)

                if is_breakout:
                    selected.append((code, strength))
            except Exception:
                continue

        selected.sort(key=lambda x: x[1], reverse=True)
        return selected[: self.max_stocks]


class GridTradingStrategy:
    """网格交易策略 - 固定间隔网格、动态网格"""

    def __init__(
        self,
        grid_type: str = "fixed",
        grid_count: int = 10,
        grid_spacing: float = 0.05,
        base_position: float = 0.1,
        max_position: float = 0.8,
        min_price: float = 2.0,
    ):
        self.grid_type = grid_type
        self.grid_count = grid_count
        self.grid_spacing = grid_spacing
        self.base_position = base_position
        self.max_position = max_position
        self.min_price = min_price
        self.grids: dict[str, list[GridLevel]] = {}

    def initialize_grids(self, code: str, current_price: float) -> list[GridLevel]:
        """初始化网格"""
        grids = []

        if self.grid_type == "fixed":
            spacing = self.grid_spacing
        else:
            volatility = 0.02
            spacing = volatility * 2

        for i in range(1, self.grid_count + 1):
            buy_price = current_price * (1 - spacing * i)
            sell_price = current_price * (1 + spacing * i)

            grids.append(GridLevel(price=buy_price, shares=100, is_buy=True))
            grids.append(GridLevel(price=sell_price, shares=100, is_buy=False))

        self.grids[code] = grids
        return grids

    def check_grid_trigger(self, code: str, current_price: float, position: float) -> tuple[str, int, float]:
        """检查网格触发"""
        if code not in self.grids:
            self.initialize_grids(code, current_price)

        grids = self.grids[code]

        for grid in grids:
            if grid.is_filled:
                continue

            if grid.is_buy:
                if current_price <= grid.price and position < self.max_position:
                    grid.is_filled = True
                    return "buy", grid.shares, grid.price
            else:
                if current_price >= grid.price and position > 0:
                    grid.is_filled = True
                    return "sell", grid.shares, grid.price

        return "hold", 0, 0.0

    def reset_grids(self, code: str, new_price: float):
        """重置网格"""
        self.initialize_grids(code, new_price)


class PairTradingStrategy:
    """配对交易策略 - 协整配对、统计套利"""

    def __init__(
        self,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        lookback_days: int = 60,
        min_correlation: float = 0.7,
        max_pairs: int = 5,
    ):
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.lookback_days = lookback_days
        self.min_correlation = min_correlation
        self.max_pairs = max_pairs
        self.pairs: list[PairInfo] = []

    def calculate_correlation(self, df1: pd.DataFrame, df2: pd.DataFrame) -> float:
        """计算相关性"""
        merged = pd.merge(
            df1[["date", "close"]],
            df2[["date", "close"]],
            on="date",
            suffixes=("_1", "_2"),
        )

        if len(merged) < self.lookback_days:
            return 0.0

        returns1 = merged["close_1"].pct_change().dropna()
        returns2 = merged["close_2"].pct_change().dropna()

        if len(returns1) < 10:
            return 0.0

        correlation = returns1.corr(returns2)
        return correlation if not np.isnan(correlation) else 0.0

    def calculate_spread(self, price1: float, price2: float, hedge_ratio: float) -> float:
        """计算价差"""
        return price1 - hedge_ratio * price2

    def find_pairs(
        self,
        all_data: dict[str, pd.DataFrame],
        stock_names: dict[str, str] | None = None,
    ) -> list[PairInfo]:
        """寻找配对股票"""
        pairs = []
        codes = list(all_data.keys())

        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                code1, code2 = codes[i], codes[j]

                df1 = all_data[code1]
                df2 = all_data[code2]

                if len(df1) < self.lookback_days or len(df2) < self.lookback_days:
                    continue

                correlation = self.calculate_correlation(df1, df2)

                if correlation < self.min_correlation:
                    continue

                merged = pd.merge(
                    df1[["date", "close"]],
                    df2[["date", "close"]],
                    on="date",
                    suffixes=("_1", "_2"),
                )

                if len(merged) < self.lookback_days:
                    continue

                hedge_ratio = merged["close_1"].mean() / merged["close_2"].mean()
                spread = merged["close_1"] - hedge_ratio * merged["close_2"]
                spread_mean = spread.mean()
                spread_std = spread.std()

                if spread_std <= 0:
                    continue

                pairs.append(
                    PairInfo(
                        code1=code1,
                        code2=code2,
                        spread_mean=spread_mean,
                        spread_std=spread_std,
                        hedge_ratio=hedge_ratio,
                        correlation=correlation,
                    )
                )

        pairs.sort(key=lambda x: x.correlation, reverse=True)
        self.pairs = pairs[: self.max_pairs]
        return self.pairs

    def generate_signal(self, pair: PairInfo, price1: float, price2: float) -> tuple[str, float]:
        """生成交易信号"""
        spread = self.calculate_spread(price1, price2, pair.hedge_ratio)
        z_score = (spread - pair.spread_mean) / pair.spread_std

        if z_score > self.entry_threshold:
            return "short_spread", z_score
        elif z_score < -self.entry_threshold:
            return "long_spread", z_score
        elif abs(z_score) < self.exit_threshold:
            return "close", z_score

        return "hold", z_score


class EventDrivenStrategy:
    """事件驱动策略 - 财报事件、分红事件、技术事件"""

    def __init__(
        self,
        event_types: list[str] | None = None,
        holding_days: int = 10,
        max_stocks: int = 10,
        min_price: float = 2.0,
        exclude_st: bool = True,
    ):
        self.event_types = event_types or ["earnings", "dividend", "technical"]
        self.holding_days = holding_days
        self.max_stocks = max_stocks
        self.min_price = min_price
        self.exclude_st = exclude_st

    def is_excluded(self, name: str) -> bool:
        return is_excluded_stock(name, self.exclude_st)

    def detect_earnings_event(self, df: pd.DataFrame, idx: int) -> tuple[bool, float]:
        """检测财报事件 - 基于成交量异常"""
        if idx < 20:
            return False, 0.0

        current_volume = float(df.iloc[idx].get("volume", 0) or 0)
        avg_volume = df.iloc[idx - 20 : idx]["volume"].mean()

        if avg_volume <= 0:
            return False, 0.0

        volume_ratio = current_volume / avg_volume

        if volume_ratio > 2.0:
            price_change = float(df.iloc[idx].get("change_percent", 0) or 0)
            if abs(price_change) > 3.0:
                return True, volume_ratio * abs(price_change)

        return False, 0.0

    def detect_dividend_event(self, df: pd.DataFrame, idx: int) -> tuple[bool, float]:
        """检测分红事件 - 基于价格行为"""
        if idx < 5:
            return False, 0.0

        current_price = float(df.iloc[idx]["close"])
        prev_close = float(df.iloc[idx - 1]["close"])

        gap = (current_price - prev_close) / prev_close

        if -0.1 < gap < -0.01:
            current_volume = float(df.iloc[idx].get("volume", 0) or 0)
            avg_volume = df.iloc[idx - 5 : idx]["volume"].mean()

            if avg_volume > 0 and current_volume > avg_volume * 0.8:
                return True, abs(gap) * 100

        return False, 0.0

    def detect_technical_event(self, df: pd.DataFrame, idx: int) -> tuple[bool, float]:
        """检测技术事件 - 金叉、突破等"""
        if idx < 30:
            return False, 0.0

        row = df.iloc[idx]
        events = []
        total_strength = 0.0

        macd = float(row.get("macd", 0) or 0)
        macd_signal = float(row.get("macd_signal", 0) or 0)
        if macd > macd_signal and macd > 0:
            events.append("MACD金叉")
            total_strength += 1.0

        rsi = float(row.get("rsi", 50) or 50)
        if rsi < 30:
            events.append("RSI超卖")
            total_strength += 1.5
        elif rsi > 70:
            events.append("RSI超买")
            total_strength -= 1.0

        ma5 = float(row.get("ma5", 0) or 0)
        ma20 = float(row.get("ma20", 0) or 0)
        if ma5 > ma20 and ma5 > 0:
            events.append("MA金叉")
            total_strength += 0.5

        close_price = float(row.get("close", 0) or 0)
        boll_upper = float(row.get("boll_upper", 0) or 0)
        boll_lower = float(row.get("boll_lower", 0) or 0)

        if boll_upper > 0 and close_price > boll_upper:
            events.append("突破布林上轨")
            total_strength += 1.0
        elif boll_lower > 0 and close_price < boll_lower:
            events.append("触及布林下轨")
            total_strength += 1.5

        if total_strength > 1.5:
            return True, total_strength

        return False, 0.0

    def select_stocks(
        self,
        all_data: dict[str, pd.DataFrame],
        date_idx: int,
        date: str,
        stock_names: dict[str, str] | None = None,
    ) -> list[tuple[str, float, str]]:
        """选择事件驱动股票"""
        selected = []

        for code, df in all_data.items():
            if stock_names and self.is_excluded(stock_names.get(code, "")):
                continue

            date_rows = df[df["date"] == date]
            if date_rows.empty:
                continue

            try:
                stock_idx = date_rows.index[0]
                row = date_rows.iloc[0]
                close_price = float(row.get("close", 0) or 0)

                if close_price < self.min_price:
                    continue

                for event_type in self.event_types:
                    is_event = False
                    strength = 0.0

                    if event_type == "earnings":
                        is_event, strength = self.detect_earnings_event(df, stock_idx)
                    elif event_type == "dividend":
                        is_event, strength = self.detect_dividend_event(df, stock_idx)
                    elif event_type == "technical":
                        is_event, strength = self.detect_technical_event(df, stock_idx)

                    if is_event:
                        selected.append((code, strength, event_type))
                        break
            except Exception:
                continue

        selected.sort(key=lambda x: x[1], reverse=True)
        return selected[: self.max_stocks]


def run_breakout_backtest(
    db_path: Path,
    breakout_type: str = "price",
    holding_days: int = 5,
    initial_capital: float = 100000.0,
    min_price: float = 2.0,
    exclude_st: bool = True,
) -> dict[str, Any]:
    """运行突破策略回测"""
    from strategy.backtest import BacktestEngine

    strategy = BreakoutStrategy(
        breakout_type=breakout_type,
        holding_days=holding_days,
        min_price=min_price,
        exclude_st=exclude_st,
    )

    engine = BacktestEngine(db_path)
    engine.connect()
    try:
        result = engine.run_backtest(strategy, initial_capital)
        return result.to_dict()
    finally:
        engine.close()


def run_grid_backtest(
    db_path: Path,
    code: str,
    initial_capital: float = 100000.0,
    grid_count: int = 10,
) -> dict[str, Any]:
    """运行网格交易策略回测"""
    strategy = GridTradingStrategy(grid_count=grid_count)

    with sqlite3.connect(str(db_path)) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM stock_analysis WHERE code = ? ORDER BY date",
            conn,
            params=(code,),
        )

    if df.empty:
        return {"success": False, "error": "无数据"}

    capital = initial_capital
    position = 0
    trades = []

    for _, row in df.iterrows():
        current_price = float(row["close"])
        action, shares, price = strategy.check_grid_trigger(code, current_price, position / initial_capital)

        if action == "buy" and capital >= price * shares:
            capital -= price * shares
            position += shares
            trades.append({"action": "buy", "price": price, "shares": shares, "date": row["date"]})
        elif action == "sell" and position >= shares:
            capital += price * shares
            position -= shares
            trades.append({"action": "sell", "price": price, "shares": shares, "date": row["date"]})

    final_value = capital + position * df.iloc[-1]["close"]
    total_return = (final_value - initial_capital) / initial_capital

    return {
        "success": True,
        "code": code,
        "initial_capital": initial_capital,
        "final_value": final_value,
        "total_return": total_return,
        "total_trades": len(trades),
        "trades": trades,
    }


def run_pair_backtest(
    db_path: Path,
    initial_capital: float = 100000.0,
    lookback_days: int = 60,
) -> dict[str, Any]:
    """运行配对交易策略回测"""
    with sqlite3.connect(str(db_path)) as conn:
        codes = pd.read_sql_query("SELECT DISTINCT code FROM stock_analysis", conn)["code"].tolist()

        all_data = {}
        for code in codes[:50]:
            df = pd.read_sql_query(
                "SELECT date, close FROM stock_analysis WHERE code = ? ORDER BY date",
                conn,
                params=(code,),
            )
            if len(df) >= lookback_days:
                all_data[code] = df

    strategy = PairTradingStrategy(lookback_days=lookback_days)
    pairs = strategy.find_pairs(all_data)

    if not pairs:
        return {"success": False, "error": "未找到配对"}

    return {
        "success": True,
        "pairs_found": len(pairs),
        "pairs": [
            {
                "code1": p.code1,
                "code2": p.code2,
                "correlation": round(p.correlation, 3),
                "hedge_ratio": round(p.hedge_ratio, 3),
            }
            for p in pairs
        ],
    }


def run_event_backtest(
    db_path: Path,
    event_types: list[str] | None = None,
    holding_days: int = 10,
    initial_capital: float = 100000.0,
) -> dict[str, Any]:
    """运行事件驱动策略回测"""
    from strategy.backtest import BacktestEngine

    strategy = EventDrivenStrategy(
        event_types=event_types,
        holding_days=holding_days,
    )

    engine = BacktestEngine(db_path)
    engine.connect()
    try:
        result = engine.run_backtest(strategy, initial_capital)
        return result.to_dict()
    finally:
        engine.close()

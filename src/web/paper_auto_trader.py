"""策略驱动的模拟仓自动交易器 (Paper Auto Trader).

把「策略信号」自动转成模拟仓的建仓/平仓, 让「模拟仓」Tab 直接展示一个量化策略
的真实持仓表现。核心设计:

1. **信号**: 复用 ``strategy.backtest`` 里现成的策略 (动量/均值回归/趋势/多因子),
   以最新交易日 D 的数据选股。
2. **次日开盘成交**: D 日收盘后产生的信号, 记为待成交订单 (pending), 在下一次运行时
   用**下一交易日开盘价**成交 —— 避免「用当日收盘价成交」的前视 (look-ahead) 偏差。
3. **卖出规则**: 止损 / 止盈 / 持有到期, 同样以下一交易日开盘价成交。
4. **成本**: 佣金 (万三, 最低 5 元) + 印花税 (千一, 仅卖出), 与回测引擎口径一致。

运行方式 (每日收盘数据更新后调用一次)::

    from web.paper_auto_trader import PaperAutoTrader, AutoTraderConfig
    trader = PaperAutoTrader(db_path, store_path, AutoTraderConfig(...))
    trader.run()

存储复用 ``PaperPortfolio`` 的 ``data/paper_portfolio.json`` (positions/closed/cash/pending)。
"""

import logging
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy.backtest import BacktestEngine
from web.paper_trading import PaperPortfolio

logger = logging.getLogger(__name__)


@dataclass
class AutoTraderConfig:
    """自动交易配置"""

    strategy_type: str = "momentum"
    max_positions: int = 10
    position_pct: float = 0.10
    initial_capital: float = 100000.0
    stop_loss: float = 0.08
    take_profit: float = 0.20
    max_holding_days: int = 20
    lookback_days: int = 20
    min_momentum: float = 0.0
    max_momentum: float = 1.0
    max_volatility: float = 0.15
    min_price: float = 2.0
    exclude_st: bool = True
    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_commission: float = 5.0
    slippage_rate: float = 0.0

    @classmethod
    def from_file(cls, path: str | Path) -> "AutoTraderConfig":
        import json

        p = Path(path)
        if not p.exists():
            return cls()
        try:
            with p.open(encoding="utf-8") as f:
                data = json.load(f)
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        except Exception as e:  # pragma: no cover
            logger.warning("读取自动交易配置失败, 使用默认值: %s", e)
            return cls()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_STRATEGY_LABELS = {
    "momentum": "动量信号",
    "mean_reversion": "均值回归超卖",
    "trend_following": "趋势突破",
    "multi_factor": "多因子",
}


def _limit_pct(code: str) -> float:
    """按代码判断涨跌停幅度 (bj 30%, 科创板/创业板 20%, 主板 10%)"""
    c = str(code).lower()
    if c.startswith("bj"):
        return 0.30
    if c.startswith(("sz300", "sh688", "sz688", "300", "688")):
        return 0.20
    return 0.10


class PaperAutoTrader:
    """策略驱动的模拟仓自动交易器"""

    def __init__(
        self,
        db_path: str | Path,
        store_path: str | Path,
        config: AutoTraderConfig | None = None,
    ):
        self.db_path = Path(db_path)
        self.store_path = Path(store_path)
        self.config = config or AutoTraderConfig()

    # ---------- 对外入口 ----------
    def run(self, as_of_date: str | None = None, dry_run: bool = False) -> dict[str, Any]:
        """执行一轮自动交易: 先按 D 日开盘成交昨日订单, 再按 D 日信号生成新订单。

        Args:
            as_of_date: 指定信号日 D (YYYY-MM-DD); 默认取数据库最新交易日。
            dry_run: 只计算不落盘。

        Returns:
            {success, date, prev_date, executed:[...], new_orders:[...],
             positions, cash, note}
        """
        if not self.db_path.exists():
            return {"success": False, "error": f"数据库不存在: {self.db_path}"}

        engine = BacktestEngine(self.db_path)
        engine.connect()
        try:
            all_data = engine.get_all_stock_data()
            dates = engine.get_date_range(all_data)
            if not dates:
                return {"success": False, "error": "数据库无行情数据"}

            d = as_of_date or dates[-1]
            if d not in dates:
                # 取 <= d 的最近交易日
                prior = [x for x in dates if x <= d]
                if not prior:
                    return {"success": False, "error": f"无 <= {d} 的交易日"}
                d = prior[-1]

            pf = PaperPortfolio(self.db_path, self.store_path)
            if dry_run:
                pf.persist = False  # 内存态, 不落盘
            if pf.data.get("cash") is None:
                pf.set_initial_capital(self.config.initial_capital)

            executed = self._execute_pending(pf, all_data, d)
            carried = pf.get_pending()
            new_orders = self._generate_orders(pf, engine, all_data, dates, d, carried)
            pending = carried + new_orders

            if not dry_run:
                pf.save_pending(pending)

            diag = pf.get_diagnosis()
            return {
                "success": True,
                "date": d,
                "dry_run": dry_run,
                "strategy": self.config.strategy_type,
                "strategy_label": _STRATEGY_LABELS.get(
                    self.config.strategy_type, self.config.strategy_type
                ),
                "executed": executed,
                "new_orders": new_orders,
                "positions": len(pf.data["positions"]),
                "cash": round(pf.get_cash(), 2),
                "summary": diag["summary"],
            }
        finally:
            engine.close()

    def current_state(self) -> dict[str, Any]:
        """只读查看当前模拟仓状态(含待成交订单)"""
        pf = PaperPortfolio(self.db_path, self.store_path)
        if pf.data.get("cash") is None:
            pf.get_cash()
        return pf.get_diagnosis()

    def reset(self, initial_capital: float | None = None) -> dict[str, Any]:
        pf = PaperPortfolio(self.db_path, self.store_path)
        pf.reset(initial_capital if initial_capital is not None else self.config.initial_capital)
        return {"success": True, "message": f"模拟仓已重置, 初始资金 {pf.get_cash():.2f}"}

    # ---------- 成交 ----------
    def _execute_pending(
        self, pf, all_data: dict, exec_date: str
    ) -> list[dict[str, Any]]:
        """把 signal_date < exec_date 的待成交订单, 以 exec_date 开盘价成交。"""
        pending = pf.get_pending()
        if not pending:
            return []

        cfg = self.config
        executed: list[dict[str, Any]] = []
        carried: list[dict[str, Any]] = []

        for order in pending:
            signal_date = order.get("signal_date", "")
            if signal_date >= exec_date:
                carried.append(order)
                continue

            code = order["code"]
            side = order["side"]
            bar = self._get_bar(code, exec_date)
            if bar is None or bar.get("stale"):
                # 当日无行情(停牌) —— 继续挂着, 下次再试
                carried.append(order)
                continue

            open_px = bar["open"]
            prev_close = bar["prev_close"]
            if open_px <= 0 or np.isnan(open_px):
                carried.append(order)
                continue

            limit = _limit_pct(code)
            chg = (open_px - prev_close) / prev_close if prev_close > 0 else 0.0

            if side == "buy":
                if cfg.exclude_st and chg >= limit - 1e-4:
                    # 开盘涨停买不进 —— 作废(不追高)
                    executed.append({"code": code, "side": "buy", "status": "canceled", "reason": "开盘涨停"})
                    continue
                result = self._do_buy(pf, code, open_px, order, exec_date)
            else:  # sell
                if chg <= -limit + 1e-4:
                    # 开盘跌停卖不掉 —— 继续挂, 下次再试
                    carried.append(order)
                    continue
                result = self._do_sell(pf, code, open_px, order, exec_date)

            executed.append({"code": code, "side": side, **result})

        pf.save_pending(carried)
        return executed

    def _do_buy(self, pf, code: str, open_px: float, order: dict, exec_date: str) -> dict[str, Any]:
        cfg = self.config
        exec_price = open_px * (1 + cfg.slippage_rate)
        target_value = float(order.get("position_value") or 0.0)
        if target_value <= 0:
            target_value = pf.get_cash()
        shares = int(target_value / exec_price / 100) * 100  # A 股 100 股整手
        if shares <= 0:
            return {"status": "skipped", "reason": "资金不足一手"}
        # 现金约束
        max_affordable = int(pf.get_cash() / (exec_price * 100)) * 100
        shares = min(shares, max_affordable)
        if shares <= 0:
            return {"status": "skipped", "reason": "现金不足"}

        res = pf.add_position(
            code,
            exec_price,
            shares,
            buy_date=exec_date,
            stop_loss=cfg.stop_loss,
            take_profit=cfg.take_profit,
            commission_rate=cfg.commission_rate,
            min_commission=cfg.min_commission,
            deduct_cash=True,
            reason=order.get("reason", ""),
        )
        return {"status": "filled" if res.get("success") else "failed", "message": res.get("message", "")}

    def _do_sell(self, pf, code: str, open_px: float, order: dict, exec_date: str) -> dict[str, Any]:
        cfg = self.config
        if code not in pf.data["positions"]:
            return {"status": "canceled", "reason": "已无持仓"}
        exec_price = open_px * (1 - cfg.slippage_rate)
        res = pf.close_position(
            code,
            exec_price,
            sell_date=exec_date,
            commission_rate=cfg.commission_rate,
            stamp_tax_rate=cfg.stamp_tax_rate,
            min_commission=cfg.min_commission,
            reason=order.get("reason", ""),
        )
        return {"status": "filled" if res.get("success") else "failed", "message": res.get("message", "")}

    # ---------- 信号 ----------
    def _generate_orders(
        self, pf, engine, all_data: dict, dates: list[str], d: str, carried: list[dict]
    ) -> list[dict[str, Any]]:
        cfg = self.config
        positions = pf.data["positions"]
        orders: list[dict[str, Any]] = []

        # 1) 卖出信号: 止损 / 止盈 / 持有到期
        for code, pos in list(positions.items()):
            bar = self._get_bar(code, d)
            if bar is None:
                continue
            cur = bar["close"]
            if not cur or np.isnan(cur):
                continue
            buy_price = pos["buy_price"]
            pnl = (cur - buy_price) / buy_price if buy_price > 0 else 0.0
            holding = self._holding_days(dates, pos.get("buy_date", ""), d)
            reason = ""
            if pnl <= -pos.get("stop_loss", cfg.stop_loss):
                reason = f"止损({pnl:.1%})"
            elif pnl >= pos.get("take_profit", cfg.take_profit):
                reason = f"止盈({pnl:.1%})"
            elif holding >= cfg.max_holding_days:
                reason = f"持有到期({holding}日)"
            if reason and not self._has_order(carried, "sell", code):
                orders.append({"side": "sell", "code": code, "signal_date": d, "reason": reason})

        # 2) 买入信号: 策略选股
        held = set(positions)
        pending_sell = {o["code"] for o in carried if o["side"] == "sell"} | {
            o["code"] for o in orders if o["side"] == "sell"
        }
        pending_buy = {o["code"] for o in carried if o["side"] == "buy"}
        free_slots = cfg.max_positions - len(held) + len(pending_sell)
        if free_slots > 0:
            strategy = self._build_strategy()
            names = engine.get_stock_names()
            try:
                selected = strategy.select_stocks(
                    all_data, 0, d, stock_names=names, lookup=engine._row_pos
                )
            except Exception as e:
                logger.warning("策略选股失败: %s", e)
                selected = []

            total_asset = self._portfolio_value(pf, all_data, d)
            position_value = total_asset * cfg.position_pct
            label = _STRATEGY_LABELS.get(cfg.strategy_type, cfg.strategy_type)
            for code, score in selected:
                if free_slots <= 0:
                    break
                if code in held or code in pending_sell or code in pending_buy:
                    continue
                if self._has_order(orders, "buy", code):
                    continue
                orders.append(
                    {
                        "side": "buy",
                        "code": code,
                        "signal_date": d,
                        "position_value": round(position_value, 2),
                        "reason": f"{label}({score:.3f})",
                    }
                )
                free_slots -= 1

        return orders

    def _build_strategy(self):
        from strategy.backtest import (
            MeanReversionStrategy,
            MomentumStrategy,
            MultiFactorStrategy,
            TrendFollowingStrategy,
        )

        cfg = self.config
        if cfg.strategy_type == "mean_reversion":
            return MeanReversionStrategy(
                holding_days=cfg.max_holding_days,
                max_stocks=cfg.max_positions,
                min_price=cfg.min_price,
                exclude_st=cfg.exclude_st,
                stop_loss=cfg.stop_loss,
                take_profit=cfg.take_profit,
            )
        if cfg.strategy_type == "trend_following":
            return TrendFollowingStrategy(
                holding_days=cfg.max_holding_days,
                min_price=cfg.min_price,
                exclude_st=cfg.exclude_st,
                stop_loss=cfg.stop_loss,
                take_profit=cfg.take_profit,
            )
        if cfg.strategy_type == "multi_factor":
            return MultiFactorStrategy(
                holding_days=cfg.max_holding_days,
                max_stocks=cfg.max_positions,
                min_price=cfg.min_price,
                exclude_st=cfg.exclude_st,
                stop_loss=cfg.stop_loss,
                take_profit=cfg.take_profit,
            )
        return MomentumStrategy(
            lookback_days=cfg.lookback_days,
            top_n=cfg.max_positions,
            holding_days=cfg.max_holding_days,
            min_momentum=cfg.min_momentum,
            max_momentum=cfg.max_momentum,
            max_volatility=cfg.max_volatility,
            min_price=cfg.min_price,
            exclude_st=cfg.exclude_st,
            stop_loss=cfg.stop_loss,
            take_profit=cfg.take_profit,
        )

    # ---------- 工具 ----------
    @staticmethod
    def _has_order(orders: list[dict], side: str, code: str) -> bool:
        return any(o.get("side") == side and o.get("code") == code for o in orders)

    @staticmethod
    def _holding_days(dates: list[str], buy_date: str, cur_date: str) -> int:
        if not buy_date:
            return 0
        try:
            start = dates.index(buy_date)
            end = dates.index(cur_date)
            return max(0, end - start)
        except ValueError:
            return 0

    def _portfolio_value(self, pf, all_data: dict, d: str) -> float:
        total = pf.get_cash()
        for code, pos in pf.data["positions"].items():
            bar = self._get_bar(code, d)
            px = bar["close"] if bar and bar.get("close") else pos.get("buy_price", 0.0)
            total += px * pos.get("shares", 0)
        return total

    def _get_bar(self, code: str, d: str) -> dict[str, Any] | None:
        """取 code 在 <= d 的最近一行 (date/open/close/volume) 及前一日收盘。"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT date, open, close, volume
                    FROM stock_analysis WHERE code = ? AND date <= ?
                    ORDER BY date DESC LIMIT 2
                    """,
                    (code, d),
                ).fetchall()
            if not rows:
                return None
            cur = dict(rows[0])
            prev_close = float(rows[1]["close"]) if len(rows) > 1 and rows[1]["close"] else cur["close"]
            # 只有当最近一行正好是 d 时才算"当日有行情"
            if str(cur["date"])[:10] != str(d)[:10]:
                return {
                    "date": str(cur["date"])[:10],
                    "open": float(cur["open"]) if cur["open"] is not None else 0.0,
                    "close": float(cur["close"]) if cur["close"] is not None else 0.0,
                    "prev_close": prev_close,
                    "stale": True,
                }
            return {
                "date": str(cur["date"])[:10],
                "open": float(cur["open"]) if cur["open"] is not None else 0.0,
                "close": float(cur["close"]) if cur["close"] is not None else 0.0,
                "prev_close": prev_close,
                "stale": False,
            }
        except Exception as e:  # pragma: no cover
            logger.warning("读取 %s@%s 行情失败: %s", code, d, e)
            return None


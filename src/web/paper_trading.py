"""
Paper Trading for Stock Analyzer.
模拟仓交易 - 记录模拟买入/卖出, 结合实时行情给出持仓诊断

记录用户的模拟建仓(买入价+股数), 依据 stock_analysis 最新行情与技术指标,
对每只持仓生成「持有/关注/减仓/止盈/止损」诊断, 并对投资组合做整体体检。
支持卖出成交并沉淀卖出历史。

存储: data/paper_portfolio.json (本地 JSON, 无需迁移数据库)
"""

import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PaperPortfolio:
    """模拟仓存储 + 持仓诊断"""

    def __init__(self, db_path: str | Path, store_path: str | Path):
        self.db_path = Path(db_path)
        self.store_path = Path(store_path)
        self.data = self._load()

    # ---------- 持久化 ----------
    def _load(self) -> dict[str, Any]:
        default = {
            "updated_at": "",
            "positions": {},   # code -> dict
            "closed": [],      # 卖出历史
        }
        if self.store_path.exists():
            try:
                with self.store_path.open(encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("positions", {})
                    data.setdefault("closed", [])
                    return data
            except Exception as e:
                logger.warning(f"模拟仓文件损坏, 重新初始化: {e}")
        return default

    def _save(self):
        self.data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store_path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.store_path)

    # ---------- 股票信息 ----------
    def _name(self, code: str) -> str:
        try:
            from ..data.stock_info import get_stock_info_fetcher
        except Exception:
            try:
                from src.data.stock_info import get_stock_info_fetcher
            except Exception as base:
                logger.warning(f"导入 StockInfoFetcher 失败: {base}")
                return code
        try:
            fetcher = get_stock_info_fetcher()
            name = fetcher.get_cached_name(code)          # 先按原样
            if not name:
                name = fetcher.get_cached_name(self._full_code(code))  # 再按 sh/sz 前缀
            if name:
                return name
        except Exception as e:
            logger.warning(f"读取 [{code}] 名称失败: {e}")
        return code

    @staticmethod
    def _full_code(code: str) -> str:
        """将 6 位代码补成带市场前缀的完整代码 (600xxx/000xxx->sh, 002/300/301->sz)"""
        c = code.strip().lower()
        if c.startswith(("sh", "sz")):
            return c
        if len(c) == 6 and c.isdigit():
            return ("sh" if c[0] in "5689" else "sz") + c
        return c

    # ---------- 建仓 / 卖出 ----------
    def add_position(
        self,
        code: str,
        buy_price: float,
        shares: float,
        buy_date: str | None = None,
        stop_loss: float = 0.08,
        take_profit: float = 0.20,
    ) -> dict[str, Any]:
        if not code or buy_price <= 0 or shares <= 0:
            return {"success": False, "message": "股票代码、买入价、股数必须大于0"}
        if code in self.data["positions"]:
            return {"success": False, "message": f"已持有 {self._name(code)}({code}), 请先卖出或改选其他股票"}
        if stop_loss <= 0 or take_profit <= 0:
            return {"success": False, "message": "止损/止盈比例必须大于0"}

        self.data["positions"][code] = {
            "name": self._name(code),
            "buy_date": buy_date or date.today().isoformat(),
            "buy_price": float(buy_price),
            "shares": float(shares),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
        }
        self._save()
        return {"success": True, "message": f"已建仓 {self._name(code)}({code}) {shares:g} 股 @ {buy_price:g}"}

    def close_position(
        self,
        code: str,
        sell_price: float,
        sell_date: str | None = None,
        shares: float | None = None,
    ) -> dict[str, Any]:
        pos = self.data["positions"].get(code)
        if not pos:
            return {"success": False, "message": f"未持有 {self._name(code)}({code})"}
        if sell_price <= 0:
            return {"success": False, "message": "卖出价必须大于0"}

        held = pos["shares"]
        sell_shares = held if shares is None else min(shares, held)

        buy_price = pos["buy_price"]
        profit_pct = (sell_price - buy_price) / buy_price
        self.data["closed"].append({
            "code": code,
            "name": pos["name"],
            "sell_date": sell_date or date.today().isoformat(),
            "buy_date": pos.get("buy_date", ""),
            "buy_price": buy_price,
            "sell_price": float(sell_price),
            "shares": sell_shares,
            "profit": (float(sell_price) - buy_price) * sell_shares,
            "profit_pct": profit_pct,
        })

        remaining = held - sell_shares
        if remaining <= 1e-9:
            del self.data["positions"][code]
        else:
            pos["shares"] = remaining

        self._save()
        return {"success": True, "message": f"已卖出 {pos['name']}({code}) {sell_shares:g} 股 @ {sell_price:g}"}

    # ---------- 单只持仓诊断 ----------
    def _holding_diagnosis(self, code: str, pos: dict[str, Any]) -> dict[str, Any]:
        cur, prev = self._latest_rows(code)
        buy_price = pos["buy_price"]
        shares = pos["shares"]

        base = {
            "code": code,
            "name": pos["name"],
            "buy_date": pos.get("buy_date", ""),
            "buy_price": buy_price,
            "shares": shares,
            "cost": buy_price * shares,
            "stop_loss": pos.get("stop_loss", 0.08),
            "take_profit": pos.get("take_profit", 0.20),
        }

        if cur is None:
            return {**base, "current_price": None, "pnl": 0, "pnl_pct": 0,
                    "action": "无数据", "level": "muted", "advice": "该股票无最新行情(可能停牌/退市)", "reasons": []}

        cur_price = cur["close"]
        value = cur_price * shares
        pnl = value - base["cost"]
        pnl_pct = (cur_price - buy_price) / buy_price

        reasons = []
        neg_signals = []   # 偏空信号
        crit_signals = []  # 明显转弱信号

        def f(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        cur_close = f(cur.get("close"))
        cur_ma20 = f(cur.get("ma20"))
        cur_ma10 = f(cur.get("ma10"))
        prev_close = f(prev.get("close")) if prev else None
        prev_ma20 = f(prev.get("ma20")) if prev else None
        prev_ma10 = f(prev.get("ma10")) if prev else None
        cur_macd_hist = f(cur.get("macd_hist"))
        prev_macd_hist = f(prev.get("macd_hist")) if prev else None
        cur_rsi = f(cur.get("rsi"))
        prev_rsi = f(prev.get("rsi")) if prev else None

        if None not in (cur_close, cur_ma20, prev_close, prev_ma20) and prev_close >= prev_ma20 and cur_close < cur_ma20:
            crit_signals.append("跌破MA20")
        elif cur_close is not None and cur_ma20 is not None and cur_close < cur_ma20:
            neg_signals.append("位于MA20下方")
        if None not in (cur_close, cur_ma10, prev_close, prev_ma10) and prev_close >= prev_ma10 and cur_close < cur_ma10:
            crit_signals.append("跌破MA10")
        if None not in (cur_macd_hist, prev_macd_hist) and prev_macd_hist > 0 and cur_macd_hist < 0:
            crit_signals.append("MACD死叉")
        if cur_rsi is not None:
            if prev_rsi is not None and prev_rsi > 70 and cur_rsi <= 70:
                neg_signals.append("RSI高位回落")
            if cur_rsi > 70:
                neg_signals.append("RSI超买")
        change_pct = f(cur.get("change_percent"))
        if change_pct is not None and abs(change_pct) >= 9.5:
            neg_signals.append("当日价格异动")

        reasons = (neg_signals + crit_signals)

        stop_loss = pos.get("stop_loss", 0.08)
        take_profit = pos.get("take_profit", 0.20)
        if pnl_pct <= -stop_loss:
            action, level, advice = "止损", "danger", f"已亏 {pnl_pct:.1%}, 跌破止损线 -{stop_loss:.0%}, 建议止跌离场"
        elif pnl_pct >= take_profit:
            action, level, advice = "止盈", "success", f"已盈利 {pnl_pct:.1%}, 达到目标 {take_profit:.0%}, 可分步止盈锁定"
        elif crit_signals:
            action, level, advice = "减仓/离场", "danger", f"{'、'.join(crit_signals)}, 趋势转弱, 建议减仓或离场"
        elif neg_signals:
            action, level, advice = "关注/减仓", "warning", f"{'、'.join(neg_signals)}, 短期转弱, 建议适当减仓或设好止损"
        else:
            action, level, advice = "持有", "info", "技术信号与趋势正常, 可按计划继续持有"

        return {
            **base,
            "current_price": round(cur_price, 2),
            "change_percent": round(change_pct, 2) if change_pct is not None else 0,
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct * 100, 2),
            "action": action,
            "level": level,
            "advice": advice,
            "reasons": reasons,
        }

    def _latest_rows(self, code: str) -> tuple[dict | None, dict | None]:
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT close, ma10, ma20, macd_hist, rsi, change_percent
                    FROM stock_analysis WHERE code = ?
                    ORDER BY date DESC LIMIT 2
                    """,
                    (code,),
                ).fetchall()
            if not rows:
                return None, None
            cur = dict(rows[0])
            prev = dict(rows[1]) if len(rows) > 1 else None
            return cur, prev
        except Exception as e:
            logger.warning(f"查询 {code} 行情失败: {e}")
            return None, None

    # ---------- 大盘环境 (贪便宜读缓存, 有则用) ----------
    def _market_backdrop(self) -> dict[str, str]:
        try:
            cache_dir = self.store_path.parent / "cache"
            files = sorted(cache_dir.glob("market_timing_*.json"))
            if not files:
                return {"state": "", "advice": ""}
            with files[-1].open(encoding="utf-8") as f:
                d = json.load(f)
            return {"state": d.get("state", ""), "advice": d.get("position_advice", "")}
        except Exception:
            return {"state": "", "advice": ""}

    # ---------- 组合体检 ----------
    def get_diagnosis(self) -> dict[str, Any]:
        positions = []
        total_cost = 0.0
        total_value = 0.0
        danger_count = 0
        for code, pos in self.data["positions"].items():
            d = self._holding_diagnosis(code, pos)
            positions.append(d)
            total_cost += d["cost"]
            if d.get("value"):
                total_value += d["value"]
            if d["level"] == "danger":
                danger_count += 1

        weights = {d["code"]: (d.get("value") or 0) / total_value if total_value else 0 for d in positions}
        max_weight = max(weights.values()) if weights else 0
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

        # 卖出历史倒序
        closed = sorted(self.data["closed"], key=lambda x: x.get("sell_date", ""), reverse=True)[-100:]

        return {
            "success": True,
            "updated_at": self.data.get("updated_at", ""),
            "market": self._market_backdrop(),
            "summary": {
                "position_count": len(positions),
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "max_weight": round(max_weight * 100, 2),
                "danger_count": danger_count,
            },
            "positions": positions,
            "closed": closed,
        }


# 默认实例 (由 api.py 用真实 db 路径初始化)
paper_portfolio: PaperPortfolio | None = None


def get_paper(db_path: str | Path) -> PaperPortfolio:
    global paper_portfolio
    if paper_portfolio is None:
        from config import PROJECT_ROOT

        store_path = Path(PROJECT_ROOT) / "data" / "paper_portfolio.json"
        paper_portfolio = PaperPortfolio(db_path, store_path)
    return paper_portfolio

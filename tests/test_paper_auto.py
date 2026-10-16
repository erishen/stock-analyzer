"""
Tests for Paper Portfolio & Paper Auto Trader.
模拟仓记账 + 策略驱动自动交易测试
"""

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.test_web import _STOCK_ANALYSIS_SCHEMA
from web.paper_auto_trader import AutoTraderConfig, PaperAutoTrader, _limit_pct
from web.paper_trading import PaperPortfolio


def _make_db(path: Path, n_days: int = 60, codes=("sh600000", "sz000001", "sz000002")) -> list[str]:
    """造一个 uptrend 的小库, 返回交易日列表。"""
    conn = sqlite3.connect(str(path))
    conn.executescript(_STOCK_ANALYSIS_SCHEMA)
    start = date(2026, 1, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(n_days)]
    rows = []
    for ci, code in enumerate(codes):
        prev = 10.0 + ci
        for i, d in enumerate(dates):
            close = 10.0 + ci + 0.1 * i
            rows.append((code, d, prev, close, close + 1, close - 1, 1_000_000.0, close, close))
            prev = close
    conn.executemany(
        "INSERT INTO stock_analysis (code, date, open, close, high, low, volume, ma20, rsi) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return dates


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "stock_analysis.db"
    store = tmp_path / "paper_portfolio.json"
    dates = _make_db(db)
    return db, store, dates


class TestLimitPct:
    @pytest.mark.parametrize(
        "code,expected",
        [("bj430047", 0.30), ("sz300750", 0.20), ("sh688981", 0.20), ("sh600000", 0.10), ("sz000002", 0.10)],
    )
    def test_limit_pct(self, code, expected):
        assert _limit_pct(code) == expected


class TestPaperCostAccounting:
    def test_buy_then_sell_applies_costs(self, tmp_path):
        pf = PaperPortfolio(tmp_path / "x.db", tmp_path / "p.json")
        pf.set_initial_capital(100000.0)

        r = pf.add_position("sh600000", 10.0, 1000, deduct_cash=True)
        assert r["success"]
        # 佣金 = 10000*0.0003 = 3 -> 取最低 5 元
        pos = pf.data["positions"]["sh600000"]
        assert pos["buy_cost"] == 5.0
        assert pf.get_cash() == pytest.approx(100000.0 - 10000.0 - 5.0)

        r2 = pf.close_position("sh600000", 11.0)
        assert r2["success"]
        rec = pf.data["closed"][-1]
        # 卖出: 佣金 max(11000*0.0003,5)=5, 印花税 11000*0.001=11
        assert rec["sell_cost"] == pytest.approx(16.0)
        assert rec["total_cost"] == pytest.approx(21.0)
        assert rec["profit"] == pytest.approx(1000.0 - 21.0)
        assert pf.get_cash() == pytest.approx(100000.0 - 10005.0 + 11000.0 - 16.0)

    def test_add_position_rejects_when_cash_insufficient(self, tmp_path):
        pf = PaperPortfolio(tmp_path / "x.db", tmp_path / "p.json")
        pf.set_initial_capital(1000.0)
        r = pf.add_position("sh600000", 10.0, 1000, deduct_cash=True)
        assert not r["success"]
        assert "现金不足" in r["message"]


class TestPaperAutoTrader:
    def test_generate_then_execute_at_next_open(self, env):
        db, store, dates = env
        cfg = AutoTraderConfig(max_positions=2, position_pct=0.5, min_price=2.0)
        trader = PaperAutoTrader(db, store, cfg)

        r1 = trader.run(as_of_date=dates[-3])
        assert r1["success"]
        assert len(r1["new_orders"]) == 2
        assert all(o["side"] == "buy" for o in r1["new_orders"])
        assert r1["positions"] == 0

        r2 = trader.run(as_of_date=dates[-2])
        filled = [e for e in r2["executed"] if e["status"] == "filled"]
        assert len(filled) == 2
        assert r2["positions"] == 2

        pf = PaperPortfolio(db, store)
        assert pf.get_cash() < cfg.initial_capital
        for p in pf.data["positions"].values():
            assert p["buy_cost"] >= 5.0  # 最低佣金
            assert p["shares"] % 100 == 0  # 整手

    def test_stop_loss_generates_sell_order(self, env):
        db, store, dates = env
        cfg = AutoTraderConfig(max_positions=2, position_pct=0.5)
        trader = PaperAutoTrader(db, store, cfg)

        pf = PaperPortfolio(db, store)
        pf.set_initial_capital(cfg.initial_capital)
        pf.data["positions"]["sh600000"] = {
            "name": "T", "buy_date": dates[-5], "buy_price": 999.0, "shares": 100,
            "stop_loss": 0.08, "take_profit": 0.20, "buy_cost": 30.0, "reason": "",
        }
        pf._save()

        r = trader.run(as_of_date=dates[-2])
        sells = [o for o in r["new_orders"] if o["side"] == "sell"]
        assert any(o["code"] == "sh600000" for o in sells)

        r2 = trader.run(as_of_date=dates[-1])
        assert any(e["side"] == "sell" and e["status"] == "filled" for e in r2["executed"])
        assert "sh600000" not in PaperPortfolio(db, store).data["positions"]

    def test_max_positions_respected(self, env):
        db, store, dates = env
        cfg = AutoTraderConfig(max_positions=1, position_pct=0.5)
        trader = PaperAutoTrader(db, store, cfg)
        r1 = trader.run(as_of_date=dates[-3])
        assert len(r1["new_orders"]) == 1

    def test_missing_db_returns_error(self, tmp_path):
        trader = PaperAutoTrader(tmp_path / "nope.db", tmp_path / "p.json")
        r = trader.run()
        assert not r["success"]

    def test_suspended_stock_order_not_filled(self, env):
        db, store, dates = env
        # 一只只在最早一天有行情的股票: 在 exec_date 无当日报价(相当于停牌)
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO stock_analysis (code, date, open, close, high, low, volume, ma20, rsi) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("sh600099", dates[0], 10.0, 10.0, 11.0, 9.0, 1_000_000.0, 10.0, 50.0),
        )
        conn.commit()
        conn.close()

        pf = PaperPortfolio(db, store)
        pf.set_initial_capital(100000.0)
        pf.save_pending(
            [{"side": "buy", "code": "sh600099", "signal_date": dates[0], "position_value": 10000.0, "reason": "t"}]
        )

        trader = PaperAutoTrader(db, store, AutoTraderConfig())
        trader.run(as_of_date=dates[-1])

        # 无当日报价 -> 继续挂在待成交, 未建仓
        reloaded = PaperPortfolio(db, store)
        assert any(o["code"] == "sh600099" for o in reloaded.get_pending())
        assert "sh600099" not in reloaded.data["positions"]


class TestPaperAutoEndpoint:
    def test_auto_dry_run_no_write(self, env, tmp_path):
        from starlette.testclient import TestClient

        import web.api as api_mod

        db, _store, dates = env
        with patch.object(api_mod, "db_path", db), patch.object(api_mod, "DATA_DIR", tmp_path):
            client = TestClient(api_mod.app)
            resp = client.post(
                "/api/paper/auto",
                json={
                    "strategy": "momentum",
                    "max_positions": 2,
                    "position_pct": 0.5,
                    "initial_capital": 100000.0,
                    "date": dates[-3],
                    "dry_run": True,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True, body.get("error")
        assert body["dry_run"] is True
        assert len(body["new_orders"]) == 2
        # dry-run 不落盘
        assert not (tmp_path / "paper_portfolio.json").exists()

"""
Tests for Paper Portfolio & Paper Auto Trader.
模拟仓记账 + 策略驱动自动交易测试
"""

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestPaperClearAll:
    def test_close_all_sells_positions_and_cancels_pending(self, env):
        db, store, dates = env
        pf = PaperPortfolio(db, store)
        pf.set_initial_capital(100000.0)
        pf.add_position("sh600000", 10.0, 100, deduct_cash=True)
        pf.add_position("sz000001", 11.0, 100, deduct_cash=True)
        pf.save_pending([{"side": "buy", "code": "sz000002", "signal_date": dates[-1], "reason": "t"}])

        r = pf.close_all(sell_date=dates[-1])
        assert r["success"]
        assert r["closed_count"] == 2
        assert r["total_proceeds"] > 0
        assert pf.data["positions"] == {}
        assert pf.data["pending"] == []
        # 两只都进了卖出历史
        assert {c["code"] for c in pf.data["closed"]} == {"sh600000", "sz000001"}

    def test_close_all_skips_position_without_quote(self, env):
        db, store, dates = env
        pf = PaperPortfolio(db, store)
        pf.set_initial_capital(100000.0)
        # 手工塞一只数据库里没有行情的持仓
        pf.data["positions"]["sh600099"] = {
            "name": "NODATA", "buy_date": dates[0], "buy_price": 10.0, "shares": 100,
            "stop_loss": 0.08, "take_profit": 0.20, "buy_cost": 5.0, "reason": "",
        }
        pf._save()

        r = pf.close_all()
        assert r["success"]
        assert r["closed_count"] == 0
        assert any(s["code"] == "sh600099" for s in r["skipped"])
        # 无行情的持仓仍保留
        assert "sh600099" in pf.data["positions"]

    def test_close_all_empty_portfolio(self, env):
        db, store, _dates = env
        pf = PaperPortfolio(db, store)
        r = pf.close_all()
        assert r["success"]
        assert r["closed_count"] == 0
        assert "无持仓" in r["message"]


class TestPaperReload:
    """宿主端(定时任务)写入存储文件后, 常驻 Web 进程靠 mtime 热重载, 无需重启容器。"""

    def test_reload_if_changed_detects_external_write(self, env):
        import json
        import os

        db, store, _dates = env
        pf = PaperPortfolio(db, store)
        pf.reset(100000)
        assert pf.reload_if_changed() is False  # 无变更不重载

        data = json.loads(store.read_text(encoding="utf-8"))
        data["cash"] = 4321.0
        store.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        st = store.stat()
        os.utime(store, (st.st_atime, st.st_mtime + 2))  # 确保 mtime 前进

        assert pf.reload_if_changed() is True
        assert pf.get_cash() == pytest.approx(4321.0)
        assert pf.reload_if_changed() is False  # 重载后稳定, 不重复加载

    def test_get_paper_invokes_reload_on_cached_instance(self):
        import web.paper_trading as pt

        fake = MagicMock()
        with patch.object(pt, "paper_portfolio", fake):
            returned = pt.get_paper("dummy.db")
        assert returned is fake
        fake.reload_if_changed.assert_called_once()


class TestPendingOrderNames:
    def test_pending_order_name_enriched_from_code(self, env):
        db, store, dates = env
        pf = PaperPortfolio(db, store)
        pf.save_pending([{"side": "buy", "code": "sh600241", "signal_date": dates[-1], "reason": "t"}])
        with patch.object(PaperPortfolio, "_name", return_value="时代万恒"):
            diag = pf.get_diagnosis()
        assert diag["pending"][0]["name"] == "时代万恒"

    def test_pending_order_name_kept_when_present(self, env):
        db, store, dates = env
        pf = PaperPortfolio(db, store)
        pf.save_pending(
            [{"side": "sell", "code": "sh600000", "signal_date": dates[-1], "reason": "t", "name": "浦发银行"}]
        )
        diag = pf.get_diagnosis()
        assert diag["pending"][0]["name"] == "浦发银行"


class TestPaperAutoTrader:
    def test_generate_then_execute_at_next_open(self, env):
        db, store, dates = env
        cfg = AutoTraderConfig(max_positions=2, position_pct=0.5, min_price=2.0)
        trader = PaperAutoTrader(db, store, cfg)

        r1 = trader.run(as_of_date=dates[-3])
        assert r1["success"]
        assert r1["strategy"] == "momentum"
        assert r1["strategy_label"] == "动量信号"
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

    def test_clear_all_endpoint(self, env, tmp_path):
        from starlette.testclient import TestClient

        import web.api as api_mod

        db, store, dates = env
        # 预置一只持仓
        pf0 = PaperPortfolio(db, store)
        pf0.set_initial_capital(100000.0)
        pf0.add_position("sh600000", 10.0, 100, deduct_cash=True)

        with patch.object(api_mod, "db_path", db), patch.object(api_mod, "DATA_DIR", tmp_path):
            # 让 get_paper 用临时 store
            with patch.object(api_mod, "get_paper", lambda _db: PaperPortfolio(db, store)):
                client = TestClient(api_mod.app)
                resp = client.post("/api/paper/clear", json={"sell_date": dates[-1]})

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True, body.get("error")
        assert body["closed_count"] == 1
        assert PaperPortfolio(db, store).data["positions"] == {}

    def test_clear_all_notifies_dingtalk(self, env, tmp_path):
        from starlette.testclient import TestClient

        import web.api as api_mod

        db, store, dates = env
        pf0 = PaperPortfolio(db, store)
        pf0.set_initial_capital(100000.0)
        pf0.add_position("sh600000", 10.0, 100, deduct_cash=True)

        class _FakeNotify:
            def __init__(self):
                self.sent = []

            def configured(self):
                return True

            def send_markdown(self, text, title="模拟仓"):
                self.sent.append((title, text))
                return True, "ok"

        fake = _FakeNotify()
        with patch.object(api_mod, "db_path", db), patch.object(api_mod, "DATA_DIR", tmp_path):
            with patch.object(api_mod, "get_paper", lambda _db: PaperPortfolio(db, store)):
                with patch.object(api_mod, "notify_hook", fake):
                    client = TestClient(api_mod.app)
                    resp = client.post("/api/paper/clear", json={"sell_date": dates[-1]})

        assert resp.status_code == 200
        assert len(fake.sent) == 1
        title, text = fake.sent[0]
        assert "600000" in text
        assert "清仓" in title or "清仓" in text

    def test_clear_all_no_notify_when_empty(self, env, tmp_path):
        from starlette.testclient import TestClient

        import web.api as api_mod

        db, store, _dates = env

        class _FakeNotify:
            def __init__(self):
                self.sent = []

            def configured(self):
                return True

            def send_markdown(self, text, title="模拟仓"):
                self.sent.append((title, text))
                return True, "ok"

        fake = _FakeNotify()
        with patch.object(api_mod, "db_path", db), patch.object(api_mod, "DATA_DIR", tmp_path):
            with patch.object(api_mod, "get_paper", lambda _db: PaperPortfolio(db, store)):
                with patch.object(api_mod, "notify_hook", fake):
                    client = TestClient(api_mod.app)
                    resp = client.post("/api/paper/clear", json={})

        assert resp.status_code == 200
        assert resp.json()["closed_count"] == 0
        assert fake.sent == []

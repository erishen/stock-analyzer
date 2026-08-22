"""
FastAPI Application for Stock Analyzer.
FastAPI 应用
"""

import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import get_stock_analysis_db_path

from .schemas import (
    AgentChatRequest,
    BacktestRequest,
    BacktestResponse,
    LLMSettingsRequest,
    MarketHistoryResponse,
    MarketTimingResponse,
    OptimizeRequest,
    OptimizeResponse,
    PaperAddRequest,
    PaperCloseRequest,
    PortfolioRequest,
    PortfolioResponse,
    ScanRequest,
    ScanResponse,
    ScreenerCondition,
    ScreenerRequest,
    ScreenerResponse,
    SectorItem,
    SectorResponse,
    SignalItem,
    StatsResponse,
    StockDetailResponse,
    StockRowItem,
    StocksResponse,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
sys.path.insert(0, str(PROJECT_ROOT / "src"))
STATIC_DIR = Path(__file__).parent / "static"
ASSETS_DIR = STATIC_DIR / "assets"

db_path = Path(get_stock_analysis_db_path())

# 初始化缓存 (慢接口结果落盘, 数据更新后自动失效)
from .api_cache import init_cache, run_cached

init_cache(db_path)

# 模拟仓 (懒初始化, 存储于 data/paper_portfolio.json)
from .paper_trading import get_paper


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("\n📊 Stock Analyzer Web Server")
    logger.info(f"   数据库: {db_path}")
    logger.error(f"   状态: {'✅ 已连接' if db_path.exists() else '❌ 不存在'}")
    yield
    logger.info("\n👋 服务器关闭")


app = FastAPI(
    title="Stock Analyzer API",
    description="股票分析器 API",
    version="1.0.0",
    lifespan=lifespan,
)

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


def _is_loopback(client_host: str) -> bool:
    """是否本机访问(127.0.0.1 / ::1 / localhost)。"""
    return client_host in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost")


def _chat_auth_required(request: Request, authorization: str | None = Header(default=None)):
    """/api/agent/chat 鉴权: 本机放行; 非本机需 Bearer TOKEN。

    令牌读 WEB_CHAT_TOKEN (.env / 环境变量)。未配置令牌时非本机访问一律拒绝(安全默认)。
    """
    host = (request.client.host if request.client else "") or ""
    if _is_loopback(host):
        return
    expected = os.environ.get("WEB_CHAT_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=401,
            detail="非本机访问 Agent 对话需配置 WEB_CHAT_TOKEN",
        )
    given = (authorization or "").removeprefix("Bearer ").strip()
    if given != expected:
        raise HTTPException(status_code=401, detail="认证失败: 无效或缺失令牌")


@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content=get_default_html())


# stats 全表聚合(700万行)耗时数秒, 结果仅随 ETL 变化, 缓存 10 分钟
_stats_cache: dict = {"data": None, "ts": 0.0}


@app.get("/api/stats")
async def get_stats():
    """获取数据统计"""
    if not db_path.exists():
        return JSONResponse(content=StatsResponse(success=False, error="数据库不存在").to_dict())

    import time as _time

    if _stats_cache["data"] is not None and _time.time() - _stats_cache["ts"] < 600:
        return JSONResponse(content=_stats_cache["data"])

    with sqlite3.connect(str(db_path)) as conn:
        try:
            cursor = conn.execute("""
                SELECT
                    COUNT(DISTINCT code) as stock_count,
                    COUNT(*) as total_records,
                    MIN(date) as min_date,
                    MAX(date) as max_date
                FROM stock_analysis
            """)
            row = cursor.fetchone()

            cursor = conn.execute("PRAGMA table_info(stock_analysis)")
            columns = cursor.fetchall()
            indicator_cols = [
                c[1]
                for c in columns
                if c[1]
                not in [
                    "id",
                    "code",
                    "date",
                    "open",
                    "close",
                    "high",
                    "low",
                    "volume",
                    "amount",
                    "amplitude",
                    "change_percent",
                    "change_amount",
                    "turnover_rate",
                    "created_at",
                ]
            ]

            payload = StatsResponse(
                success=True,
                stock_count=row[0],
                total_records=row[1],
                min_date=row[2] or "",
                max_date=row[3] or "",
                indicator_count=len(indicator_cols),
            ).to_dict()
            _stats_cache["data"] = payload
            _stats_cache["ts"] = _time.time()
            return JSONResponse(content=payload)
        except KeyError as e:
            return JSONResponse(content=StatsResponse(success=False, error=str(e)).to_dict())

        except Exception as e:
            return JSONResponse(content=StatsResponse(success=False, error=str(e)).to_dict())


@app.get("/api/paper")
async def paper_status():
    """获取模拟仓持仓与实时诊断"""
    if not db_path.exists():
        return JSONResponse(content={"success": False, "message": "分析数据库不存在"})
    pf = get_paper(db_path)
    return JSONResponse(content=pf.get_diagnosis())


@app.post("/api/paper/position")
async def paper_add_position(req: PaperAddRequest):
    """模拟建仓"""
    pf = get_paper(db_path)
    return JSONResponse(
        content=pf.add_position(
            req.code, req.buy_price, req.shares, req.buy_date, req.stop_loss, req.take_profit
        )
    )


@app.post("/api/paper/close")
async def paper_close_position(req: PaperCloseRequest):
    """模拟卖出"""
    pf = get_paper(db_path)
    return JSONResponse(
        content=pf.close_position(req.code, req.sell_price, req.sell_date, req.shares)
    )


@app.post("/api/agent/chat")
async def agent_chat(req: AgentChatRequest, _: None = Depends(_chat_auth_required)):
    """Agent 对话: 自然语言 -> 只读 SQL 查库 -> 中文作答 + 可选图表

    复刻 datapulse 的 Text2SQL 方法; 问及持仓时自动注入模拟仓快照作为上下文。
    本机访问免鉴权; 非本机访问需 Authorization: Bearer WEB_CHAT_TOKEN。
    """
    if not db_path.exists():
        return JSONResponse(content={"success": False, "message": "分析数据库不存在"})

    messages = req.messages or []
    if not messages or not messages[-1].get("content", "").strip():
        return JSONResponse(content={"success": False, "message": "问题不能为空"})

    try:
        from agent import pipeline as agent_pipeline
        from agent import portfolio as agent_portfolio
    except Exception as e:  # pragma: no cover
        logger.error("导入 agent 失败: %s", e)
        return JSONResponse(content={"success": False, "message": f"Agent 模块不可用: {e}"})

    question = (messages[-1].get("content") or "").strip()
    history = [
        {"role": m.get("role", "user"), "content": (m.get("content") or "")}
        for m in messages[:-1]
    ]

    # 问及持仓/买卖时, 注入模拟仓快照帮助模型作答
    context = ""
    if any(k in question for k in ("持仓", "我的股票", "我买的", "减仓", "模拟", "止盈", "止损")):
        try:
            context = agent_portfolio.build_paper_context(db_path)
        except Exception as e:
            logger.warning("加载持仓上下文失败: %s", e)

    result = agent_pipeline.run_question(db_path, str(PROJECT_ROOT), question, history, context)
    status = 200 if result.get("success") else 500
    return JSONResponse(content=result, status_code=status)


@app.get("/api/agent/settings")
async def agent_settings():
    """读取当前 LLM 配置(供设置 Tab 展示)。api_key 脱敏返回。"""
    try:
        from agent import llm as agent_llm
        cfg = agent_llm.get_llm_config()
    except Exception as e:  # pragma: no cover
        return JSONResponse(content={"success": False, "message": f"读取配置失败: {e}"}, status_code=500)
    mask = (cfg.get("api_key") or "")
    masked = (mask[:4] + "****" + mask[-4:]) if len(mask) > 8 else ("****" if mask else "")
    return JSONResponse(content={
        "success": True,
        "base_url": cfg.get("base_url", ""),
        "model": cfg.get("model", ""),
        "configured_api_key": bool(mask),
        "api_key_masked": masked,
    })


@app.post("/api/agent/settings")
async def agent_settings_save(req: LLMSettingsRequest):
    """保存运行时 LLM 配置覆盖。空字段表示该项沿用 .env 默认。"""
    try:
        from agent import llm as agent_llm
        base = agent_llm.get_llm_config()
        merged = {
            "base_url": (req.base_url or "").strip() or base["base_url"],
            "api_key": (req.api_key or "").strip() or base["api_key"],
            "model": (req.model or "").strip() or base["model"],
        }
        if not merged["api_key"]:
            return JSONResponse(content={"success": False, "message": "API Key 不能为空"})
        agent_llm.save_override(merged)
    except Exception as e:  # pragma: no cover
        return JSONResponse(content={"success": False, "message": f"保存失败: {e}"}, status_code=500)
    return JSONResponse(content={"success": True, "message": "已保存, 下次问答生效"})


@app.post("/api/agent/settings/reset")
async def agent_settings_reset():
    """清除运行时覆盖, 恢复使用 .env 配置。"""
    try:
        from agent import llm as agent_llm
        agent_llm.clear_override()
    except Exception as e:  # pragma: no cover
        return JSONResponse(content={"success": False, "message": f"重置失败: {e}"}, status_code=500)
    return JSONResponse(content={"success": True, "message": "已恢复 .env 默认配置"})


@app.post("/api/scan")
async def scan_signals(request: ScanRequest):
    """扫描信号

    只缓存「一次全量扫描结果」, signal_type / min_score / limit 在内存中对
    全量结果做过滤与截断, 因此任何筛选组合都无需重跑昂贵的全市场扫描。
    """
    if not db_path.exists():
        return JSONResponse(content=ScanResponse(success=False, error="数据库不存在").to_dict())

    from scanner import SignalType

    def _fetch_full():
        from scanner import run_scan

        result = run_scan(
            db_path=db_path, signal_type=None, min_score=0,
            parallel=True, max_workers=8,
        )
        return {
            "total_stocks": result.total_stocks,
            "summary": result.summary,
            "signals": [s.to_dict() for s in result.signals],  # 全量, 未过滤
        }

    try:
        # 固定参数: 全量结果只受数据日期影响, 与过滤参数无关
        data = run_cached("scan", {"all": 1}, _fetch_full, force_refresh=request.refresh)
    except Exception as e:
        return JSONResponse(content=ScanResponse(success=False, error=str(e)).to_dict())

    # 内存中对全量结果做筛选 + 排序 + 取前 N, 秒回
    if request.signal_type:
        st = None
        with suppress(ValueError):
            st = SignalType(request.signal_type)
        if st is not None:
            want = st.value
            filtered = [s for s in data["signals"] if s["signal_type"] == want]
            data = {**data, "signals": filtered}

    if request.min_score > 0:
        data = {**data, "signals": [s for s in data["signals"] if s["score"] >= request.min_score]}

    top = sorted(data["signals"], key=lambda s: s["score"], reverse=True)[: request.limit]
    signals = [
        SignalItem(
            code=s["code"],
            name=s.get("name") or s["code"],
            signal_type=s["signal_type"],
            strength=s["strength"],
            score=s["score"],
            price=s["price"],
            change_percent=s.get("change_percent", 0),
            date=s.get("date", ""),
        )
        for s in top
    ]
    return JSONResponse(
        content=ScanResponse(
            success=True,
            total_stocks=data["total_stocks"],
            signals_found=len(data["signals"]),
            signals=signals,
            summary=data["summary"],
        ).to_dict()
    )


@app.get("/api/screener/fields")
async def screener_fields():
    """返回自定义规则可选的字段列表(字段名 + 中文注释 + 分组)"""
    from scanner.screener import list_fields

    if not db_path.exists():
        return JSONResponse(content={"success": False, "items": [], "error": "数据库不存在"})
    try:
        fields = list_fields(db_path)
    except Exception as e:
        return JSONResponse(content={"success": False, "items": [], "error": str(e)})
    return JSONResponse(content={"success": True, "items": fields})


@app.get("/api/asset/snapshot")
async def asset_snapshot():
    """获取资产快照(市值/股本/估值)。无快照时返回 updated_at 为空。"""
    from data.asset import load_snapshot

    snap = load_snapshot()
    return JSONResponse(content={"success": True, **snap})


@app.post("/api/asset/refresh")
async def asset_refresh():
    """拉取并更新全市场资产快照(东财源, 可能耗时数秒~数十秒)

    与 /api/update 同属「外部行情抓取」能力, 受 WEB_ENABLE_UPDATE 开关控制。
    抓取逻辑位于 data_tools/asset_fetch.py (不随仓库分发)。
    """
    if not _update_enabled():
        return JSONResponse(
            content={"success": False, "message": "数据更新功能未开启 (WEB_ENABLE_UPDATE)"},
            status_code=403,
        )
    module = _import_asset_fetch()
    if module is None:
        return JSONResponse(
            content={"success": False, "message": "资产抓取模块未就绪 (data_tools/asset_fetch.py)"},
            status_code=500,
        )
    result = module.refresh_snapshot()
    code = 200 if result.get("success") else 500
    return JSONResponse(content={"success": result.get("success"), **result}, status_code=code)


@app.post("/api/screener")
async def screener_scan(request: ScreenerRequest):
    """自定义规则选股: 全部条件 AND 匹配, 结果取每只股票最近一天数据"""
    if not db_path.exists():
        return JSONResponse(content=ScreenerResponse(success=False, error="数据库不存在").to_dict())

    from scanner.screener import scan as screener_scan

    try:
        conds = [
            ScreenerCondition(
                field=str(d.get("field") or "").strip(),
                op=str(d.get("op") or ">").strip(),
                value=float(d.get("value", 0) or 0),
            )
            for d in (request.conditions or [])
            if d.get("field")
        ]
        result = screener_scan(
            db_path,
            conditions=conds,
            limit=request.limit if request.limit > 0 else 50,
            offset=max(0, request.offset),
            sort_field=request.sort_field,
            sort_dir=request.sort_dir,
        )
    except ValueError as e:
        return JSONResponse(content=ScreenerResponse(success=False, error=str(e)).to_dict())
    except Exception as e:  # pragma: no cover
        return JSONResponse(content=ScreenerResponse(success=False, error=str(e)).to_dict())

    return JSONResponse(
        content=ScreenerResponse(
            success=True,
            total=result["total"],
            date=result["date"],
            items=result["items"],
        ).to_dict()
    )


@app.post("/api/backtest")
def run_backtest(request: BacktestRequest):
    """运行回测 (结果带缓存, 数据更新后失效; 可传 refresh=true 强刷)"""
    if not db_path.exists():
        return JSONResponse(content=BacktestResponse(success=False, error="数据库不存在").to_dict())

    def _compute():
        from strategy import run_backtest as run_strategy_backtest

        result = run_strategy_backtest(
            db_path=db_path,
            strategy_type=request.strategy,
            holding_days=request.holding_days,
            lookback_days=request.lookback_days,
            initial_capital=request.initial_capital,
            min_price=request.min_price,
            max_volatility=request.max_volatility,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            exclude_st=request.exclude_st,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        trades = []
        for t in result.trades:
            trades.append(
                {
                    "code": t.code,
                    "name": t.name,
                    "entry_date": t.entry_date,
                    "exit_date": t.exit_date,
                    "entry_price": round(t.entry_price, 2),
                    "exit_price": round(t.exit_price, 2),
                    "profit_percent": round(t.profit_percent * 100, 2),
                }
            )

        return BacktestResponse(
            success=True,
            strategy_name=result.strategy_name,
            start_date=result.start_date,
            end_date=result.end_date,
            initial_capital=result.initial_capital,
            final_capital=result.final_capital,
            total_return=result.total_return,
            annualized_return=result.annualized_return,
            max_drawdown=result.max_drawdown,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            calmar_ratio=result.calmar_ratio,
            volatility=result.volatility,
            total_trades=result.total_trades,
            win_rate=result.win_rate,
            profit_factor=result.profit_factor,
            trades=trades,
            equity_curve=result.equity_curve,
        ).to_dict()

    try:
        params = {
            "strategy": request.strategy,
            "holding_days": request.holding_days,
            "lookback_days": request.lookback_days,
            "initial_capital": request.initial_capital,
            "min_price": request.min_price,
            "max_volatility": request.max_volatility,
            "stop_loss": request.stop_loss,
            "take_profit": request.take_profit,
            "exclude_st": request.exclude_st,
            "start_date": request.start_date,
            "end_date": request.end_date,
        }
        data = run_cached("backtest", params, _compute, force_refresh=request.refresh)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content=BacktestResponse(success=False, error=str(e)).to_dict())


# ---- 后台寻优任务 (异步执行 + 进度回传) ----
# 动量寻优网格可达数百组, 串行执行需数分钟, 交互体验差。
# 改用后台线程池执行, 提交即返回 task_id, 前端轮询状态接口获取进度与结果。
_optimize_tasks: dict[str, dict] = {}
_optimize_lock = threading.Lock()
_optimize_pool = ThreadPoolExecutor(max_workers=1)  # 单并发, 避免多个寻优抢占计算资源

# 完成的寻优任务保留时长(秒), 过期清理
_TASK_TTL = 3600.0


def _poll_optimize_tasks():
    now = time.monotonic()
    stale = [
        tid
        for tid, t in _optimize_tasks.items()
        if t["status"] in ("done", "error") and now - t["finished_at"] > _TASK_TTL
    ]
    for tid in stale:
        _optimize_tasks.pop(tid, None)


@app.post("/api/optimize")
def submit_optimize(request: OptimizeRequest):
    """提交参数寻优任务 (异步执行, 返回 task_id)"""
    if not db_path.exists():
        return JSONResponse(content=OptimizeResponse(success=False, error="数据库不存在").to_dict())
    if request.strategy not in ("momentum", "mean_reversion"):
        return JSONResponse(
            content={"success": False, "error": f"暂只支持动量/均值回归策略, 当前: {request.strategy}"}
        )

    task_id = uuid.uuid4().hex[:16]
    task = {
        "task_id": task_id,
        "status": "running",  # running / done / error
        "progress": 0,  # 已完成组合数
        "total": 0,  # 总组合数
        "stage": "排队中...",
        "started_at": time.monotonic(),
        "finished_at": None,
        "result": None,
        "error": "",
    }
    with _optimize_lock:
        _optimize_tasks[task_id] = task
        _poll_optimize_tasks()

    def _progress(done: int, total: int):
        task["progress"] = done
        task["total"] = total
        task["stage"] = f"寻优中 {done}/{total}"

    def _run():
        try:
            from strategy.optimization import optimize_with_split

            result = optimize_with_split(
                db_path=db_path,
                strategy_type=request.strategy,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
                progress_callback=_progress,
            )
            data = OptimizeResponse(
                success=True,
                strategy=request.strategy,
                best_params=result.best_params,
                best_return=result.best_return,
                best_sharpe=result.best_sharpe,
                best_drawdown=result.best_drawdown,
                total_combinations=result.total_combinations,
                train_start=result.train_start,
                train_end=result.train_end,
                val_start=result.val_start,
                val_end=result.val_end,
                val_return=result.val_return,
                val_sharpe=result.val_sharpe,
                val_drawdown=result.val_drawdown,
                top_results=[
                    {
                        "params": r["params"],
                        "total_return": r["total_return"],
                        "sharpe_ratio": r["sharpe_ratio"],
                        "max_drawdown": r["max_drawdown"],
                        "win_rate": r["win_rate"],
                    }
                    for r in result.all_results
                ],
            ).to_dict()
            task["status"] = "done"
            task["stage"] = "完成"
            task["result"] = data
        except Exception as e:
            logger.exception("寻优任务失败")
            task["status"] = "error"
            task["stage"] = "失败"
            task["error"] = str(e)
        finally:
            task["finished_at"] = time.monotonic()

    _optimize_pool.submit(_run)

    return JSONResponse(
        content={
            "success": True,
            "task_id": task_id,
            "status": "running",
            "progress": 0,
            "stage": task["stage"],
        }
    )


@app.get("/api/optimize/status/{task_id}")
def optimize_status(task_id: str):
    """查询寻优任务状态与进度"""
    with _optimize_lock:
        task = _optimize_tasks.get(task_id)
    if task is None:
        return JSONResponse(content={"success": False, "error": "任务不存在"})
    return JSONResponse(
        content={
            "success": True,
            "task_id": task_id,
            "status": task["status"],
            "progress": task["progress"],
            "total": task["total"],
            "stage": task["stage"],
            "result": task["result"],
            "error": task["error"],
        }
    )


@app.post("/api/portfolio")
def run_portfolio(request: PortfolioRequest):
    """运行组合回测 (结果带缓存, 数据更新后失效; 可传 refresh=true 强刷)"""
    if not db_path.exists():
        return JSONResponse(content=PortfolioResponse(success=False, error="数据库不存在").to_dict())

    def _compute():
        from strategy import run_portfolio_backtest

        strategies = [
            {"name": s, "type": s, "weight": 0, "params": {"holding_days": request.holding_days}}
            for s in request.strategies
        ]

        result = run_portfolio_backtest(
            db_path=db_path,
            strategies=strategies,
            weight_method=request.weight_method,
            initial_capital=request.initial_capital,
        )

        strategy_results = []
        for r in result.strategy_results:
            strategy_results.append(
                {
                    "name": r.strategy_name,
                    "total_return": round(r.total_return * 100, 2),
                    "sharpe_ratio": round(r.sharpe_ratio, 2),
                    "max_drawdown": round(r.max_drawdown * 100, 2),
                }
            )

        return PortfolioResponse(
            success=True,
            name=result.name,
            start_date=result.start_date,
            end_date=result.end_date,
            initial_capital=result.initial_capital,
            final_capital=result.final_capital,
            total_return=result.total_return,
            annualized_return=result.annualized_return,
            max_drawdown=result.max_drawdown,
            sharpe_ratio=result.sharpe_ratio,
            volatility=result.volatility,
            diversification_ratio=result.diversification_ratio,
            strategy_weights=result.strategy_weights,
            correlation_matrix=result.correlation_matrix,
            strategy_results=strategy_results,
        ).to_dict()

    try:
        params = {
            "strategies": request.strategies,
            "weight_method": request.weight_method,
            "holding_days": request.holding_days,
            "initial_capital": request.initial_capital,
        }
        data = run_cached("portfolio", params, _compute, force_refresh=request.refresh)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content=PortfolioResponse(success=False, error=str(e)).to_dict())


@app.get("/api/sector")
async def get_sector(refresh: bool = False):
    """获取行业轮动 (结果带缓存, 数据更新后失效; 可传 refresh=true 强刷)"""
    if not db_path.exists():
        return JSONResponse(content=SectorResponse(success=False, error="数据库不存在").to_dict())

    def _compute():
        from strategy import run_sector_analysis

        result = run_sector_analysis(db_path)

        sectors = []
        for s in result.sectors[:20]:
            sectors.append(
                SectorItem(
                    name=s.name,
                    momentum=s.momentum,
                    strength=s.strength.value,
                    stock_count=len(s.stocks),
                    top_stocks=s.stocks[:5],
                )
            )

        rotation_signals = []
        for r in result.rotations:
            rotation_signals.append(
                {
                    "sector": r.sector,
                    "signal": r.signal.value,
                    "score": round(r.score, 2),
                    "confidence": round(r.score, 2),
                    "reason": r.reason,
                }
            )

        return SectorResponse(
            success=True,
            analysis_date=result.date,
            sectors=sectors,
            rotation_signals=rotation_signals,
        ).to_dict()

    try:
        data = run_cached("sector", {}, _compute, force_refresh=refresh)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content=SectorResponse(success=False, error=str(e)).to_dict())


@app.get("/api/market-timing")
async def get_market_timing(refresh: bool = False):
    """获取大盘择时 (结果带缓存, 数据更新后失效; 可传 refresh=true 强刷)"""
    if not db_path.exists():
        return JSONResponse(content=MarketTimingResponse(success=False, error="数据库不存在").to_dict())

    def _compute():
        from strategy import run_market_timing

        result = run_market_timing(db_path)

        return MarketTimingResponse(
            success=True,
            state=result.state.value,
            score=result.score,
            position_advice=result.signal,
            indicators={
                "均线趋势": result.ma_trend,
                "RSI强弱": result.rsi_level,
                "波动率": result.volatility,
                "市场广度": {
                    "value": round(result.breadth * 100, 2),
                    "signal": "neutral",
                },
            },
        ).to_dict()

    try:
        data = run_cached("market_timing", {}, _compute, force_refresh=refresh)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content=MarketTimingResponse(success=False, error=str(e)).to_dict())


@app.get("/api/market/history")
async def market_history(days: int = 90):
    """获取全市场近期走势 (日均收盘/涨跌/RSI/市场广度/波动率), 用于图表展示"""
    if not db_path.exists():
        return JSONResponse(content=MarketHistoryResponse(success=False, error="数据库不存在").to_dict())

    days = max(10, min(int(days), 500))

    def _compute():
        import pandas as pd

        with sqlite3.connect(str(db_path)) as conn:
            # 最近 days 个交易日
            trade_dates = [r[0] for r in conn.execute(
                "SELECT DISTINCT date FROM stock_analysis ORDER BY date DESC LIMIT ?", (days,)
            ).fetchall()][::-1]
            if not trade_dates:
                return MarketHistoryResponse(success=False, error="无数据").to_dict()

            rows = conn.execute(
                """
                SELECT date,
                       AVG(close) as avg_close,
                       AVG(ma5) as avg_ma5,
                       AVG(ma20) as avg_ma20,
                       AVG(change_percent) as avg_change,
                       AVG(rsi) as avg_rsi,
                       SUM(CASE WHEN change_percent > 0 THEN 1 ELSE 0 END) * 1.0
                           / NULLIF(SUM(CASE WHEN change_percent <> 0 THEN 1 ELSE 0 END), 0) as breadth
                FROM stock_analysis
                WHERE date >= ?
                GROUP BY date
                ORDER BY date
                """,
                (trade_dates[0],),
            ).fetchall()

        dates = [r[0] for r in rows]
        closes = [r[1] for r in rows]
        ma5s = [r[2] for r in rows]
        ma20s = [r[3] for r in rows]
        changes = [r[4] for r in rows]
        rsis = [r[5] for r in rows]
        breadths = [(r[6] or 0) * 100 for r in rows]

        # 波动率 = 近20个交易日 日均涨跌幅(%) 的滚动标准差
        vol = [None] * len(changes)
        s = pd.Series(changes)
        rolling = s.rolling(20).std()
        for i in range(len(changes)):
            if not pd.isna(rolling.iloc[i]):
                vol[i] = float(rolling.iloc[i])
            else:
                vol[i] = None if i < len(changes) else 0

        return MarketHistoryResponse(
            success=True,
            days=len(dates),
            start_date=dates[0],
            end_date=dates[-1],
            dates=dates,
            avg_close=[round(c, 2) if c is not None else None for c in closes],
            avg_ma5=[round(m, 2) if m is not None else None for m in ma5s],
            avg_ma20=[round(m, 2) if m is not None else None for m in ma20s],
            avg_change=[round(c, 2) if c is not None else None for c in changes],
            avg_rsi=[round(r, 2) if r is not None else None for r in rsis],
            breadth=[round(b, 2) if b is not None else None for b in breadths],
            volatility=[round(v, 4) if v is not None else None for v in vol],
        ).to_dict()

    try:
        data = run_cached("market_history", {"days": days}, _compute, force_refresh=False)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content=MarketHistoryResponse(success=False, error=str(e)).to_dict())


def get_market_by_code(code: str) -> str:
    """按代码前缀判断市场板块

    上交所: 60x 主板, 688/689 科创板
    深交所: 000/001/002/003 主板, 300/301/302 创业板
    北交所: 43x/83x/87x/88x/920 (当前库暂无)
    """
    if code.startswith(("688", "689")):
        return "科创板"
    if code.startswith("60"):
        return "上证主板"
    if code.startswith(("300", "301", "302")):
        return "创业板"
    if code.startswith(("000", "001", "002", "003")):
        return "深证主板"
    if code.startswith(("43", "83", "87", "88", "920")):
        return "北交所"
    return "其他"


# 市场筛选值 -> 板块名集合
MARKET_FILTERS: dict[str, set[str]] = {
    "sh": {"上证主板", "科创板"},
    "sz": {"深证主板", "创业板"},
    "bj": {"北交所"},
    "sh_main": {"上证主板"},
    "star": {"科创板"},
    "sz_main": {"深证主板"},
    "chinext": {"创业板"},
    "bse": {"北交所"},
}


def _update_enabled() -> bool:
    """数据更新功能开关 (WEB_ENABLE_UPDATE): 默认关闭, 仅在本机 .env 显式开启后可用。

    该能力对应 data_tools/ 的抓取/ETL——不随仓库分发。
    """
    return os.environ.get("WEB_ENABLE_UPDATE", "").strip() == "1"


def _load_update_task():
    """从 data_tools 动态加载更新任务模块 (该目录不随仓库分发)。

    data_tools 不在 src 包内, 需按 PROJECT_ROOT 注入 sys.path 后以包形式导入。
    """
    sys.path.insert(0, str(PROJECT_ROOT))
    from data_tools import update_task

    return update_task


def _import_asset_fetch():
    """从 data_tools 动态加载资产快照抓取模块; 缺失时返回 None。"""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from data_tools import asset_fetch

        return asset_fetch
    except Exception as e:  # pragma: no cover
        logger.error("加载资产抓取模块失败: %s", e)
        return None


@app.get("/api/enabled")
async def get_enabled_features():
    """功能开关 (供前端决定是否展示数据更新入口)"""
    return JSONResponse(content={"update": _update_enabled()})


@app.post("/api/update")
async def start_data_update():
    """触发数据更新 (后台线程: 增量拉取 K 线 + 增量 ETL)

    仅在 WEB_ENABLE_UPDATE=1 时可用; 关闭时拒绝。
    """
    if not _update_enabled():
        return JSONResponse(
            content={"success": False, "message": "数据更新功能未开启 (WEB_ENABLE_UPDATE)"},
            status_code=403,
        )
    return JSONResponse(content=_load_update_task().start_update_task())


@app.get("/api/update/status")
async def get_update_status():
    """查询数据更新任务进度 (仅开启时可用)"""
    if not _update_enabled():
        return JSONResponse(content={"status": "disabled", "message": "数据更新功能未开启 (WEB_ENABLE_UPDATE)"})
    return JSONResponse(content=_load_update_task().get_status())


@app.get("/api/stocks")
async def get_stocks(
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    date: str = "",
    market: str = "",
    sort_by: str = "code",
    sort_order: str = "asc",
):
    """全市场行情分页查询

    Args:
        page: 页码 (从 1 开始)
        page_size: 每页数量 (1-200)
        search: 按代码或名称模糊搜索
        date: 交易日 (默认最新)
        market: 市场筛选 sh|sz|bj 或板块 sh_main|star|sz_main|chinext|bse
        sort_by: 排序字段 code|change_percent|volume|amount|turnover_rate
        sort_order: asc|desc
    """
    if not db_path.exists():
        return JSONResponse(content=StocksResponse(success=False, error="数据库不存在").to_dict())

    try:
        page = max(1, page)
        page_size = min(200, max(1, page_size))

        with sqlite3.connect(str(db_path)) as conn:
            # 交易日: 默认取最近的完整交易日
            # 最新日期可能只有部分市场完成更新(如北交所先入库、沪深增量未跑),
            # 覆盖不足近期峰值 90% 时向前回退, 保证默认视图是全市场统一列表
            if not date:
                recent = conn.execute(
                    """
                    SELECT date, COUNT(DISTINCT code) AS c
                    FROM stock_analysis
                    WHERE date IN (SELECT DISTINCT date FROM stock_analysis ORDER BY date DESC LIMIT 7)
                    GROUP BY date
                    ORDER BY date DESC
                    """
                ).fetchall()
                if recent:
                    peak = max(r[1] for r in recent)
                    date = next((r[0] for r in recent if r[1] >= peak * 0.9), recent[0][0])
                else:
                    date = ""

            rows = conn.execute(
                """
                SELECT code, open, high, low, close, change_percent, volume, amount, turnover_rate
                FROM stock_analysis
                WHERE date = ?
                """,
                (date,),
            ).fetchall()

        if not rows:
            return JSONResponse(
                content=StocksResponse(success=True, date=date, page=page, page_size=page_size).to_dict()
            )

        # 名称: 仅从本地缓存取, 不触发网络请求
        from data import get_stock_info_fetcher

        fetcher = get_stock_info_fetcher()
        items: list[StockRowItem] = []
        for r in rows:
            items.append(
                StockRowItem(
                    code=r[0],
                    name=fetcher.get_cached_name(r[0]) or r[0],
                    market=get_market_by_code(r[0]),
                    open=r[1] or 0,
                    high=r[2] or 0,
                    low=r[3] or 0,
                    close=r[4] or 0,
                    change_percent=r[5] or 0,
                    volume=r[6] or 0,
                    amount=r[7] or 0,
                    turnover_rate=r[8] or 0,
                )
            )

        # 搜索: 代码前缀或名称包含
        if search:
            s = search.strip().lower()
            items = [i for i in items if i.code.startswith(s) or (i.name and s in i.name.lower())]

        # 市场筛选
        markets = MARKET_FILTERS.get(market)
        if markets:
            items = [i for i in items if i.market in markets]

        # 排序
        sort_keys = {"code", "change_percent", "volume", "amount", "turnover_rate", "close"}
        if sort_by not in sort_keys:
            sort_by = "code"
        items.sort(key=lambda i: getattr(i, sort_by), reverse=(sort_order == "desc"))

        total = len(items)
        total_pages = (total + page_size - 1) // page_size
        start = (page - 1) * page_size

        return JSONResponse(
            content=StocksResponse(
                success=True,
                date=date,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                items=items[start : start + page_size],
            ).to_dict()
        )
    except Exception as e:
        return JSONResponse(content=StocksResponse(success=False, error=str(e)).to_dict())


# 区间收益窗口 (交易日); None 表示上市以来(整个可用历史)
_PERIOD_WINDOWS = {"1月": 22, "3月": 66, "6月": 132, "1年": 244, "2年": 488, "3年": 732, "5年": 1220, "全部": None}


@app.get("/api/stock/{code}")
async def get_stock_detail(code: str, limit: int = 120, days: int = 250):
    """单只股票详情: 历史 K 线 + 最新指标 + 区间收益

    Args:
        code: 六位股票代码
        limit: 返回的 K 线条数 (最近 limit 个交易日)
        days: 用于计算区间收益与指标的历史窗口 (默认 250, 覆盖约 1 年)
    """
    if not db_path.exists():
        return JSONResponse(content=StockDetailResponse(success=False, error="数据库不存在").to_dict())

    try:
        limit = min(3000, max(10, limit))
        days = min(3000, max(60, days))
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(
                """
                SELECT date, open, high, low, close, volume, amount, turnover_rate,
                       change_percent, ma5, ma10, ma20, ma60,
                       macd, macd_hist, rsi, kdj_k, kdj_d, kdj_j,
                       boll_upper, boll_mid, boll_lower, atr
                FROM stock_analysis
                WHERE code = ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (code, days),
            ).fetchall()

        if not rows:
            return JSONResponse(content=StockDetailResponse(success=False, code=code, error="未找到该股票数据").to_dict())

        rows.reverse()  # 升序: 旧 → 新

        # 名称: 仅从本地缓存取, 不触发网络请求
        from data import get_stock_info_fetcher

        fetcher = get_stock_info_fetcher()
        name = fetcher.get_cached_name(code) or code
        market = get_market_by_code(code)

        # 资产快照 (市值/股本/估值, 本地 asset_snapshot.db)。无记录则返回空 dict
        from data.asset import load_snapshot

        asset = {}
        for a in load_snapshot().get("items", []):
            if a.get("code") == code:
                asset = a
                break

        last = rows[-1]
        latest = {
            "date": last[0],
            "open": round(last[1] or 0, 2),
            "high": round(last[2] or 0, 2),
            "low": round(last[3] or 0, 2),
            "close": round(last[4] or 0, 2),
            "volume": last[5] or 0,
            "amount": last[6] or 0,
            "turnover_rate": round(last[7] or 0, 2),
            "change_percent": round(last[8] or 0, 2),
        }

        indicators = {
            "ma5": round(last[9] or 0, 2),
            "ma10": round(last[10] or 0, 2),
            "ma20": round(last[11] or 0, 2),
            "ma60": round(last[12] or 0, 2),
            "macd": round(last[13] or 0, 3),
            "macd_hist": round(last[14] or 0, 3),
            "rsi": round(last[15] or 0, 2),
            "kdj_k": round(last[16] or 0, 2),
            "kdj_d": round(last[17] or 0, 2),
            "kdj_j": round(last[18] or 0, 2),
            "boll_upper": round(last[19] or 0, 2),
            "boll_mid": round(last[20] or 0, 2),
            "boll_lower": round(last[21] or 0, 2),
            "atr": round(last[22] or 0, 2),
        }

        # 区间收益: 当前收盘价相对 N 个交易日前 (或上市以来) 收盘价
        closes = [r[4] for r in rows]
        cur = closes[-1]
        period_returns: dict[str, float] = {}
        for label, w in _PERIOD_WINDOWS.items():
            base = closes[0] if w is None else (closes[len(closes) - 1 - w] if len(closes) - 1 - w >= 0 else None)
            if base is None:
                period_returns[label] = None  # 历史不足
            else:
                period_returns[label] = round(((cur / base) - 1) * 100, 2) if base else None

        kline = [
            {
                "date": r[0],
                "open": round(r[1] or 0, 2),
                "high": round(r[2] or 0, 2),
                "low": round(r[3] or 0, 2),
                "close": round(r[4] or 0, 2),
                "volume": r[5] or 0,
                "change_percent": round(r[8] or 0, 2),
                "ma5": round(r[9] or 0, 2),
                "ma10": round(r[10] or 0, 2),
                "ma20": round(r[11] or 0, 2),
                "ma60": round(r[12] or 0, 2),
            }
            for r in rows[-limit:]
        ]

        return JSONResponse(
            content=StockDetailResponse(
                success=True,
                code=code,
                name=name,
                market=market,
                latest=latest,
                indicators=indicators,
                period_returns=period_returns,
                kline=kline,
                asset=asset,
            ).to_dict()
        )
    except Exception as e:
        return JSONResponse(content=StockDetailResponse(success=False, code=code, error=str(e)).to_dict())


def get_default_html() -> str:
    """获取默认 HTML"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Stock Analyzer</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>Stock Analyzer Web</h1>
    <p>请访问 <a href="/docs">/docs</a> 查看 API 文档</p>
</body>
</html>
"""


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """运行服务器"""
    import uvicorn

    logger.info("\n🚀 启动 Web 服务器")
    logger.info(f"   地址: http://{host}:{port}")
    logger.info(f"   文档: http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, log_level="warning")

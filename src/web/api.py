"""
FastAPI Application for Stock Analyzer.
FastAPI 应用
"""

import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .schemas import (
    BacktestRequest,
    BacktestResponse,
    MarketTimingResponse,
    PortfolioRequest,
    PortfolioResponse,
    ScanRequest,
    ScanResponse,
    SectorItem,
    SectorResponse,
    SignalItem,
    StatsResponse,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
DATA_DIR = PROJECT_ROOT / "data"
STATIC_DIR = Path(__file__).parent / "static"
ASSETS_DIR = STATIC_DIR / "assets"

db_path = DATA_DIR / "stock_analysis.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n📊 Stock Analyzer Web Server")
    print(f"   数据库: {db_path}")
    print(f"   状态: {'✅ 已连接' if db_path.exists() else '❌ 不存在'}")
    yield
    print("\n👋 服务器关闭")


app = FastAPI(
    title="Stock Analyzer API",
    description="股票分析器 API",
    version="1.0.0",
    lifespan=lifespan,
)

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content=get_default_html())


@app.get("/api/stats")
async def get_stats():
    """获取数据统计"""
    if not db_path.exists():
        return JSONResponse(content=StatsResponse(success=False, error="数据库不存在").to_dict())

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

            return JSONResponse(
                content=StatsResponse(
                    success=True,
                    stock_count=row[0],
                    total_records=row[1],
                    min_date=row[2] or "",
                    max_date=row[3] or "",
                    indicator_count=len(indicator_cols),
                ).to_dict()
            )
        except Exception as e:
            return JSONResponse(content=StatsResponse(success=False, error=str(e)).to_dict())


@app.post("/api/scan")
async def scan_signals(request: ScanRequest):
    """扫描信号"""
    if not db_path.exists():
        return JSONResponse(content=ScanResponse(success=False, error="数据库不存在").to_dict())

    try:
        import sys

        from scanner import SignalType, run_scan

        signal_type = None
        if request.signal_type:
            try:
                signal_type = SignalType(request.signal_type)
            except ValueError:
                pass

        result = run_scan(db_path=db_path, signal_type=signal_type, min_score=request.min_score)

        signals = []
        for s in result.top_signals[: request.limit]:
            signals.append(
                SignalItem(
                    code=s.code,
                    name=s.name or s.code,
                    signal_type=s.signal_type.value,
                    strength=s.strength.value,
                    score=s.score,
                    price=s.price,
                    change_percent=s.change_percent,
                    date=s.date,
                )
            )

        return JSONResponse(
            content=ScanResponse(
                success=True,
                total_stocks=result.total_stocks,
                signals_found=result.signals_found,
                signals=signals,
                summary=result.summary,
            ).to_dict()
        )
    except Exception as e:
        return JSONResponse(content=ScanResponse(success=False, error=str(e)).to_dict())


@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    """运行回测"""
    if not db_path.exists():
        return JSONResponse(content=BacktestResponse(success=False, error="数据库不存在").to_dict())

    try:
        import sys

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

        return JSONResponse(
            content=BacktestResponse(
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
        )
    except Exception as e:
        return JSONResponse(content=BacktestResponse(success=False, error=str(e)).to_dict())


@app.post("/api/portfolio")
async def run_portfolio(request: PortfolioRequest):
    """运行组合回测"""
    if not db_path.exists():
        return JSONResponse(content=PortfolioResponse(success=False, error="数据库不存在").to_dict())

    try:
        import sys

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

        return JSONResponse(
            content=PortfolioResponse(
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
        )
    except Exception as e:
        return JSONResponse(content=PortfolioResponse(success=False, error=str(e)).to_dict())


@app.get("/api/sector")
async def get_sector():
    """获取行业轮动"""
    if not db_path.exists():
        return JSONResponse(content=SectorResponse(success=False, error="数据库不存在").to_dict())

    try:
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
                    "reason": r.reason,
                }
            )

        return JSONResponse(
            content=SectorResponse(
                success=True,
                analysis_date=result.date,
                sectors=sectors,
                rotation_signals=rotation_signals,
            ).to_dict()
        )
    except Exception as e:
        return JSONResponse(content=SectorResponse(success=False, error=str(e)).to_dict())


@app.get("/api/market-timing")
async def get_market_timing():
    """获取大盘择时"""
    if not db_path.exists():
        return JSONResponse(content=MarketTimingResponse(success=False, error="数据库不存在").to_dict())

    try:
        from strategy import run_market_timing

        result = run_market_timing(db_path)

        return JSONResponse(
            content=MarketTimingResponse(
                success=True,
                state=result.state.value,
                score=result.score,
                position_advice=result.signal,
                indicators={
                    "ma_trend": result.ma_trend,
                    "rsi_level": result.rsi_level,
                    "volatility": result.volatility,
                    "breadth": round(result.breadth * 100, 2),
                },
            ).to_dict()
        )
    except Exception as e:
        return JSONResponse(content=MarketTimingResponse(success=False, error=str(e)).to_dict())


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

    print("\n🚀 启动 Web 服务器")
    print(f"   地址: http://{host}:{port}")
    print(f"   文档: http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, log_level="warning")

"""
FastAPI Application for Stock Analyzer.
FastAPI 应用
"""

import asyncio
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import get_stock_analysis_db_path

from . import notify_hook
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
    PaperAutoRequest,
    PaperClearRequest,
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
    # 清残留更新状态文件: 上次任务被强杀(kill/重启容器)会留下 running 僵尸态,
    # 阻塞下一次触发。容器 /tmp 不随 restart 清空, 须在 Web 启动时主动清理。
    with suppress(OSError):
        Path(os.environ.get("STOCK_UPDATE_STATUS_FILE", "/tmp/stock_analyzer_update_status.json")).unlink(
            missing_ok=True
        )
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

    公开演示场景(如 Render 免费 Demo)可通过环境变量 AGENT_CHAT_PUBLIC=1 关闭令牌校验,
    允许任意来源访问 Agent 对话。该接口仅做只读 SQL 查询, 不暴露任何密钥或可写操作, 风险可控。
    本地/私有部署默认仍走令牌或本机放行(不开启公开模式)。
    """
    host = (request.client.host if request.client else "") or ""
    if _is_loopback(host):
        return
    expected = os.environ.get("WEB_CHAT_TOKEN", "").strip()
    if expected:
        given = (authorization or "").removeprefix("Bearer ").strip()
        if given != expected:
            raise HTTPException(status_code=401, detail="认证失败: 无效或缺失令牌")
        return
    # 未配置令牌: 仅在显式开启公开模式时才放行, 否则拒绝
    if os.environ.get("AGENT_CHAT_PUBLIC", "").strip() == "1":
        return
    raise HTTPException(
        status_code=401,
        detail="非本机访问 Agent 对话需配置 WEB_CHAT_TOKEN(或设置 AGENT_CHAT_PUBLIC=1 开启公开演示模式)",
    )


def _require_settings_local(request: Request):
    """模型设置接口仅允许本地(localhost)访问。

    Render 等公网/共享部署下, 设置接口返回 403 使其不可用, 避免全局 LLM 配置
    (含明文 api_key) 被任意访问者读取或篡改。
    如需在远程临时开启(例如一次性配置后关闭), 设置环境变量 SETTINGS_REMOTE_ALLOW=1。
    """
    host = (request.client.host if request.client else "") or ""
    if _is_loopback(host):
        return
    if os.environ.get("SETTINGS_REMOTE_ALLOW", "").strip() == "1":
        return
    raise HTTPException(
        status_code=403,
        detail={"disabled": True, "message": "模型设置仅在本地(localhost)部署可用"},
    )


# ---- 公网 Demo 算力护栏 ---- #
# 背景: Render 免费实例只有 0.1 vCPU, 全市场扫描/回测/参数寻优/GBM 训练都能被匿名批量触发,
# 换一组参数就绕过结果缓存, 很容易把实例刷满(表现为页面整体超时)。原有护栏只挡了模拟仓写接口。
# DEMO_READONLY=1 时:
#   1) 禁"强制刷新"(refresh=true) —— 只允许读缓存或按默认参数算一次
#   2) 禁后台重计算与库刷新(参数寻优 / GBM 训练 / 资产快照刷新)
#   3) 对仍允许的耗时接口(扫描/回测/组合)按来源 IP 做滑动窗口限流
_DEMO_BLOCKED_ACTIONS = {"optimize", "gbm_train", "asset_refresh"}
_DEMO_RATE_LIMITS = {"scan": (60.0, 6), "backtest": (60.0, 4), "portfolio": (60.0, 4)}
_demo_hits: dict[str, deque[float]] = {}
_demo_hits_lock = threading.Lock()


def _demo_mode() -> bool:
    """是否运行在只读演示模式。"""
    return os.environ.get("DEMO_READONLY", "").strip() == "1"


def _client_ip(http_request: Request) -> str:
    """取真实来源 IP: 反代(Render/Nginx)场景优先 X-Forwarded-For 首个地址。"""
    xff = http_request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return (http_request.client.host if http_request.client else "") or "?"


def _demo_rate_limit(http_request: Request, action: str) -> None:
    """按 (接口, IP) 做滑动窗口限流, 超限返回 429。"""
    window, limit = _DEMO_RATE_LIMITS[action]
    key = f"{action}:{_client_ip(http_request)}"
    now = time.time()
    with _demo_hits_lock:
        hits = _demo_hits.setdefault(key, deque())
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(
                status_code=429,
                detail={"disabled": True, "message": f"演示环境限流: 每 {int(window)} 秒最多 {limit} 次"},
            )
        hits.append(now)


def _demo_protect(http_request: Request, action: str, refresh: bool = False) -> None:
    """演示模式护栏: 拦截禁用的重计算入口、强制刷新与超频请求。非演示模式下是空操作。"""
    if not _demo_mode():
        return
    if action in _DEMO_BLOCKED_ACTIONS:
        raise HTTPException(
            status_code=403,
            detail={"disabled": True, "message": "演示环境已禁用该操作(算力保护), 本地部署可用"},
        )
    if refresh:
        raise HTTPException(
            status_code=403,
            detail={"disabled": True, "message": "演示环境不支持强制刷新(refresh), 请使用缓存结果"},
        )
    if action in _DEMO_RATE_LIMITS:
        _demo_rate_limit(http_request, action)


@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content=get_default_html())


# stats 全表聚合(700万行)耗时数秒, 结果仅随 ETL 变化, 缓存 10 分钟
_stats_cache: dict = {"data": None, "ts": 0.0}


@app.get("/api/indicators")
async def get_indicators():
    """指标数学词典: 51 个技术指标的数学定义 + 人话含义 + 信号判读。

    与 AI 选股 Agent 提示词同源(见 src/agent/math_glossary.py),
    前端「术语字典」页面据此渲染「指标数学」分类。
    """
    from src.agent.math_glossary import INDICATOR_MATH, SCHEMA_GLOSSARY_KEYS

    return {"success": True, "indicators": INDICATOR_MATH, "core_keys": SCHEMA_GLOSSARY_KEYS}


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


def _paper_write_guard() -> None:
    """模拟仓写接口护栏: PAPER_WRITE_DISABLED=1 时禁掉建仓/平仓/清仓/自动交易。

    用于公网 demo (render.yaml): 合成库 + 免费实例, 禁写防止被第三方刷算力。
    本地/私有部署不设该变量, 行为不变。读接口 /api/paper 不受影响。
    """
    if os.environ.get("PAPER_WRITE_DISABLED", "").strip() == "1":
        raise HTTPException(
            status_code=403,
            detail="模拟仓写接口已在演示环境禁用 (PAPER_WRITE_DISABLED=1)",
        )


@app.post("/api/paper/position")
async def paper_add_position(req: PaperAddRequest):
    """模拟建仓 (消耗现金余额, 计入佣金)"""
    _paper_write_guard()
    pf = get_paper(db_path)
    return JSONResponse(
        content=pf.add_position(
            req.code,
            req.buy_price,
            req.shares,
            req.buy_date,
            req.stop_loss,
            req.take_profit,
            deduct_cash=True,
        )
    )


@app.post("/api/paper/close")
async def paper_close_position(req: PaperCloseRequest):
    """模拟卖出"""
    _paper_write_guard()
    pf = get_paper(db_path)
    return JSONResponse(content=pf.close_position(req.code, req.sell_price, req.sell_date, req.shares))


def _notify_clear(result: dict) -> None:
    """把一键清仓结果渲染成 Markdown 推到钉钉群 (尽力而为, 失败只记日志)。"""
    try:
        if not notify_hook.configured():
            return
        details = result.get("details") or []
        skipped = result.get("skipped") or []
        date = datetime.now().strftime("%Y-%m-%d")
        lines = [f"**🧹 模拟仓一键清仓 {date}**", ""]
        if details:
            lines.append(f"**卖出 {len(details)} 只**")
            for d in details:
                lines.append(
                    f"- {d.get('name', '')} {d.get('code', '')} @ {d.get('sell_price', '')}"
                    f" → 回款 {float(d.get('proceeds') or 0):,.2f}"
                )
        if skipped:
            lines.append("")
            lines.append(f"**⚠️ 跳过 {len(skipped)} 只（无最新行情/停牌）**")
            for s in skipped:
                lines.append(f"- {s.get('name', '')} {s.get('code', '')} · {s.get('reason', '')}")
        lines.append("")
        lines.append(f"合计回款 {float(result.get('total_proceeds') or 0):,.2f} | {result.get('message', '')}")
        ok, msg = notify_hook.send_markdown("\n".join(lines), title="模拟仓一键清仓")
        if not ok:
            logger.warning("钉钉推送失败: %s", msg)
    except Exception as e:
        logger.warning("钉钉推送异常: %s", e)


@app.post("/api/paper/clear")
async def paper_clear_all(req: PaperClearRequest):
    """一键清仓: 按最新收盘价卖出全部持仓, 并撤销待成交订单"""
    _paper_write_guard()
    pf = get_paper(db_path)
    result = pf.close_all(req.sell_date)
    # 可选: 推送到钉钉群 (无 data_tools/webhook 时静默跳过, 不影响返回)
    if result.get("success") and (result.get("closed_count") or 0) > 0:
        await asyncio.to_thread(_notify_clear, result)
    return JSONResponse(content=result)


@app.post("/api/paper/auto")
async def paper_auto_run(req: PaperAutoRequest):
    """策略驱动的模拟仓自动交易: 生成信号 -> 次日开盘成交 -> 止损/止盈/到期卖出"""
    _paper_write_guard()
    if not db_path.exists():
        return JSONResponse(content={"success": False, "error": "数据库不存在"})
    try:
        from .paper_auto_trader import AutoTraderConfig, PaperAutoTrader

        cfg = AutoTraderConfig(
            strategy_type=req.strategy,
            max_positions=req.max_positions,
            position_pct=req.position_pct,
            initial_capital=req.initial_capital,
        )
        trader = PaperAutoTrader(db_path, DATA_DIR / "paper_portfolio.json", cfg)
        if req.reset:
            trader.reset(cfg.initial_capital)
        result = await asyncio.to_thread(trader.run, req.date, req.dry_run)
        return JSONResponse(content=result)
    except Exception as e:  # pragma: no cover
        logger.exception("模拟仓自动交易失败")
        return JSONResponse(content={"success": False, "error": str(e)})


@app.post("/api/agent/chat")
async def agent_chat(req: AgentChatRequest, _: None = Depends(_chat_auth_required)):
    """Agent 对话: 自然语言 -> 只读 SQL 查库 -> 中文作答 + 可选图表

    两阶段 Text2SQL 方法(生成 + 自纠错, 见 src/agent/pipeline.py); 问及持仓时自动注入模拟仓快照作为上下文。
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
    history = [{"role": m.get("role", "user"), "content": (m.get("content") or "")} for m in messages[:-1]]

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


@app.get("/api/agent/settings", dependencies=[Depends(_require_settings_local)])
async def agent_settings():
    """读取当前 LLM 配置(供设置 Tab 展示)。api_key 脱敏返回。"""
    try:
        from agent import llm as agent_llm

        cfg = agent_llm.get_llm_config()
    except Exception as e:  # pragma: no cover
        return JSONResponse(content={"success": False, "message": f"读取配置失败: {e}"}, status_code=500)
    mask = cfg.get("api_key") or ""
    masked = (mask[:4] + "****" + mask[-4:]) if len(mask) > 8 else ("****" if mask else "")
    return JSONResponse(
        content={
            "success": True,
            "base_url": cfg.get("base_url", ""),
            "model": cfg.get("model", ""),
            "configured_api_key": bool(mask),
            "api_key_masked": masked,
        }
    )


@app.post("/api/agent/settings", dependencies=[Depends(_require_settings_local)])
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


@app.post("/api/agent/settings/reset", dependencies=[Depends(_require_settings_local)])
async def agent_settings_reset():
    """清除运行时覆盖, 恢复使用 .env 配置。"""
    try:
        from agent import llm as agent_llm

        agent_llm.clear_override()
    except Exception as e:  # pragma: no cover
        return JSONResponse(content={"success": False, "message": f"重置失败: {e}"}, status_code=500)
    return JSONResponse(content={"success": True, "message": "已恢复 .env 默认配置"})


@app.post("/api/scan")
async def scan_signals(request: ScanRequest, http_request: Request):
    """扫描信号

    只缓存「一次全量扫描结果」, signal_type / min_score / limit 在内存中对
    全量结果做过滤与截断, 因此任何筛选组合都无需重跑昂贵的全市场扫描。
    """
    _demo_protect(http_request, "scan", request.refresh)
    if not db_path.exists():
        return JSONResponse(content=ScanResponse(success=False, error="数据库不存在").to_dict())

    from scanner import SignalType

    def _fetch_full():
        from scanner import run_scan

        result = run_scan(
            db_path=db_path,
            signal_type=None,
            min_score=0,
            parallel=True,
            max_workers=8,
        )
        return {
            "total_stocks": result.total_stocks,
            "summary": result.summary,
            "signals": [s.to_dict() for s in result.signals],  # 全量, 未过滤
            "diagnostics": result.diagnostics or {},
        }

    try:
        # 固定参数: 全量结果只受数据日期影响, 与过滤参数无关
        data = run_cached("scan", {"all": 1}, _fetch_full, force_refresh=request.refresh)
    except Exception as e:
        return JSONResponse(content=ScanResponse(success=False, error=str(e)).to_dict())

    # 内存中对全量结果做筛选 + 排序 + 取前 N, 秒回
    # 漏斗: 全市场 → 有数据可分析 → 每级过滤后剩余信号数 → 实际返回。
    # 这些计数以前是"静默"的: 数据缺失/异常/过滤过多都表现为"结果变少"。
    diag = data.get("diagnostics") or {}
    funnel = {
        "codes": int(diag.get("codes", data["total_stocks"])),
        "scanned": int(diag.get("scanned", data["total_stocks"])),
        "no_data": int(diag.get("no_data", 0)),
        "error": int(diag.get("error", 0)),
        "stocks_with_signals": int(diag.get("with_signals", 0)),
        "signals": len(data["signals"]),
    }

    if request.signal_type:
        st = None
        with suppress(ValueError):
            st = SignalType(request.signal_type)
        if st is not None:
            want = st.value
            filtered = [s for s in data["signals"] if s["signal_type"] == want]
            data = {**data, "signals": filtered}
            funnel["after_signal_type"] = len(filtered)

    if request.min_score > 0:
        data = {**data, "signals": [s for s in data["signals"] if s["score"] >= request.min_score]}
        funnel["after_min_score"] = len(data["signals"])

    top = sorted(data["signals"], key=lambda s: s["score"], reverse=True)[: request.limit]
    funnel["returned"] = len(top)
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
            funnel=funnel,
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
async def asset_refresh(http_request: Request):
    """拉取并更新全市场资产快照(东财源, 可能耗时数秒~数十秒)

    与 /api/update 同属「外部行情抓取」能力, 受 WEB_ENABLE_UPDATE 开关控制。
    抓取逻辑位于 data_tools/asset_fetch.py (不随仓库分发)。
    """
    _demo_protect(http_request, "asset_refresh")
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
def run_backtest(request: BacktestRequest, http_request: Request):
    """运行回测 (结果带缓存, 数据更新后失效; 可传 refresh=true 强刷)"""
    _demo_protect(http_request, "backtest", request.refresh)
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
            **{
                k: getattr(request, k)
                for k in (
                    "slippage_rate",
                    "max_participation",
                    "enable_limit",
                    "enable_slippage",
                    "enable_volume_cap",
                )
                if hasattr(request, k)
            },
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

        payload = BacktestResponse(
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
            cost_sensitivity=result.cost_sensitivity,
        ).to_dict()

        # 基准对比(同窗口、同成本口径): 逐票全表读要 5s+, 这里走 market_daily 汇总表。
        try:
            from strategy.benchmark import calculate_equal_weight_benchmark_from_summary

            cost_rate = 2 * 0.0003 + 0.001 + 2 * float(request.slippage_rate or 0.0005)
            curve = calculate_equal_weight_benchmark_from_summary(
                db_path, result.start_date, result.end_date, cost_rate
            )
            if len(curve) > 1:
                b0, b1 = curve[0]["equity"], curve[-1]["equity"]
                bench_return = (b1 - b0) / b0
                step = max(1, len(curve) // 120)
                payload["benchmark"] = {
                    "return": round(bench_return * 100, 2),
                    "excess_return": round((result.total_return - bench_return) * 100, 2),
                    "cost_pct": round(cost_rate * 100, 3),
                    "method": "全市场等权日收益连乘(market_daily), 建仓+清仓一次性成本",
                    "curve": curve[::step],
                }
        except Exception as e:  # 基准是附加信息, 失败不影响回测本身
            logger.warning(f"基准对比计算失败: {e}")

        payload["methodology"] = {
            "modeled": ["佣金/印花税/最低佣金", "固定比例滑点", "成交额参与率上限", "T+1 禁卖", "涨停不可买/跌停不可卖"],
            "not_modeled": ["真实盘口与冲击成本", "历史 ST 状态(用当前名称)", "退市路径(按最后收盘价退出)", "停牌日按最后收盘价估值"],
            "cost_sensitivity": result.cost_sensitivity,
        }
        return payload

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
def submit_optimize(request: OptimizeRequest, http_request: Request):
    """提交参数寻优任务 (异步执行, 返回 task_id)"""
    _demo_protect(http_request, "optimize")
    if not db_path.exists():
        return JSONResponse(content=OptimizeResponse(success=False, error="数据库不存在").to_dict())
    if request.strategy not in ("momentum", "mean_reversion"):
        return JSONResponse(content={"success": False, "error": f"暂只支持动量/均值回归策略, 当前: {request.strategy}"})

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
def run_portfolio(request: PortfolioRequest, http_request: Request):
    """运行组合回测 (结果带缓存, 数据更新后失效; 可传 refresh=true 强刷)"""
    _demo_protect(http_request, "portfolio", request.refresh)
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
            start_date=request.start_date,
            end_date=request.end_date,
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
            "start_date": request.start_date,
            "end_date": request.end_date,
        }
        data = run_cached("portfolio", params, _compute, force_refresh=request.refresh)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content=PortfolioResponse(success=False, error=str(e)).to_dict())


@app.get("/api/sector")
async def get_sector(http_request: Request, refresh: bool = False):
    """获取行业轮动 (结果带缓存, 数据更新后失效; 可传 refresh=true 强刷)"""
    _demo_protect(http_request, "sector", refresh)
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
            snapshot=getattr(result, "snapshot", {}),
        ).to_dict()

    try:
        data = run_cached("sector", {}, _compute, force_refresh=refresh)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content=SectorResponse(success=False, error=str(e)).to_dict())


@app.get("/api/market-timing")
async def get_market_timing(http_request: Request, refresh: bool = False):
    """获取大盘择时 (结果带缓存, 数据更新后失效; 可传 refresh=true 强刷)"""
    _demo_protect(http_request, "market_timing", refresh)
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

        # 延迟导入: api 既被 `src.web.api` 也被 `web.api`(测试) 两种方式加载,
        # 顶层相对导入 `..data` 在后者会越界。
        from data import market_summary

        with sqlite3.connect(str(db_path)) as conn:
            if market_summary.table_ready(db_path):
                # 快路径: 读 ETL 维护的 market_daily(1,430 行窄表), 毫秒级。
                # 多取 20 行用于算 20 日波动率, 再切回请求的窗口。
                rows = conn.execute(
                    """
                    SELECT date, avg_close, avg_ma5, avg_ma20, avg_change, avg_rsi, breadth
                    FROM market_daily ORDER BY date DESC LIMIT ?
                    """,
                    (days + 20,),
                ).fetchall()[::-1]
            else:
                rows = []

        if not rows:
            return _market_history_slow(days)

        changes_all = [r[4] for r in rows]
        s = pd.Series(changes_all)
        rolling = s.rolling(20).std()
        rows = rows[-days:]
        vol = []
        for i in range(len(rows)):
            idx_all = len(changes_all) - len(rows) + i
            v = rolling.iloc[idx_all]
            vol.append(None if pd.isna(v) else float(v))

        dates = [r[0] for r in rows]
        return MarketHistoryResponse(
            success=True,
            days=len(dates),
            start_date=dates[0],
            end_date=dates[-1],
            dates=dates,
            avg_close=[round(r[1], 2) if r[1] is not None else None for r in rows],
            avg_ma5=[round(r[2], 2) if r[2] is not None else None for r in rows],
            avg_ma20=[round(r[3], 2) if r[3] is not None else None for r in rows],
            avg_change=[round(r[4], 2) if r[4] is not None else None for r in rows],
            avg_rsi=[round(r[5], 2) if r[5] is not None else None for r in rows],
            breadth=[round(r[6] * 100, 2) if r[6] is not None else None for r in rows],
            volatility=[round(v, 4) if v is not None else None for v in vol],
        ).to_dict()

    def _market_history_slow(days: int):

        import pandas as pd

        with sqlite3.connect(str(db_path)) as conn:
            # 最近 days 个交易日
            trade_dates = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT date FROM stock_analysis ORDER BY date DESC LIMIT ?", (days,)
                ).fetchall()
            ][::-1]
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
        # 广度 = 上涨家数 / 有涨跌家数。全天全平盘(或当日无有效涨跌幅)时分母为 NULL,
        # 此时给 None 让前端断线, 而不是画成 0% —— "0% 上涨"是一个误导性结论。
        breadths = [(r[6] * 100) if r[6] is not None else None for r in rows]

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

    兼容带市场前缀的代码 (sh600519 / sz000001 / bj8xxxxx) 与纯六位代码。
    """
    raw = str(code or "").strip().lower()
    if raw[:2] in ("sh", "sz", "bj"):
        raw = raw[2:]
    if not raw or not raw.isdigit():
        return "其他"
    if raw.startswith(("688", "689")):
        return "科创板"
    if raw.startswith("60"):
        return "上证主板"
    if raw.startswith(("300", "301", "302")):
        return "创业板"
    if raw.startswith(("000", "001", "002", "003")):
        return "深证主板"
    if raw.startswith(("43", "83", "87", "88", "920")):
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


def _spawn_update_task() -> dict:
    """用独立子进程执行更新任务 (而非 Web 进程内线程)。

    macOS Docker Desktop 的 bind mount(FUSE) 文件缓存不会随外部写入失效:
    Web 长驻进程持有的旧页缓存会让更新任务误判"指标全缺"而全量重算 5506 只。
    独立子进程的新缓存能读到最新数据(已实测), 且容器内子进程写→Web 读同侧一致。
    """
    import subprocess

    ut = _load_update_task()
    cur = ut.load_status()
    if cur.get("status") == "running":
        # 僵尸态判定: 上次进程被强杀未收尾时状态文件停在 running; mtime 超过
        # 5 分钟且无真实任务(子进程早已退出)视为僵尸, 允许重置重启。
        try:
            stale = time.time() - ut.STATUS_FILE.stat().st_mtime > 300
        except OSError:
            stale = True
        if not stale:
            return {"success": False, "message": "更新任务已在运行中", "status": cur}
    # 先重置状态并落盘 (running), 避免子进程尚未写盘时 API 读到旧状态
    ut._set(
        status="running",
        stage="prepare",
        total=0,
        current=0,
        fetched_rows=0,
        failed=0,
        skipped=0,
        no_new=0,
        etl_loaded=0,
        message="准备中...",
        started_at=datetime.now().isoformat(),
        finished_at="",
        error="",
    )
    script = PROJECT_ROOT / "data_tools" / "update_task.py"
    env = os.environ.copy()
    env["STOCK_UPDATE_STATUS_FILE"] = str(ut.STATUS_FILE)
    try:
        subprocess.Popen(
            [sys.executable, str(script)],
            env=env,
            cwd=str(PROJECT_ROOT),
        )
    except Exception as e:  # pragma: no cover
        ut._set(
            status="error",
            stage="done",
            error=f"{type(e).__name__}: {e}",
            finished_at=datetime.now().isoformat(),
        )
        return {"success": False, "message": f"启动更新失败: {e}", "status": ut.load_status()}
    return {"success": True, "message": "更新任务已启动", "status": ut.load_status()}


def _update_host() -> str:
    """宿主更新服务地址 (STOCK_UPDATE_HOST): 配置后按钮转发宿主执行。
    容器内跑更新受 Docker FUSE 缓存限制不可靠(见 _spawn_update_task 注释),
    宿主执行 + HTTP 状态回传是最稳路径。"""
    return os.environ.get("STOCK_UPDATE_HOST", "").strip()


def _forward_update(path: str, method: str = "get", timeout: int = 10) -> dict:
    import requests

    r = requests.request(method, f"{_update_host()}{path}", timeout=timeout)
    return r.json()


@app.get("/api/enabled")
async def get_enabled_features():
    """功能开关 (供前端决定是否展示数据更新入口)

    ``demo``: 只读演示模式(DEMO_READONLY=1) —— 前端据此显示"演示环境"横幅,
    并让被 403 拦下的操作按普通错误提示, 而不是静默变成空结果。
    """
    return JSONResponse(content={"update": _update_enabled(), "demo": _demo_mode()})


@app.post("/api/update")
async def start_data_update():
    """触发数据更新。

    优先转发宿主更新服务(STOCK_UPDATE_HOST); 未配置时退回容器内子进程(仅
    macOS Docker FUSE 缓存不可靠的已知问题下不建议使用)。
    """
    if not _update_enabled():
        return JSONResponse(
            content={"success": False, "message": "数据更新功能未开启 (WEB_ENABLE_UPDATE)"},
            status_code=403,
        )
    if _update_host():
        try:
            return JSONResponse(content=_forward_update("/update", method="post"))
        except Exception as e:
            return JSONResponse(
                content={"success": False, "message": f"宿主更新服务不可达: {e}"},
                status_code=502,
            )
    return JSONResponse(content=_spawn_update_task())


@app.get("/api/update/status")
async def get_update_status():
    """查询数据更新任务进度 (优先转发宿主服务, 仅开启时可用)"""
    if not _update_enabled():
        return JSONResponse(content={"status": "disabled", "message": "数据更新功能未开启 (WEB_ENABLE_UPDATE)"})
    if _update_host():
        try:
            return JSONResponse(content=_forward_update("/status"))
        except Exception as e:
            return JSONResponse(content={"status": "error", "message": f"宿主更新服务不可达: {e}"})
    return JSONResponse(content=_load_update_task().load_status())


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
            # 最新日期可能只有部分市场完成更新(如北交所先入库、沪深增量未跑, 或
            # 收盘后过早拉取时源端尚未发布部分深市当日 bar), 覆盖不足近期峰值 97%
            # 时向前回退, 保证默认视图是全市场统一列表。
            # 阈值曾为 90%: 2026-11-27 缺 216 只(4%)仍被判为完整交易日, 界面把残缺
            # 的一天当全市场展示, 下游横截面选股/信号随之失真, 故收紧到 97%。
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
                    date = next((r[0] for r in recent if r[1] >= peak * 0.97), recent[0][0])
                else:
                    date = ""

            rows = conn.execute(
                """
                SELECT code, open, high, low, close, change_percent, volume, amount
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
                    turnover_rate=0,
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
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT date, open, high, low, close, volume, amount,
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
            rows = [dict(r) for r in rows]

        if not rows:
            return JSONResponse(
                content=StockDetailResponse(success=False, code=code, error="未找到该股票数据").to_dict()
            )

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
            "date": last["date"],
            "open": round(last["open"] or 0, 2),
            "high": round(last["high"] or 0, 2),
            "low": round(last["low"] or 0, 2),
            "close": round(last["close"] or 0, 2),
            "volume": last["volume"] or 0,
            "amount": last["amount"] or 0,
            "turnover_rate": 0,
            "change_percent": round(last["change_percent"] or 0, 2),
        }

        indicators = {
            "ma5": round(last["ma5"] or 0, 2),
            "ma10": round(last["ma10"] or 0, 2),
            "ma20": round(last["ma20"] or 0, 2),
            "ma60": round(last["ma60"] or 0, 2),
            "macd": round(last["macd"] or 0, 3),
            "macd_hist": round(last["macd_hist"] or 0, 3),
            "rsi": round(last["rsi"] or 0, 2),
            "kdj_k": round(last["kdj_k"] or 0, 2),
            "kdj_d": round(last["kdj_d"] or 0, 2),
            "kdj_j": round(last["kdj_j"] or 0, 2),
            "boll_upper": round(last["boll_upper"] or 0, 2),
            "boll_mid": round(last["boll_mid"] or 0, 2),
            "boll_lower": round(last["boll_lower"] or 0, 2),
            "atr": round(last["atr"] or 0, 2),
        }

        # 区间收益: 当前收盘价相对 N 个交易日前 (或上市以来) 收盘价
        closes = [r["close"] for r in rows]
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
                "date": r["date"],
                "open": round(r["open"] or 0, 2),
                "high": round(r["high"] or 0, 2),
                "low": round(r["low"] or 0, 2),
                "close": round(r["close"] or 0, 2),
                "volume": r["volume"] or 0,
                "change_percent": round(r["change_percent"] or 0, 2),
                "ma5": round(r["ma5"] or 0, 2),
                "ma10": round(r["ma10"] or 0, 2),
                "ma20": round(r["ma20"] or 0, 2),
                "ma60": round(r["ma60"] or 0, 2),
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


# ===================== ML 模型接口 (需 uv sync --extra ml) =====================


def _ml_error(exc: Exception) -> JSONResponse:
    logger.warning("ML 接口失败: %s", exc)
    return JSONResponse(content={"success": False, "error": str(exc)}, status_code=500)


@app.get("/api/ml/status")
async def ml_status():
    """ML 依赖可用性 (供前端决定是否渲染计算按钮)。"""
    from ml.common import require_ml

    available = {}
    for name in ("lightgbm", "sklearn", "arch"):
        try:
            require_ml(name)
            available[name] = True
        except Exception:
            available[name] = False
    return JSONResponse(content={"success": True, "available": available})


@app.get("/api/ml/anomaly")
async def ml_anomaly(http_request: Request, refresh: bool = False):
    """Isolation Forest 异常检测 (最新交易日全市场, 结果缓存)。"""
    _demo_protect(http_request, "ml_anomaly", refresh)
    if not db_path.exists():
        return JSONResponse(content={"success": False, "error": "数据库不存在"})
    try:
        from ml import compute_anomaly_report

        def _compute():
            return compute_anomaly_report(db_path=db_path, top_n=20)

        data = run_cached("ml_anomaly", {}, _compute, force_refresh=refresh)
        return JSONResponse(content=data)
    except Exception as e:
        return _ml_error(e)


@app.get("/api/ml/cluster")
async def ml_cluster(http_request: Request, k: int = 6, refresh: bool = False):
    """K-Means 聚类 (最新交易日全市场, 结果缓存)。"""
    _demo_protect(http_request, "ml_cluster", refresh)
    if not db_path.exists():
        return JSONResponse(content={"success": False, "error": "数据库不存在"})
    try:
        from ml import compute_cluster_report

        k = max(2, min(15, int(k)))

        def _compute():
            return compute_cluster_report(k=k, db_path=db_path)

        data = run_cached("ml_cluster", {"k": k}, _compute, force_refresh=refresh)
        return JSONResponse(content=data)
    except Exception as e:
        return _ml_error(e)


@app.get("/api/ml/garch")
async def ml_garch(code: str, window: int = 300, horizon: int = 5, dist: str = "normal"):
    """GARCH(1,1) 单股波动率 (含条件波动率序列, 供前端画图)。"""
    if not db_path.exists():
        return JSONResponse(content={"success": False, "error": "数据库不存在"})
    if dist not in ("normal", "t", "skewt"):
        dist = "normal"
    try:
        from ml import compute_garch_report

        data = compute_garch_report(
            code,
            window=max(60, min(3000, int(window))),
            horizon=max(1, min(30, int(horizon))),
            dist=dist,
            db_path=db_path,
            with_series=True,
        )
        return JSONResponse(content=data)
    except Exception as e:
        return _ml_error(e)


@app.get("/api/ml/gbm")
async def ml_gbm():
    """读取最近的 ml-gbm 训练报告 (若有)。

    完整训练需数分钟, 不适合在线请求; 该接口只读最近一次 make ml-gbm 落盘的报告。
    """
    reports_dir = PROJECT_ROOT / "output" / "reports"
    if not reports_dir.exists():
        return JSONResponse(content={"success": False, "error": "无训练报告 (请先运行 make ml-gbm)"})
    files = sorted(reports_dir.glob("ml_gbm*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return JSONResponse(content={"success": False, "error": "无训练报告 (请先运行 make ml-gbm)"})
    import json as _json

    data = _json.loads(files[0].read_text(encoding="utf-8"))
    return JSONResponse(content={"success": True, "report": data, "file": files[0].name})


@app.get("/api/methodology")
async def methodology():
    """方法论/算法说明 (静态内容, 含各算法的近似口径与未建模项)。"""
    from .methodology import get_methodology

    return JSONResponse(content=get_methodology())


@app.get("/api/universe/survivorship")
async def universe_survivorship(start: str | None = None, end: str | None = None):
    """幸存者偏差口径: 窗口内新上市/中途停止更新/两端可交易标的数量。

    数据来自 ``code_lifecycle`` 窄表 (``make universe`` 重建), 不扫行情全表。
    """
    from data.universe import survivorship_report

    report = survivorship_report(start, end, DATA_DIR / "stock_klines.db")
    if not report.get("ok"):
        return JSONResponse(content={"success": False, "error": report.get("error")})
    return JSONResponse(content={"success": True, "report": report})


@app.get("/api/universe/asof")
async def universe_asof(date: str | None = None):
    """某交易日真实存在的标的 (first_date <= date <= last_date)。"""
    from data.universe import has_lifecycle, universe_as_of

    db_path = DATA_DIR / "stock_klines.db"
    if not has_lifecycle(db_path):
        return JSONResponse(
            content={"success": False, "error": "缺少 code_lifecycle 表 (请先运行 make universe)"}
        )
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        target = date or conn.execute(
            "SELECT MAX(last_date) FROM code_lifecycle"
        ).fetchone()[0]
    codes = universe_as_of(target, db_path)
    return JSONResponse(
        content={"success": True, "date": target, "count": len(codes), "codes": codes}
    )


@app.get("/api/ml/walkforward")
async def ml_walkforward():
    """读取最近的 ml-walk-forward 报告 (若有)。

    滚动重训 = N 次 GBDT 训练, 分钟级且吃内存, 不适合在线请求;
    与 /api/ml/gbm 一致: 训练走 `make ml-walkforward`, 这里只读最近一次落盘报告。
    """
    reports_dir = PROJECT_ROOT / "output" / "reports"
    files = sorted(reports_dir.glob("ml_walkforward*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if reports_dir.exists() else []
    if not files:
        return JSONResponse(content={"success": False, "error": "无滚动验证报告 (请先运行 make ml-walkforward)"})
    import json as _json

    data = _json.loads(files[0].read_text(encoding="utf-8"))
    return JSONResponse(content={"success": True, "report": data, "file": files[0].name})


# ---- LightGBM 训练任务 (转发宿主执行 + 阶段进度) ----
# 容器内 FUSE 只读挂载读 4.4GB 分析库 + 8G 内存限制, 全量训练会卡死/被重启;
# 宿主内存/CPU 充裕且可跑, 故训练转发宿主 web_trigger_server (STOCK_UPDATE_HOST:19090)
# 执行, 容器只透传状态。复用 /update 的既有"容器按钮 -> 宿主执行"架构。
_ML_HOST = os.environ.get("STOCK_UPDATE_HOST", "http://host.docker.internal:19090").rstrip("/")


def _host_call(method: str, path: str, payload: dict | None = None, timeout: float = 30.0):
    """调宿主 web_trigger_server, 返回 (ok, body_dict)。"""
    import urllib.request

    url = f"{_ML_HOST}{path}"
    data = None
    headers = {}
    if payload is not None:
        import json as _json

        data = _json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.read().decode("utf-8")
    except Exception as e:
        return False, str(e)


@app.post("/api/ml/gbm/train")
def submit_ml_gbm_train(http_request: Request, payload: dict | None = None):
    """提交 LightGBM 排名模型训练任务 (转发宿主异步执行, 返回状态)。

    Body (可选): {start_year?, end_year?} 训练窗口。默认 2020~2026 全量;
    容器内 FUSE 读库慢, 建议用小窗口 (如 2022 起)。
    """
    _demo_protect(http_request, "gbm_train")
    try:
        from ml.common import require_ml

        require_ml("lightgbm")
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

    payload = payload or {}
    try:
        start_year = int(payload.get("start_year", 2020) or 2020)
        end_year = int(payload.get("end_year", 2027) or 2027)
    except (TypeError, ValueError):
        return JSONResponse(content={"success": False, "error": "年份参数非法"})
    if end_year <= start_year or end_year - start_year > 10:
        return JSONResponse(
            content={"success": False, "error": f"训练窗口不合法: {start_year}~{end_year} (需 1~10 年)"}
        )

    ok, body = _host_call("POST", "/ml-gbm", payload, timeout=15)
    if not ok:
        return JSONResponse(
            content={"success": False, "error": f"宿主训练服务不可用 ({_ML_HOST}): {body}"}, status_code=502
        )
    try:
        import json as _json

        data = _json.loads(body)
    except Exception:
        data = {"success": False, "error": f"宿主响应解析失败: {body[:200]}"}
    if not data.get("success"):
        return JSONResponse(content=data)
    # 统一返回结构: task_id 占位 (宿主单实例), 前端轮询同 task_id
    return JSONResponse(
        content={"success": True, "task_id": "host", "status": "running", "stage": data.get("stage", "排队中...")}
    )


@app.get("/api/ml/gbm/train/status/{task_id}")
def ml_gbm_train_status(task_id: str):
    """查询 LightGBM 训练任务状态 (透传宿主 /ml-gbm/status)。"""
    ok, body = _host_call("GET", "/ml-gbm/status", timeout=15)
    if not ok:
        return JSONResponse(
            content={"success": False, "error": f"宿主训练服务不可用 ({_ML_HOST}): {body}"}, status_code=502
        )
    try:
        import json as _json

        data = _json.loads(body)
    except Exception:
        data = {"success": False, "error": f"宿主响应解析失败: {body[:200]}"}
    data["task_id"] = task_id
    data["success"] = True
    # 宿主状态字段对齐前端期望: running/done/error
    if data.get("status") == "success":
        data["status"] = "done"
    elif data.get("status") == "idle":
        data["status"] = "idle"
    return JSONResponse(content=data)


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

# Stock Analyzer

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[中文文档](README.zh.md)

An A-share stock market analysis toolkit — ETL pipeline for daily K-line data, full-market technical signal scanning, strategy backtesting, and a React + FastAPI web dashboard with an AI stock-picking assistant (Text2SQL).

## ⚠️ Disclaimer

This project is a quantitative-research / paper-trading tool for educational and research purposes only. It does not execute real money, and its outputs are **not investment advice**.

- All backtest results, technical indicators, signals, and AI answers are for reference only and do not guarantee accuracy
- Market data is sourced from public feeds (akshare / Tencent / EastMoney), for research purposes only; data belongs to their respective owners
- Backtests are built on historical data and are subject to overfitting and survivorship bias; past performance does not guarantee future results
- Stock market investment carries risk; never rely on this tool for actual trading decisions. The author is not responsible for any losses

### Privacy: what leaves your machine

- Everything is **local by default**: market data, paper portfolio, backtests and models live in `data/`; the databases are gitignored and never uploaded
- The only outbound path is the **AI stock-picking / agent chat** tab: your question text (plus the auto-attached market context) is sent to whatever `LLM_BASE_URL` in `.env` points at, which may be a foreign provider. Skip that tab and nothing leaves the machine
- "Fetch latest data" only calls the market data feeds from local scripts; no private data is uploaded

## ✨ Features

- **ETL Pipeline** — Ingest raw daily K-line data and compute 51 technical indicators with a true incremental window (only recent rows are recomputed, ~6x less writes)
- **Signal Scanner** — Full-market technical signal detection with configurable score thresholds
- **Custom Rule Screener** — Screens full market by AND-combined conditions over 70+ technical + asset fields (market cap, float value, P/E, P/B, volume ratio…)
- **Asset Snapshot** — Market-wide market-cap / shares / valuation fields stored independently (`asset_snapshot.db`), enabling asset-based screening
- **Strategy Backtesting & Optimization** — Multiple strategies with risk metrics and parameter sweeps
- **Market Analysis** — Market timing (bull/bear/range), market breadth pulse charts, sector rotation
- **Paper Trading** — Simulated portfolio: record positions, get MA/MACD/RSI-based diagnostics, stop-loss/take-profit alerts, and trade history
- **🤖 AI Stock Picking** — Ask questions in natural language; the system runs a read-only Text2SQL pipeline against real data and answers with charts, portfolio diagnostics, and dynamic follow-up questions
- **ML Models** — LightGBM cross-sectional ranking (stock picking), Isolation Forest anomaly detection, K-Means style clustering, and GARCH(1,1) volatility modeling (`src/ml/`, see [docs/ML_MODELS.md](docs/ML_MODELS.md))
- **Web UI** — React + Vite + TypeScript frontend with ECharts, 12 tabs, red-up/green-down coloring, and a terminology dictionary

## 🚀 Quick Start

```bash
# 1. Install dependencies
uv sync --extra web

# 2. Run ETL to compute technical indicators
make etl

# 3. Start the web interface (backend :8001 + frontend :3000, hot reload)
make dev
# → open http://localhost:3000
```

> For the **AI tab**, configure the LLM in `.env` (see [LLM Configuration](#llm-configuration)). Without credentials the other tabs still work.

## 🐳 Docker

Two modes depending on your repository layout:

| Layout | Files | Build context |
|---|---|---|
| monorepo (root has `pyproject.toml` / `uv.lock` / `libs/`) | `docker-compose.yml` + `Dockerfile` | `../..` |
| **this repo cloned alone** | `docker-compose.standalone.yml` + `Dockerfile.standalone` | `.` (repo root) |

```bash
cp .env.example .env                 # optional; without it there is just no LLM
# put stock_analysis.db / stock_klines.db under ./data/
docker compose -f docker-compose.standalone.yml up -d --build
# → http://127.0.0.1:18001
```

Two caveats:

- `data_tools/` (fetching / ETL helpers) is **not distributed**; the standalone image only carries a placeholder README, so there is no "fetch latest data" capability. Missing modules degrade to a "not ready" response, everything else works
- The default compose files are tuned for **private, local-only** deployment (auth off, update endpoints on). Before exposing it publicly, change `WEB_CHAT_TOKEN`, `AGENT_CHAT_PUBLIC`, `SETTINGS_REMOTE_ALLOW`, `WEB_ENABLE_UPDATE` per the ⚠️ block at the top of `docker-compose.yml`, and keep the `127.0.0.1:` port binding

## Web Interface

The dashboard has 11 tabs:

| Tab | Description |
|-----|-------------|
| 🤖 AI Stock Picking | Ask questions in natural language; read-only Text2SQL against real data, answers with charts + portfolio diagnosis + follow-up questions |
| 📋 Stock Data | Browse stocks, filter by market/date, view K-line details with multiple time ranges |
| 🔍 Signal Scan | Full-market signal scanning; includes a **Custom Rule** sub-tab to screen by technical + asset conditions |
| 📒 Paper Trading | Paper trading: record positions, get diagnostics, stop-loss/take-profit alerts, trade history |
| 📈 Market Analysis | Market timing + market breadth pulse charts |
| 📊 Strategy Backtesting | Backtest built-in strategies, view equity curve and risk metrics |
| 📦 Portfolio Analysis | Multi-strategy portfolio backtesting, correlation matrix, weight allocation |
| 🏭 Sector Rotation | Sector strength ranking and rotation signals |
| 🧠 ML Models | LightGBM ranking, Isolation Forest anomaly, K-Means clustering, GARCH volatility |
| 📖 Glossary | A-share/indicator glossary with search |
| ⚙️ Settings | Configure the LLM model at runtime (saved to `data/llm_settings.json`) |

### LLM Configuration

Copy `.env.example` to `.env` and fill in the model credentials:

```ini
WEB_PORT=8001
VITE_PORT=3000

LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-key
LLM_MODEL=gpt-4o-mini
```

Precedence: runtime settings tab → project-root `.env` (already gitignored; credentials never leave the repo) → environment variables.

### Security

The AI agent is restricted to **read-only** queries:

- Database opened with `mode=ro`
- SQL validated against a read-only allowlist (blocks writes, dangerous functions, multiple statements, oversized `LIMIT`)
- Results capped at 200 rows

**Agent chat endpoint (`/api/agent/chat`) access control** — three modes, pick one:

| Mode | Config | Behavior |
|---|---|---|
| Local / loopback | (default) | Requests from `127.0.0.1`/`::1` are always allowed. |
| Public demo | `AGENT_CHAT_PUBLIC=1` (no `WEB_CHAT_TOKEN`) | Non-loopback requests allowed **without** a token. Interface is read-only SQL only — safe for public demos. This is what the hosted demo uses. |
| Token-protected | `WEB_CHAT_TOKEN=<secret>` (no `AGENT_CHAT_PUBLIC`) | Non-loopback requests require `Authorization: Bearer <secret>`. Frontend: click the "设置访问令牌（可选）" ("Access token (optional)") button in the AI chat panel and paste the same value. |

Generate a token:

```bash
openssl rand -hex 32
# or
python -c "import secrets; print(secrets.token_hex(32))"
```

Setting both `WEB_CHAT_TOKEN` and `AGENT_CHAT_PUBLIC=1`: token takes precedence for non-loopback (Bearer still checked); loopback is always allowed. If you run your own deployment and want real LLM answers (free-form Q&A / portfolio diagnosis) instead of the read-only SQL fallback, set `LLM_API_KEY` (+ `LLM_BASE_URL`/`LLM_MODEL`) **and** `WEB_CHAT_TOKEN`, then remove `AGENT_CHAT_PUBLIC`.

**Hosted demo compute guard (`DEMO_READONLY=1`)** — the free demo instance has 0.1 vCPU, so every expensive endpoint that can be re-triggered anonymously is throttled or disabled:

| Behavior | Endpoints |
|---|---|
| `refresh=true` rejected | `/api/scan`, `/api/backtest`, `/api/portfolio`, `/api/sector`, `/api/market-timing`, `/api/ml/anomaly`, `/api/ml/cluster` |
| Blocked entirely (403) | `/api/optimize`, `/api/ml/gbm/train`, `/api/asset/refresh` |
| Per-IP sliding-window limit (429) | `/api/scan` 6/min, `/api/backtest` 4/min, `/api/portfolio` 4/min |

Unset it for local/private deployments — every guard becomes a no-op.

## Project Structure

```
stock-analyzer/
├── data/                       # Data directory
│   ├── stock_klines.db         # Raw daily K-line data (source)
│   ├── stock_analysis.db       # Analysis DB (~7M rows, 51 indicators)
│   ├── asset_snapshot.db       # Market-wide asset snapshot (mkt cap / valuation)
│   ├── stock_info_cache.json   # Stock name ↔ code cache
│   ├── cache/                  # Slow-API result cache (auto-cleaned after 14 days)
│   ├── paper_portfolio.json    # Paper trading portfolio
│   └── llm_settings.json       # Runtime LLM overrides (from settings tab)
├── frontend/                   # React + Vite + TS web UI
│   └── src/components/         # 10 tab panels
├── output/                     # Reports & charts
├── scripts/                    # strategy mining / param sweep / demo scripts
├── src/                        # Source code
│   ├── agent/                  # Text2SQL: llm, sqlsafety, schema, pipeline, portfolio
│   ├── data/                   # fetcher, stock_info, asset snapshot, sync_env
│   ├── etl/                    # ETL pipeline
│   ├── ml/                     # LightGBM rank, Isolation Forest, K-Means, GARCH
│   ├── scanner/                # signals, screener, monitor, accuracy
│   ├── strategy/               # backtest, timing, sector rotation, portfolio, risk
│   ├── web/                    # FastAPI, api_cache, paper_trading
│   └── main.py                 # CLI entry point
├── tests/                      # pytest suite
├── Makefile                    # Common tasks (make dev / etl …)
├── pyproject.toml
└── README.md
```

Database schema (table structures) is documented in [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md); the database files are not distributed with the repo. ML model methodology is in [docs/ML_MODELS.md](docs/ML_MODELS.md).

## CLI / Make Commands

```bash
make etl              # incremental ETL (computes indicators)
make scan             # full-market signal scan
make backtest / optimize / compare / sector / portfolio   # strategy work
make paper-auto       # strategy-driven paper trading: signals → next-day-open fills, stops/take-profit
make ml-gbm           # LightGBM cross-sectional rank model (needs `uv sync --extra ml`)
make ml-walkforward   # rolling out-of-sample: retrain every N days + per-period IC + bootstrap
make universe         # rebuild code_lifecycle (point-in-time universe) + survivorship report
make ml-anomaly       # Isolation Forest anomaly detection
make ml-cluster       # K-Means clustering
make ml-garch CODE=600000   # GARCH(1,1) volatility model for one stock
make daily-update     # daily incremental update + ML sweep (anomaly+cluster) + DingTalk push
make daily-update-ml  # daily update + full LightGBM retrain (heavier)
make dev              # backend :8001 + frontend :3000 with hot reload, Ctrl+C stops both
make web-build        # build frontend into src/web/static (served by FastAPI)
make web-public       # build + serve on 0.0.0.0
make check-coverage   # verify today's coverage (source vs prior trading day's code set)
make check-gaps       # scan per-stock history holes (>=10 consecutive missing days)
make build-factors    # build ratio adjustment factors (dividends/splits, for backtests)
make test             # run the full pytest suite
```

## Related Articles
- [51 Indicators × 5000 Stocks: Engineering Practices for Full-Market Technical Scanning](https://erishen.cn/stock_analyzer-en/)

## License

MIT (see [LICENSE](LICENSE)). Third-party dependency licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).


MIT
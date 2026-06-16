# Stock Analyzer

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A stock market technical analysis tool — scans 5000+ A-share stocks for trading signals, with ETL pipeline, backtesting, and web dashboard.

## ⚠️ Disclaimer

This project is for educational and research purposes only. Not financial advice.

- All technical indicators and signals are for reference only
- Stock market investment carries risk
- Do not use this tool for actual trading decisions
- Author is not responsible for any losses

## ✨ Features

- **ETL Pipeline** — Extract, transform, load raw K-line data with 51 technical indicators
- **Signal Scanner** — Scan 5000+ stocks for technical signals
- **Strategy Backtesting** — Validate signal effectiveness
- **Market Timing** — Trend analysis and position sizing
- **Web UI** — React frontend with ECharts visualization
- **Technical Indicators** — MA, MACD, RSI, KDJ, BOLL, ATR, and more

## 📊 Backtest Results

| Metric | Value |
|--------|-------|
| Annualized Return | 57.37% |
| Max Drawdown | 7.71% |
| Win Rate | 80.91% |
| Sharpe Ratio | 5.92 |

> Backtest period: 2023-01-01 ~ 2024-12-31

## Project Structure

```
stock-analyzer/
├── data/                       # Data directory
│   ├── asset_lens.db           # Source DB (raw K-line)
│   ├── stock_analysis.db       # Analysis DB (with indicators)
│   └── stock_info_cache.json   # Stock name cache
├── output/                     # Output directory
│   ├── scan_result.json        # Scan results
│   └── *.png                   # Charts
├── src/                        # Source code
│   ├── data/                   # Data module
│   │   └── stock_info.py       # Stock info fetcher
│   ├── etl/                    # ETL module
│   │   └── pipeline.py         # Data pipeline
│   ├── scanner/                # Scanner module
│   │   └── signals.py          # Signal detection
│   ├── web/                    # Web UI
│   │   └── api.py              # FastAPI server
│   ├── strategy/               # Strategy module
│   ├── analyze_stocks.py       # Stock analyzer
│   └── main.py                 # CLI entry point
├── scripts/
│   └── seed_demo.py            # Demo data generator
├── render.yaml                 # Render deploy config
├── pyproject.toml
└── README.md
```

## Installation

```bash
git clone https://github.com/erishen/stock-analyzer.git
cd stock-analyzer

# Install with uv
uv sync

# Install web extras (optional)
uv sync --extra web
```

## 🚀 Quick Start

```bash
# 1. Generate demo data (12 stocks, 200 days)
uv run python scripts/seed_demo.py

# 2. Launch web UI
uv run stock-analyzer web --port 8082

# 3. Open http://localhost:8082
```

Or use the live demo: https://stock-analyzer-demo.onrender.com

## Usage

### ETL Pipeline

```bash
# Run full ETL
uv run python -m src.main etl

# Process specific stocks
uv run python -m src.main etl --codes sh600519,sh600036
```

### Signal Scanning

```bash
# Full market scan
uv run python -m src.main scan

# Filter by signal type
uv run python -m src.main scan --type "MACD金叉"

# Minimum score threshold
uv run python -m src.main scan --min-score 50

# Save to JSON
uv run python -m src.main scan --output output/scan_result.json
```

### Web UI

```bash
uv run stock-analyzer web --port 8082
```

## Signal Types

| Signal | Description | Condition |
|--------|-------------|-----------|
| MACD Golden Cross | Bullish | MACD crosses above signal line |
| MACD Death Cross | Bearish | MACD crosses below signal line |
| KDJ Golden Cross | Bullish | K line crosses above D line |
| KDJ Death Cross | Bearish | K line crosses below D line |
| MA5 Cross MA20 | Bullish | Short MA crosses above long MA |
| MA5 Cross MA20↓ | Bearish | Short MA crosses below long MA |
| RSI Oversold | Bullish | RSI < 30 |
| RSI Overbought | Bearish | RSI > 70 |
| Breakout Upper Boll | Strong | Price breaks above upper band |
| Breakout Lower Boll | Weak | Price breaks below lower band |
| Volume Surge | Watch | Volume ratio > 2 |
| Uptrend | Bullish | MA5 > MA10 > MA20 |
| Downtrend | Bearish | MA5 < MA10 < MA20 |

## Technical Indicators (51)

| Category | Indicators |
|----------|------------|
| Moving Averages | MA5, MA10, MA20, MA60 |
| Exponential MA | EMA12, EMA26 |
| MACD | MACD, Signal, Hist, Cross |
| RSI | RSI, Oversold, Overbought |
| Bollinger Bands | Upper, Lower, Mid, Width, Position |
| KDJ | K, D, J, RSV, Cross |
| ATR | ATR, ATR Ratio |
| OBV | OBV, OBV MA10, Signal |
| Williams | Williams %R, Oversold, Overbought |
| Momentum | Momentum 5d/10d/20d, ROC |
| Volatility | Volatility 5d/10d/20d |
| Price | High/Low Ratio, Body Size, Shadows |

## Data Sources

This project uses [AkShare](https://github.com/akfamily/akshare) as data source:

- ✅ **Open source** — no paid subscription needed
- ✅ **No API key** — install and use
- ✅ **Full A-share market** — 5000+ stocks
- ✅ **Local storage** — SQLite, offline capable

### Online Fetch (Recommended)

```bash
# Fetch specific stocks
python -m src.main fetch --codes 000001,600519,000858

# Fetch sample (10 stocks)
make fetch-sample

# Fetch full market (5000+ stocks)
make fetch
```

### External Database

```bash
export SYNC_DB_SOURCE=/path/to/stock_data.db
python -m src.main sync --source /path/to/stock_data.db
```

## License

MIT

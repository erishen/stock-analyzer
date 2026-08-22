# Stock Analyzer

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A 股市场分析工具集 —— 面向日线 K 线的 ETL 数据管道、全市场技术信号扫描、策略回测，以及一个集成 AI 选股助手（Text2SQL）的 React + FastAPI Web 仪表盘。

## ⚠️ 免责声明

本项目仅供技术学习和研究使用，不构成任何投资建议。

- 所有技术指标、信号和 AI 回答仅供参考，不保证准确性
- 股市有风险，投资需谨慎，请勿将本工具用于实际投资决策
- 作者不对使用本工具造成的任何损失负责

## ✨ 功能特点

- **ETL 数据管道** — 摄取原始日线 K 线数据并计算 51 个技术指标，采用真正的增量窗口（只重算近期数据，写入量减少约 6 倍）
- **信号扫描器** — 全市场技术信号检测，支持可配置的分数阈值
- **自定义规则选股** — 基于 70+ 个技术与资产字段（市值、流通市值、市盈率、市净率、量比…）做 AND 组合条件筛选全市场
- **资产快照** — 全市场市值 / 股本 / 估值字段独立存储（`asset_snapshot.db`），支持基于资产的筛选
- **策略回测与优化** — 多种内置策略，含风险指标与参数扫描
- **市场分析** — 大盘择时（牛 / 熊 / 震荡）、市场广度脉搏图、行业轮动
- **模拟交易** — 模拟持仓：记录仓位，基于 MA/MACD/RSI 的持仓诊断、止损 / 止盈提醒、交易历史
- **🤖 AI 选股** — 用自然语言提问，系统对真实数据运行只读 Text2SQL 数据管道，并以图表、持仓诊断和动态追问给出回答
- **Web 界面** — React + Vite + TypeScript 前端，基于 ECharts，共 10 个 Tab，红涨绿跌配色，含术语字典

## 🚀 快速开始

```bash
# 1. 安装依赖
uv sync --extra web

# 2. 运行 ETL，计算技术指标
make etl

# 3. 启动 Web 界面 (后端 :8001 + 前端 :3000，热更新)
make dev
# → 打开 http://localhost:3000
```

> 使用 **AI 选股** Tab 需在 `.env` 中配置 LLM（见 [LLM 配置](#llm-配置)）。未配置凭据时，其他 Tab 仍可正常使用。

## Web 界面

仪表盘共 10 个 Tab：

| Tab | 说明 |
|-----|------|
| 🤖 AI 选股 | 自然语言提问，对真实数据执行只读 Text2SQL，以图表 + 持仓诊断 + 追问的方式回答 |
| 📋 股票数据 | 浏览股票，按市场 / 日期筛选，查看多时间周期的 K 线详情 |
| 🔍 信号扫描 | 全市场信号扫描；内置 **自定义规则** 子页面，可按技术指标 + 资产字段组合筛选 |
| 📒 模拟仓 | 模拟交易：记录仓位、持仓诊断、止损 / 止盈提醒、交易历史 |
| 📈 市场分析 | 大盘择时 + 市场广度脉搏图 |
| 📊 策略回测 | 回测内置策略，查看资金曲线与风险指标 |
| 📦 组合分析 | 多策略组合回测、相关性矩阵、权重配置 |
| 🏭 行业轮动 | 行业强度排名与轮动信号 |
| 📖 术语字典 | A 股 / 指标术语词典，支持搜索 |
| ⚙️ 设置 | 运行时配置 LLM 模型（保存到 `data/llm_settings.json`） |

### LLM 配置

复制 `.env.example` 为 `.env` 并填写模型凭据：

```ini
WEB_PORT=8001
VITE_PORT=3000

LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-key
LLM_MODEL=gpt-4o-mini
```

配置优先级：运行时设置 Tab → `stock-analyzer/.env` → `invest-kit/work/harness/datapulse/.env` → 环境变量。

### 安全机制

AI 智能体被限制为 **只读** 查询：

- 数据库以 `mode=ro` 只读方式打开
- SQL 经过只读白名单校验（拦截写操作、危险函数、多条语句、过大的 `LIMIT`）
- 结果最多返回 200 行

## 项目结构

```
stock-analyzer/
├── data/                       # 数据目录
│   ├── stock_klines.db         # 原始日线 K 线数据 (源库)
│   ├── stock_analysis.db       # 分析数据库 (~700 万行，51 个指标)
│   ├── asset_snapshot.db       # 全市场资产快照 (市值 / 估值)
│   ├── stock_info_cache.json   # 股票名称 ↔ 代码缓存
│   ├── cache/                  # 慢接口结果缓存 (14 天后自动清理)
│   ├── paper_portfolio.json    # 模拟交易持仓
│   └── llm_settings.json       # 运行时 LLM 配置覆盖 (设置 Tab)
├── frontend/                   # React + Vite + TS Web 界面
│   └── src/components/         # 10 个 Tab 面板
├── output/                     # 报告与图表
├── scripts/                    # 策略挖掘 / 参数扫描 / 演示数据脚本
├── src/                        # 源代码
│   ├── agent/                  # Text2SQL: llm、sqlsafety、schema、pipeline、portfolio
│   ├── data/                   # fetcher、stock_info、资产快照、sync_env
│   ├── etl/                    # ETL 数据管道
│   ├── scanner/                # signals、screener、monitor、accuracy
│   ├── strategy/               # backtest、timing、行业轮动、portfolio、risk
│   ├── web/                    # FastAPI、api_cache、paper_trading
│   └── main.py                 # CLI 入口
├── tests/                      # pytest 测试套件
├── Makefile                    # 常用任务 (make dev / etl …)
├── pyproject.toml
└── README.md
```

数据库 Schema（表结构）见 [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)；数据库本体不随仓库分发。

## CLI / Make 命令

```bash
make etl              # 增量 ETL (计算指标)
make scan             # 全市场信号扫描
make backtest / optimize / compare / sector / portfolio   # 策略相关
make dev              # 后端 :8001 + 前端 :3000，热更新，Ctrl+C 同时停止
make web-build        # 构建前端到 src/web/static (由 FastAPI 托管)
make web-public       # 构建并在 0.0.0.0 提供服务
make test             # 运行完整 pytest 测试套件
```

## License

MIT
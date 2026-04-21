# Stock Analyzer

股票数据分析工具 - 扫描全市场技术信号，发现交易机会

## ⚠️ 免责声明

本项目仅供技术学习和研究使用，不构成任何投资建议。

- 所有技术指标和信号仅供参考，不保证准确性
- 股市有风险，投资需谨慎
- 请勿将本工具用于实际投资决策
- 作者不对使用本工具造成的任何损失负责

## 功能特点

- **ETL 数据管道**: 从原始 K 线数据提取、转换、加载，计算 51 个技术指标
- **信号扫描器**: 扫描全市场 5000+ 股票，发现技术信号
- **技术指标计算**: MA、MACD、RSI、KDJ、BOLL、ATR 等
- **可视化分析**: 价格趋势图、成交量图、信号分布图

## 项目结构

```
stock-analyzer/
├── data/                       # 数据目录
│   ├── asset_lens.db           # 源数据库 (原始 K 线)
│   ├── stock_analysis.db       # 分析数据库 (含技术指标)
│   └── stock_info_cache.json   # 股票名称缓存
├── output/                     # 输出目录
│   ├── scan_result.json        # 扫描结果
│   └── *.png                   # 图表文件
├── src/                        # 源代码
│   ├── data/                   # 数据模块
│   │   └── stock_info.py       # 股票信息获取
│   ├── etl/                    # ETL 模块
│   │   └── pipeline.py         # 数据管道
│   ├── scanner/                # 扫描器模块
│   │   └── signals.py          # 信号检测
│   ├── analyze_stocks.py       # 股票分析器
│   └── main.py                 # CLI 入口
├── pyproject.toml              # 项目配置
└── README.md                   # 说明文档
```

## 安装

```bash
# 使用 uv 安装依赖
cd stock-analyzer
uv sync
```

## 使用方法

### ETL 数据管道

```bash
# 运行完整 ETL (处理所有股票)
uv run python -m src.main etl

# 指定股票处理
uv run python -m src.main etl --codes sh600519,sh600036
```

### 信号扫描

```bash
# 全市场扫描
uv run python -m src.main scan

# 筛选特定信号
uv run python -m src.main scan --type "MACD金叉"

# 只显示高分信号
uv run python -m src.main scan --min-score 50

# 保存结果到 JSON
uv run python -m src.main scan --output output/scan_result.json
```

### 数据统计

```bash
# 显示数据统计信息
uv run python -m src.main stats
```

### 股票分析

```bash
# 运行基础分析
uv run python -m src.main analyze
```

## 信号类型

| 信号类型 | 说明 | 条件 |
|----------|------|------|
| MACD金叉 | 看涨 | MACD 上穿信号线 |
| MACD死叉 | 看跌 | MACD 下穿信号线 |
| KDJ金叉 | 看涨 | K 线上穿 D 线 |
| KDJ死叉 | 看跌 | K 线下穿 D 线 |
| MA5上穿MA20 | 看涨 | 短期均线上穿 |
| MA5下穿MA20 | 看跌 | 短期均线下穿 |
| RSI超卖 | 看涨 | RSI < 30 |
| RSI超买 | 看跌 | RSI > 70 |
| 突破布林上轨 | 强势 | 价格突破上轨 |
| 跌破布林下轨 | 弱势 | 价格跌破下轨 |
| 成交量异动 | 关注 | 量比 > 2 |
| 上升趋势 | 看涨 | MA5 > MA10 > MA20 |
| 下降趋势 | 看跌 | MA5 < MA10 < MA20 |

## 技术指标 (51个)

| 类别 | 指标 |
|------|------|
| 均线 | MA5, MA10, MA20, MA60 |
| 指数均线 | EMA12, EMA26 |
| MACD | MACD, Signal, Hist, Cross |
| RSI | RSI, Oversold, Overbought |
| 布林带 | Upper, Lower, Mid, Width, Position |
| KDJ | K, D, J, RSV, Cross |
| ATR | ATR, ATR Ratio |
| OBV | OBV, OBV MA10, Signal |
| 威廉 | Williams %R, Oversold, Overbought |
| 动量 | Momentum 5d/10d/20d, ROC |
| 波动 | Volatility 5d/10d/20d |
| 价格 | High/Low Ratio, Body Size, Shadows |

## 数据库结构

### stock_analysis 表

| 字段 | 类型 | 说明 |
|------|------|------|
| code | TEXT | 股票代码 |
| date | TEXT | 日期 |
| open | REAL | 开盘价 |
| close | REAL | 收盘价 |
| high | REAL | 最高价 |
| low | REAL | 最低价 |
| volume | REAL | 成交量 |
| amount | REAL | 成交额 |
| ma5/ma10/ma20/ma60 | REAL | 移动平均线 |
| macd/macd_signal | REAL | MACD 指标 |
| rsi | REAL | RSI 指标 |
| kdj_k/kdj_d/kdj_j | REAL | KDJ 指标 |
| boll_upper/boll_lower | REAL | 布林带 |
| ... | ... | 其他技术指标 |

## 作为模块使用

```python
from pathlib import Path
from src.scanner import run_scan, SignalType
from src.etl import run_etl

# 运行 ETL
result = run_etl(
    source_db=Path("data/asset_lens.db"),
    target_db=Path("data/stock_analysis.db")
)
print(f"处理了 {result.stocks_processed} 只股票")

# 运行扫描
scan_result = run_scan(
    db_path=Path("data/stock_analysis.db"),
    min_score=50
)

for signal in scan_result.top_signals:
    print(f"{signal.code} {signal.name}: {signal.signal_type.value}")
```

## 依赖

- Python >= 3.13
- pandas
- numpy
- matplotlib
- akshare (股票信息获取)

## 数据源

本项目使用 [AkShare](https://github.com/akfamily/akshare) 作为数据源：

- ✅ **开源免费** - 无需付费订阅
- ✅ **无需 API Key** - 安装即可使用
- ✅ **A 股全市场** - 支持 5000+ 股票
- ✅ **本地存储** - 数据存储在本地 SQLite，离线可用

### 方式 1: 在线获取 (推荐)

使用 `fetch` 命令从 AkShare 获取 A 股 K 线数据（免费，无需 API Key）：

```bash
# 获取指定股票
python -m src.main fetch --codes 000001,600519,000858

# 获取样本数据 (10只股票)
make fetch-sample

# 获取全市场数据 (约 5000+ 只股票，需要较长时间)
make fetch
```

数据将保存到 `data/stock_klines.db`。

### 方式 2: 外部数据库

如果你已有股票数据库，可以同步过来：

```bash
# 设置环境变量
export SYNC_DB_SOURCE=/path/to/stock_data.db

# 或通过命令行
python -m src.main sync --source /path/to/stock_data.db
```

数据库表结构要求：

```sql
CREATE TABLE stock_klines (
    code TEXT,        -- 股票代码
    date TEXT,        -- 日期
    open REAL,        -- 开盘价
    close REAL,       -- 收盘价
    high REAL,        -- 最高价
    low REAL,         -- 最低价
    volume REAL,      -- 成交量
    amount REAL       -- 成交额
);
```

### 方式 3: 股票信息缓存

```bash
# 刷新股票名称缓存
python -m src.main refresh-names
```

## License

MIT

# 数据库 Schema / Database Schema

数据库本体**不随仓库分发**，请按下列表结构自行接入数据源或生成兼容数据。
The database files themselves are **not** distributed with the repo. Use the table structures below to plug in your own data source or generate compatible data.

---

## `data/stock_klines.db` — 原始日线 K 线（源库）/ Raw daily K-line (source DB)

表 `stock_klines`（`code, date` 唯一）。Table `stock_klines` (unique on `code, date`):

| 字段 Column | 类型 Type | 说明 Description |
|---|---|---|
| id | INTEGER | 自增主键 / Auto-increment primary key |
| code | TEXT NOT NULL | 股票代码（6 位数字，如 `000001`）/ Stock code (6 digits) |
| date | TEXT NOT NULL | 交易日期 `YYYY-MM-DD` / Trading date |
| open / close / high / low | REAL | 开 / 收 / 高 / 低价 / Open / close / high / low |
| volume | REAL | 成交量 / Volume |
| amount | REAL | 成交额 / Turnover amount |
| amplitude | REAL | 振幅（%）/ Amplitude (%) |
| change_percent | REAL | 涨跌幅（%）/ Change (%) |
| change_amount | REAL | 涨跌额 / Price change |
| turnover_rate | REAL | 换手率（%）/ Turnover rate (%) |
| created_at | TEXT | 入库时间 / Ingestion timestamp |

索引 Indexes：`idx_klines_code`、`idx_klines_date`、`idx_klines_code_date`。

---

## `data/stock_analysis.db` — 分析库（ETL 产物） / Analysis DB (ETL output)

表 `stock_analysis`（`code, date` 唯一）：在 `stock_klines` 全部字段基础上追加技术指标。
Table `stock_analysis` (unique on `code, date`): all `stock_klines` columns plus technical indicators.

| 字段组 Group | 字段 Columns |
|---|---|
| 均线 Moving averages | ma5 / ma10 / ma20 / ma60，close_ma5_ratio / close_ma10_ratio / close_ma20_ratio / close_ma60_ratio |
| MACD | ema12 / ema26，macd，macd_signal，macd_hist，macd_cross |
| RSI | rsi，rsi_oversold，rsi_overbought |
| 布林带 Bollinger | boll_mid / boll_std / boll_upper / boll_lower / boll_width / boll_position |
| KDJ | kdj_rsv / kdj_k / kdj_d / kdj_j / kdj_cross |
| ATR | atr，atr_ratio |
| OBV | obv，obv_ma10，obv_signal |
| Williams | williams_r，williams_oversold，williams_overbought |
| 动量 Momentum | momentum_5d / momentum_10d / momentum_20d，roc_10 / roc_20，pct_change |
| 波动 Volatility | volatility_5d / volatility_10d / volatility_20d，volatility_ratio |
| K 线形态 Candle patterns | high_low_ratio，close_open_ratio，upper_shadow，lower_shadow，body_size |

另有 `etl_logs` 表记录每次 ETL 运行统计（处理股票数、拉取/转换/写入条数、错误、耗时）。
There is also an `etl_logs` table recording per-run ETL stats (stocks processed, rows extracted/transformed/loaded, errors, duration).

---

## `data/asset_snapshot.db` — 全市场资产快照 / Market-wide asset snapshot

表 `asset_snapshot`。Table `asset_snapshot`:

| 字段 Column | 说明 Description |
|---|---|
| code（主键 PK） | 6 位股票代码 / 6-digit stock code |
| name | 股票名称 / Stock name |
| close / change_percent | 收盘价 / 涨跌幅 / Close / change (%) |
| volume / amount / volume_ratio / turnover_rate | 量能类字段 / Volume-related fields |
| total_market_value / float_market_value | 总市值 / 流通市值 / Total / float market value |
| total_shares / float_shares | 总股本 / 流通股本 / Total / float shares |
| pe / pb | 市盈率 / 市净率 / P/E / P/B |
| updated_at | 更新时间 / Last update time |
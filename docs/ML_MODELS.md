# ML 模型 / ML Models

`src/ml/` 提供四类可复用模型，统一从 `stock_analysis.db` 取数（复用 51 指标分析库），
安装依赖：`uv sync --extra ml`。

| 模块 | 模型 | 用途 | 依赖 |
|---|---|---|---|
| `gbm_rank` | LightGBM 横截面排名 | 选股排序（未来收益排名预测） | lightgbm |
| `anomaly` | Isolation Forest | 指标画像异常股检测 | scikit-learn |
| `clustering` | K-Means | 按指标画像聚类（风格/板块识别） | scikit-learn |
| `volatility` | GARCH(1,1) | 条件波动率估计与预测 | arch |

公共工具在 `common.py`（数据加载、横截面排名归一化、ST/低价过滤、日度 RankIC、代码解析）。

## 方法论 / Methodology

### LightGBM 排名（`ml-gbm`）
- 样本：每股每日一条记录，特征为技术指标（横截面排名归一化，消除量纲与市场状态）
- 目标：未来 `--horizon` 日收益的当日横截面排名（百分位）——关心选股排序而非点值
- 切分：train / valid / test 完全样本外，尾部各留 ~1 个月 embargo 防目标泄漏
- 早停：以 valid 集日度 RankIC 为目标（直接优化关心的指标）
- 评估：日度 RankIC（均值 / ICIR / t 值 / 正率）、十分位组合单调性、Top-N 含费回测 vs 随机 / 等权

### Isolation Forest 异常检测（`ml-anomaly`）
- 样本：某交易日全市场横截面，特征为技术指标（横截面排名归一化）
- 模型：`sklearn.ensemble.IsolationForest`（默认 contamination 1%，即尾部 ~1% 视为异常）
- 输出：每只股票异常分数 + 判定标签（`-1`=异常，`1`=正常）+ 归一化异常度（0~100）

### K-Means 聚类（`ml-cluster`）
- 样本：某交易日全市场横截面，特征为技术指标（横截面排名归一化 + StandardScaler）
- 模型：`sklearn.cluster.KMeans`（默认 k=6；`--auto-k` 按轮廓系数在 3~10 自动选 k）
- 输出：每簇画像（相对全市场 z-score）、规模占比、代表个股

### GARCH 波动率（`ml-garch`）
- 输入：单股日对数收益序列（最近 `--window` 个交易日）
- 模型：`arch.arch_model(returns*100, vol='GARCH', p=1, q=1)`（乘 100 改善数值稳定性）
- 输出：参数（ω / α / β / 持续性）、当前条件波动率、未来 `--horizon` 日预测、年化波动率，
  并与 30 日已实现波动率对比；另存图表 `output/charts/ml_garch_<code>.png`

## 已知局限 / Known limitations

- ST 过滤基于当前名称，历史上 ST 状态变化无法回溯
- 中途退市股票按最后可得收盘价退出（实际退市损失可能更大）
- 无滑点假设，实盘 Top-N 组合冲击成本会更高
- 以上均为研究/模拟用途，不构成投资建议

## 运行 / Commands

```bash
make ml-gbm          # LightGBM 排名模型（默认 2020~2026 全量，较重）
make ml-anomaly      # Isolation Forest 异常检测（最新交易日）
make ml-cluster      # K-Means 聚类（最新交易日）
make ml-garch CODE=600000   # GARCH 单股（需传 CODE）

# 等价 CLI（可带更多参数）
uv run python -m src.main ml-gbm --start-year 2023 --end-year 2025 --top-n 10
uv run python -m src.main ml-anomaly --contamination 0.01 --top-n 20
uv run python -m src.main ml-cluster --k 5
uv run python -m src.main ml-garch --code 600000 --window 300 --horizon 5
```

输出：`output/reports/ml_*_report.json`（GARCH 另存 `output/charts/ml_garch_<code>.png`）。

## Web 界面集成 / Web panel

前端「🧠 ML 模型」Tab（共 11 个 Tab）调用后端接口：

| 接口 | 说明 |
|---|---|
| `GET /api/ml/status` | ML 依赖可用性（lightgbm / sklearn / arch） |
| `GET /api/ml/anomaly?refresh=` | Isolation Forest 异常检测（结果缓存） |
| `GET /api/ml/cluster?k=6&refresh=` | K-Means 聚类（结果缓存） |
| `GET /api/ml/garch?code=&window=&horizon=` | GARCH 单股波动率 + 条件波动率序列 |
| `GET /api/ml/gbm` | 读取最近一次 `make ml-gbm` 的训练报告（只读，不触发在线训练） |
| `POST /api/ml/gbm/train` | 提交 LightGBM 训练（异步，**转发宿主** `web_trigger_server` 执行，返回状态） |
| `GET /api/ml/gbm/train/status/{task_id}` | 查询训练任务状态（透传宿主 `/ml-gbm/status`） |

> **训练为何走宿主执行**：容器内数据经 Docker FUSE 只读挂载读 4.4GB 分析库，全量加载
> 内存峰值高（8G 限制内仍会卡死/被重启）。故训练转发宿主 19090 端口的
> `web_trigger_server`（复用「容器按钮→宿主执行」架构，同每日更新），宿主跑
> `python -m src.main ml-gbm --start-year X --end-year Y`，状态回传容器轮询。
> 宿主需保持 `web_trigger_server.py` 常驻（见 `data_tools/web_trigger_server.py` 用法）。
> UI 默认训练窗口为近 4 年（2022~2027，约 3 分钟），全量 2020 起更久但可选。

## 风控集成 / Risk integration

`src/strategy/risk_control.py` 新增波动率目标仓位管理：

- `PositionSizer.garch_volatility_targeting(weights, target_volatility, ...)` — 对每只持仓拟合
  GARCH 得未来 `horizon` 日条件波动率，按 `target/vol` 缩放权重、封顶 `max_single_position_pct`；
  超配时才向下归一化（保留现金尊重封顶）。单股拟合失败或 `arch` 缺失时该股保留原权重，不阻断。
- `garch_volatility_sizing_report(weights, target_volatility, ...)` — 返回逐股波动率与建议权重详情
  （供 CLI / Web 展示）。

## 每日巡检集成 / Daily routine

`data_tools/daily_update.py` 新增 `--ml`（快速：异常检测 + 聚类）与 `--ml-gbm`（重型：LightGBM
全量训练）两个开关，结果写入当日报告 `report["ml"]`，任一失败只记录不阻断主流程。

```bash
make daily-update        # 每日更新 + ML 巡检(异常+聚类) + 钉钉推送
make daily-update-ml     # 每日更新 + LightGBM 全量训练(较重)
```


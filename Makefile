.PHONY: help install deps sync-env fetch fetch-sample etl scan visualize analyze accuracy score monitor trade-report export market-timing compare sector sector-validate portfolio portfolio-sharpe web dev web-dev web-build web-public backtest backtest-momentum backtest-reversion backtest-trend backtest-multifactor backtest-optimized backtest-viz backtest-full backtest-benchmark optimize optimize-momentum optimize-reversion db-optimize stats test test-cov lint format clean

help:
	@echo "Stock Analyzer - 股票数据分析工具"
	@echo ""
	@echo "使用方法: make [命令]"
	@echo ""
	@echo "命令:"
	@echo "  install     安装依赖"
	@echo "  deps        同步依赖"
	@echo "  fetch       获取股票 K 线数据 (全市场, 同时自动刷新资产快照)"
	@echo "  fetch-sample 获取样本数据 (10只股票)"
	@echo "  fetch-codes 获取指定股票数据"
	@echo "  asset-snapshot 拉取并更新全市场资产快照 (市值/股本/估值)"
	@echo "  sync-env    从外部项目同步环境变量"
	@echo "  refresh-names 刷新股票名称缓存"
	@echo "  etl         运行 ETL 数据管道"
	@echo "  scan        全市场信号扫描"
	@echo "  monitor     市场实时监控"
	@echo "  visualize   生成可视化图表"
	@echo "  analyze     运行股票分析"
	@echo "  accuracy    信号准确率分析"
	@echo "  score       选股评分排名"
	@echo "  trade-report  交易报告生成"
	@echo "  export      数据导出 (CSV/JSON)"
	@echo "  market-timing   大盘择时分析"
	@echo "  compare     策略对比"
	@echo "  sector      行业轮动分析"
	@echo "  sector-validate  行业轮动验证"
	@echo "  portfolio   多策略组合回测"
	@echo "  portfolio-sharpe  夏普加权组合回测"
	@echo "  web         启动 Web 界面 (生产模式)"
	@echo "  dev         开发模式: 后端 + 前端 Vite 热更新 (Ctrl+C 一键停止)"
	@echo "  web-dev     启动 Web 界面 (开发模式，热更新)"
	@echo "  web-build   构建 React 前端"
	@echo "  web-public  启动 Web 界面 (公开访问)"
	@echo "  backtest    策略回测 (默认)"
	@echo "  backtest-momentum   动量策略回测"
	@echo "  backtest-reversion  均值回归策略回测"
	@echo "  backtest-trend      趋势跟踪策略回测"
	@echo "  backtest-multifactor 多因子策略回测"
	@echo "  backtest-optimized  优化参数回测"
	@echo "  backtest-viz        回测结果可视化"
	@echo "  backtest-full       回测+可视化"
	@echo "  backtest-benchmark  回测+基准对比"
	@echo "  optimize            策略参数优化"
	@echo "  optimize-momentum   动量策略参数优化"
	@echo "  optimize-reversion  均值回归策略参数优化"
	@echo "  db-optimize         数据库性能优化"
	@echo "  stats       显示数据统计"
	@echo "  test        运行测试"
	@echo "  test-cov    运行测试并生成覆盖率报告"
	@echo "  lint        运行代码检查"
	@echo "  format      格式化代码"
	@echo "  clean       清理缓存文件"

install:
	uv sync --extra dev --extra web

deps:
	uv sync

fetch:
	@echo "获取全市场股票 K 线数据..."
	@echo "警告: 这将需要较长时间 (约 5000+ 只股票)"
	uv run python -m src.main fetch

fetch-sample:
	@echo "获取样本数据 (10只股票)..."
	uv run python -m src.main fetch --limit 10

fetch-codes:
	@read -p "输入股票代码(逗号分隔): " codes; \
	uv run python -m src.main fetch --codes $$codes

asset-snapshot:
	@echo "拉取全市场资产快照 (市值/股本/估值)..."
	@echo "用法: make asset-snapshot   (东财优先, 限流自动回退腾讯)"
	@echo "      make asset-snapshot SOURCE=tencent   (强制腾讯源)"
	@echo "      make asset-snapshot SOURCE=eastmoney (强制东财源)"
	@if [ -n "$(SOURCE)" ]; then \
		uv run python -m src.main asset-snapshot --source $(SOURCE); \
	else \
		uv run python -m src.main asset-snapshot; \
	fi

sync-env:
	@echo "使用方法:"
	@echo "  make sync-env SOURCE=/path/to/.env"
	@echo "  或设置环境变量: export SYNC_ENV_SOURCE=/path/to/.env"
	@if [ -n "$(SOURCE)" ]; then \
		uv run python -m src.main sync-env --source $(SOURCE); \
	else \
		uv run python -m src.main sync-env; \
	fi

refresh-names:
	uv run python -m src.main refresh-names

etl:
	uv run python -m src.main etl

daily-update:
	@echo "每日增量更新: 活跃股票增量拉取 -> 增量 ETL -> 信号扫描"
	uv run python data_tools/daily_update.py

etl-codes:
	@read -p "输入股票代码(逗号分隔): " codes; \
	uv run python -m src.main etl --codes $$codes

scan:
	uv run python -m src.main scan --output output/reports/scan_result.json

scan-type:
	@read -p "输入信号类型: " signal_type; \
	uv run python -m src.main scan --type "$$signal_type" --output output/reports/scan_result.json

visualize:
	uv run python -m src.main visualize

analyze:
	uv run python -m src.main analyze

accuracy:
	uv run python -m src.main accuracy --output output/reports/accuracy_report.json

accuracy-10:
	uv run python -m src.main accuracy --holding-days 10 --output output/reports/accuracy_report_10d.json

score:
	uv run python -m src.main score --output output/reports/scoring_report.json

score-100:
	uv run python -m src.main score --top-n 100 --output output/reports/scoring_report_100.json

backtest:
	uv run python -m src.main backtest --output output/reports/backtest_report.json

backtest-momentum:
	uv run python -m src.main backtest --strategy momentum --lookback 20 --holding 5 --min-momentum 0.02 --max-momentum 0.5 --max-volatility 0.08 --min-price 3.0 --output output/reports/backtest_momentum.json

backtest-reversion:
	uv run python -m src.main backtest --strategy mean_reversion --holding 5 --min-price 3.0 --output output/reports/backtest_reversion.json

backtest-trend:
	uv run python -m src.main backtest --strategy trend_following --holding 5 --min-price 3.0 --output output/reports/backtest_trend.json

backtest-multifactor:
	uv run python -m src.main backtest --strategy multi_factor --holding 5 --min-price 3.0 --output output/reports/backtest_multifactor.json

backtest-optimized:
	uv run python -m src.main backtest --strategy momentum --lookback 10 --holding 3 --min-momentum 0.05 --max-momentum 0.3 --max-volatility 0.06 --min-price 5.0 --output output/reports/backtest_optimized.json

backtest-viz:
	uv run python -m src.main backtest-viz

backtest-full: backtest backtest-viz
	@echo "✅ 回测完成并生成可视化图表"

optimize:
	uv run python -m src.main optimize --output output/reports/optimization_report.json

optimize-momentum:
	uv run python -m src.main optimize --strategy momentum --output output/reports/optimization_momentum.json

optimize-reversion:
	uv run python -m src.main optimize --strategy mean_reversion --output output/reports/optimization_reversion.json

db-optimize:
	uv run python -m src.main db-optimize

backtest-benchmark:
	uv run python -m src.main backtest --strategy mean_reversion --holding 9 --benchmark

monitor:
	uv run python -m src.main monitor --output output/reports/market_monitor.json

trade-report:
	uv run python -m src.main trade-report --strategy mean_reversion --holding 9 --output output/reports/trade_report.json

export:
	uv run python -m src.main export --type trades --format csv --output-dir output/exports

market-timing:
	uv run python -m src.main market-timing

compare:
	uv run python -m src.main compare --holding 5 --output output/reports/strategy_comparison.json

sector:
	uv run python -m src.main sector --output output/reports/sector_rotation.json

sector-validate:
	uv run python -m src.main sector --validate

portfolio:
	uv run python -m src.main portfolio --holding 5 --output output/reports/portfolio_result.json

portfolio-sharpe:
	uv run python -m src.main portfolio --weight-method sharpe --holding 5 --output output/reports/portfolio_sharpe.json

portfolio-risk-parity:
	uv run python -m src.main portfolio --weight-method risk_parity --holding 5 --output output/reports/portfolio_risk_parity.json

web:
	uv sync --extra web
	cd frontend && npm install && npm run build
	uv run python -m src.main web

dev:
	@backend_port=$$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d ' '); \
	backend_port=$${backend_port:-8001}; \
	frontend_port=$$(grep -E '^VITE_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d ' '); \
	frontend_port=$${frontend_port:-3000}; \
	echo "开发模式: 后端 http://127.0.0.1:$$backend_port + 前端 http://localhost:$$frontend_port (热更新)"; \
	echo "Ctrl+C 一次性停止前后端"; \
	for port in $$backend_port $$frontend_port; do \
		pids=$$(lsof -ti :$$port 2>/dev/null); \
		if [ -n "$$pids" ]; then \
			echo "清理端口 $$port 上的残留进程 (PID: $$pids)"; \
			echo "$$pids" | xargs kill 2>/dev/null || true; \
		fi; \
	done; \
	sleep 1
	@uv sync --extra web >/dev/null 2>&1 || uv sync --extra web
	@cd frontend && npm install --silent 2>/dev/null || npm install
	@backend_port=$$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d ' '); \
	backend_port=$${backend_port:-8001}; \
	trap 'echo ""; echo "🛑 正在停止服务..."; bp=$$(grep -E "^WEB_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d " "); bp=$${bp:-8001}; fp=$$(grep -E "^VITE_PORT=" .env 2>/dev/null | cut -d= -f2 | tr -d " "); fp=$${fp:-3000}; for p in $$bp $$fp; do pids=$$(lsof -ti :$$p 2>/dev/null); if [ -n "$$pids" ]; then echo "清理端口 $$p (PID: $$pids)"; echo "$$pids" | xargs kill 2>/dev/null || true; fi; done; sleep 1; for p in $$bp $$fp; do pids=$$(lsof -ti :$$p 2>/dev/null); if [ -n "$$pids" ]; then echo "强制清理端口 $$p"; echo "$$pids" | xargs kill -9 2>/dev/null || true; fi; done' INT TERM EXIT; \
	echo "🚀 启动后端..."; \
	uv run python -m src.main web & \
	BACKEND_PID=$$!; \
	echo "⏳ 等待后端就绪 (http://127.0.0.1:$$backend_port)"; \
	ready=0; \
	for i in $$(seq 1 60); do \
		if curl -sf -m 3 -o /dev/null "http://127.0.0.1:$$backend_port/docs"; then ready=1; break; fi; \
		if ! kill -0 $$BACKEND_PID 2>/dev/null; then echo "❌ 后端启动失败"; break; fi; \
		sleep 1; \
	done; \
	if [ $$ready -eq 1 ]; then \
		echo "✅ 后端就绪, 启动前端..."; \
		cd frontend && npm run dev & \
		FRONTEND_PID=$$!; \
	else \
		echo "❌ 后端未就绪, 不启动前端"; \
		exit 1; \
	fi; \
	wait

web-dev:
	uv sync --extra web
	cd frontend && npm install && npm run dev &

web-build:
	cd frontend && npm install && npm run build

web-public:
	uv sync --extra web
	cd frontend && npm install && npm run build
	uv run python -m src.main web --host 0.0.0.0

stats:
	uv run python -m src.main stats

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov/ 2>/dev/null || true

all: install etl scan visualize
	@echo "✅ 全部完成！"

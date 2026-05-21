"""
Stock Analyzer - Main Entry Point
股票分析器主入口
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, OUTPUT_DIR, get_asset_lens_db_path, get_stock_analysis_db_path

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).parent.parent
CHARTS_DIR = OUTPUT_DIR / "charts"
REPORTS_DIR = OUTPUT_DIR / "reports"

CHARTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_etl(args):
    """运行 ETL 流程"""

    from etl import run_etl as etl_pipeline

    logger.info("\n" + "=" * 60)
    logger.info("📦 ETL 数据管道")
    logger.info("=" * 60)

    source_db = args.source_db if args.source_db else get_asset_lens_db_path()
    target_db = args.target_db if args.target_db else get_stock_analysis_db_path()

    stock_codes = args.codes.split(",") if args.codes else None

    result = etl_pipeline(source_db=source_db, target_db=target_db, stock_codes=stock_codes)

    if result.errors:
        logger.error(f"\n⚠️ 有 {len(result.errors)} 个错误:")
        for err in result.errors[:5]:
            logger.info(f"   - {err}")


def run_analyze(args):
    """运行分析"""

    from analyze_stocks import StockAnalyzer

    analyzer = StockAnalyzer()

    db_path = args.db if args.db else None
    if db_path:
        analyzer.db_path = db_path

    logger.info("\n" + "=" * 60)
    logger.info("📊 股票数据分析")
    logger.info("=" * 60)

    logger.info("\n加载数据中...")
    analyzer.load_data(limit=args.limit)

    logger.info("\n生成价格趋势图...")
    analyzer.plot_price_trend(top_n=args.top_n)

    logger.info("\n生成成交量趋势图...")
    analyzer.plot_volume_trend(top_n=args.top_n)

    logger.info("\n计算移动平均线...")
    analyzer.calculate_moving_average(window=20, top_n=args.top_n)

    logger.info(f"\n✅ 分析完成！图表已保存到 {OUTPUT_DIR}")


def run_stats(args):
    """显示统计信息"""
    import sqlite3

    db_path = args.db if args.db else get_stock_analysis_db_path()

    if not Path(db_path).exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    with sqlite3.connect(str(db_path)) as conn:
        logger.info("\n" + "=" * 60)
        logger.info("📈 数据统计")
        logger.info("=" * 60)

        cursor = conn.execute("""
            SELECT
                COUNT(DISTINCT code) as stock_count,
                COUNT(*) as total_records,
                MIN(date) as min_date,
                MAX(date) as max_date
            FROM stock_analysis
        """)
        row = cursor.fetchone()
        logger.info("\n📊 基本统计:")
        logger.info(f"   股票数量: {row[0]:,}")
        logger.info(f"   总记录数: {row[1]:,}")
        logger.info(f"   日期范围: {row[2]} ~ {row[3]}")

        cursor = conn.execute("""
            SELECT code, COUNT(*) as cnt
            FROM stock_analysis
            GROUP BY code
            ORDER BY cnt DESC
            LIMIT 10
        """)
        logger.info("\n📈 数据量 Top 10:")
        for i, row in enumerate(cursor.fetchall(), 1):
            logger.info(f"   {i}. {row[0]}: {row[1]:,} 条")

        cursor = conn.execute("""
            SELECT
                COUNT(*) as cnt
            FROM stock_analysis
            WHERE rsi IS NOT NULL AND rsi != 0
        """)
        indicator_count = cursor.fetchone()[0]
        logger.info("\n📐 技术指标:")
        logger.info(f"   已计算记录: {indicator_count:,}")

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
        logger.info(f"   指标数量: {len(indicator_cols)}")
        logger.info(f"   指标列表: {', '.join(indicator_cols[:10])}...")


def run_scan(args):
    """运行信号扫描"""

    from scanner import run_scan

    logger.info("\n" + "=" * 60)
    logger.info("🔍 全市场信号扫描")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    signal_type = args.type if args.type else None
    min_score = args.min_score if args.min_score else 0
    parallel = args.parallel if hasattr(args, "parallel") else False
    max_workers = args.workers if hasattr(args, "workers") else 4

    result = run_scan(
        db_path=db_path,
        signal_type=signal_type,
        min_score=min_score,
        parallel=parallel,
        max_workers=max_workers,
    )

    logger.info("\n📊 扫描结果:")
    logger.info(f"   扫描股票: {result.total_stocks:,}")
    logger.info(f"   发现信号: {result.signals_found:,}")

    if result.summary:
        logger.info("\n📈 信号分布:")
        for signal_name, count in sorted(result.summary.items(), key=lambda x: -x[1]):
            logger.info(f"   {signal_name}: {count}")

    if result.top_signals:
        logger.info("\n🏆 Top 20 高分信号:")
        logger.info(
            f"{'代码':<12} {'名称':<10} {'信号类型':<15} {'强度':<6} {'得分':<8} {'价格':<10} {'涨跌幅':<8}"
        )
        logger.info("-" * 85)
        for s in result.top_signals:
            name = s.name[:8] if s.name else s.code
            logger.info(
                f"{s.code:<12} {name:<10} {s.signal_type.value:<15} {s.strength.value:<6} "
                f"{s.score:<8.1f} {s.price:<10.2f} {s.change_percent:+.2f}%"
            )

    if args.output:
        import json

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 结果已保存到: {output_path}")


def run_visualize(args):
    """运行可视化"""

    from scanner import visualize_scan_result

    logger.info("\n" + "=" * 60)
    logger.info("📊 信号可视化")
    logger.info("=" * 60)

    scan_result_path = Path(args.input) if args.input else REPORTS_DIR / "scan_result.json"

    if not scan_result_path.exists():
        logger.error(f"❌ 扫描结果文件不存在: {scan_result_path}")
        logger.info("   请先运行: python -m src.main scan")
        return

    output_dir = Path(args.output_dir) if args.output_dir else CHARTS_DIR

    paths = visualize_scan_result(scan_result_path, output_dir)

    if paths:
        logger.info(f"\n✅ 已生成 {len(paths)} 个图表:")
        for p in paths:
            logger.info(f"   - {p}")


def run_sync(args):
    """运行数据同步"""

    from data import run_sync

    result = run_sync(backup=not args.no_backup, source_path=args.source)

    if result["success"] and args.run_etl:
        logger.info("\n" + "=" * 60)
        logger.info("📦 自动运行 ETL...")
        logger.info("=" * 60)
        from etl import run_etl as etl_pipeline

        etl_pipeline()


def run_refresh_names(args):
    """刷新股票名称缓存"""

    from data import get_stock_info_fetcher

    logger.info("\n" + "=" * 60)
    logger.info("🔄 刷新股票名称缓存")
    logger.info("=" * 60)

    fetcher = get_stock_info_fetcher()
    count = fetcher.refresh_cache()

    logger.info(f"\n✅ 已更新 {count} 只股票名称")


def run_fetch(args):
    """获取股票数据"""

    from data import run_fetch

    codes = args.codes.split(",") if args.codes else None

    run_fetch(
        db_path=args.db if args.db else None,
        codes=codes,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
    )


def run_sync_env(args):
    """同步环境变量"""

    from data import run_sync_env

    run_sync_env(args.source)


def run_accuracy(args):
    """运行信号准确率分析"""
    import json

    from scanner import run_accuracy_analysis

    logger.info("\n" + "=" * 60)
    logger.info("📊 信号准确率分析")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    report = run_accuracy_analysis(db_path=db_path, holding_days=args.holding_days)

    logger.info("\n📈 分析结果:")
    logger.info(f"   分析日期: {report.analysis_date}")
    logger.info(f"   数据范围: {report.date_range}")
    logger.info(f"   总信号数: {report.total_signals_analyzed:,}")
    logger.info(f"   总体胜率: {report.overall_win_rate * 100:.2f}%")

    if report.signal_performances:
        logger.info("\n📊 各信号表现:")
        logger.info(
            f"{'信号类型':<15} {'数量':<8} {'胜率':<10} {'平均收益':<12} {'最大收益':<12} {'最大亏损':<12}"
        )
        logger.info("-" * 80)
        for p in report.signal_performances:
            logger.info(
                f"{p.signal_type.value:<15} {p.total_signals:<8} "
                f"{p.win_rate * 100:>6.2f}%   "
                f"{p.avg_return * 100:>+8.2f}%    "
                f"{p.max_return * 100:>+8.2f}%    "
                f"{p.max_loss * 100:>+8.2f}%"
            )

    if report.recommendations:
        logger.info("\n💡 投资建议:")
        for rec in report.recommendations:
            logger.info(f"   • {rec}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 报告已保存到: {output_path}")


def run_score(args):
    """运行选股评分"""
    import json

    from scorer import run_scoring

    logger.info("\n" + "=" * 60)
    logger.info("📊 选股评分系统")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    report = run_scoring(db_path=db_path, top_n=args.top_n)

    logger.info("\n📈 评分结果:")
    logger.info(f"   评分日期: {report.scoring_date}")
    logger.info(f"   评分股票: {report.total_stocks:,}")

    if report.market_overview:
        logger.info("\n📊 市场概览:")
        logger.info(f"   平均得分: {report.market_overview.get('avg_score', 0):.2f}")
        logger.info(f"   中位数: {report.market_overview.get('median_score', 0):.2f}")
        logger.info(
            f"   强势股: {report.market_overview.get('strong_count', 0)} ({report.market_overview.get('strong_ratio', 0):.1f}%)"
        )
        logger.info(f"   弱势股: {report.market_overview.get('weak_count', 0)}")

    if report.top_stocks:
        logger.info(f"\n🏆 Top {len(report.top_stocks)} 推荐股票:")
        logger.info(
            f"{'排名':<6} {'代码':<12} {'名称':<10} {'得分':<8} {'价格':<10} {'涨跌幅':<10} {'建议':<12}"
        )
        logger.info("-" * 75)
        for s in report.top_stocks[:20]:
            logger.info(
                f"{s.rank:<6} {s.code:<12} {s.name[:8]:<10} "
                f"{s.total_score:<8.1f} {s.price:<10.2f} {s.change_percent:+.2f}%    {s.recommendation}"
            )

    if report.bottom_stocks:
        logger.error("\n⚠️ 得分最低的股票:")
        logger.info(
            f"{'排名':<6} {'代码':<12} {'名称':<10} {'得分':<8} {'价格':<10} {'涨跌幅':<10}"
        )
        logger.info("-" * 60)
        for s in report.bottom_stocks:
            logger.info(
                f"{s.rank:<6} {s.code:<12} {s.name[:8]:<10} "
                f"{s.total_score:<8.1f} {s.price:<10.2f} {s.change_percent:+.2f}%"
            )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 报告已保存到: {output_path}")


def run_monitor(args):
    """运行市场监控"""
    import json

    from scanner import run_monitor as run_market_monitor

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    result = run_market_monitor(db_path)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 报告已保存到: {output_path}")


def run_backtest(args):
    """运行策略回测"""
    import json

    from strategy import run_backtest as run_strategy_backtest

    logger.info("\n" + "=" * 60)
    logger.info("📈 策略回测")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    exclude_st = not args.include_st if args.include_st else args.exclude_st

    result = run_strategy_backtest(
        db_path=db_path,
        strategy_type=args.strategy,
        lookback_days=args.lookback,
        top_n=args.top_n,
        holding_days=args.holding,
        initial_capital=args.capital,
        min_momentum=args.min_momentum,
        max_momentum=args.max_momentum,
        max_volatility=args.max_volatility,
        min_price=args.min_price,
        exclude_st=exclude_st,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
        use_ma_cross=args.use_ma_cross,
    )

    logger.info("\n📊 回测结果:")
    logger.info(f"   策略: {result.strategy_name}")
    logger.info(f"   回测区间: {result.start_date} ~ {result.end_date}")
    logger.info(f"   初始资金: {result.initial_capital:,.0f}")
    logger.info(f"   最终资金: {result.final_capital:,.0f}")

    logger.info("\n📈 收益指标:")
    logger.info(f"   总收益率: {result.total_return * 100:.2f}%")
    logger.info(f"   年化收益: {result.annualized_return * 100:.2f}%")
    logger.info(f"   最大回撤: {result.max_drawdown * 100:.2f}%")
    logger.info(f"   夏普比率: {result.sharpe_ratio:.2f}")

    logger.info("\n📊 交易统计:")
    logger.info(f"   总交易数: {result.total_trades}")
    logger.info(f"   盈利交易: {result.winning_trades}")
    logger.info(f"   亏损交易: {result.losing_trades}")
    logger.info(f"   胜率: {result.win_rate * 100:.2f}%")
    logger.info(f"   平均盈利: {result.avg_profit * 100:.2f}%")
    logger.info(f"   平均亏损: {result.avg_loss * 100:.2f}%")
    logger.info(f"   盈亏比: {result.profit_factor:.2f}")

    logger.info("\n📉 风险指标:")
    logger.info(f"   夏普比率: {result.sharpe_ratio:.2f}")
    logger.info(f"   索提诺比率: {result.sortino_ratio:.2f}")
    logger.info(f"   卡玛比率: {result.calmar_ratio:.2f}")
    logger.info(f"   年化波动率: {result.volatility * 100:.2f}%")

    logger.info("\n💰 交易费用:")
    logger.info(f"   总佣金: {result.total_commission:,.2f} 元")
    logger.info(f"   总印花税: {result.total_stamp_tax:,.2f} 元")
    logger.info(f"   总交易成本: {result.total_trading_cost:,.2f} 元")

    if result.trades:
        logger.info("\n📋 最近交易记录:")
        logger.info(
            f"{'代码':<12} {'名称':<10} {'买入日期':<12} {'买入价':<10} {'卖出价':<10} {'收益%':<10}"
        )
        logger.info("-" * 70)
        for t in result.trades[:10]:
            logger.info(
                f"{t.code:<12} {t.name[:8]:<10} {t.entry_date:<12} "
                f"{t.entry_price:<10.2f} {t.exit_price:<10.2f} {t.profit_percent:+.2f}%"
            )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 报告已保存到: {output_path}")

    if args.benchmark:
        from strategy import compare_with_benchmark, print_benchmark_comparison

        logger.info("\n" + "=" * 60)
        logger.info("📊 基准对比分析")
        logger.info("=" * 60)

        try:
            benchmark_result = compare_with_benchmark(result, db_path)
            print_benchmark_comparison(benchmark_result)
        except Exception as e:
            logger.error(f"❌ 基准对比失败: {e}")


def run_trade_report(args):
    """生成交易报告"""

    from strategy import (
        generate_trade_report,
        print_trade_report,
        save_trade_report,
    )
    from strategy import (
        run_backtest as run_strategy_backtest,
    )

    logger.info("\n" + "=" * 60)
    logger.info("📋 交易报告生成")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    result = run_strategy_backtest(
        db_path=db_path,
        strategy_type=args.strategy,
        holding_days=args.holding,
    )

    report = generate_trade_report(result)
    print_trade_report(report)

    if args.output:
        output_path = Path(args.output)
        save_trade_report(report, output_path)
        logger.info(f"\n💾 报告已保存到: {output_path}")


def run_backtest_viz(args):
    """运行回测可视化"""

    from strategy import visualize_backtest

    logger.info("\n" + "=" * 60)
    logger.info("📊 回测可视化")
    logger.info("=" * 60)

    backtest_path = Path(args.input) if args.input else REPORTS_DIR / "backtest_report.json"

    if not backtest_path.exists():
        logger.error(f"❌ 回测报告不存在: {backtest_path}")
        logger.info("   请先运行: python -m src.main backtest")
        return

    output_dir = Path(args.output_dir) if args.output_dir else CHARTS_DIR

    paths = visualize_backtest(backtest_path, output_dir)

    if paths:
        logger.info(f"\n✅ 已生成 {len(paths)} 个图表")


def run_export(args):
    """导出数据"""

    from strategy import run_backtest as run_strategy_backtest
    from utils import export_backtest_trades

    logger.info("\n" + "=" * 60)
    logger.info("📤 数据导出")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    output_dir = Path(args.output_dir) if args.output_dir else Path("output/exports")
    format_type = args.format or "csv"

    if args.type == "trades":
        result = run_strategy_backtest(
            db_path=db_path,
            strategy_type=args.strategy,
            holding_days=args.holding,
        )
        paths = export_backtest_trades(result, output_dir, format=format_type)
        logger.info("\n✅ 已导出交易数据:")
        for path in paths.values():
            logger.info(f"   - {path}")
    else:
        logger.error(f"❌ 未知导出类型: {args.type}")


def run_market_timing(args):
    """运行大盘择时"""

    from strategy import run_market_timing

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    run_market_timing(db_path)


def run_compare(args):
    """运行策略对比"""
    import json

    from strategy import run_comparison

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    strategies = args.strategies.split(",") if args.strategies else None

    result = run_comparison(
        db_path=db_path,
        strategies=strategies,
        holding_days=args.holding,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 报告已保存到: {output_path}")


def run_sector(args):
    """运行行业轮动分析"""
    import json

    from strategy import run_sector_analysis, run_sector_validation

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    result = (
        run_sector_validation(db_path) if args.validate else run_sector_analysis(db_path, args.date)
    )

    if args.output and not args.validate:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 报告已保存到: {output_path}")


def run_portfolio(args):
    """运行多策略组合回测"""
    import json

    from strategy import run_portfolio_backtest

    logger.info("\n" + "=" * 60)
    logger.info("📊 多策略组合回测")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    strategies = None
    if args.strategies:
        strategy_list = args.strategies.split(",")
        strategies = []
        for s in strategy_list:
            parts = s.split(":")
            strategy_type = parts[0]
            weight = float(parts[1]) if len(parts) > 1 else 0
            strategies.append(
                {
                    "name": strategy_type,
                    "type": strategy_type,
                    "weight": weight,
                    "params": {"holding_days": args.holding},
                }
            )
    else:
        strategies = [
            {
                "name": "momentum",
                "type": "momentum",
                "weight": 0,
                "params": {"holding_days": args.holding},
            },
            {
                "name": "mean_reversion",
                "type": "mean_reversion",
                "weight": 0,
                "params": {"holding_days": args.holding},
            },
            {
                "name": "trend_following",
                "type": "trend_following",
                "weight": 0,
                "params": {"holding_days": args.holding},
            },
        ]

    weight_method = args.weight_method or "equal"

    result = run_portfolio_backtest(
        db_path=db_path,
        strategies=strategies,
        weight_method=weight_method,
        initial_capital=args.capital,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 报告已保存到: {output_path}")


def run_web(args):
    """运行 Web 服务器"""

    from web import run_server

    logger.info("\n" + "=" * 60)
    logger.info("🌐 启动 Web 服务器")
    logger.info("=" * 60)

    run_server(host=args.host, port=args.port)


def run_optimize(args):
    """运行参数优化"""
    import json

    from strategy import run_optimization

    logger.info("\n" + "=" * 60)
    logger.info("🔧 策略参数优化")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    result = run_optimization(db_path=db_path, strategy_type=args.strategy)

    logger.info("\n🏆 最优参数:")
    for key, value in result.best_params.items():
        logger.info(f"   {key}: {value}")

    logger.info("\n📊 最优结果:")
    logger.info(f"   总收益率: {result.best_return * 100:.2f}%")
    logger.info(f"   夏普比率: {result.best_sharpe:.2f}")
    logger.info(f"   最大回撤: {result.best_drawdown * 100:.2f}%")

    logger.info("\n📈 Top 10 参数组合:")
    logger.info(f"{'排名':<6} {'收益率':<12} {'夏普比率':<10} {'最大回撤':<12} {'胜率':<10}")
    logger.info("-" * 55)
    for i, r in enumerate(
        sorted(result.all_results, key=lambda x: x["sharpe_ratio"], reverse=True)[:10], 1
    ):
        logger.info(
            f"{i:<6} {r['total_return'] * 100:>+8.2f}%    {r['sharpe_ratio']:>6.2f}     {r['max_drawdown'] * 100:>6.2f}%      {r['win_rate'] * 100:>6.2f}%"
        )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 报告已保存到: {output_path}")


def run_interactive_mode(args):
    """运行交互式模式"""

    from utils.interactive_cli import run_interactive

    run_interactive()


def run_db_optimize(args):
    """运行数据库性能优化"""

    from utils import optimize_database

    logger.info("\n" + "=" * 60)
    logger.info("🔧 数据库性能优化")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        logger.info("   请先运行: python -m src.main etl")
        return

    logger.info(f"\n📂 数据库: {db_path}")

    result = optimize_database(db_path)

    logger.info("\n📊 表信息:")
    table_info = result["table_info"]
    logger.info(f"   列数: {table_info['column_count']}")
    logger.info(f"   行数: {table_info['row_count']:,}")
    logger.info(f"   股票数: {table_info['code_count']:,}")
    logger.info(f"   交易日数: {table_info['date_count']:,}")

    logger.info("\n📇 索引优化:")
    logger.info(f"   优化前索引: {', '.join(result['indexes_before']) or '无'}")
    if result["indexes_created"]:
        logger.info(f"   新建索引: {', '.join(result['indexes_created'])}")
    if result["indexes_existing"]:
        logger.info(f"   已有索引: {', '.join(result['indexes_existing'])}")
    logger.info(f"   优化后索引: {', '.join(result['indexes_after'])}")

    logger.info("\n✅ 数据库优化完成！")


def run_signal_backtest(args):
    """运行信号有效性回测"""

    from strategy import run_signal_backtest as run_backtest

    logger.info("\n" + "=" * 60)
    logger.info("📊 信号有效性回测")
    logger.info("=" * 60)

    db_path = Path(args.db) if args.db else get_stock_analysis_db_path()

    if not db_path.exists():
        logger.error(f"❌ 数据库不存在: {db_path}")
        return

    signal_type = args.type if hasattr(args, "type") else None
    holding_days = args.holding_days if hasattr(args, "holding_days") else 5

    logger.info(f"\n持有天数: {holding_days}")

    result = run_backtest(db_path=db_path, signal_type=signal_type, holding_days=holding_days)

    if isinstance(result, list):
        logger.info(f"\n回测信号类型: {len(result)} 种\n")
        logger.info(f"{'信号类型':<20} {'总数':>8} {'胜率':>8} {'平均收益':>10} {'夏普':>8}")
        logger.info("-" * 60)
        for r in sorted(result, key=lambda x: x.sharpe_ratio, reverse=True):
            logger.info(
                f"{r.signal_type:<20} {r.total_signals:>8} "
                f"{r.win_rate * 100:>7.2f}% {r.avg_return * 100:>+9.2f}% {r.sharpe_ratio:>8.2f}"
            )

        if args.output:
            import json

            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in result], f, ensure_ascii=False, indent=2)
            logger.info(f"\n💾 结果已保存到: {output_path}")
    else:
        logger.info(f"\n信号类型: {result.signal_type}")
        logger.info(f"总信号数: {result.total_signals}")
        logger.info(f"胜率: {result.win_rate * 100:.2f}%")
        logger.info(f"平均收益: {result.avg_return * 100:+.2f}%")
        logger.info(f"夏普比率: {result.sharpe_ratio:.2f}")


def run_portfolio_opt(args):
    """运行组合优化"""

    import numpy as np

    from strategy import PortfolioOptimizer, create_position_limit

    logger.info("\n" + "=" * 60)
    logger.info("📐 组合优化")
    logger.info("=" * 60)

    max_positions = args.max_positions if hasattr(args, "max_positions") else 10
    max_single_pct = args.max_single_pct if hasattr(args, "max_single_pct") else 0.15
    max_sector_pct = args.max_sector_pct if hasattr(args, "max_sector_pct") else 0.30

    position_limit = create_position_limit(
        max_positions=max_positions,
        max_single_position_pct=max_single_pct,
        max_sector_position_pct=max_sector_pct,
    )

    logger.info("\n持仓限制:")
    logger.info(f"  最大持仓数量: {position_limit.max_positions}")
    logger.info(f"  单只股票最大仓位: {position_limit.max_single_position_pct * 100:.1f}%")
    logger.info(f"  行业最大仓位: {position_limit.max_sector_position_pct * 100:.1f}%")

    optimizer = PortfolioOptimizer()

    assets = ["000001", "000002", "000063", "000333", "000651"]
    volatilities = {a: 0.02 + (hash(a) % 100) / 10000 for a in assets}
    expected_returns = {a: 0.0005 + (hash(a) % 50) / 10000 for a in assets}

    import pandas as pd

    correlations = pd.DataFrame(1.0, index=assets, columns=assets)
    np.fill_diagonal(correlations.values, 1.0)

    result = optimizer.optimize_with_constraints(
        assets=assets,
        expected_returns=expected_returns,
        volatilities=volatilities,
        correlations=correlations,
        position_limit=position_limit,
    )

    logger.info("\n优化结果:")
    logger.info(f"  期望收益: {result.expected_return * 100:.2f}%")
    logger.info(f"  期望波动: {result.expected_volatility * 100:.2f}%")
    logger.info(f"  夏普比率: {result.sharpe_ratio:.2f}")
    logger.info(f"  分散度: {result.diversification_ratio:.2f}")
    logger.info(f"  集中度 HHI: {result.concentration_hhi:.4f}")

    logger.info("\n权重分配:")
    for asset, weight in sorted(result.weights.items(), key=lambda x: -x[1]):
        logger.info(f"  {asset}: {weight * 100:.2f}%")

    if args.output:
        import json

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 结果已保存到: {output_path}")


def run_risk_attribution(args):
    """运行风险归因分析"""

    import numpy as np
    import pandas as pd

    from strategy import RiskAttributor

    logger.info("\n" + "=" * 60)
    logger.info("📈 风险归因分析")
    logger.info("=" * 60)

    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=100)
    assets = ["000001", "000002", "000063", "000333", "000651"]
    returns_data = pd.DataFrame(np.random.randn(100, 5) * 0.02, index=dates, columns=assets)
    weights = {a: 0.2 for a in assets}

    attributor = RiskAttributor(returns_data, weights)
    result = attributor.calculate_risk_attribution()

    logger.info("\n风险分解:")
    logger.info(f"  总风险: {result.total_risk * 100:.2f}%")
    logger.info(f"  系统性风险: {result.systematic_risk * 100:.2f}%")
    logger.info(f"  特质风险: {result.idiosyncratic_risk * 100:.2f}%")

    logger.info("\n因子贡献:")
    for factor, contrib in result.factor_contributions.items():
        logger.info(f"  {factor}: {contrib * 100:.2f}%")

    if args.output:
        import json

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"\n💾 结果已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Stock Analyzer - 股票数据分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.main sync             # 同步外部数据库
  python -m src.main sync --run-etl   # 同步后自动运行 ETL
  python -m src.main etl              # 运行 ETL 流程
  python -m src.main analyze          # 运行分析
  python -m src.main stats            # 显示统计信息
  python -m src.main scan             # 全市场信号扫描
  python -m src.main visualize        # 生成可视化图表
  python -m src.main accuracy         # 信号准确率分析
  python -m src.main score            # 选股评分排名
  python -m src.main backtest         # 动量策略回测
  python -m src.main backtest --strategy mean_reversion  # 均值回归策略
  python -m src.main backtest-viz     # 回测结果可视化
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    sync_parser = subparsers.add_parser("sync", help="从外部数据库同步")
    sync_parser.add_argument("--source", type=str, help="源数据库路径")
    sync_parser.add_argument("--no-backup", action="store_true", help="不备份目标数据库")
    sync_parser.add_argument("--run-etl", action="store_true", help="同步后自动运行 ETL")

    subparsers.add_parser("refresh-names", help="刷新股票名称缓存")

    fetch_parser = subparsers.add_parser("fetch", help="获取股票 K 线数据")
    fetch_parser.add_argument("--db", type=str, help="数据库路径")
    fetch_parser.add_argument("--codes", type=str, help="指定股票代码(逗号分隔)")
    fetch_parser.add_argument("--start-date", type=str, help="开始日期 (如 20240101)")
    fetch_parser.add_argument("--end-date", type=str, help="结束日期 (如 20241231)")
    fetch_parser.add_argument("--limit", type=int, help="限制获取数量")

    sync_env_parser = subparsers.add_parser("sync-env", help="从外部项目同步环境变量")
    sync_env_parser.add_argument("--source", type=str, help="源 .env 文件路径")

    etl_parser = subparsers.add_parser("etl", help="运行 ETL 数据管道")
    etl_parser.add_argument("--source-db", type=str, help="源数据库路径")
    etl_parser.add_argument("--target-db", type=str, help="目标数据库路径")
    etl_parser.add_argument("--codes", type=str, help="指定股票代码(逗号分隔)")

    analyze_parser = subparsers.add_parser("analyze", help="运行股票分析")
    analyze_parser.add_argument("--db", type=str, help="数据库路径")
    analyze_parser.add_argument("--limit", type=int, default=50000, help="数据量限制")
    analyze_parser.add_argument("--top-n", type=int, default=5, help="分析前N只股票")

    stats_parser = subparsers.add_parser("stats", help="显示数据统计")
    stats_parser.add_argument("--db", type=str, help="数据库路径")

    scan_parser = subparsers.add_parser("scan", help="全市场信号扫描")
    scan_parser.add_argument("--db", type=str, help="数据库路径")
    scan_parser.add_argument("--type", type=str, help="信号类型筛选")
    scan_parser.add_argument("--min-score", type=float, default=0, help="最低得分筛选")
    scan_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")
    scan_parser.add_argument("--parallel", action="store_true", help="并行扫描")
    scan_parser.add_argument("--workers", type=int, default=4, help="并行工作数")

    visualize_parser = subparsers.add_parser("visualize", help="生成可视化图表")
    visualize_parser.add_argument("--input", type=str, help="扫描结果 JSON 文件路径")
    visualize_parser.add_argument("--output-dir", type=str, help="输出目录")

    accuracy_parser = subparsers.add_parser("accuracy", help="信号准确率分析")
    accuracy_parser.add_argument("--db", type=str, help="数据库路径")
    accuracy_parser.add_argument("--holding-days", type=int, default=5, help="持有天数")
    accuracy_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    score_parser = subparsers.add_parser("score", help="选股评分排名")
    score_parser.add_argument("--db", type=str, help="数据库路径")
    score_parser.add_argument("--top-n", type=int, default=50, help="返回前N只股票")
    score_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    backtest_parser = subparsers.add_parser("backtest", help="策略回测")
    backtest_parser.add_argument("--db", type=str, help="数据库路径")
    backtest_parser.add_argument(
        "--strategy",
        type=str,
        default="momentum",
        choices=["momentum", "mean_reversion", "trend_following", "multi_factor"],
        help="策略类型",
    )
    backtest_parser.add_argument("--lookback", type=int, default=20, help="动量回看天数")
    backtest_parser.add_argument("--top-n", type=int, default=10, help="选股数量")
    backtest_parser.add_argument("--holding", type=int, default=5, help="持有天数")
    backtest_parser.add_argument("--capital", type=float, default=100000.0, help="初始资金")
    backtest_parser.add_argument("--min-momentum", type=float, default=0.0, help="最小动量阈值")
    backtest_parser.add_argument("--max-momentum", type=float, default=1.0, help="最大动量阈值")
    backtest_parser.add_argument(
        "--max-volatility", type=float, default=0.15, help="最大波动率阈值"
    )
    backtest_parser.add_argument("--min-price", type=float, default=2.0, help="最低价格过滤")
    backtest_parser.add_argument(
        "--exclude-st", action="store_true", default=True, help="排除ST股票"
    )
    backtest_parser.add_argument("--include-st", action="store_true", help="包含ST股票")
    backtest_parser.add_argument(
        "--stop-loss", type=float, default=0.0, help="止损比例 (如 0.05 表示 5%%)"
    )
    backtest_parser.add_argument(
        "--take-profit", type=float, default=0.0, help="止盈比例 (如 0.1 表示 10%%)"
    )
    backtest_parser.add_argument("--use-ma-cross", action="store_true", help="趋势策略使用均线交叉")
    backtest_parser.add_argument("--benchmark", action="store_true", help="与基准对比")
    backtest_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    backtest_viz_parser = subparsers.add_parser("backtest-viz", help="回测结果可视化")
    backtest_viz_parser.add_argument("--input", type=str, help="回测报告 JSON 文件路径")
    backtest_viz_parser.add_argument("--output-dir", type=str, help="输出目录")

    optimize_parser = subparsers.add_parser("optimize", help="策略参数优化")
    optimize_parser.add_argument("--db", type=str, help="数据库路径")
    optimize_parser.add_argument(
        "--strategy",
        type=str,
        default="momentum",
        choices=["momentum", "mean_reversion"],
        help="策略类型",
    )
    optimize_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    monitor_parser = subparsers.add_parser("monitor", help="市场实时监控")
    monitor_parser.add_argument("--db", type=str, help="数据库路径")
    monitor_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    trade_report_parser = subparsers.add_parser("trade-report", help="交易报告生成")
    trade_report_parser.add_argument("--db", type=str, help="数据库路径")
    trade_report_parser.add_argument(
        "--strategy",
        type=str,
        default="mean_reversion",
        choices=["momentum", "mean_reversion"],
        help="策略类型",
    )
    trade_report_parser.add_argument("--holding", type=int, default=5, help="持有天数")
    trade_report_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    export_parser = subparsers.add_parser("export", help="数据导出")
    export_parser.add_argument("--db", type=str, help="数据库路径")
    export_parser.add_argument(
        "--type",
        type=str,
        default="trades",
        choices=["trades", "signals", "scores"],
        help="导出类型",
    )
    export_parser.add_argument(
        "--strategy",
        type=str,
        default="mean_reversion",
        choices=["momentum", "mean_reversion"],
        help="策略类型",
    )
    export_parser.add_argument("--holding", type=int, default=9, help="持有天数")
    export_parser.add_argument(
        "--format", type=str, default="csv", choices=["csv", "json"], help="导出格式"
    )
    export_parser.add_argument("--output-dir", type=str, help="输出目录")

    market_timing_parser = subparsers.add_parser("market-timing", help="大盘择时分析")
    market_timing_parser.add_argument("--db", type=str, help="数据库路径")

    compare_parser = subparsers.add_parser("compare", help="策略对比")
    compare_parser.add_argument("--db", type=str, help="数据库路径")
    compare_parser.add_argument("--strategies", type=str, help="策略列表(逗号分隔)")
    compare_parser.add_argument("--holding", type=int, default=5, help="持有天数")
    compare_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    sector_parser = subparsers.add_parser("sector", help="行业轮动分析")
    sector_parser.add_argument("--db", type=str, help="数据库路径")
    sector_parser.add_argument("--date", type=str, help="分析日期")
    sector_parser.add_argument("--validate", action="store_true", help="验证行业数据和信号")
    sector_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    portfolio_parser = subparsers.add_parser("portfolio", help="多策略组合回测")
    portfolio_parser.add_argument("--db", type=str, help="数据库路径")
    portfolio_parser.add_argument(
        "--strategies", type=str, help="策略列表(格式: momentum:0.3,mean_reversion:0.4)"
    )
    portfolio_parser.add_argument(
        "--weight-method",
        type=str,
        default="equal",
        choices=["equal", "risk_parity", "sharpe", "custom"],
        help="权重方法",
    )
    portfolio_parser.add_argument("--holding", type=int, default=5, help="持有天数")
    portfolio_parser.add_argument("--capital", type=float, default=100000.0, help="初始资金")
    portfolio_parser.add_argument("--output", type=str, help="输出文件路径(JSON)")

    web_parser = subparsers.add_parser("web", help="启动 Web 界面")
    web_parser.add_argument("--host", type=str, default="127.0.0.1", help="服务器地址")
    web_parser.add_argument("--port", type=int, default=8000, help="服务器端口")

    db_optimize_parser = subparsers.add_parser("db-optimize", help="数据库性能优化")
    db_optimize_parser.add_argument("--db", type=str, help="数据库路径")

    subparsers.add_parser("interactive", help="交互式模式")

    signal_backtest_parser = subparsers.add_parser("signal-backtest", help="信号有效性回测")
    signal_backtest_parser.add_argument("--db", type=str, help="数据库路径")
    signal_backtest_parser.add_argument("--type", type=str, help="信号类型 (不指定则测试全部)")
    signal_backtest_parser.add_argument("--holding-days", type=int, default=5, help="持有天数")
    signal_backtest_parser.add_argument("--output", type=str, help="输出文件路径")

    portfolio_opt_parser = subparsers.add_parser("portfolio-opt", help="组合优化")
    portfolio_opt_parser.add_argument("--db", type=str, help="数据库路径")
    portfolio_opt_parser.add_argument("--max-positions", type=int, default=10, help="最大持仓数量")
    portfolio_opt_parser.add_argument(
        "--max-single-pct", type=float, default=0.15, help="单只股票最大仓位"
    )
    portfolio_opt_parser.add_argument(
        "--max-sector-pct", type=float, default=0.30, help="行业最大仓位"
    )
    portfolio_opt_parser.add_argument("--output", type=str, help="输出文件路径")

    risk_attr_parser = subparsers.add_parser("risk-attribution", help="风险归因分析")
    risk_attr_parser.add_argument("--db", type=str, help="数据库路径")
    risk_attr_parser.add_argument("--output", type=str, help="输出文件路径")

    args = parser.parse_args()

    if args.command == "interactive":
        run_interactive_mode(args)
    elif args.command == "sync":
        run_sync(args)
    elif args.command == "sync-env":
        run_sync_env(args)
    elif args.command == "refresh-names":
        run_refresh_names(args)
    elif args.command == "fetch":
        run_fetch(args)
    elif args.command == "etl":
        run_etl(args)
    elif args.command == "analyze":
        run_analyze(args)
    elif args.command == "stats":
        run_stats(args)
    elif args.command == "scan":
        run_scan(args)
    elif args.command == "visualize":
        run_visualize(args)
    elif args.command == "accuracy":
        run_accuracy(args)
    elif args.command == "score":
        run_score(args)
    elif args.command == "monitor":
        run_monitor(args)
    elif args.command == "backtest":
        run_backtest(args)
    elif args.command == "backtest-viz":
        run_backtest_viz(args)
    elif args.command == "optimize":
        run_optimize(args)
    elif args.command == "trade-report":
        run_trade_report(args)
    elif args.command == "export":
        run_export(args)
    elif args.command == "market-timing":
        run_market_timing(args)
    elif args.command == "compare":
        run_compare(args)
    elif args.command == "sector":
        run_sector(args)
    elif args.command == "portfolio":
        run_portfolio(args)
    elif args.command == "web":
        run_web(args)
    elif args.command == "db-optimize":
        run_db_optimize(args)
    elif args.command == "signal-backtest":
        run_signal_backtest(args)
    elif args.command == "portfolio-opt":
        run_portfolio_opt(args)
    elif args.command == "risk-attribution":
        run_risk_attribution(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

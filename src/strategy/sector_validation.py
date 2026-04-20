"""
Sector Rotation Backtest Module.
行业轮动回测验证模块 - 验证轮动信号有效性
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .sector_rotation import (
    RotationSignal,
    SectorRotationAnalyzer,
)


@dataclass
class SectorBacktestResult:
    """行业轮动回测结果"""

    start_date: str
    end_date: str
    total_periods: int
    total_signals: int
    enter_signals: int
    exit_signals: int
    avg_return_after_enter: float
    avg_return_after_exit: float
    win_rate_enter: float
    win_rate_exit: float
    best_sector: str
    worst_sector: str
    sector_performance: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_periods": self.total_periods,
            "total_signals": self.total_signals,
            "enter_signals": self.enter_signals,
            "exit_signals": self.exit_signals,
            "avg_return_after_enter": round(self.avg_return_after_enter * 100, 2),
            "avg_return_after_exit": round(self.avg_return_after_exit * 100, 2),
            "win_rate_enter": round(self.win_rate_enter * 100, 2),
            "win_rate_exit": round(self.win_rate_exit * 100, 2),
            "best_sector": self.best_sector,
            "worst_sector": self.worst_sector,
            "sector_performance": {k: round(v * 100, 2) for k, v in self.sector_performance.items()},
        }


def backtest_sector_rotation(
    db_path: Path,
    holding_days: int = 5,
    lookback_days: int = 20,
) -> SectorBacktestResult:
    """
    回测行业轮动信号

    Args:
        db_path: 数据库路径
        holding_days: 持有天数
        lookback_days: 回看天数

    Returns:
        回测结果
    """
    conn = sqlite3.connect(str(db_path))

    cursor = conn.execute("""
        SELECT DISTINCT date FROM stock_analysis
        ORDER BY date
    """)
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()

    if len(dates) < lookback_days + holding_days:
        raise ValueError("数据不足，无法进行回测")

    analyzer = SectorRotationAnalyzer(lookback_days=lookback_days)

    enter_returns = []
    exit_returns = []
    sector_returns = {}

    test_dates = dates[lookback_days::holding_days]

    print("\n🔄 行业轮动回测验证")
    print(f"   回测区间: {test_dates[0]} ~ {test_dates[-1]}")
    print(f"   测试周期数: {len(test_dates)}")

    for i, date in enumerate(test_dates[:-1]):
        if (i + 1) % 10 == 0:
            print(f"   进度: {i + 1}/{len(test_dates)}")

        try:
            result = analyzer.analyze_sectors(db_path, date)

            next_date = test_dates[i + 1] if i + 1 < len(test_dates) else None
            if not next_date:
                continue

            for rotation in result.rotations:
                sector = rotation.sector

                sector_return = _get_sector_return(db_path, sector, date, next_date)

                if sector_return is not None:
                    if sector not in sector_returns:
                        sector_returns[sector] = []
                    sector_returns[sector].append(sector_return)

                    if rotation.signal == RotationSignal.ENTER:
                        enter_returns.append(sector_return)
                    elif rotation.signal == RotationSignal.EXIT:
                        exit_returns.append(-sector_return)

        except Exception:
            continue

    avg_enter = np.mean(enter_returns) if enter_returns else 0
    avg_exit = np.mean(exit_returns) if exit_returns else 0

    win_enter = sum(1 for r in enter_returns if r > 0) / len(enter_returns) if enter_returns else 0
    win_exit = sum(1 for r in exit_returns if r > 0) / len(exit_returns) if exit_returns else 0

    sector_avg = {k: np.mean(v) for k, v in sector_returns.items() if v}

    if sector_avg:
        best_sector = max(sector_avg.keys(), key=lambda x: sector_avg[x])
        worst_sector = min(sector_avg.keys(), key=lambda x: sector_avg[x])
    else:
        best_sector = ""
        worst_sector = ""

    return SectorBacktestResult(
        start_date=test_dates[0],
        end_date=test_dates[-1],
        total_periods=len(test_dates),
        total_signals=len(enter_returns) + len(exit_returns),
        enter_signals=len(enter_returns),
        exit_signals=len(exit_returns),
        avg_return_after_enter=avg_enter,
        avg_return_after_exit=avg_exit,
        win_rate_enter=win_enter,
        win_rate_exit=win_exit,
        best_sector=best_sector,
        worst_sector=worst_sector,
        sector_performance=sector_avg,
    )


def _get_sector_return(
    db_path: Path,
    sector: str,
    start_date: str,
    end_date: str,
) -> float | None:
    """计算行业收益"""
    from .sector_rotation import DEFAULT_SECTORS

    stocks = DEFAULT_SECTORS.get(sector, [])
    if not stocks:
        return None

    conn = sqlite3.connect(str(db_path))

    placeholders = ",".join(["?" for _ in stocks])
    query = f"""
        SELECT code, date, close
        FROM stock_analysis
        WHERE date IN (?, ?) AND code IN ({placeholders})
        ORDER BY date, code
    """
    params = [start_date, end_date] + stocks

    try:
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
    except Exception:
        conn.close()
        return None

    if df.empty:
        return None

    start_prices = df[df["date"] == start_date].set_index("code")["close"]
    end_prices = df[df["date"] == end_date].set_index("code")["close"]

    common = start_prices.index.intersection(end_prices.index)
    if len(common) == 0:
        return None

    returns = (end_prices[common] - start_prices[common]) / start_prices[common]
    return returns.mean()


def validate_sector_data(db_path: Path) -> dict[str, Any]:
    """
    验证行业数据

    Args:
        db_path: 数据库路径

    Returns:
        验证结果
    """
    from .sector_rotation import DEFAULT_SECTORS

    conn = sqlite3.connect(str(db_path))

    cursor = conn.execute("SELECT DISTINCT code FROM stock_analysis")
    all_codes = set(row[0] for row in cursor.fetchall())
    conn.close()

    results = {
        "total_stocks_in_db": len(all_codes),
        "sectors": {},
        "missing_stocks": {},
        "coverage": 0,
    }

    total_mapped = 0
    for sector, stocks in DEFAULT_SECTORS.items():
        found = [s for s in stocks if s in all_codes]
        missing = [s for s in stocks if s not in all_codes]
        total_mapped += len(found)

        results["sectors"][sector] = {
            "total": len(stocks),
            "found": len(found),
            "missing": len(missing),
            "coverage": round(len(found) / len(stocks) * 100, 2) if stocks else 0,
        }

        if missing:
            results["missing_stocks"][sector] = missing

    results["coverage"] = round(total_mapped / len(all_codes) * 100, 2) if all_codes else 0

    return results


def print_sector_validation(validation: dict[str, Any]):
    """打印验证结果"""
    print(f"\n{'=' * 60}")
    print("📊 行业数据验证")
    print(f"{'=' * 60}")

    print("\n📈 数据库统计:")
    print(f"   总股票数: {validation['total_stocks_in_db']}")
    print(f"   行业覆盖率: {validation['coverage']}%")

    print("\n📋 各行业覆盖情况:")
    print(f"{'行业':<12} {'总数':<8} {'找到':<8} {'缺失':<8} {'覆盖率':<10}")
    print("-" * 50)

    for sector, data in validation["sectors"].items():
        print(f"{sector:<12} {data['total']:<8} {data['found']:<8} {data['missing']:<8} {data['coverage']}%")


def print_sector_backtest(result: SectorBacktestResult):
    """打印回测结果"""
    print(f"\n{'=' * 60}")
    print("📊 行业轮动回测验证")
    print(f"{'=' * 60}")

    print(f"\n📅 回测区间: {result.start_date} ~ {result.end_date}")
    print(f"📊 测试周期: {result.total_periods}")

    print("\n📈 信号统计:")
    print(f"   总信号数: {result.total_signals}")
    print(f"   进入信号: {result.enter_signals}")
    print(f"   退出信号: {result.exit_signals}")

    print("\n📊 信号效果:")
    print(f"   进入后平均收益: {result.avg_return_after_enter:+.2f}%")
    print(f"   退出后平均收益: {result.avg_return_after_exit:+.2f}%")
    print(f"   进入信号胜率: {result.win_rate_enter:.2f}%")
    print(f"   退出信号胜率: {result.win_rate_exit:.2f}%")

    print("\n🏆 行业表现:")
    print(f"   最佳行业: {result.best_sector}")
    print(f"   最差行业: {result.worst_sector}")

    print("\n📋 各行业平均收益:")
    sorted_sectors = sorted(result.sector_performance.items(), key=lambda x: x[1], reverse=True)
    for sector, ret in sorted_sectors[:10]:
        print(f"   {sector}: {ret:+.2f}%")

    print("\n💡 验证结论:")
    if result.avg_return_after_enter > 0 and result.win_rate_enter > 50:
        print("   ✅ 进入信号有效 - 平均收益为正，胜率超过50%")
    else:
        print("   ⚠️ 进入信号需优化 - 建议调整参数")

    if result.avg_return_after_exit > 0:
        print("   ✅ 退出信号有效 - 退出后避免下跌")
    else:
        print("   ⚠️ 退出信号需优化")


def run_sector_validation(db_path: Path | None = None) -> dict[str, Any]:
    """运行行业验证"""
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"
    db_path = db_path or data_dir / "stock_analysis.db"

    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    print("\n🔍 验证行业数据...")
    validation = validate_sector_data(db_path)
    print_sector_validation(validation)

    print("\n🔄 回测轮动信号...")
    backtest = backtest_sector_rotation(db_path)
    print_sector_backtest(backtest)

    return {
        "validation": validation,
        "backtest": backtest.to_dict(),
    }

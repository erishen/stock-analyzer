"""
Data Export Module.
数据导出模块 - 支持多种格式导出
"""

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def export_to_csv(
    data: list[dict] | list[Any],
    output_path: Path,
    fieldnames: list[str] | None = None,
) -> Path:
    """
    导出数据到 CSV 文件

    Args:
        data: 数据列表
        output_path: 输出路径
        fieldnames: 字段名列表

    Returns:
        输出文件路径
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not data:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            pass
        return output_path

    if hasattr(data[0], "to_dict"):
        data = [item.to_dict() for item in data]
    elif hasattr(data[0], "__dataclass_fields__"):
        data = [asdict(item) for item in data]

    if fieldnames is None:
        fieldnames = list(data[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            filtered_row = {k: v for k, v in row.items() if k in fieldnames}
            writer.writerow(filtered_row)

    return output_path


def export_to_json(
    data: Any,
    output_path: Path,
    indent: int = 2,
) -> Path:
    """
    导出数据到 JSON 文件

    Args:
        data: 数据
        output_path: 输出路径
        indent: 缩进

    Returns:
        输出文件路径
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(data, "to_dict"):
        data = data.to_dict()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)

    return output_path


def export_backtest_trades(
    backtest_result: Any,
    output_dir: Path,
    format: str = "csv",
) -> dict[str, Path]:
    """
    导出回测交易记录

    Args:
        backtest_result: 回测结果
        output_dir: 输出目录
        format: 导出格式 (csv, json)

    Returns:
        导出文件路径字典
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    trades = backtest_result.trades
    if trades:
        trades_data = [t.to_dict() for t in trades]

        if format == "csv":
            fieldnames = [
                "code",
                "name",
                "entry_date",
                "entry_price",
                "exit_date",
                "exit_price",
                "shares",
                "profit",
                "profit_percent",
                "holding_days",
                "signal",
                "commission",
                "stamp_tax",
                "total_cost",
            ]
            paths["trades"] = export_to_csv(
                trades_data,
                output_dir / "trades.csv",
                fieldnames=fieldnames,
            )
        else:
            paths["trades"] = export_to_json(
                trades_data,
                output_dir / "trades.json",
            )

    equity_curve = backtest_result.equity_curve
    if equity_curve:
        if format == "csv":
            paths["equity_curve"] = export_to_csv(
                equity_curve,
                output_dir / "equity_curve.csv",
                fieldnames=["date", "equity"],
            )
        else:
            paths["equity_curve"] = export_to_json(
                equity_curve,
                output_dir / "equity_curve.json",
            )

    summary = backtest_result.to_dict()
    summary.pop("trades", None)
    summary.pop("equity_curve", None)
    paths["summary"] = export_to_json(
        summary,
        output_dir / "summary.json",
    )

    return paths


def export_signals(
    signals: list[Any],
    output_path: Path,
    format: str = "csv",
) -> Path:
    """
    导出信号数据

    Args:
        signals: 信号列表
        output_path: 输出路径
        format: 导出格式

    Returns:
        输出文件路径
    """
    if not signals:
        return output_path

    if hasattr(signals[0], "to_dict"):
        signals = [s.to_dict() for s in signals]

    if format == "csv":
        fieldnames = [
            "code",
            "name",
            "date",
            "signal_type",
            "strength",
            "price",
            "volume",
            "description",
        ]
        return export_to_csv(signals, output_path.with_suffix(".csv"), fieldnames=fieldnames)
    else:
        return export_to_json(signals, output_path.with_suffix(".json"))


def export_stock_scores(
    scores: list[Any],
    output_path: Path,
    format: str = "csv",
) -> Path:
    """
    导出股票评分

    Args:
        scores: 评分列表
        output_path: 输出路径
        format: 导出格式

    Returns:
        输出文件路径
    """
    if not scores:
        return output_path

    if hasattr(scores[0], "to_dict"):
        scores = [s.to_dict() for s in scores]

    if format == "csv":
        fieldnames = [
            "rank",
            "code",
            "name",
            "total_score",
            "trend_score",
            "momentum_score",
            "volatility_score",
            "volume_score",
            "signal_score",
            "price",
            "change_percent",
            "recommendation",
        ]
        return export_to_csv(scores, output_path.with_suffix(".csv"), fieldnames=fieldnames)
    else:
        return export_to_json(scores, output_path.with_suffix(".json"))


def export_market_monitor(
    monitor_data: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """
    导出市场监控数据

    Args:
        monitor_data: 监控数据
        output_dir: 输出目录

    Returns:
        导出文件路径字典
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    if "summary" in monitor_data:
        paths["summary"] = export_to_json(
            monitor_data["summary"],
            output_dir / "market_summary.json",
        )

    if "oversold_signals" in monitor_data:
        paths["oversold"] = export_to_json(
            monitor_data["oversold_signals"],
            output_dir / "oversold_signals.json",
        )

    if "golden_cross_signals" in monitor_data:
        paths["golden_cross"] = export_to_json(
            monitor_data["golden_cross_signals"],
            output_dir / "golden_cross_signals.json",
        )

    return paths


def export_optimization_results(
    results: list[dict[str, Any]],
    output_path: Path,
    format: str = "csv",
) -> Path:
    """
    导出优化结果

    Args:
        results: 优化结果列表
        output_path: 输出路径
        format: 导出格式

    Returns:
        输出文件路径
    """
    if not results:
        return output_path

    flat_results = []
    for r in results:
        flat = {
            "total_return": r.get("total_return", 0),
            "sharpe_ratio": r.get("sharpe_ratio", 0),
            "max_drawdown": r.get("max_drawdown", 0),
            "win_rate": r.get("win_rate", 0),
            "total_trades": r.get("total_trades", 0),
        }
        params = r.get("params", {})
        for k, v in params.items():
            flat[f"param_{k}"] = v
        flat_results.append(flat)

    if format == "csv":
        return export_to_csv(flat_results, output_path.with_suffix(".csv"))
    else:
        return export_to_json(flat_results, output_path.with_suffix(".json"))

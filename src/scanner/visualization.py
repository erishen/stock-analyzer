"""
Signal Visualization for Stock Analyzer.
信号可视化 - 生成信号分布图表
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.font_config import setup_chinese_font


@dataclass
class VisualizationConfig:
    """可视化配置"""

    output_dir: Path
    figsize: tuple[int, int] = (12, 8)
    dpi: int = 150
    font_size: int = 12
    color_scheme: str = "default"


class SignalVisualizer:
    """信号可视化器"""

    COLORS: ClassVar[dict[str, str]] = {
        "bullish": "#2ecc71",
        "bearish": "#e74c3c",
        "neutral": "#3498db",
        "highlight": "#f39c12",
    }

    SIGNAL_CATEGORIES: ClassVar[dict[str, list[str]]] = {
        "bullish": ["MACD金叉", "KDJ金叉", "MA5上穿MA20", "RSI超卖", "跌破布林下轨", "上升趋势"],
        "bearish": ["MACD死叉", "KDJ死叉", "MA5下穿MA20", "RSI超买", "突破布林上轨", "下降趋势"],
        "neutral": ["成交量异动"],
    }

    def __init__(self, config: VisualizationConfig):
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        setup_chinese_font()
        plt.rcParams["font.size"] = config.font_size

    def plot_signal_distribution(self, summary: dict[str, int], title: str = "信号分布"):
        """绘制信号分布图"""
        if not summary:
            print("没有信号数据")
            return

        _fig, ax = plt.subplots(figsize=self.config.figsize)

        signals = list(summary.keys())
        counts = list(summary.values())

        colors = []
        for signal in signals:
            if signal in self.SIGNAL_CATEGORIES["bullish"]:
                colors.append(self.COLORS["bullish"])
            elif signal in self.SIGNAL_CATEGORIES["bearish"]:
                colors.append(self.COLORS["bearish"])
            else:
                colors.append(self.COLORS["neutral"])

        y_pos = np.arange(len(signals))
        bars = ax.barh(y_pos, counts, color=colors, alpha=0.8)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(signals)
        ax.invert_yaxis()
        ax.set_xlabel("数量")
        ax.set_title(title)

        for _i, (bar, count) in enumerate(zip(bars, counts, strict=False)):
            ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2, str(count), va="center", fontsize=10)

        from matplotlib.patches import Patch

        legend_elements = [
            Patch(facecolor=self.COLORS["bullish"], alpha=0.8, label="看涨信号"),
            Patch(facecolor=self.COLORS["bearish"], alpha=0.8, label="看跌信号"),
            Patch(facecolor=self.COLORS["neutral"], alpha=0.8, label="中性信号"),
        ]
        ax.legend(handles=legend_elements, loc="lower right")

        ax.grid(True, axis="x", alpha=0.3)
        plt.tight_layout()

        output_path = self.config.output_dir / "signal_distribution.png"
        plt.savefig(output_path, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()

        print(f"信号分布图已保存: {output_path}")
        return output_path

    def plot_signal_pie(self, summary: dict[str, int], title: str = "信号类型占比"):
        """绘制信号饼图"""
        if not summary:
            print("没有信号数据")
            return

        _fig, ax = plt.subplots(figsize=(10, 10))

        bullish_count = sum(summary.get(s, 0) for s in self.SIGNAL_CATEGORIES["bullish"])
        bearish_count = sum(summary.get(s, 0) for s in self.SIGNAL_CATEGORIES["bearish"])
        neutral_count = sum(summary.get(s, 0) for s in self.SIGNAL_CATEGORIES["neutral"])

        sizes = [bullish_count, bearish_count, neutral_count]
        labels = [f"看涨信号\n{bullish_count}", f"看跌信号\n{bearish_count}", f"中性信号\n{neutral_count}"]
        colors = [self.COLORS["bullish"], self.COLORS["bearish"], self.COLORS["neutral"]]

        sizes = [s for s in sizes if s > 0]
        labels = [
            label for label, s in zip(labels, [bullish_count, bearish_count, neutral_count], strict=False) if s > 0
        ]
        colors = [c for c, s in zip(colors, [bullish_count, bearish_count, neutral_count], strict=False) if s > 0]

        if not sizes:
            print("没有信号数据")
            return

        _wedges, _texts, _autotexts = ax.pie(
            sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90, explode=[0.02] * len(sizes)
        )

        ax.set_title(title, fontsize=14, fontweight="bold")

        plt.tight_layout()

        output_path = self.config.output_dir / "signal_pie.png"
        plt.savefig(output_path, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()

        print(f"信号饼图已保存: {output_path}")
        return output_path

    def plot_top_signals(self, signals: list[dict], title: str = "Top 20 高分信号"):
        """绘制高分信号图"""
        if not signals:
            print("没有信号数据")
            return

        _fig, ax = plt.subplots(figsize=(14, 10))

        codes = [f"{s['code']}\n{s.get('name', '')[:6]}" for s in signals[:20]]
        scores = [s["score"] for s in signals[:20]]
        signal_types = [s["signal_type"] for s in signals[:20]]

        colors = []
        for st in signal_types:
            if st in self.SIGNAL_CATEGORIES["bullish"]:
                colors.append(self.COLORS["bullish"])
            elif st in self.SIGNAL_CATEGORIES["bearish"]:
                colors.append(self.COLORS["bearish"])
            else:
                colors.append(self.COLORS["neutral"])

        y_pos = np.arange(len(codes))
        bars = ax.barh(y_pos, scores, color=colors, alpha=0.8)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(codes)
        ax.invert_yaxis()
        ax.set_xlabel("得分")
        ax.set_title(title, fontsize=14, fontweight="bold")

        for _i, (bar, score, st) in enumerate(zip(bars, scores, signal_types, strict=False)):
            ax.text(
                bar.get_width() + 1, bar.get_y() + bar.get_height() / 2, f"{score:.1f} | {st}", va="center", fontsize=9
            )

        from matplotlib.patches import Patch

        legend_elements = [
            Patch(facecolor=self.COLORS["bullish"], alpha=0.8, label="看涨"),
            Patch(facecolor=self.COLORS["bearish"], alpha=0.8, label="看跌"),
            Patch(facecolor=self.COLORS["neutral"], alpha=0.8, label="中性"),
        ]
        ax.legend(handles=legend_elements, loc="lower right")

        ax.grid(True, axis="x", alpha=0.3)
        plt.tight_layout()

        output_path = self.config.output_dir / "top_signals.png"
        plt.savefig(output_path, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()

        print(f"高分信号图已保存: {output_path}")
        return output_path

    def plot_score_distribution(self, signals: list[dict], title: str = "信号得分分布"):
        """绘制得分分布直方图"""
        if not signals:
            print("没有信号数据")
            return

        _fig, ax = plt.subplots(figsize=self.config.figsize)

        scores = [s["score"] for s in signals]

        bins = np.arange(0, 110, 10)
        _n, bins_out, patches = ax.hist(scores, bins=bins, edgecolor="white", alpha=0.8)

        for i, patch in enumerate(patches):
            if bins_out[i] >= 70:
                patch.set_facecolor(self.COLORS["bullish"])
            elif bins_out[i] >= 40:
                patch.set_facecolor(self.COLORS["highlight"])
            else:
                patch.set_facecolor(self.COLORS["neutral"])

        ax.set_xlabel("得分")
        ax.set_ylabel("信号数量")
        ax.set_title(title, fontsize=14, fontweight="bold")

        ax.axvline(x=50, color="red", linestyle="--", alpha=0.7, label="中线 (50)")
        ax.axvline(x=70, color="green", linestyle="--", alpha=0.7, label="高分线 (70)")

        ax.legend()
        ax.grid(True, axis="y", alpha=0.3)

        plt.tight_layout()

        output_path = self.config.output_dir / "score_distribution.png"
        plt.savefig(output_path, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()

        print(f"得分分布图已保存: {output_path}")
        return output_path

    def generate_report(self, scan_result: dict) -> list[Path]:
        """生成完整可视化报告"""
        output_paths = []

        print("\n📊 生成可视化报告...")

        if "summary" in scan_result:
            path = self.plot_signal_distribution(scan_result["summary"])
            if path:
                output_paths.append(path)

            path = self.plot_signal_pie(scan_result["summary"])
            if path:
                output_paths.append(path)

        if "signals" in scan_result:
            path = self.plot_top_signals(scan_result["signals"])
            if path:
                output_paths.append(path)

            path = self.plot_score_distribution(scan_result["signals"])
            if path:
                output_paths.append(path)

        print(f"\n✅ 已生成 {len(output_paths)} 个图表")
        return output_paths


def visualize_scan_result(scan_result_path: Path, output_dir: Path | None = None) -> list[Path]:
    """
    可视化扫描结果

    Args:
        scan_result_path: 扫描结果 JSON 文件路径
        output_dir: 输出目录

    Returns:
        生成的图表文件路径列表
    """
    if not scan_result_path.exists():
        raise FileNotFoundError(f"扫描结果文件不存在: {scan_result_path}")

    with open(scan_result_path, encoding="utf-8") as f:
        scan_result = json.load(f)

    if output_dir is None:
        output_dir = scan_result_path.parent

    config = VisualizationConfig(output_dir=output_dir)
    visualizer = SignalVisualizer(config)

    return visualizer.generate_report(scan_result)

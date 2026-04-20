#!/usr/bin/env python3
"""
Stock Analyzer - 股票分析器

分析股票数据并生成可视化图表
"""

import sqlite3
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from utils.font_config import setup_chinese_font

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

OUTPUT_DIR.mkdir(exist_ok=True)

setup_chinese_font()


class StockAnalyzer:
    """股票分析器"""

    def __init__(self, db_path: str | None = None, use_analysis_db: bool = True):
        """
        初始化分析器

        Args:
            db_path: 数据库文件路径
            use_analysis_db: 是否使用分析数据库 (含技术指标)
        """
        if db_path is None:
            if use_analysis_db:
                db_path = str(DATA_DIR / "stock_analysis.db")
            else:
                db_path = str(DATA_DIR / "asset_lens.db")
        self.db_path = db_path
        self.conn = None
        self.df = None

    def connect_db(self):
        """连接到数据库"""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"数据库不存在: {self.db_path}")

        self.conn = sqlite3.connect(self.db_path)
        print(f"已连接数据库: {self.db_path}")

    def load_data(self, table_name: str = "stock_analysis", limit: int | None = None, codes: list[str] | None = None):
        """
        从数据库加载数据

        Args:
            table_name: 表名
            limit: 限制记录数
            codes: 指定股票代码列表
        """
        if not self.conn:
            self.connect_db()

        query = f"SELECT * FROM {table_name}"
        conditions = []

        if codes:
            code_list = ",".join([f"'{c}'" for c in codes])
            conditions.append(f"code IN ({code_list})")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY code, date"

        if limit:
            query += f" LIMIT {limit}"

        self.df = pd.read_sql_query(query, self.conn)
        print(f"已加载 {len(self.df)} 条记录")

        if "date" in self.df.columns:
            self.df["date"] = pd.to_datetime(self.df["date"])

        return self.df

    def get_stock_list(self) -> list[str]:
        """获取股票列表"""
        if not self.conn:
            self.connect_db()

        query = "SELECT DISTINCT code FROM stock_analysis ORDER BY code"
        cursor = self.conn.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def get_stock_data(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取单只股票数据"""
        if not self.conn:
            self.connect_db()

        query = f"""
            SELECT * FROM stock_analysis
            WHERE code = ?
            ORDER BY date DESC
            LIMIT {days}
        """
        df = pd.read_sql_query(query, self.conn, params=(code,))
        if not df.empty:
            df = df.sort_values("date").reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"])
        return df

    def analyze_stocks(self, top_n: int = 10):
        """分析股票数据"""
        if self.df is None:
            self.load_data()

        print("\n=== 股票分析 ===")

        print("\n基本统计:")
        print(self.df.describe())

        if "code" in self.df.columns:
            print(f"\n按股票代码分析 (前 {top_n} 只):")
            stock_groups = self.df.groupby("code")
            stock_counts = stock_groups.size().sort_values(ascending=False).head(top_n)

            for code in stock_counts.index:
                group = stock_groups.get_group(code)
                print(f"\n股票: {code}")
                print(f"  记录数: {len(group)}")
                print(f"  日期范围: {group['date'].min()} ~ {group['date'].max()}")
                print(f"  平均价: {group['close'].mean():.2f}")
                print(f"  最高价: {group['close'].max():.2f}")
                print(f"  最低价: {group['close'].min():.2f}")
                print(f"  平均成交量: {group['volume'].mean():,.0f}")

                if "rsi" in group.columns:
                    latest = group.iloc[-1]
                    print(f"  最新 RSI: {latest['rsi']:.2f}")
                if "macd" in group.columns:
                    latest = group.iloc[-1]
                    print(f"  最新 MACD: {latest['macd']:.4f}")

    def plot_price_trend(self, top_n: int = 5):
        """绘制价格趋势图"""
        if self.df is None:
            self.load_data()

        if "date" not in self.df.columns or "close" not in self.df.columns:
            print("错误: 缺少 date 或 close 列")
            return

        plt.figure(figsize=(14, 7))

        if "code" in self.df.columns:
            stock_groups = self.df.groupby("code")
            stock_counts = stock_groups.size().sort_values(ascending=False).head(top_n)

            for code in stock_counts.index:
                stock_data = self.df[self.df["code"] == code].sort_values("date")
                plt.plot(stock_data["date"], stock_data["close"], label=code, linewidth=1.5)

            plt.legend(loc="upper left", bbox_to_anchor=(1, 1))
        else:
            plt.plot(self.df["date"], self.df["close"])

        plt.title("股票价格趋势")
        plt.xlabel("日期")
        plt.ylabel("收盘价")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        output_path = OUTPUT_DIR / "price_trend.png"
        plt.savefig(output_path, dpi=150)
        plt.close()
        print(f"价格趋势图已保存: {output_path}")

    def plot_volume_trend(self, top_n: int = 5):
        """绘制成交量趋势图"""
        if self.df is None:
            self.load_data()

        if "date" not in self.df.columns or "volume" not in self.df.columns:
            print("错误: 缺少 date 或 volume 列")
            return

        plt.figure(figsize=(14, 7))

        if "code" in self.df.columns:
            stock_groups = self.df.groupby("code")
            stock_counts = stock_groups.size().sort_values(ascending=False).head(top_n)

            for code in stock_counts.index:
                stock_data = self.df[self.df["code"] == code].sort_values("date")
                plt.plot(stock_data["date"], stock_data["volume"], label=code, linewidth=1.5)

            plt.legend(loc="upper left", bbox_to_anchor=(1, 1))
        else:
            plt.plot(self.df["date"], self.df["volume"])

        plt.title("成交量趋势")
        plt.xlabel("日期")
        plt.ylabel("成交量")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        output_path = OUTPUT_DIR / "volume_trend.png"
        plt.savefig(output_path, dpi=150)
        plt.close()
        print(f"成交量趋势图已保存: {output_path}")

    def calculate_moving_average(self, window: int = 20, top_n: int = 3):
        """计算移动平均线"""
        if self.df is None:
            self.load_data()

        if "close" not in self.df.columns:
            print("错误: 缺少 close 列")
            return

        print(f"\n=== 移动平均线 (窗口={window}) ===")

        if "code" in self.df.columns:
            stock_groups = self.df.groupby("code")
            stock_counts = stock_groups.size().sort_values(ascending=False).head(top_n)

            for code in stock_counts.index:
                stock_data = self.df[self.df["code"] == code].copy().sort_values("date")

                if f"ma{window}" in stock_data.columns:
                    ma_col = f"ma{window}"
                    ma_value = stock_data[ma_col].iloc[-1]
                else:
                    stock_data[f"ma{window}"] = stock_data["close"].rolling(window=window).mean()
                    ma_col = f"ma{window}"
                    ma_value = stock_data[ma_col].iloc[-1]

                print(f"\n股票: {code}")
                print(f"  {window}日均线: {ma_value:.2f}")
                print(f"  最新收盘: {stock_data['close'].iloc[-1]:.2f}")

                plt.figure(figsize=(14, 7))
                plt.plot(stock_data["date"], stock_data["close"], label="收盘价", linewidth=1.5)
                plt.plot(stock_data["date"], stock_data[ma_col], label=f"{window}日均线", linewidth=2)

                if "boll_upper" in stock_data.columns:
                    plt.plot(stock_data["date"], stock_data["boll_upper"], "--", label="布林上轨", alpha=0.7)
                    plt.plot(stock_data["date"], stock_data["boll_lower"], "--", label="布林下轨", alpha=0.7)

                plt.title(f"{code} 价格与 {window}日均线")
                plt.xlabel("日期")
                plt.ylabel("价格")
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.tight_layout()

                output_path = OUTPUT_DIR / f"{code}_ma{window}.png"
                plt.savefig(output_path, dpi=150)
                plt.close()
                print(f"  图表已保存: {output_path}")

    def plot_technical_indicators(self, code: str):
        """绘制技术指标图"""
        df = self.get_stock_data(code, days=60)

        if df.empty:
            print(f"股票 {code} 没有数据")
            return

        fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

        ax1 = axes[0]
        ax1.plot(df["date"], df["close"], label="收盘价", linewidth=1.5)
        if "ma5" in df.columns:
            ax1.plot(df["date"], df["ma5"], label="MA5", linewidth=1)
        if "ma20" in df.columns:
            ax1.plot(df["date"], df["ma20"], label="MA20", linewidth=1)
        if "boll_upper" in df.columns and "boll_lower" in df.columns:
            ax1.fill_between(df["date"], df["boll_upper"], df["boll_lower"], alpha=0.1, label="布林带")
        ax1.set_ylabel("价格")
        ax1.legend(loc="upper left")
        ax1.set_title(f"{code} 技术指标")
        ax1.grid(True, alpha=0.3)

        ax2 = axes[1]
        if "macd" in df.columns:
            ax2.plot(df["date"], df["macd"], label="MACD", linewidth=1)
        if "macd_signal" in df.columns:
            ax2.plot(df["date"], df["macd_signal"], label="Signal", linewidth=1)
        if "macd_hist" in df.columns:
            colors = ["red" if x >= 0 else "green" for x in df["macd_hist"]]
            ax2.bar(df["date"], df["macd_hist"], label="Hist", color=colors, alpha=0.5)
        ax2.set_ylabel("MACD")
        ax2.legend(loc="upper left")
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color="black", linestyle="-", linewidth=0.5)

        ax3 = axes[2]
        if "rsi" in df.columns:
            ax3.plot(df["date"], df["rsi"], label="RSI", linewidth=1.5)
            ax3.axhline(y=70, color="red", linestyle="--", alpha=0.5)
            ax3.axhline(y=30, color="green", linestyle="--", alpha=0.5)
        ax3.set_ylabel("RSI")
        ax3.legend(loc="upper left")
        ax3.grid(True, alpha=0.3)
        ax3.set_ylim(0, 100)

        ax4 = axes[3]
        ax4.bar(df["date"], df["volume"], label="成交量", alpha=0.7)
        ax4.set_ylabel("成交量")
        ax4.set_xlabel("日期")
        ax4.legend(loc="upper left")
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        output_path = OUTPUT_DIR / f"{code}_indicators.png"
        plt.savefig(output_path, dpi=150)
        plt.close()
        print(f"技术指标图已保存: {output_path}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("数据库连接已关闭")


def main():
    """主函数"""
    print("=== 股票分析器 ===")
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"数据目录: {DATA_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")

    analyzer = StockAnalyzer()

    try:
        analyzer.connect_db()
        analyzer.load_data(limit=50000)
        analyzer.analyze_stocks(top_n=10)
        analyzer.plot_price_trend(top_n=5)
        analyzer.plot_volume_trend(top_n=5)
        analyzer.calculate_moving_average(window=20, top_n=3)

        codes = analyzer.get_stock_list()[:3]
        for code in codes:
            analyzer.plot_technical_indicators(code)

    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()

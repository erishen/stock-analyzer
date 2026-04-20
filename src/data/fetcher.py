"""
Stock Data Fetcher for Stock Analyzer.
股票数据获取模块 - 从 AkShare 获取 A 股 K 线数据

数据源: AkShare (开源免费，无需 API Key)
"""

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FetchResult:
    """获取结果"""

    success: bool
    stocks_fetched: int = 0
    total_records: int = 0
    errors: list[str] = None
    message: str = ""

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "stocks_fetched": self.stocks_fetched,
            "total_records": self.total_records,
            "errors": self.errors,
            "message": self.message,
        }


class StockDataFetcher:
    """股票数据获取器"""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._akshare = None
        self._conn = None

    @property
    def akshare(self):
        """延迟加载 AkShare"""
        if self._akshare is None:
            try:
                import akshare as ak

                self._akshare = ak
            except ImportError:
                raise ImportError("请安装 akshare: pip install akshare") from None
        return self._akshare

    def connect(self):
        """连接数据库"""
        self._conn = sqlite3.connect(str(self.db_path))

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def create_tables(self):
        """创建数据表"""
        if not self._conn:
            self.connect()

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_klines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                amplitude REAL,
                change_percent REAL,
                change_amount REAL,
                turnover_rate REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, date)
            )
        """)

        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_klines_code ON stock_klines(code)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_klines_date ON stock_klines(date)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_klines_code_date ON stock_klines(code, date)")

        self._conn.commit()

    def get_stock_list(self) -> list[dict]:
        """获取 A 股股票列表"""
        try:
            df = self.akshare.stock_zh_a_spot_em()
            if df is None or df.empty:
                return []

            stocks = []
            for _, row in df.iterrows():
                code = row.get("代码", "")
                name = row.get("名称", "")
                if code and name:
                    if not code.startswith(("688", "300", "301")) or True:
                        stocks.append(
                            {
                                "code": code,
                                "name": name,
                            }
                        )
            return stocks
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return []

    def fetch_stock_klines(
        self,
        code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        adjust: str = "qfq",
    ) -> list[dict]:
        """
        获取单只股票的 K 线数据

        Args:
            code: 股票代码 (如 "000001")
            start_date: 开始日期 (如 "20240101")
            end_date: 结束日期 (如 "20241231")
            adjust: 复权类型 ("qfq" 前复权, "hfq" 后复权, "" 不复权)
        """
        try:
            df = self.akshare.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date or "20200101",
                end_date=end_date or datetime.now().strftime("%Y%m%d"),
                adjust=adjust,
            )

            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "code": code,
                        "date": row.get("日期", "").strftime("%Y-%m-%d")
                        if hasattr(row.get("日期"), "strftime")
                        else str(row.get("日期", "")),
                        "open": float(row.get("开盘", 0)),
                        "close": float(row.get("收盘", 0)),
                        "high": float(row.get("最高", 0)),
                        "low": float(row.get("最低", 0)),
                        "volume": float(row.get("成交量", 0)),
                        "amount": float(row.get("成交额", 0)),
                        "amplitude": float(row.get("振幅", 0)),
                        "change_percent": float(row.get("涨跌幅", 0)),
                        "change_amount": float(row.get("涨跌额", 0)),
                        "turnover_rate": float(row.get("换手率", 0)),
                    }
                )
            return records
        except Exception as e:
            print(f"获取 {code} K线数据失败: {e}")
            return []

    def save_klines(self, records: list[dict]):
        """保存 K 线数据"""
        if not self._conn:
            self.connect()

        for record in records:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO stock_klines
                (code, date, open, close, high, low, volume, amount,
                 amplitude, change_percent, change_amount, turnover_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["code"],
                    record["date"],
                    record["open"],
                    record["close"],
                    record["high"],
                    record["low"],
                    record["volume"],
                    record["amount"],
                    record.get("amplitude", 0),
                    record.get("change_percent", 0),
                    record.get("change_amount", 0),
                    record.get("turnover_rate", 0),
                ),
            )

        self._conn.commit()

    def fetch_all_stocks(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
        delay: float = 0.5,
        progress_callback: Any = None,
    ) -> FetchResult:
        """
        获取所有股票的 K 线数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制获取数量 (用于测试)
            delay: 请求间隔 (秒)，避免请求过快
            progress_callback: 进度回调函数
        """
        self.create_tables()

        stocks = self.get_stock_list()
        if not stocks:
            return FetchResult(success=False, message="获取股票列表失败")

        if limit:
            stocks = stocks[:limit]

        result = FetchResult(success=True, stocks_fetched=0, total_records=0, errors=[])

        total = len(stocks)
        for i, stock in enumerate(stocks):
            try:
                records = self.fetch_stock_klines(
                    code=stock["code"],
                    start_date=start_date,
                    end_date=end_date,
                )

                if records:
                    self.save_klines(records)
                    result.stocks_fetched += 1
                    result.total_records += len(records)

                if progress_callback:
                    progress_callback(i + 1, total, stock["code"], len(records))

                time.sleep(delay)

            except Exception as e:
                result.errors.append(f"{stock['code']}: {str(e)}")

        result.message = f"成功获取 {result.stocks_fetched} 只股票，共 {result.total_records:,} 条记录"
        return result

    def fetch_stocks(
        self,
        codes: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        delay: float = 0.5,
    ) -> FetchResult:
        """
        获取指定股票的 K 线数据

        Args:
            codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            delay: 请求间隔 (秒)
        """
        self.create_tables()

        result = FetchResult(success=True, stocks_fetched=0, total_records=0, errors=[])

        for code in codes:
            try:
                records = self.fetch_stock_klines(
                    code=code,
                    start_date=start_date,
                    end_date=end_date,
                )

                if records:
                    self.save_klines(records)
                    result.stocks_fetched += 1
                    result.total_records += len(records)
                    print(f"  ✓ {code}: {len(records)} 条记录")

                time.sleep(delay)

            except Exception as e:
                result.errors.append(f"{code}: {str(e)}")
                print(f"  ✗ {code}: {e}")

        result.message = f"成功获取 {result.stocks_fetched} 只股票，共 {result.total_records:,} 条记录"
        return result

    def get_stats(self) -> dict:
        """获取数据库统计信息"""
        if not self._conn:
            self.connect()

        cursor = self._conn.execute("SELECT COUNT(DISTINCT code) FROM stock_klines")
        stock_count = cursor.fetchone()[0]

        cursor = self._conn.execute("SELECT COUNT(*) FROM stock_klines")
        total_records = cursor.fetchone()[0]

        cursor = self._conn.execute("SELECT MIN(date), MAX(date) FROM stock_klines")
        date_range = cursor.fetchone()

        return {
            "stock_count": stock_count,
            "total_records": total_records,
            "min_date": date_range[0],
            "max_date": date_range[1],
        }


def run_fetch(
    db_path: Path | str | None = None,
    codes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> FetchResult:
    """
    运行数据获取

    Args:
        db_path: 数据库路径
        codes: 指定股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        limit: 限制获取数量
    """
    print("\n" + "=" * 60)
    print("📥 获取股票数据")
    print("=" * 60)

    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "stock_klines.db"

    fetcher = StockDataFetcher(db_path)

    if codes:
        print(f"\n📊 获取指定股票: {', '.join(codes)}")
        result = fetcher.fetch_stocks(
            codes=codes,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        print("\n📊 获取全市场股票数据...")
        if limit:
            print(f"   限制数量: {limit} 只")

        def progress(current, total, code, records):
            pct = current / total * 100
            print(f"\r   进度: {current}/{total} ({pct:.1f}%) - {code}: {records} 条", end="")

        result = fetcher.fetch_all_stocks(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            progress_callback=progress,
        )
        print()

    print(f"\n{'✅' if result.success else '❌'} {result.message}")

    if result.errors:
        print(f"\n⚠️ 有 {len(result.errors)} 个错误:")
        for err in result.errors[:5]:
            print(f"   - {err}")

    stats = fetcher.get_stats()
    print("\n📊 数据库统计:")
    print(f"   股票数量: {stats['stock_count']:,}")
    print(f"   总记录数: {stats['total_records']:,}")
    print(f"   日期范围: {stats['min_date']} ~ {stats['max_date']}")

    fetcher.close()

    return result

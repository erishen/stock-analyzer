"""
Stock Data Fetcher for Stock Analyzer.
股票数据获取模块 - 从 AkShare 获取 A 股 K 线数据

数据源: AkShare (开源免费，无需 API Key)
"""

import json
import logging
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
import requests

from config import get_stock_klines_db_path

logger = logging.getLogger(__name__)


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
        self._em_failures = 0  # 东财源连续失败计数(熔断用)

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
        """获取 A 股股票列表 (东财源优先, 失败自动回退新浪源)"""
        try:
            stocks = self._get_stock_list_em()
            if stocks:
                return stocks
            raise ValueError("东财源返回空列表")
        except Exception as e:
            logger.warning(f"东财源获取股票列表失败({str(e)[:80]}), 回退新浪源...")
        return self._get_stock_list_sina()

    def _get_stock_list_em(self) -> list[dict]:
        """东财源股票列表 (akshare stock_zh_a_spot_em, 纯6位代码)"""
        df = self.akshare.stock_zh_a_spot_em()
        if df is None or df.empty:
            return []
        stocks = []
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            name = str(row.get("名称", "")).strip()
            if code and name and not code.startswith(("688", "300", "301")):
                stocks.append({"code": code, "name": name})
        return stocks

    def _get_stock_list_sina(self) -> list[dict]:
        """新浪源股票列表 (stock_zh_a_spot, 代码带 sh/sz/bj 前缀需规范化)"""
        df = self.akshare.stock_zh_a_spot()
        if df is None or df.empty:
            return []
        stocks = []
        for _, row in df.iterrows():
            code = self._normalize_code(str(row.get("代码", "")))
            name = str(row.get("名称", "")).strip()
            if code and name and not code.startswith(("688", "300", "301")):
                stocks.append({"code": code, "name": name})
        return stocks

    @staticmethod
    def _normalize_code(c: str) -> str:
        """去掉 sh/sz/bj 等市场前缀, 只留纯6位代码。"""
        c = c.lower().strip()
        for p in ("sh", "sz", "bj", "sse.", "szse.", "bse."):
            if c.startswith(p):
                return c[len(p):]
        return c

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
        # 北交所代码走新浪源 (东财/腾讯均无北交所 K 线)
        if code.startswith(("43", "83", "87", "92")):
            return self._fetch_bj_sina(code, start_date, end_date)

        # 东财源连续失败达到阈值后熔断，本次运行剩余请求直接走腾讯源
        if self._em_failures >= 10:
            return self._fetch_from_tencent(code, start_date, end_date)

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

            self._em_failures = 0

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
        except (requests.RequestException, ValueError) as e:
            # 东财源失败(如 TLS 指纹拦截)，降级到腾讯源重试
            self._em_failures += 1
            if self._em_failures == 10:
                logger.warning("东财源连续失败 10 次，本次运行剩余请求直接走腾讯源")
            else:
                logger.warning(f"东财源获取 {code} 失败({type(e).__name__})，尝试腾讯源...")
            return self._fetch_from_tencent(code, start_date, end_date)
        except Exception as e:
            logger.error(f"获取 {code} K线数据失败: {e}")
            return []

    def _fetch_bj_sina(self, code: str, start_date: str | None, end_date: str | None) -> list[dict]:
        """北交所新浪源 (腾讯 K 线接口无北交所数据, 东财被 TLS 拦截)

        接口: CN_MarketDataService.getKLineData, volume 单位为股, 单次上限 1023 条。
        成交额/换手率缺失填 0, 由 ETL/换手率补算模块处理。
        """
        try:
            resp = requests.get(
                "https://quotes.sina.cn/cn/api/jsonp_v2.php/var/CN_MarketDataService.getKLineData",
                params={"symbol": f"bj{code}", "scale": 240, "ma": "no", "datalen": 1023},
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                },
                timeout=15,
            )
            m = re.search(r"\((\[.*\])\)", resp.text, re.S)
            if not m:
                return []
            records = []
            for row in json.loads(m.group(1)):
                date_str = str(row["day"]).replace("/", "-")
                if start_date and date_str.replace("-", "") < start_date:
                    continue
                if end_date and date_str.replace("-", "") > end_date:
                    continue
                records.append(
                    {
                        "code": code,
                        "date": date_str,
                        "open": float(row["open"]),
                        "close": float(row["close"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "volume": float(row["volume"]),
                        "amount": 0.0,
                    }
                )
            logger.info(f"✅ 新浪北交所源获取 {code} 成功: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"新浪北交所源获取 {code} 失败: {e}")
            return []

    def _fetch_from_tencent(
        self, code: str, start_date: str | None, end_date: str | None
    ) -> list[dict]:
        """从腾讯源获取 K 线数据 (stock_zh_a_hist_tx 降级方案)

        腾讯源返回列: date/open/close/high/low/amount，其中 amount 为成交量，
        无成交额/振幅/换手率，缺失字段以 0 填充。

        单位注意 (经成交额交叉验证): 科创板(688/689)返回的是股，其余板块返回的是手(×100 转股)。
        """
        try:
            prefix = "sh" if code.startswith(("6", "9")) else "sz"
            df = self.akshare.stock_zh_a_hist_tx(
                symbol=f"{prefix}{code}",
                start_date=start_date or "20200101",
                end_date=end_date or datetime.now().strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                return []

            is_star = code.startswith(("688", "689"))  # 科创板: 源已是股
            records = []
            for _, row in df.iterrows():
                d = row.get("date", "")
                date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
                vol = float(row.get("amount", 0))
                records.append(
                    {
                        "code": code,
                        "date": date_str,
                        "open": float(row.get("open", 0)),
                        "close": float(row.get("close", 0)),
                        "high": float(row.get("high", 0)),
                        "low": float(row.get("low", 0)),
                        "volume": vol if is_star else vol * 100,  # 手 -> 股 (科创板已是股)
                        "amount": 0.0,
                    }
                )
            logger.info(f"✅ 腾讯源获取 {code} 成功: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"腾讯源获取 {code} K线数据失败: {e}")
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

            except KeyError as e:
                result.errors.append(f"{stock['code']}: {e!s}")

            except Exception as e:
                result.errors.append(f"{stock['code']}: {e!s}")

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
                    logger.info(f"  ✓ {code}: {len(records)} 条记录")

                time.sleep(delay)

            except Exception as e:
                result.errors.append(f"{code}: {e!s}")
                logger.info(f"  ✗ {code}: {e}")

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
    logger.info("\n" + "=" * 60)
    logger.info("📥 获取股票数据")
    logger.info("=" * 60)

    if db_path is None:
        db_path = get_stock_klines_db_path()

    fetcher = StockDataFetcher(db_path)

    if codes:
        logger.info(f"\n📊 获取指定股票: {', '.join(codes)}")
        result = fetcher.fetch_stocks(
            codes=codes,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        logger.info("\n📊 获取全市场股票数据...")
        if limit:
            logger.info(f"   限制数量: {limit} 只")

        def progress(current, total, code, records):
            pct = current / total * 100
            logger.info(f"\r   进度: {current}/{total} ({pct:.1f}%) - {code}: {records} 条", end="")

        result = fetcher.fetch_all_stocks(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            progress_callback=progress,
        )
        logger.info("")

    logger.error(f"\n{'✅' if result.success else '❌'} {result.message}")

    if result.errors:
        logger.error(f"\n⚠️ 有 {len(result.errors)} 个错误:")
        for err in result.errors[:5]:
            logger.info(f"   - {err}")

    stats = fetcher.get_stats()
    logger.info("\n📊 数据库统计:")
    logger.info(f"   股票数量: {stats['stock_count']:,}")
    logger.info(f"   总记录数: {stats['total_records']:,}")
    logger.info(f"   日期范围: {stats['min_date']} ~ {stats['max_date']}")

    fetcher.close()

    return result

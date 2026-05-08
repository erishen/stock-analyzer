"""
ETL Pipeline for Stock Analyzer.
ETL 数据管道 - 提取、转换、加载股票数据

流程:
1. Extract: 从源数据库提取原始 K 线数据
2. Transform: 数据清洗、计算技术指标、特征工程
3. Load: 保存处理后的数据到分析数据库
"""

import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_asset_lens_db_path, get_stock_analysis_db_path


@dataclass
class ETLConfig:
    """ETL 配置"""

    source_db: Path
    target_db: Path
    batch_size: int = 10000
    min_data_days: int = 30
    calculate_indicators: bool = True
    indicator_windows: list[int] = field(default_factory=lambda: [5, 10, 20, 60])


@dataclass
class ETLResult:
    """ETL 执行结果"""

    stocks_processed: int = 0
    records_extracted: int = 0
    records_transformed: int = 0
    records_loaded: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0


class DataExtractor:
    """数据提取器 - 从源数据库提取原始数据"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接数据库"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()

    def get_stock_codes(self) -> list[str]:
        """获取所有股票代码"""
        query = "SELECT DISTINCT code FROM stock_klines ORDER BY code"
        cursor = self.conn.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def get_stock_count(self) -> int:
        """获取股票数量"""
        query = "SELECT COUNT(DISTINCT code) FROM stock_klines"
        cursor = self.conn.execute(query)
        return cursor.fetchone()[0]

    def get_total_records(self) -> int:
        """获取总记录数"""
        query = "SELECT COUNT(*) FROM stock_klines"
        cursor = self.conn.execute(query)
        return cursor.fetchone()[0]

    def extract_stock_data(self, code: str) -> pd.DataFrame:
        """提取单只股票的 K 线数据"""
        query = """
            SELECT
                code, date, open, close, high, low,
                volume, amount, amplitude, change_percent,
                change_amount, turnover_rate
            FROM stock_klines
            WHERE code = ?
            ORDER BY date ASC
        """
        df = pd.read_sql_query(query, self.conn, params=(code,))
        return df

    def extract_all_stocks(self, batch_size: int = 100) -> list[tuple[str, pd.DataFrame]]:
        """批量提取所有股票数据"""
        codes = self.get_stock_codes()
        for i in range(0, len(codes), batch_size):
            batch = codes[i : i + batch_size]
            for code in batch:
                yield code, self.extract_stock_data(code)


class DataTransformer:
    """数据转换器 - 清洗数据、计算技术指标"""

    def __init__(self, config: ETLConfig):
        self.config = config

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行完整的数据转换流程"""
        if df.empty:
            return df

        df = self._clean_data(df)
        df = self._convert_types(df)
        df = self._sort_by_date(df)

        if self.config.calculate_indicators:
            df = self._calculate_all_indicators(df)

        return df

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        df = df.copy()
        df = df.drop_duplicates(subset=["date"], keep="last")
        numeric_cols = ["open", "close", "high", "low", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].replace([np.inf, -np.inf], np.nan)
        df = df.dropna(subset=["close"])
        return df

    def _convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """类型转换"""
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        numeric_cols = [
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
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df

    def _sort_by_date(self, df: pd.DataFrame) -> pd.DataFrame:
        """按日期排序"""
        return df.sort_values("date").reset_index(drop=True)

    def _calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        df = df.copy()

        df = self._calculate_ma(df)
        df = self._calculate_ema(df)
        df = self._calculate_macd(df)
        df = self._calculate_rsi(df)
        df = self._calculate_boll(df)
        df = self._calculate_kdj(df)
        df = self._calculate_atr(df)
        df = self._calculate_obv(df)
        df = self._calculate_williams_r(df)
        df = self._calculate_momentum(df)
        df = self._calculate_volatility(df)
        df = self._calculate_price_features(df)

        return df

    def _calculate_ma(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算移动平均线"""
        for window in self.config.indicator_windows:
            df[f"ma{window}"] = df["close"].rolling(window=window).mean()
            df[f"close_ma{window}_ratio"] = df["close"] / df[f"ma{window}"]
        return df

    def _calculate_ema(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算指数移动平均线"""
        for window in [12, 26]:
            df[f"ema{window}"] = df["close"].ewm(span=window, adjust=False).mean()
        return df

    def _calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 MACD"""
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        df["macd_cross"] = (
            (df["macd"] > df["macd_signal"]) & (df["macd"].shift(1) <= df["macd_signal"].shift(1))
        ).astype(int)
        return df

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算 RSI"""
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.inf)
        df["rsi"] = 100 - (100 / (1 + rs))
        df["rsi_oversold"] = (df["rsi"] < 30).astype(int)
        df["rsi_overbought"] = (df["rsi"] > 70).astype(int)
        return df

    def _calculate_boll(self, df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """计算布林带"""
        df["boll_mid"] = df["close"].rolling(window=period).mean()
        df["boll_std"] = df["close"].rolling(window=period).std()
        df["boll_upper"] = df["boll_mid"] + std_dev * df["boll_std"]
        df["boll_lower"] = df["boll_mid"] - std_dev * df["boll_std"]
        df["boll_width"] = (df["boll_upper"] - df["boll_lower"]) / df["boll_mid"]
        df["boll_position"] = (df["close"] - df["boll_lower"]) / (df["boll_upper"] - df["boll_lower"])
        return df

    def _calculate_kdj(self, df: pd.DataFrame, n: int = 9) -> pd.DataFrame:
        """计算 KDJ"""
        low_min = df["low"].rolling(window=n).min()
        high_max = df["high"].rolling(window=n).max()
        df["kdj_rsv"] = (df["close"] - low_min) / (high_max - low_min) * 100
        df["kdj_k"] = df["kdj_rsv"].ewm(alpha=1 / 3, adjust=False).mean()
        df["kdj_d"] = df["kdj_k"].ewm(alpha=1 / 3, adjust=False).mean()
        df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]
        df["kdj_cross"] = ((df["kdj_k"] > df["kdj_d"]) & (df["kdj_k"].shift(1) <= df["kdj_d"].shift(1))).astype(int)
        return df

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算 ATR"""
        high = df["high"]
        low = df["low"]
        close = df["close"].shift(1)
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=period).mean()
        df["atr_ratio"] = df["atr"] / df["close"]
        return df

    def _calculate_obv(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 OBV"""
        df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
        df["obv_ma10"] = df["obv"].rolling(window=10).mean()
        df["obv_signal"] = (df["obv"] > df["obv_ma10"]).astype(int)
        return df

    def _calculate_williams_r(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算威廉指标"""
        high_max = df["high"].rolling(window=period).max()
        low_min = df["low"].rolling(window=period).min()
        df["williams_r"] = (high_max - df["close"]) / (high_max - low_min) * -100
        df["williams_oversold"] = (df["williams_r"] < -80).astype(int)
        df["williams_overbought"] = (df["williams_r"] > -20).astype(int)
        return df

    def _calculate_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算动量指标"""
        df["momentum_5d"] = df["close"] / df["close"].shift(5) - 1
        df["momentum_10d"] = df["close"] / df["close"].shift(10) - 1
        df["momentum_20d"] = df["close"] / df["close"].shift(20) - 1
        df["roc_10"] = (df["close"] - df["close"].shift(10)) / df["close"].shift(10) * 100
        df["roc_20"] = (df["close"] - df["close"].shift(20)) / df["close"].shift(20) * 100
        return df

    def _calculate_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算波动率"""
        df["pct_change"] = df["close"].pct_change()
        df["volatility_5d"] = df["pct_change"].rolling(window=5).std()
        df["volatility_10d"] = df["pct_change"].rolling(window=10).std()
        df["volatility_20d"] = df["pct_change"].rolling(window=20).std()
        df["volatility_ratio"] = df["volatility_5d"] / df["volatility_20d"]
        return df

    def _calculate_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算价格特征"""
        df["high_low_ratio"] = df["high"] / df["low"]
        df["close_open_ratio"] = df["close"] / df["open"]
        df["upper_shadow"] = (df["high"] - df[["open", "close"]].max(axis=1)) / df["close"]
        df["lower_shadow"] = (df[["open", "close"]].min(axis=1) - df["low"]) / df["close"]
        df["body_size"] = abs(df["close"] - df["open"]) / df["close"]
        return df


class DataLoader:
    """数据加载器 - 保存处理后的数据"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_tables()

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()

    def _create_tables(self):
        """创建目标表"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS stock_analysis (
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
                ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL,
                close_ma5_ratio REAL, close_ma10_ratio REAL, close_ma20_ratio REAL, close_ma60_ratio REAL,
                ema12 REAL, ema26 REAL,
                macd REAL, macd_signal REAL, macd_hist REAL, macd_cross INTEGER,
                rsi REAL, rsi_oversold INTEGER, rsi_overbought INTEGER,
                boll_mid REAL, boll_std REAL, boll_upper REAL, boll_lower REAL, boll_width REAL, boll_position REAL,
                kdj_rsv REAL, kdj_k REAL, kdj_d REAL, kdj_j REAL, kdj_cross INTEGER,
                atr REAL, atr_ratio REAL,
                obv REAL, obv_ma10 REAL, obv_signal INTEGER,
                williams_r REAL, williams_oversold INTEGER, williams_overbought INTEGER,
                momentum_5d REAL, momentum_10d REAL, momentum_20d REAL,
                roc_10 REAL, roc_20 REAL,
                pct_change REAL,
                volatility_5d REAL, volatility_10d REAL, volatility_20d REAL, volatility_ratio REAL,
                high_low_ratio REAL, close_open_ratio REAL,
                upper_shadow REAL, lower_shadow REAL, body_size REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, date)
            );

            CREATE INDEX IF NOT EXISTS idx_analysis_code ON stock_analysis(code);
            CREATE INDEX IF NOT EXISTS idx_analysis_date ON stock_analysis(date);
            CREATE INDEX IF NOT EXISTS idx_analysis_code_date ON stock_analysis(code, date);

            CREATE TABLE IF NOT EXISTS etl_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                stocks_processed INTEGER,
                records_extracted INTEGER,
                records_transformed INTEGER,
                records_loaded INTEGER,
                errors TEXT,
                duration_seconds REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    def load_stock_data(self, df: pd.DataFrame) -> int:
        """加载单只股票数据"""
        if df.empty:
            return 0

        df = df.copy()
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        columns = [col for col in df.columns if col not in ["created_at"]]
        placeholders = ", ".join(["?" for _ in columns])
        column_names = ", ".join(columns)

        records = []
        for _, row in df.iterrows():
            record = tuple(row[col] if col in df.columns else None for col in columns)
            records.append(record)

        query = f"""
            INSERT OR REPLACE INTO stock_analysis ({column_names})
            VALUES ({placeholders})
        """

        self.conn.executemany(query, records)
        self.conn.commit()

        return len(records)

    def log_etl_run(self, result: ETLResult, run_id: str):
        """记录 ETL 运行日志"""
        self.conn.execute(
            """
            INSERT INTO etl_logs (run_id, stocks_processed, records_extracted,
                                  records_transformed, records_loaded, errors, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_id,
                result.stocks_processed,
                result.records_extracted,
                result.records_transformed,
                result.records_loaded,
                "; ".join(result.errors),
                result.duration_seconds,
            ),
        )
        self.conn.commit()


class ETLPipeline:
    """ETL 管道 - 协调 Extract、Transform、Load"""

    def __init__(self, config: ETLConfig):
        self.config = config
        self.extractor = DataExtractor(config.source_db)
        self.transformer = DataTransformer(config)
        self.loader = DataLoader(config.target_db)

    def run(self, stock_codes: list[str] | None = None) -> ETLResult:
        """
        执行 ETL 流程

        Args:
            stock_codes: 指定股票代码列表，为空则处理全部

        Returns:
            ETL 执行结果
        """
        start_time = datetime.now()
        result = ETLResult()
        run_id = start_time.strftime("%Y%m%d_%H%M%S")

        print(f"\n{'=' * 60}")
        print("🚀 ETL Pipeline 开始执行")
        print(f"   Run ID: {run_id}")
        print(f"   源数据库: {self.config.source_db}")
        print(f"   目标数据库: {self.config.target_db}")
        print(f"{'=' * 60}\n")

        try:
            self.extractor.connect()
            self.loader.connect()

            codes = stock_codes if stock_codes else self.extractor.get_stock_codes()
            total_codes = len(codes)
            print(f"📊 待处理股票数量: {total_codes}")

            for i, code in enumerate(codes, 1):
                try:
                    raw_df = self.extractor.extract_stock_data(code)
                    result.records_extracted += len(raw_df)

                    if len(raw_df) < self.config.min_data_days:
                        continue

                    transformed_df = self.transformer.transform(raw_df)
                    result.records_transformed += len(transformed_df)

                    loaded = self.loader.load_stock_data(transformed_df)
                    result.records_loaded += loaded
                    result.stocks_processed += 1

                    if i % 100 == 0 or i == total_codes:
                        print(
                            f"   进度: {i}/{total_codes} ({i / total_codes * 100:.1f}%) - "
                            f"已处理 {result.stocks_processed} 只股票"
                        )

                except Exception as e:
                    error_msg = f"{code}: {str(e)}"
                    result.errors.append(error_msg)
                    print(f"   ⚠️ 错误: {error_msg}")

            self.loader.log_etl_run(result, run_id)

        finally:
            self.extractor.close()
            self.loader.close()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()

        print(f"\n{'=' * 60}")
        print("✅ ETL Pipeline 执行完成")
        print(f"   处理股票: {result.stocks_processed}")
        print(f"   提取记录: {result.records_extracted}")
        print(f"   转换记录: {result.records_transformed}")
        print(f"   加载记录: {result.records_loaded}")
        print(f"   错误数量: {len(result.errors)}")
        print(f"   执行时间: {result.duration_seconds:.2f} 秒")
        print(f"{'=' * 60}\n")

        return result

    def get_statistics(self) -> dict[str, Any]:
        """获取 ETL 统计信息"""
        self.loader.connect()
        try:
            cursor = self.loader.conn.execute("""
                SELECT
                    COUNT(DISTINCT code) as stock_count,
                    COUNT(*) as total_records,
                    MIN(date) as min_date,
                    MAX(date) as max_date
                FROM stock_analysis
            """)
            row = cursor.fetchone()
            return {"stock_count": row[0], "total_records": row[1], "date_range": f"{row[2]} ~ {row[3]}"}
        finally:
            self.loader.close()


def run_etl(
    source_db: str | Path | None = None, target_db: str | Path | None = None, stock_codes: list[str] | None = None
) -> ETLResult:
    """
    运行 ETL 流程的便捷函数

    Args:
        source_db: 源数据库路径
        target_db: 目标数据库路径
        stock_codes: 指定股票代码列表

    Returns:
        ETL 执行结果
    """
    project_root = Path(__file__).parent.parent
    project_root / "data"

    config = ETLConfig(
        source_db=Path(source_db) if source_db else get_asset_lens_db_path(),
        target_db=Path(target_db) if target_db else get_stock_analysis_db_path(),
    )

    pipeline = ETLPipeline(config)
    return pipeline.run(stock_codes)

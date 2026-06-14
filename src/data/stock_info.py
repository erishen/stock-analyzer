"""
Stock Info Fetcher for Stock Analyzer.
股票信息获取模块 - 获取股票名称、行业等信息

数据源: AkShare (开源免费)
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class StockInfo:
    """股票信息"""

    code: str
    name: str = ""
    industry: str = ""
    sector: str = ""
    market: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "industry": self.industry,
            "sector": self.sector,
            "market": self.market,
        }


class StockInfoFetcher:
    """股票信息获取器"""

    def __init__(self, cache_path: Path | None = None):
        self.cache_path = cache_path or Path(__file__).parent.parent.parent / "data"
        self.cache_file = self.cache_path / "stock_info_cache.json"
        self._akshare = None
        self._cache: dict[str, StockInfo] = {}
        self._load_cache()

    @property
    def akshare(self):
        """延迟加载 AkShare"""
        if self._akshare is None:
            try:
                import akshare as ak

                self._akshare = ak
            except ImportError:
                pass
        return self._akshare

    def _load_cache(self):
        """加载缓存"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if "stocks" in data:
                        for code, info in data.get("stocks", {}).items():
                            self._cache[code] = StockInfo(
                                code=code,
                                name=info.get("name", ""),
                                industry=info.get("industry", ""),
                                sector=info.get("sector", ""),
                                market=info.get("market", ""),
                            )
                    if "data" in data:
                        for item in data.get("data", []):
                            code = item.get("code", "")
                            if code and code not in self._cache:
                                self._cache[code] = StockInfo(
                                    code=code,
                                    name=item.get("name", ""),
                                    market=item.get("market", ""),
                                )
            except requests.RequestException:
                pass

            except Exception:
                pass

    def _save_cache(self):
        """保存缓存"""
        self.cache_path.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "stocks": {code: info.to_dict() for code, info in self._cache.items()},
        }
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_stock_info(self, code: str) -> StockInfo:
        """获取单只股票信息"""
        if code in self._cache:
            return self._cache[code]

        info = StockInfo(code=code)

        if self.akshare:
            try:
                df = self.akshare.stock_individual_info_em(symbol=code)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        item = row.get("item", "")
                        value = row.get("value", "")
                        if item == "股票简称":
                            info.name = str(value)
                        elif item == "行业":
                            info.industry = str(value)
                        elif item == "板块":
                            info.sector = str(value)
                        elif item == "市场":
                            info.market = str(value)
            except Exception:
                pass

        self._cache[code] = info
        return info

    def get_stock_name(self, code: str) -> str:
        """获取股票名称"""
        info = self.get_stock_info(code)
        return info.name if info.name else code

    def fetch_all_stock_list(self) -> dict[str, StockInfo]:
        """获取全部A股列表"""
        if not self.akshare:
            return {}

        try:
            df = self.akshare.stock_zh_a_spot_em()
            if df is None or df.empty:
                return {}

            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                name = str(row.get("名称", ""))

                if code and name:
                    if code not in self._cache:
                        self._cache[code] = StockInfo(code=code, name=name)
                    else:
                        self._cache[code].name = name

            self._save_cache()
            return self._cache

        except requests.RequestException as e:
            logger.error(f"获取股票列表失败: {e}")
            return {}

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return {}

    def batch_get_names(self, codes: list[str]) -> dict[str, str]:
        """批量获取股票名称"""
        result = {}
        for code in codes:
            info = self.get_stock_info(code)
            result[code] = info.name if info.name else code
        return result

    def refresh_cache(self) -> int:
        """刷新缓存"""
        stocks = self.fetch_all_stock_list()
        self._save_cache()
        return len(stocks)


_stock_info_fetcher: StockInfoFetcher | None = None


def get_stock_info_fetcher() -> StockInfoFetcher:
    """获取全局股票信息获取器"""
    global _stock_info_fetcher
    if _stock_info_fetcher is None:
        _stock_info_fetcher = StockInfoFetcher()
    return _stock_info_fetcher


def get_stock_name(code: str) -> str:
    """获取股票名称的便捷函数"""
    return get_stock_info_fetcher().get_stock_name(code)


def get_stock_info(code: str) -> StockInfo:
    """获取股票信息的便捷函数"""
    return get_stock_info_fetcher().get_stock_info(code)

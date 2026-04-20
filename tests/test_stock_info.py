"""
Tests for Stock Info.
股票信息测试
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.stock_info import (
    StockInfo,
    StockInfoFetcher,
    get_stock_info,
    get_stock_info_fetcher,
    get_stock_name,
)


@pytest.fixture
def temp_cache_file():
    """创建临时缓存文件"""
    cache_data = {
        "update_time": "2024-01-01",
        "data": [
            {"code": "sh600000", "name": "浦发银行", "market": "A股"},
            {"code": "sh600519", "name": "贵州茅台", "market": "A股"},
            {"code": "sz000001", "name": "平安银行", "market": "A股"},
        ],
    }

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump(cache_data, f)
        cache_path = Path(f.name)

    yield cache_path

    if cache_path.exists():
        cache_path.unlink()


class TestStockInfo:
    """股票信息测试"""

    def test_stock_info_creation(self):
        """测试创建股票信息"""
        info = StockInfo(
            code="sh600000",
            name="浦发银行",
            industry="银行",
            sector="金融",
            market="A股",
        )

        assert info.code == "sh600000"
        assert info.name == "浦发银行"
        assert info.industry == "银行"

    def test_stock_info_to_dict(self):
        """测试股票信息转字典"""
        info = StockInfo(
            code="sh600000",
            name="浦发银行",
            industry="银行",
        )

        d = info.to_dict()

        assert d["code"] == "sh600000"
        assert d["name"] == "浦发银行"
        assert d["industry"] == "银行"
        assert d["sector"] == ""
        assert d["market"] == ""


class TestStockInfoFetcher:
    """股票信息获取器测试"""

    def test_load_cache(self, temp_cache_file):
        """测试加载缓存"""
        fetcher = StockInfoFetcher(cache_path=temp_cache_file.parent)
        fetcher.cache_file = temp_cache_file
        fetcher._cache = {}
        fetcher._load_cache()

        assert len(fetcher._cache) == 3
        assert "sh600000" in fetcher._cache
        assert fetcher._cache["sh600000"].name == "浦发银行"

    def test_get_stock_info(self, temp_cache_file):
        """测试获取股票信息"""
        fetcher = StockInfoFetcher(cache_path=temp_cache_file.parent)
        fetcher.cache_file = temp_cache_file
        fetcher._cache = {}
        fetcher._load_cache()

        info = fetcher.get_stock_info("sh600000")

        assert info.code == "sh600000"
        assert info.name == "浦发银行"

    def test_get_stock_name(self, temp_cache_file):
        """测试获取股票名称"""
        fetcher = StockInfoFetcher(cache_path=temp_cache_file.parent)
        fetcher.cache_file = temp_cache_file
        fetcher._cache = {}
        fetcher._load_cache()

        name = fetcher.get_stock_name("sh600519")

        assert name == "贵州茅台"

    def test_get_unknown_stock(self, temp_cache_file):
        """测试获取未知股票"""
        fetcher = StockInfoFetcher(cache_path=temp_cache_file.parent)
        fetcher.cache_file = temp_cache_file
        fetcher._cache = {}
        fetcher._load_cache()

        name = fetcher.get_stock_name("sh999999")

        assert name == "sh999999"

    def test_batch_get_names(self, temp_cache_file):
        """测试批量获取名称"""
        fetcher = StockInfoFetcher(cache_path=temp_cache_file.parent)
        fetcher.cache_file = temp_cache_file
        fetcher._cache = {}
        fetcher._load_cache()

        names = fetcher.batch_get_names(["sh600000", "sh600519", "sz000001"])

        assert names["sh600000"] == "浦发银行"
        assert names["sh600519"] == "贵州茅台"
        assert names["sz000001"] == "平安银行"


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_get_stock_info_fetcher(self):
        """测试获取全局获取器"""
        fetcher1 = get_stock_info_fetcher()
        fetcher2 = get_stock_info_fetcher()

        assert fetcher1 is fetcher2

    def test_get_stock_name_function(self):
        """测试获取股票名称函数"""
        name = get_stock_name("sh600000")

        assert isinstance(name, str)

    def test_get_stock_info_function(self):
        """测试获取股票信息函数"""
        info = get_stock_info("sh600000")

        assert isinstance(info, StockInfo)
        assert info.code == "sh600000"

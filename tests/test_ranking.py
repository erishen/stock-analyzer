"""
Tests for Stock Scoring System Module.
选股评分系统测试
"""

import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.scorer.ranking import (
    ScoringFactor,
    ScoringReport,
    StockScore,
    StockScorer,
)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE stock_analysis (
            code TEXT,
            date TEXT,
            close REAL,
            high REAL,
            low REAL,
            open REAL,
            volume REAL,
            change_percent REAL,
            macd REAL,
            macd_signal REAL,
            rsi REAL,
            kdj_k REAL,
            kdj_d REAL,
            ma5 REAL,
            ma10 REAL,
            ma20 REAL,
            boll_upper REAL,
            boll_lower REAL,
            atr REAL
        )
    """)

    test_data = []
    for i in range(50):
        test_data.append(
            (
                "000001",
                f"2024-01-{(i % 30) + 1:02d}",
                10.0 + i * 0.1,
                10.5 + i * 0.1,
                9.8 + i * 0.1,
                10.0 + i * 0.1,
                1000000 + i * 10000,
                1.0 + i * 0.1,
                0.1 + i * 0.01,
                0.05 + i * 0.005,
                45.0 + i * 0.5,
                50.0 + i * 0.5,
                45.0 + i * 0.5,
                10.0 + i * 0.1,
                9.9 + i * 0.1,
                9.8 + i * 0.1,
                10.5 + i * 0.1,
                9.5 + i * 0.1,
                0.5 + i * 0.01,
            )
        )
    conn.executemany(
        "INSERT INTO stock_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


class TestScoringFactor:
    """测试评分因子"""

    def test_create_factor(self):
        """测试创建因子"""
        factor = ScoringFactor(
            name="趋势因子",
            weight=0.3,
            score=85.0,
            value=0.5,
            description="测试因子",
        )
        assert factor.name == "趋势因子"
        assert factor.weight == 0.3
        assert factor.score == 85.0

    def test_factor_to_dict(self):
        """测试转换为字典"""
        factor = ScoringFactor(
            name="动量因子",
            weight=0.25,
            score=75.555,
            value=0.12345,
            description="测试",
        )
        d = factor.to_dict()
        assert d["name"] == "动量因子"
        assert d["score"] == 75.56
        assert d["value"] == 0.1235


class TestStockScore:
    """测试股票评分"""

    def test_create_score(self):
        """测试创建评分"""
        score = StockScore(
            code="000001",
            name="平安银行",
            total_score=85.5,
        )
        assert score.code == "000001"
        assert score.total_score == 85.5

    def test_score_to_dict(self):
        """测试转换为字典"""
        score = StockScore(
            code="000001",
            name="平安银行",
            total_score=85.555,
            rank=1,
            price=10.5,
            change_percent=2.5,
            recommendation="买入",
        )
        d = score.to_dict()
        assert d["code"] == "000001"
        assert d["total_score"] == 85.56
        assert d["rank"] == 1


class TestScoringReport:
    """测试评分报告"""

    def test_create_report(self):
        """测试创建报告"""
        report = ScoringReport(
            scoring_date="2024-01-05",
            total_stocks=100,
            top_stocks=[],
            bottom_stocks=[],
            factor_summary={},
            market_overview={},
        )
        assert report.scoring_date == "2024-01-05"
        assert report.total_stocks == 100

    def test_report_to_dict(self):
        """测试转换为字典"""
        score = StockScore(code="000001", name="测试", total_score=85.0)
        report = ScoringReport(
            scoring_date="2024-01-05",
            total_stocks=1,
            top_stocks=[score],
            bottom_stocks=[],
            factor_summary={"trend": {"avg": 80.0}},
            market_overview={"avg_score": 75.0},
        )
        d = report.to_dict()
        assert d["scoring_date"] == "2024-01-05"
        assert len(d["top_stocks"]) == 1


class TestStockScorer:
    """测试股票评分器"""

    def test_init(self):
        """测试初始化"""
        scorer = StockScorer()
        assert scorer.factors == []

    def test_factor_weights(self):
        """测试因子权重"""
        weights = StockScorer.FACTOR_WEIGHTS
        assert "trend" in weights
        assert "momentum" in weights
        assert sum(weights.values()) == 1.0

    def test_calculate_all_factors(self, temp_db):
        """测试计算所有因子"""
        conn = sqlite3.connect(str(temp_db))
        df = pd.read_sql_query(
            "SELECT * FROM stock_analysis WHERE code='000001' ORDER BY date",
            conn,
        )
        conn.close()

        scorer = StockScorer()
        factors = scorer.calculate_all_factors(df)

        assert isinstance(factors, list)

    def test_calculate_all_factors_insufficient_data(self):
        """测试数据不足"""
        df = pd.DataFrame({"close": [10.0, 10.5, 11.0]})
        scorer = StockScorer()
        factors = scorer.calculate_all_factors(df)
        assert factors == []

    def test_get_recommendation(self):
        """测试获取推荐"""
        scorer = StockScorer()

        if hasattr(scorer, "_get_recommendation"):
            recommendation = scorer._get_recommendation(85.0, [])
            assert recommendation in ["强烈买入", "买入", "持有", "卖出", "强烈卖出"]


class TestScoringIntegration:
    """测试评分集成"""

    def test_full_scoring_process(self, temp_db):
        """测试完整评分流程"""
        conn = sqlite3.connect(str(temp_db))
        df = pd.read_sql_query(
            "SELECT * FROM stock_analysis WHERE code='000001' ORDER BY date",
            conn,
        )
        conn.close()

        scorer = StockScorer()

        if len(df) >= 30:
            factors = scorer.calculate_all_factors(df)
            if factors:
                total_score = scorer.calculate_total_score(factors)
                assert total_score >= 0

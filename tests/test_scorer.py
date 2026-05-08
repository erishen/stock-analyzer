"""
Tests for Scorer Module.
评分模块测试
"""



from scorer.ranking import (
    ScoringFactor,
    ScoringReport,
    StockScore,
)


class TestScoringFactor:
    """评分因子测试"""

    def test_create_factor(self):
        """测试创建评分因子"""
        factor = ScoringFactor(
            name="trend",
            weight=0.25,
            score=75.0,
            value=1.5,
            description="趋势因子",
        )
        assert factor.name == "trend"
        assert factor.weight == 0.25
        assert factor.score == 75.0

    def test_factor_to_dict(self):
        """测试因子转换为字典"""
        factor = ScoringFactor(
            name="momentum",
            weight=0.3,
            score=85.567,
            value=2.3456,
            description="动量因子",
        )
        d = factor.to_dict()
        assert d["name"] == "momentum"
        assert d["weight"] == 0.3
        assert d["score"] == 85.57
        assert d["value"] == 2.3456


class TestStockScore:
    """股票评分测试"""

    def test_create_stock_score(self):
        """测试创建股票评分"""
        score = StockScore(
            code="sh600000",
            name="浦发银行",
            total_score=85.5,
            price=10.5,
            change_percent=2.5,
            recommendation="买入",
        )
        assert score.code == "sh600000"
        assert score.name == "浦发银行"
        assert score.total_score == 85.5
        assert score.rank == 0

    def test_stock_score_to_dict(self):
        """测试股票评分转换为字典"""
        factor = ScoringFactor(name="trend", weight=0.25, score=80.0)
        score = StockScore(
            code="sh600000",
            name="浦发银行",
            total_score=85.567,
            rank=1,
            factors=[factor],
            price=10.567,
            change_percent=2.567,
            recommendation="买入",
        )
        d = score.to_dict()
        assert d["code"] == "sh600000"
        assert d["total_score"] == 85.57
        assert d["rank"] == 1
        assert len(d["factors"]) == 1
        assert d["price"] == 10.57
        assert d["change_percent"] == 2.57

    def test_stock_score_with_factors(self):
        """测试带因子的股票评分"""
        factors = [
            ScoringFactor(name="trend", weight=0.25, score=80.0),
            ScoringFactor(name="momentum", weight=0.25, score=90.0),
        ]
        score = StockScore(
            code="sh600000",
            name="浦发银行",
            total_score=85.0,
            factors=factors,
        )
        assert len(score.factors) == 2


class TestScoringReport:
    """评分报告测试"""

    def test_create_report(self):
        """测试创建评分报告"""
        top_stock = StockScore(
            code="sh600000",
            name="浦发银行",
            total_score=90.0,
        )
        bottom_stock = StockScore(
            code="sh600001",
            name="邯郸钢铁",
            total_score=30.0,
        )
        report = ScoringReport(
            scoring_date="2026-04-17",
            total_stocks=5000,
            top_stocks=[top_stock],
            bottom_stocks=[bottom_stock],
            factor_summary={"trend": {"avg": 50.0}},
            market_overview={"bull_ratio": 0.6},
        )
        assert report.scoring_date == "2026-04-17"
        assert report.total_stocks == 5000
        assert len(report.top_stocks) == 1
        assert len(report.bottom_stocks) == 1

    def test_report_to_dict(self):
        """测试报告转换为字典"""
        stock = StockScore(
            code="sh600000",
            name="浦发银行",
            total_score=90.0,
        )
        report = ScoringReport(
            scoring_date="2026-04-17",
            total_stocks=5000,
            top_stocks=[stock],
            bottom_stocks=[],
            factor_summary={"trend": {"avg": 50.0}},
            market_overview={"bull_ratio": 0.6},
        )
        d = report.to_dict()
        assert d["scoring_date"] == "2026-04-17"
        assert d["total_stocks"] == 5000
        assert len(d["top_stocks"]) == 1
        assert d["factor_summary"]["trend"]["avg"] == 50.0

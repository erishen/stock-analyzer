"""
Tests for Sector Rotation Module.
行业轮动模块测试
"""



from strategy.sector_rotation import (
    RotationSignal,
    SectorAnalysisResult,
    SectorInfo,
    SectorRotation,
    SectorRotationAnalyzer,
    SectorStrength,
)


class TestSectorStrength:
    """行业强度枚举测试"""

    def test_strength_values(self):
        """测试强度值"""
        assert SectorStrength.STRONG.value == "strong"
        assert SectorStrength.WEAK.value == "weak"
        assert SectorStrength.NEUTRAL.value == "neutral"


class TestRotationSignal:
    """轮动信号枚举测试"""

    def test_signal_values(self):
        """测试信号值"""
        assert RotationSignal.ENTER.value == "enter"
        assert RotationSignal.EXIT.value == "exit"
        assert RotationSignal.HOLD.value == "hold"
        assert RotationSignal.REDUCE.value == "reduce"


class TestSectorInfo:
    """行业信息测试"""

    def test_sector_info_creation(self):
        """测试行业信息创建"""
        info = SectorInfo(
            name="银行",
            stocks=["sh600000", "sh600036"],
            avg_return=0.02,
            avg_volume=1000000,
            strength=SectorStrength.STRONG,
            rank=1,
            momentum=0.03,
            trend="多头",
        )
        assert info.name == "银行"
        assert len(info.stocks) == 2
        assert info.strength == SectorStrength.STRONG

    def test_sector_info_to_dict(self):
        """测试行业信息转字典"""
        info = SectorInfo(
            name="银行",
            stocks=["sh600000", "sh600036"],
            avg_return=0.02,
            avg_volume=1000000,
            strength=SectorStrength.STRONG,
            rank=1,
            momentum=0.03,
            trend="多头",
        )

        d = info.to_dict()
        assert d["name"] == "银行"
        assert d["stock_count"] == 2
        assert d["avg_return"] == 2.0
        assert d["strength"] == "strong"


class TestSectorRotation:
    """行业轮动信号测试"""

    def test_rotation_creation(self):
        """测试轮动信号创建"""
        rotation = SectorRotation(
            sector="银行",
            signal=RotationSignal.ENTER,
            score=60,
            reason="行业强势;排名靠前",
            recommended_weight=0.25,
        )
        assert rotation.sector == "银行"
        assert rotation.signal == RotationSignal.ENTER
        assert rotation.score == 60

    def test_rotation_to_dict(self):
        """测试轮动信号转字典"""
        rotation = SectorRotation(
            sector="银行",
            signal=RotationSignal.ENTER,
            score=60,
            reason="行业强势",
            recommended_weight=0.25,
        )

        d = rotation.to_dict()
        assert d["sector"] == "银行"
        assert d["signal"] == "enter"
        assert d["recommended_weight"] == 25.0


class TestSectorAnalysisResult:
    """行业分析结果测试"""

    def test_result_creation(self):
        """测试结果创建"""
        info = SectorInfo(
            name="银行",
            stocks=["sh600000"],
            avg_return=0.02,
            avg_volume=1000000,
            strength=SectorStrength.STRONG,
            rank=1,
            momentum=0.03,
            trend="多头",
        )

        rotation = SectorRotation(
            sector="银行",
            signal=RotationSignal.ENTER,
            score=60,
            reason="强势",
            recommended_weight=0.25,
        )

        result = SectorAnalysisResult(
            date="2024-01-01",
            sectors=[info],
            rotations=[rotation],
            top_sectors=["银行"],
            bottom_sectors=["传媒"],
            market_breadth=0.6,
        )

        assert result.date == "2024-01-01"
        assert len(result.sectors) == 1
        assert result.top_sectors == ["银行"]

    def test_result_to_dict(self):
        """测试结果转字典"""
        info = SectorInfo(
            name="银行",
            stocks=["sh600000"],
            avg_return=0.02,
            avg_volume=1000000,
            strength=SectorStrength.STRONG,
            rank=1,
            momentum=0.03,
            trend="多头",
        )

        rotation = SectorRotation(
            sector="银行",
            signal=RotationSignal.ENTER,
            score=60,
            reason="强势",
            recommended_weight=0.25,
        )

        result = SectorAnalysisResult(
            date="2024-01-01",
            sectors=[info],
            rotations=[rotation],
            top_sectors=["银行"],
            bottom_sectors=["传媒"],
            market_breadth=0.6,
        )

        d = result.to_dict()
        assert d["date"] == "2024-01-01"
        assert len(d["sectors"]) == 1
        assert d["market_breadth"] == 60.0


class TestSectorRotationAnalyzer:
    """行业轮动分析器测试"""

    def test_analyzer_creation(self):
        """测试分析器创建"""
        analyzer = SectorRotationAnalyzer(
            lookback_days=20,
            top_n=5,
            momentum_threshold=0.05,
        )
        assert analyzer.lookback_days == 20
        assert analyzer.top_n == 5
        assert analyzer.momentum_threshold == 0.05

    def test_get_sector_stocks(self):
        """测试获取行业股票"""
        analyzer = SectorRotationAnalyzer()

        stocks = analyzer.get_sector_stocks("银行")
        assert isinstance(stocks, list)
        assert len(stocks) > 0

    def test_get_sector_stocks_unknown(self):
        """测试获取未知行业股票"""
        analyzer = SectorRotationAnalyzer()

        stocks = analyzer.get_sector_stocks("未知行业")
        assert stocks == []

    def test_generate_rotation_signal_strong(self):
        """测试强势行业信号"""
        analyzer = SectorRotationAnalyzer()

        sector = SectorInfo(
            name="银行",
            stocks=["sh600000"],
            avg_return=0.15,
            avg_volume=1000000,
            strength=SectorStrength.STRONG,
            rank=1,
            momentum=0.15,
            trend="多头",
        )

        all_sectors = [sector]
        for i in range(4):
            all_sectors.append(
                SectorInfo(
                    name=f"行业{i}",
                    stocks=[],
                    avg_return=0,
                    avg_volume=0,
                    strength=SectorStrength.NEUTRAL,
                    rank=i + 2,
                    momentum=0,
                    trend="震荡",
                )
            )

        signal, score, _reason, weight = analyzer._generate_rotation_signal(sector, all_sectors)

        assert signal == RotationSignal.ENTER
        assert score >= 50
        assert weight > 0

    def test_generate_rotation_signal_weak(self):
        """测试弱势行业信号"""
        analyzer = SectorRotationAnalyzer()

        sector = SectorInfo(
            name="传媒",
            stocks=["sh000156"],
            avg_return=-0.15,
            avg_volume=500000,
            strength=SectorStrength.WEAK,
            rank=10,
            momentum=-0.12,
            trend="空头",
        )

        all_sectors = [sector]
        for i in range(9):
            all_sectors.append(
                SectorInfo(
                    name=f"行业{i}",
                    stocks=[],
                    avg_return=0,
                    avg_volume=0,
                    strength=SectorStrength.NEUTRAL,
                    rank=i + 2,
                    momentum=0,
                    trend="震荡",
                )
            )

        signal, score, _reason, _weight = analyzer._generate_rotation_signal(sector, all_sectors)

        assert signal == RotationSignal.EXIT
        assert score < 0

    def test_get_sector_allocation(self):
        """测试行业配置"""
        analyzer = SectorRotationAnalyzer()

        info1 = SectorInfo(
            name="银行",
            stocks=["sh600000"],
            avg_return=0.1,
            avg_volume=1000000,
            strength=SectorStrength.STRONG,
            rank=1,
            momentum=0.08,
            trend="多头",
        )

        rotation1 = SectorRotation(
            sector="银行",
            signal=RotationSignal.ENTER,
            score=70,
            reason="强势",
            recommended_weight=0.3,
        )

        result = SectorAnalysisResult(
            date="2024-01-01",
            sectors=[info1],
            rotations=[rotation1],
            top_sectors=["银行"],
            bottom_sectors=[],
            market_breadth=0.5,
        )

        allocation = analyzer.get_sector_allocation(result)

        assert isinstance(allocation, dict)
        assert "银行" in allocation

    def test_get_sector_allocation_empty(self):
        """测试空配置"""
        analyzer = SectorRotationAnalyzer()

        result = SectorAnalysisResult(
            date="2024-01-01",
            sectors=[],
            rotations=[],
            top_sectors=["银行", "证券", "保险"],
            bottom_sectors=[],
            market_breadth=0.5,
        )

        allocation = analyzer.get_sector_allocation(result)

        assert len(allocation) == 3
        assert abs(sum(allocation.values()) - 1.0) < 0.01

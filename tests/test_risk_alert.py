"""
Tests for Risk Alert System.
"""

import pytest

from src.scanner.risk_alert import (
    AlertLevel,
    AlertType,
    RiskAlert,
    RiskAlertSystem,
    RiskConfig,
)


class TestRiskConfig:
    """Test RiskConfig"""

    def test_default_config(self):
        """Test default configuration"""
        config = RiskConfig()
        assert config.max_drawdown_threshold == 0.10
        assert config.volatility_threshold == 0.30
        assert config.concentration_threshold == 0.30
        assert config.stop_loss_threshold == 0.08
        assert config.take_profit_threshold == 0.20

    def test_custom_config(self):
        """Test custom configuration"""
        config = RiskConfig(
            max_drawdown_threshold=0.15,
            stop_loss_threshold=0.05,
        )
        assert config.max_drawdown_threshold == 0.15
        assert config.stop_loss_threshold == 0.05


class TestRiskAlert:
    """Test RiskAlert"""

    def test_alert_creation(self):
        """Test creating an alert"""
        alert = RiskAlert(
            alert_type=AlertType.MAX_DRAWDOWN,
            level=AlertLevel.DANGER,
            message="Test alert",
            value=0.15,
            threshold=0.10,
        )
        assert alert.alert_type == AlertType.MAX_DRAWDOWN
        assert alert.level == AlertLevel.DANGER
        assert alert.message == "Test alert"
        assert alert.value == 0.15

    def test_alert_to_dict(self):
        """Test alert serialization"""
        alert = RiskAlert(
            alert_type=AlertType.STOP_LOSS,
            level=AlertLevel.WARNING,
            message="Stop loss warning",
            code="000001",
            value=-0.05,
            threshold=-0.08,
        )
        d = alert.to_dict()
        assert d["alert_type"] == "stop_loss"
        assert d["level"] == "warning"
        assert d["code"] == "000001"
        assert d["value"] == -0.05


class TestRiskAlertSystem:
    """Test RiskAlertSystem"""

    def test_check_max_drawdown_normal(self):
        """Test normal drawdown (no alert)"""
        system = RiskAlertSystem()
        alert = system.check_max_drawdown(95000, 100000)
        assert alert is None

    def test_check_max_drawdown_warning(self):
        """Test drawdown warning"""
        system = RiskAlertSystem()
        alert = system.check_max_drawdown(91500, 100000)
        assert alert is not None
        assert alert.level == AlertLevel.WARNING

    def test_check_max_drawdown_danger(self):
        """Test drawdown danger"""
        system = RiskAlertSystem()
        alert = system.check_max_drawdown(89000, 100000)
        assert alert is not None
        assert alert.level == AlertLevel.DANGER

    def test_check_max_drawdown_critical(self):
        """Test drawdown critical"""
        system = RiskAlertSystem()
        alert = system.check_max_drawdown(84000, 100000)
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL

    def test_check_volatility_normal(self):
        """Test normal volatility"""
        system = RiskAlertSystem()
        returns = [0.01, -0.01, 0.02, -0.02] * 10
        alert = system.check_volatility(returns)
        assert alert is None

    def test_check_volatility_high(self):
        """Test high volatility"""
        system = RiskAlertSystem()
        returns = [0.05, -0.05, 0.06, -0.06] * 10
        alert = system.check_volatility(returns)
        assert alert is not None
        assert alert.alert_type == AlertType.VOLATILITY

    def test_check_concentration_normal(self):
        """Test normal concentration"""
        system = RiskAlertSystem()
        positions = {"000001": 15000, "000002": 15000, "000003": 15000, "000004": 15000}
        alert = system.check_concentration(positions, 60000)
        assert alert is None

    def test_check_concentration_high(self):
        """Test high concentration"""
        system = RiskAlertSystem()
        positions = {"000001": 40000, "000002": 10000, "000003": 10000}
        alert = system.check_concentration(positions, 60000)
        assert alert is not None
        assert alert.alert_type == AlertType.CONCENTRATION
        assert alert.code == "000001"

    def test_check_stop_loss_normal(self):
        """Test normal loss (no alert)"""
        system = RiskAlertSystem()
        alert = system.check_stop_loss("000001", 10.0, 9.5)
        assert alert is None

    def test_check_stop_loss_triggered(self):
        """Test stop loss triggered"""
        system = RiskAlertSystem()
        alert = system.check_stop_loss("000001", 10.0, 9.0)
        assert alert is not None
        assert alert.alert_type == AlertType.STOP_LOSS
        assert alert.level == AlertLevel.DANGER

    def test_check_take_profit_normal(self):
        """Test normal profit (no alert)"""
        system = RiskAlertSystem()
        alert = system.check_take_profit("000001", 10.0, 11.0)
        assert alert is None

    def test_check_take_profit_triggered(self):
        """Test take profit triggered"""
        system = RiskAlertSystem()
        alert = system.check_take_profit("000001", 10.0, 12.5)
        assert alert is not None
        assert alert.alert_type == AlertType.TAKE_PROFIT
        assert alert.level == AlertLevel.INFO

    def test_check_position_limit_normal(self):
        """Test normal position (no alert)"""
        system = RiskAlertSystem()
        alert = system.check_position_limit("000001", 15000, 100000)
        assert alert is None

    def test_check_position_limit_exceeded(self):
        """Test position limit exceeded"""
        system = RiskAlertSystem()
        alert = system.check_position_limit("000001", 25000, 100000)
        assert alert is not None
        assert alert.alert_type == AlertType.POSITION_LIMIT

    def test_check_price_change_normal(self):
        """Test normal price change"""
        system = RiskAlertSystem()
        alert = system.check_price_change("000001", 10.0, 10.3)
        assert alert is None

    def test_check_price_change_significant(self):
        """Test significant price change"""
        system = RiskAlertSystem()
        alert = system.check_price_change("000001", 10.0, 10.6)
        assert alert is not None
        assert alert.alert_type == AlertType.PRICE_CHANGE

    def test_run_all_checks(self):
        """Test running all checks"""
        system = RiskAlertSystem()
        positions = {
            "000001": {
                "entry_price": 10.0,
                "current_price": 9.0,
                "value": 30000,
            },
        }
        equity_curve = [100000, 95000, 90000, 85000]
        returns = [0.01, -0.02, 0.01, -0.01] * 10
        prices = {"000001": (10.0, 9.0)}

        alerts = system.run_all_checks(positions, equity_curve, returns, prices)
        assert len(alerts) > 0

    def test_get_alerts_by_level(self):
        """Test getting alerts by level"""
        system = RiskAlertSystem()
        system.alerts = [
            RiskAlert(AlertType.MAX_DRAWDOWN, AlertLevel.DANGER, "1"),
            RiskAlert(AlertType.STOP_LOSS, AlertLevel.WARNING, "2"),
            RiskAlert(AlertType.VOLATILITY, AlertLevel.DANGER, "3"),
        ]

        danger_alerts = system.get_alerts_by_level(AlertLevel.DANGER)
        assert len(danger_alerts) == 2

    def test_has_critical_alerts(self):
        """Test checking for critical alerts"""
        system = RiskAlertSystem()
        system.alerts = [
            RiskAlert(AlertType.MAX_DRAWDOWN, AlertLevel.WARNING, "1"),
        ]
        assert not system.has_critical_alerts()

        system.alerts.append(
            RiskAlert(AlertType.MAX_DRAWDOWN, AlertLevel.CRITICAL, "2")
        )
        assert system.has_critical_alerts()

    def test_summary(self):
        """Test alert summary"""
        system = RiskAlertSystem()
        system.alerts = [
            RiskAlert(AlertType.MAX_DRAWDOWN, AlertLevel.DANGER, "1"),
            RiskAlert(AlertType.STOP_LOSS, AlertLevel.WARNING, "2"),
        ]

        summary = system.summary()
        assert summary["total_alerts"] == 2
        assert summary["by_level"]["danger"] == 1
        assert summary["by_level"]["warning"] == 1

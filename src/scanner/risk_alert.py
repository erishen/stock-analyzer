"""
Risk Alert System for Stock Analyzer.
风险预警系统 - 实时监控投资风险

功能:
1. 最大回撤预警
2. 波动率预警
3. 集中度预警
4. 止损止盈提醒
5. 市场风险预警
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AlertLevel(Enum):
    """预警级别"""
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


class AlertType(Enum):
    """预警类型"""
    MAX_DRAWDOWN = "max_drawdown"
    VOLATILITY = "volatility"
    CONCENTRATION = "concentration"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    POSITION_LIMIT = "position_limit"
    PRICE_CHANGE = "price_change"
    MARKET_RISK = "market_risk"


@dataclass
class RiskAlert:
    """风险预警项"""
    alert_type: AlertType
    level: AlertLevel
    message: str
    code: str = ""
    value: float = 0.0
    threshold: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "message": self.message,
            "code": self.code,
            "value": round(self.value, 4),
            "threshold": round(self.threshold, 4),
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class RiskConfig:
    """风险配置"""
    max_drawdown_threshold: float = 0.10
    volatility_threshold: float = 0.30
    concentration_threshold: float = 0.30
    stop_loss_threshold: float = 0.08
    take_profit_threshold: float = 0.20
    single_position_limit: float = 0.20
    total_position_limit: float = 0.60
    price_change_threshold: float = 0.05


class RiskAlertSystem:
    """风险预警系统"""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()
        self.alerts: list[RiskAlert] = []
        self.position_history: dict[str, list[dict]] = {}
        self.equity_curve: list[float] = []

    def check_max_drawdown(self, current_equity: float, peak_equity: float) -> RiskAlert | None:
        """检查最大回撤"""
        if peak_equity <= 0:
            return None

        drawdown = (peak_equity - current_equity) / peak_equity

        if drawdown >= self.config.max_drawdown_threshold:
            level = AlertLevel.CRITICAL if drawdown >= self.config.max_drawdown_threshold * 1.5 else AlertLevel.DANGER
            return RiskAlert(
                alert_type=AlertType.MAX_DRAWDOWN,
                level=level,
                message=f"最大回撤预警: {drawdown:.2%} 超过阈值 {self.config.max_drawdown_threshold:.2%}",
                value=drawdown,
                threshold=self.config.max_drawdown_threshold,
                details={"peak_equity": peak_equity, "current_equity": current_equity},
            )
        elif drawdown >= self.config.max_drawdown_threshold * 0.8:
            return RiskAlert(
                alert_type=AlertType.MAX_DRAWDOWN,
                level=AlertLevel.WARNING,
                message=f"最大回撤接近预警线: {drawdown:.2%}",
                value=drawdown,
                threshold=self.config.max_drawdown_threshold,
                details={"peak_equity": peak_equity, "current_equity": current_equity},
            )
        return None

    def check_volatility(self, returns: list[float]) -> RiskAlert | None:
        """检查波动率"""
        if len(returns) < 20:
            return None

        import numpy as np
        volatility = float(np.std(returns) * np.sqrt(252))

        if volatility >= self.config.volatility_threshold:
            level = AlertLevel.DANGER if volatility >= self.config.volatility_threshold * 1.5 else AlertLevel.WARNING
            return RiskAlert(
                alert_type=AlertType.VOLATILITY,
                level=level,
                message=f"波动率预警: {volatility:.2%} 超过阈值 {self.config.volatility_threshold:.2%}",
                value=volatility,
                threshold=self.config.volatility_threshold,
            )
        return None

    def check_concentration(self, positions: dict[str, float], total_value: float) -> RiskAlert | None:
        """检查持仓集中度"""
        if total_value <= 0 or not positions:
            return None

        max_position = max(positions.values())
        concentration = max_position / total_value

        if concentration >= self.config.concentration_threshold:
            max_code = max(positions.keys(), key=lambda k: positions[k])
            return RiskAlert(
                alert_type=AlertType.CONCENTRATION,
                level=AlertLevel.WARNING,
                message=f"持仓集中度预警: {max_code} 占比 {concentration:.2%}",
                code=max_code,
                value=concentration,
                threshold=self.config.concentration_threshold,
                details={"positions": {k: v / total_value for k, v in positions.items()}},
            )
        return None

    def check_stop_loss(
        self,
        code: str,
        entry_price: float,
        current_price: float,
    ) -> RiskAlert | None:
        """检查止损"""
        if entry_price <= 0:
            return None

        loss_pct = (current_price - entry_price) / entry_price

        if loss_pct <= -self.config.stop_loss_threshold:
            return RiskAlert(
                alert_type=AlertType.STOP_LOSS,
                level=AlertLevel.DANGER,
                message=f"止损预警: {code} 亏损 {abs(loss_pct):.2%}",
                code=code,
                value=loss_pct,
                threshold=-self.config.stop_loss_threshold,
                details={"entry_price": entry_price, "current_price": current_price},
            )
        return None

    def check_take_profit(
        self,
        code: str,
        entry_price: float,
        current_price: float,
    ) -> RiskAlert | None:
        """检查止盈"""
        if entry_price <= 0:
            return None

        profit_pct = (current_price - entry_price) / entry_price

        if profit_pct >= self.config.take_profit_threshold:
            return RiskAlert(
                alert_type=AlertType.TAKE_PROFIT,
                level=AlertLevel.INFO,
                message=f"止盈提醒: {code} 盈利 {profit_pct:.2%}",
                code=code,
                value=profit_pct,
                threshold=self.config.take_profit_threshold,
                details={"entry_price": entry_price, "current_price": current_price},
            )
        return None

    def check_position_limit(
        self,
        code: str,
        position_value: float,
        total_capital: float,
    ) -> RiskAlert | None:
        """检查仓位限制"""
        if total_capital <= 0:
            return None

        position_pct = position_value / total_capital

        if position_pct >= self.config.single_position_limit:
            return RiskAlert(
                alert_type=AlertType.POSITION_LIMIT,
                level=AlertLevel.WARNING,
                message=f"单只股票仓位超限: {code} 占比 {position_pct:.2%}",
                code=code,
                value=position_pct,
                threshold=self.config.single_position_limit,
            )
        return None

    def check_price_change(
        self,
        code: str,
        prev_price: float,
        current_price: float,
    ) -> RiskAlert | None:
        """检查价格异动"""
        if prev_price <= 0:
            return None

        change_pct = abs(current_price - prev_price) / prev_price

        if change_pct >= self.config.price_change_threshold:
            direction = "上涨" if current_price > prev_price else "下跌"
            level = AlertLevel.DANGER if change_pct >= 0.095 else AlertLevel.WARNING
            return RiskAlert(
                alert_type=AlertType.PRICE_CHANGE,
                level=level,
                message=f"价格异动: {code} {direction} {change_pct:.2%}",
                code=code,
                value=change_pct,
                threshold=self.config.price_change_threshold,
                details={"prev_price": prev_price, "current_price": current_price},
            )
        return None

    def run_all_checks(
        self,
        positions: dict[str, dict[str, float]],
        equity_curve: list[float],
        returns: list[float],
        prices: dict[str, tuple[float, float]],
    ) -> list[RiskAlert]:
        """运行所有检查"""
        alerts = []

        if equity_curve:
            peak = max(equity_curve)
            current = equity_curve[-1]
            alert = self.check_max_drawdown(current, peak)
            if alert:
                alerts.append(alert)

        if returns:
            alert = self.check_volatility(returns)
            if alert:
                alerts.append(alert)

        total_value = sum(p.get("value", 0) for p in positions.values())
        position_values = {code: p.get("value", 0) for code, p in positions.items()}
        alert = self.check_concentration(position_values, total_value)
        if alert:
            alerts.append(alert)

        for code, pos in positions.items():
            entry_price = pos.get("entry_price", 0)
            current_price = pos.get("current_price", 0)

            alert = self.check_stop_loss(code, entry_price, current_price)
            if alert:
                alerts.append(alert)

            alert = self.check_take_profit(code, entry_price, current_price)
            if alert:
                alerts.append(alert)

            position_value = pos.get("value", 0)
            alert = self.check_position_limit(code, position_value, total_value)
            if alert:
                alerts.append(alert)

        for code, (prev_price, current_price) in prices.items():
            alert = self.check_price_change(code, prev_price, current_price)
            if alert:
                alerts.append(alert)

        self.alerts = alerts
        return alerts

    def get_alerts_by_level(self, level: AlertLevel) -> list[RiskAlert]:
        """按级别获取预警"""
        return [a for a in self.alerts if a.level == level]

    def get_alerts_by_type(self, alert_type: AlertType) -> list[RiskAlert]:
        """按类型获取预警"""
        return [a for a in self.alerts if a.alert_type == alert_type]

    def has_critical_alerts(self) -> bool:
        """是否有严重预警"""
        return any(a.level == AlertLevel.CRITICAL for a in self.alerts)

    def has_danger_alerts(self) -> bool:
        """是否有危险预警"""
        return any(a.level == AlertLevel.DANGER for a in self.alerts)

    def summary(self) -> dict[str, Any]:
        """预警摘要"""
        return {
            "total_alerts": len(self.alerts),
            "by_level": {
                "critical": len(self.get_alerts_by_level(AlertLevel.CRITICAL)),
                "danger": len(self.get_alerts_by_level(AlertLevel.DANGER)),
                "warning": len(self.get_alerts_by_level(AlertLevel.WARNING)),
                "info": len(self.get_alerts_by_level(AlertLevel.INFO)),
            },
            "by_type": {
                t.value: len(self.get_alerts_by_type(t)) for t in AlertType
            },
            "has_critical": self.has_critical_alerts(),
            "has_danger": self.has_danger_alerts(),
            "alerts": [a.to_dict() for a in self.alerts],
        }


risk_alert_system = RiskAlertSystem()

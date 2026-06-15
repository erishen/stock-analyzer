"""枚举类型定义"""

from enum import Enum


class SignalType(str, Enum):
    """信号类型"""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderType(str, Enum):
    """订单类型"""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """订单状态"""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Market(str, Enum):
    """市场类型"""

    SH = "SH"  # 上海
    SZ = "SZ"  # 深圳
    BJ = "BJ"  # 北京
    HK = "HK"  # 香港
    US = "US"  # 美股


class AssetType(str, Enum):
    """资产类型"""

    STOCK = "STOCK"
    FUND = "FUND"
    BOND = "BOND"
    CRYPTO = "CRYPTO"
    CASH = "CASH"
    OTHER = "OTHER"


class RiskLevel(str, Enum):
    """风险等级"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

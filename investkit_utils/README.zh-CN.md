# InvestKit 共享模块

> 统一的配置、日志、工具、异常、类型定义和测试工具

## 模块结构

```
shared/
├── __init__.py           # 模块入口
├── config/
│   └── config.template.yaml  # 配置模板
├── log_utils/
│   ├── __init__.py       # 模块入口
│   ├── config.py         # 日志配置
│   ├── context.py        # 上下文管理
│   ├── formatters.py     # 格式化器
│   ├── logger.py         # Logger 类
│   └── manager.py        # 日志管理器
├── api_docs/
│   ├── __init__.py       # 模块入口
│   ├── services.py       # 服务定义
│   ├── openapi.py        # OpenAPI 处理
│   └── server.py         # 文档服务
├── utils/
│   ├── __init__.py       # 模块入口
│   ├── datetime_utils.py # 日期时间工具
│   ├── retry.py          # 重试装饰器
│   ├── validators.py     # 数据验证器
│   ├── numeric.py        # 数值计算
│   └── string_utils.py   # 字符串工具
├── exceptions/
│   ├── __init__.py       # 模块入口
│   ├── base.py           # 基础异常类
│   └── handlers.py       # 异常处理器
├── types/
│   ├── __init__.py       # 模块入口
│   ├── enums.py          # 枚举类型
│   └── models.py         # 数据模型
├── testing/
│   ├── __init__.py       # 模块入口
│   ├── mocks.py          # Mock 工具
│   ├── assertions.py     # 断言工具
│   ├── fixtures.py       # 测试 fixtures
│   └── data_generators.py# 数据生成器
└── README.md             # 本文档
```

## 快速开始

```python
from shared import get_logger, setup_logging, retry, ValidationError
from investkit_utils.types import StockInfo, TradeSignal, SignalType

# 初始化日志
setup_logging(level="INFO", log_format="json")

# 获取 logger
logger = get_logger(__name__)
logger.info_with_data("操作成功", {"user_id": "123"})

# 使用重试装饰器
@retry(max_attempts=3, delay=1.0)
def fetch_data():
    return requests.get("https://api.example.com/data")

# 使用类型定义
signal = TradeSignal(
    symbol="000001",
    signal_type=SignalType.BUY,
    confidence=0.85,
    reason="MACD 金叉"
)
```

---

## 1. 统一日志

```python
from investkit_utils.log_utils import get_logger, setup_logging

# 初始化日志 (可选，默认使用 JSON 格式)
setup_logging(
    level="INFO",
    log_format="json",
    console=True
)

# 获取 logger
logger = get_logger(__name__)

# 基本日志
logger.info("操作成功")
logger.error("操作失败")

# 带数据的日志
logger.info_with_data("用户登录", {
    "user_id": "123",
    "ip": "192.168.1.1"
})

# 关联 ID (用于追踪请求)
from investkit_utils.log_utils import set_correlation_id
set_correlation_id("req-abc-123")
```

**日志格式:**

```json
{
  "timestamp": "2026-04-30T09:30:00.123456Z",
  "level": "INFO",
  "message": "用户登录成功",
  "logger": "asset_lens.auth",
  "correlation_id": "req-abc-123",
  "data": {"user_id": "123"}
}
```

---

## 2. 配置模板

复制配置模板到项目:

```bash
cp shared/config/config.template.yaml your-project/config/settings.yaml
```

配置说明:

| 配置项 | 说明 |
|--------|------|
| `app` | 应用基础配置 |
| `logging` | 日志配置 |
| `database` | 数据库配置 |
| `cache` | 缓存配置 |
| `api` | API 配置 |
| `llm` | LLM 配置 |
| `data_sources` | 数据源配置 |
| `ml` | ML 配置 |
| `monitoring` | 监控配置 |
| `security` | 安全配置 |

---

## 3. API 文档聚合

启动聚合文档服务:

```bash
make api-docs
# 访问 http://localhost:8080
```

或使用代码:

```python
from investkit_utils.api_docs import serve_aggregated_docs

app = serve_aggregated_docs(port=8080)
```

**访问地址:**
- http://localhost:8080 - 服务列表
- http://localhost:8080/docs - Swagger UI
- http://localhost:8080/redoc - ReDoc
- http://localhost:8080/openapi.json - OpenAPI JSON

---

## 4. 通用工具函数

```python
from investkit_utils.utils import (
    parse_date,
    format_date,
    retry,
    retry_async,
    validate_stock_code,
    safe_divide,
    round_to,
    percentage_change,
)

# 日期解析
date_obj = parse_date("2026-04-30")
date_str = format_date(date_obj)

# 重试装饰器
@retry(max_attempts=3, delay=1.0)
def fetch_data():
    ...

# 异步重试
@retry_async(max_attempts=3)
async def fetch_data_async():
    ...

# 数据验证
is_valid = validate_stock_code("000001")

# 数值计算
result = safe_divide(10, 0, default=0)  # 返回 0
rounded = round_to(3.14159, 2)  # 返回 3.14
pct = percentage_change(100, 120)  # 返回 20.0
```

---

## 5. 统一异常处理

```python
from investkit_utils.exceptions import (
    InvestKitError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    handle_exception,
)

# 抛出异常
raise ValidationError("无效的股票代码", field="stock_code", value="ABC")

# 处理异常
try:
    ...
except Exception as e:
    error_dict = handle_exception(e)
```

**异常类型:**

| 异常 | HTTP 状态码 | 说明 |
|------|------------|------|
| `ValidationError` | 400 | 数据验证错误 |
| `AuthenticationError` | 401 | 认证错误 |
| `AuthorizationError` | 403 | 授权错误 |
| `NotFoundError` | 404 | 资源未找到 |
| `RateLimitError` | 429 | 速率限制 |
| `DataError` | 422 | 数据错误 |
| `ExternalServiceError` | 502 | 外部服务错误 |

---

## 6. 共享类型定义

```python
from investkit_utils.types import (
    SignalType,
    OrderType,
    OrderStatus,
    Market,
    StockInfo,
    TradeSignal,
    Position,
    Portfolio,
    Order,
    RiskMetrics,
    MLPrediction,
)

# 创建股票信息
stock = StockInfo(
    code="000001",
    name="平安银行",
    market=Market.SZ,
    industry="银行"
)

# 创建交易信号
signal = TradeSignal(
    symbol="000001",
    signal_type=SignalType.BUY,
    confidence=0.85,
    reason="MACD 金叉"
)

# 创建投资组合
portfolio = Portfolio(
    name="我的组合",
    positions=[
        Position(symbol="000001", quantity=100, cost_price=10.0)
    ],
    cash=10000.0
)
portfolio.calculate_totals()
```

---

## 7. 测试工具函数

```python
from investkit_utils.testing import (
    mock_response,
    assert_dict_equal,
    temp_directory,
    temp_file,
    generate_test_stock_data,
    generate_test_portfolio,
)

# Mock HTTP 响应
response = mock_response({"data": "test"}, status_code=200)

# 断言字典相等
assert_dict_equal(actual, expected, ignore_keys=["timestamp"])

# 临时目录
with temp_directory() as tmpdir:
    filepath = os.path.join(tmpdir, "test.txt")

# 临时文件
with temp_file('{"key": "value"}', ".json") as filepath:
    ...

# 生成测试数据
stock_data = generate_test_stock_data(symbol="000001", days=30)
portfolio = generate_test_portfolio(symbols=["000001", "600000"])
```

---

## 服务配置

默认监控的服务:

| 服务 | URL | 前缀 |
|------|-----|------|
| asset-lens | http://localhost:8000 | /api/asset |
| langchain-llm-toolkit | http://localhost:8001 | /api/llm |
| lobster | http://localhost:8002 | /api/lobster |

自定义服务:

```python
from investkit_utils.api_docs import APIService, aggregate_openapi_docs

services = [
    APIService(
        name="my-service",
        url="http://localhost:3000",
        description="我的服务",
        prefix="/api/my",
    )
]

spec = await aggregate_openapi_docs(services)
```

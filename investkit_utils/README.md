# InvestKit Shared Modules

> Unified configuration, logging, utilities, exceptions, type definitions, and testing tools

## Module Structure

```
shared/
├── __init__.py             # Module entry
├── config/
│   └── config.template.yaml  # Config template
├── log_utils/
│   ├── __init__.py         # Module entry
│   ├── config.py           # Logging config
│   ├── context.py          # Context management
│   ├── formatters.py       # Formatters
│   ├── logger.py           # Logger class
│   └── manager.py          # Log manager
├── api_docs/
│   ├── __init__.py         # Module entry
│   ├── services.py         # Service definitions
│   ├── openapi.py          # OpenAPI processing
│   └── server.py           # Docs server
├── utils/
│   ├── __init__.py         # Module entry
│   ├── datetime_utils.py   # Date/time utilities
│   ├── retry.py            # Retry decorator
│   ├── validators.py       # Data validators
│   ├── numeric.py          # Numeric calculations
│   └── string_utils.py     # String utilities
├── exceptions/
│   ├── __init__.py         # Module entry
│   ├── base.py             # Base exception classes
│   └── handlers.py         # Exception handlers
├── types/
│   ├── __init__.py         # Module entry
│   ├── enums.py            # Enum types
│   └── models.py           # Data models
├── testing/
│   ├── __init__.py         # Module entry
│   ├── mocks.py            # Mock utilities
│   ├── assertions.py       # Assertion utilities
│   ├── fixtures.py         # Test fixtures
│   └── data_generators.py  # Data generators
└── README.md               # This file
```

## Quick Start

```python
from shared import get_logger, setup_logging, retry, ValidationError
from investkit_utils.types import StockInfo, TradeSignal, SignalType

# Initialize logging
setup_logging(level="INFO", log_format="json")

# Get logger
logger = get_logger(__name__)
logger.info_with_data("Operation successful", {"user_id": "123"})

# Use retry decorator
@retry(max_attempts=3, delay=1.0)
def fetch_data():
    return requests.get("https://api.example.com/data")

# Use type definitions
signal = TradeSignal(
    symbol="000001",
    signal_type=SignalType.BUY,
    confidence=0.85,
    reason="MACD golden cross"
)
```

---

## 1. Unified Logging

```python
from investkit_utils.log_utils import get_logger, setup_logging

# Initialize logging (optional, defaults to JSON format)
setup_logging(
    level="INFO",
    log_format="json",
    console=True
)

# Get logger
logger = get_logger(__name__)

# Basic logging
logger.info("Operation successful")
logger.error("Operation failed")

# Data-rich logging
logger.info_with_data("User login", {
    "user_id": "123",
    "ip": "192.168.1.1"
})

# Correlation ID (for request tracing)
from investkit_utils.log_utils import set_correlation_id
set_correlation_id("req-abc-123")
```

**Log Format:**

```json
{
  "timestamp": "2026-04-30T09:30:00.123456Z",
  "level": "INFO",
  "message": "User login succeeded",
  "logger": "asset_lens.auth",
  "correlation_id": "req-abc-123",
  "data": {"user_id": "123"}
}
```

---

## 2. Configuration Template

Copy the template to your project:

```bash
cp shared/config/config.template.yaml your-project/config/settings.yaml
```

Config reference:

| Key | Description |
|--------|------|
| `app` | Application base config |
| `logging` | Logging config |
| `database` | Database config |
| `cache` | Cache config |
| `api` | API config |
| `llm` | LLM config |
| `data_sources` | Data source config |
| `ml` | ML config |
| `monitoring` | Monitoring config |
| `security` | Security config |

---

## 3. API Documentation Aggregation

Start the aggregated docs service:

```bash
make api-docs
# Access http://localhost:8080
```

Or programmatically:

```python
from investkit_utils.api_docs import serve_aggregated_docs

app = serve_aggregated_docs(port=8080)
```

**Endpoints:**
- http://localhost:8080 - Service list
- http://localhost:8080/docs - Swagger UI
- http://localhost:8080/redoc - ReDoc
- http://localhost:8080/openapi.json - OpenAPI JSON

---

## 4. Common Utility Functions

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

# Date parsing
date_obj = parse_date("2026-04-30")
date_str = format_date(date_obj)

# Retry decorator
@retry(max_attempts=3, delay=1.0)
def fetch_data():
    ...

# Async retry
@retry_async(max_attempts=3)
async def fetch_data_async():
    ...

# Data validation
is_valid = validate_stock_code("000001")

# Numeric utilities
result = safe_divide(10, 0, default=0)  # returns 0
rounded = round_to(3.14159, 2)  # returns 3.14
pct = percentage_change(100, 120)  # returns 20.0
```

---

## 5. Unified Exception Handling

```python
from investkit_utils.exceptions import (
    InvestKitError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    handle_exception,
)

# Raise exceptions
raise ValidationError("Invalid stock code", field="stock_code", value="ABC")

# Handle exceptions
try:
    ...
except Exception as e:
    error_dict = handle_exception(e)
```

**Exception Types:**

| Exception | HTTP Status | Description |
|------|------------|------|
| `ValidationError` | 400 | Data validation error |
| `AuthenticationError` | 401 | Authentication error |
| `AuthorizationError` | 403 | Authorization error |
| `NotFoundError` | 404 | Resource not found |
| `RateLimitError` | 429 | Rate limit exceeded |
| `DataError` | 422 | Data error |
| `ExternalServiceError` | 502 | External service error |

---

## 6. Shared Type Definitions

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

# Create stock info
stock = StockInfo(
    code="000001",
    name="Ping An Bank",
    market=Market.SZ,
    industry="Banking"
)

# Create trade signal
signal = TradeSignal(
    symbol="000001",
    signal_type=SignalType.BUY,
    confidence=0.85,
    reason="MACD golden cross"
)

# Create portfolio
portfolio = Portfolio(
    name="My Portfolio",
    positions=[
        Position(symbol="000001", quantity=100, cost_price=10.0)
    ],
    cash=10000.0
)
portfolio.calculate_totals()
```

---

## 7. Testing Utilities

```python
from investkit_utils.testing import (
    mock_response,
    assert_dict_equal,
    temp_directory,
    temp_file,
    generate_test_stock_data,
    generate_test_portfolio,
)

# Mock HTTP response
response = mock_response({"data": "test"}, status_code=200)

# Assert dictionary equality
assert_dict_equal(actual, expected, ignore_keys=["timestamp"])

# Temporary directory
with temp_directory() as tmpdir:
    filepath = os.path.join(tmpdir, "test.txt")

# Temporary file
with temp_file('{"key": "value"}', ".json") as filepath:
    ...

# Generate test data
stock_data = generate_test_stock_data(symbol="000001", days=30)
portfolio = generate_test_portfolio(symbols=["000001", "600000"])
```

---

## Service Configuration

Default monitored services:

| Service | URL | Prefix |
|------|-----|------|
| asset-lens | http://localhost:8000 | /api/asset |
| langchain-llm-toolkit | http://localhost:8001 | /api/llm |
| lobster | http://localhost:8002 | /api/lobster |

Custom services:

```python
from investkit_utils.api_docs import APIService, aggregate_openapi_docs

services = [
    APIService(
        name="my-service",
        url="http://localhost:3000",
        description="My custom service",
        prefix="/api/my",
    )
]

spec = await aggregate_openapi_docs(services)
```

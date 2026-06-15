"""InvestKit 异常模块测试"""

from investkit_utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    CacheError,
    ConfigurationError,
    DatabaseError,
    DataError,
    ExternalServiceError,
    InvestKitError,
    LLMError,
    MLModelError,
    NotFoundError,
    RateLimitError,
    TradingError,
    ValidationError,
    handle_exception,
)


class TestInvestKitError:
    def test_basic_creation(self):
        err = InvestKitError("test error")
        assert "test error" in str(err)

    def test_with_code(self):
        err = InvestKitError("test", code="TEST_001")
        assert err.code == "TEST_001"

    def test_with_details(self):
        err = InvestKitError("test", details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_inheritance(self):
        err = InvestKitError("test")
        assert isinstance(err, Exception)

    def test_to_dict(self):
        err = InvestKitError("test", code="E001", details={"k": "v"})
        d = err.to_dict()
        assert "test" in str(d) or "E001" in str(d)


class TestSubErrors:
    def test_validation_error(self):
        err = ValidationError("invalid input")
        assert isinstance(err, InvestKitError)

    def test_not_found_error(self):
        err = NotFoundError("not found")
        assert isinstance(err, InvestKitError)

    def test_authentication_error(self):
        err = AuthenticationError("auth failed")
        assert isinstance(err, InvestKitError)

    def test_authorization_error(self):
        err = AuthorizationError("no permission")
        assert isinstance(err, InvestKitError)

    def test_rate_limit_error(self):
        err = RateLimitError("too many requests")
        assert isinstance(err, InvestKitError)

    def test_external_service_error(self):
        err = ExternalServiceError("service down")
        assert isinstance(err, InvestKitError)

    def test_data_error(self):
        err = DataError("data fetch failed")
        assert isinstance(err, InvestKitError)

    def test_configuration_error(self):
        err = ConfigurationError("config load failed")
        assert isinstance(err, InvestKitError)

    def test_cache_error(self):
        err = CacheError("cache miss")
        assert isinstance(err, InvestKitError)

    def test_database_error(self):
        err = DatabaseError("db error")
        assert isinstance(err, InvestKitError)

    def test_ml_model_error(self):
        err = MLModelError("model error")
        assert isinstance(err, InvestKitError)

    def test_llm_error(self):
        err = LLMError("llm error")
        assert isinstance(err, InvestKitError)

    def test_trading_error(self):
        err = TradingError("trade failed")
        assert isinstance(err, InvestKitError)


class TestHandleException:
    def test_handle_investkit_error(self):
        err = InvestKitError("test", code="E001")
        result = handle_exception(err)
        assert isinstance(result, dict)

    def test_handle_generic_exception(self):
        err = ValueError("generic error")
        result = handle_exception(err)
        assert isinstance(result, dict)

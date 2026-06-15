from investkit_utils.exceptions.base import (
    AuthenticationError,
    AuthorizationError,
    DataError,
    ExternalServiceError,
    InvestKitError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from investkit_utils.exceptions.handlers import handle_exception, raise_for_status

import pytest


class TestHandleException:
    def test_handle_investkit_error_returns_to_dict(self):
        err = ValidationError("bad input", code="VAL_001")
        result = handle_exception(err)
        assert result["error"]["code"] == "VAL_001"
        assert result["error"]["message"] == "bad input"

    def test_handle_investkit_error_with_details(self):
        err = InvestKitError("test", code="E001", details={"field": "name"})
        result = handle_exception(err)
        assert result["error"]["details"]["field"] == "name"

    def test_handle_generic_exception(self):
        err = ValueError("something wrong")
        result = handle_exception(err)
        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert result["error"]["message"] == "something wrong"

    def test_handle_runtime_error(self):
        err = RuntimeError("runtime issue")
        result = handle_exception(err)
        assert result["error"]["code"] == "INTERNAL_ERROR"


class TestRaiseForStatus:
    def test_200_ok(self):
        raise_for_status(200)

    def test_201_ok(self):
        raise_for_status(201)

    def test_299_ok(self):
        raise_for_status(299)

    def test_400_raises_validation(self):
        with pytest.raises(ValidationError):
            raise_for_status(400, "bad request")

    def test_401_raises_authentication(self):
        with pytest.raises(AuthenticationError):
            raise_for_status(401, "unauthorized")

    def test_403_raises_authorization(self):
        with pytest.raises(AuthorizationError):
            raise_for_status(403, "forbidden")

    def test_404_raises_not_found(self):
        with pytest.raises(NotFoundError):
            raise_for_status(404, "not found")

    def test_422_raises_data_error(self):
        with pytest.raises(DataError):
            raise_for_status(422, "unprocessable")

    def test_429_raises_rate_limit(self):
        with pytest.raises(RateLimitError):
            raise_for_status(429, "too many")

    def test_502_raises_external_service(self):
        with pytest.raises(ExternalServiceError):
            raise_for_status(502, "bad gateway")

    def test_500_raises_investkit_error(self):
        with pytest.raises(InvestKitError):
            raise_for_status(500, "internal")

    def test_status_code_in_exception(self):
        with pytest.raises(InvestKitError) as exc_info:
            raise_for_status(500, "server error")
        assert exc_info.value.status_code == 500

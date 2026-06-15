"""API 文档模块测试"""

import json
import tempfile

from investkit_utils.api_docs import (
    INVESTKIT_SERVICES,
    APIService,
    HealthCheckResult,
    ServiceInfo,
    ServiceRegistry,
    ServiceStatus,
    load_openapi_spec_from_file,
    merge_openapi_specs,
)


class TestAPIService:
    def test_service_creation(self):
        service = APIService(
            name="test-service",
            url="http://localhost:8000",
            description="Test service",
            prefix="/api/test",
        )
        assert service.name == "test-service"
        assert service.url == "http://localhost:8000"
        assert service.prefix == "/api/test"

    def test_default_values(self):
        service = APIService(name="test", url="http://localhost:8000")
        assert service.description == ""
        assert service.prefix == ""
        assert service.openapi_url == "/openapi.json"
        assert service.enabled is True

    def test_investkit_services(self):
        assert len(INVESTKIT_SERVICES) == 3
        names = [s.name for s in INVESTKIT_SERVICES]
        assert "asset-lens" in names
        assert "lobster" in names
        assert "langchain-llm-toolkit" in names


class TestMergeOpenAPISpecs:
    def test_merge_empty_specs(self):
        result = merge_openapi_specs([])
        assert result["openapi"] == "3.0.3"
        assert result["paths"] == {}
        assert result["components"]["schemas"] == {}

    def test_merge_single_spec(self):
        spec = {
            "paths": {"/test": {"get": {"summary": "Test"}}},
            "components": {"schemas": {"TestModel": {"type": "object"}}},
            "tags": [{"name": "test"}],
        }
        result = merge_openapi_specs([spec])
        assert "/test" in result["paths"]
        assert "TestModel" in result["components"]["schemas"]

    def test_merge_with_prefix(self):
        spec = {
            "_prefix": "/api/v1",
            "paths": {"/users": {"get": {"summary": "Users"}}},
        }
        result = merge_openapi_specs([spec])
        assert "/api/v1/users" in result["paths"]

    def test_merge_with_service_name(self):
        spec = {
            "_service": "test-service",
            "paths": {"/test": {"get": {"summary": "Test", "tags": []}}},
        }
        result = merge_openapi_specs([spec])
        assert "test-service" in result["tags"][0]["name"]

    def test_merge_custom_info(self):
        result = merge_openapi_specs([], main_info={"title": "Custom API", "version": "2.0.0"})
        assert result["info"]["title"] == "Custom API"
        assert result["info"]["version"] == "2.0.0"


class TestLoadOpenAPISpecFromFile:
    def test_load_nonexistent_file(self):
        result = load_openapi_spec_from_file("nonexistent.json")
        assert result is None


class TestServiceRegistry:
    def setup_method(self):
        self.registry = ServiceRegistry()

    def test_register_service(self):
        service = ServiceInfo(
            name="test-service",
            url="http://localhost:8000",
        )
        self.registry.register(service)
        assert "test-service" in self.registry

    def test_unregister_service(self):
        service = ServiceInfo(name="test", url="http://localhost:8000")
        self.registry.register(service)
        assert self.registry.unregister("test") is True
        assert "test" not in self.registry

    def test_get_service(self):
        service = ServiceInfo(name="test", url="http://localhost:8000")
        self.registry.register(service)
        result = self.registry.get("test")
        assert result is not None
        assert result.name == "test"

    def test_get_nonexistent_service(self):
        assert self.registry.get("nonexistent") is None

    def test_get_all_services(self):
        self.registry.register(ServiceInfo(name="s1", url="http://localhost:8001"))
        self.registry.register(ServiceInfo(name="s2", url="http://localhost:8002"))
        services = self.registry.get_all()
        assert len(services) == 2

    def test_get_all_enabled_only(self):
        self.registry.register(ServiceInfo(name="enabled", url="http://localhost:8001", enabled=True))
        self.registry.register(ServiceInfo(name="disabled", url="http://localhost:8002", enabled=False))
        services = self.registry.get_all(enabled_only=True)
        assert len(services) == 1
        assert services[0].name == "enabled"

    def test_get_by_tag(self):
        self.registry.register(ServiceInfo(name="api1", url="http://localhost:8001", tags=["core"]))
        self.registry.register(ServiceInfo(name="api2", url="http://localhost:8002", tags=["extra"]))
        services = self.registry.get_by_tag("core")
        assert len(services) == 1
        assert services[0].name == "api1"

    def test_update_service(self):
        self.registry.register(ServiceInfo(name="test", url="http://localhost:8000"))
        self.registry.update_service("test", description="Updated")
        service = self.registry.get("test")
        assert service.description == "Updated"

    def test_len(self):
        self.registry.register(ServiceInfo(name="s1", url="http://localhost:8001"))
        self.registry.register(ServiceInfo(name="s2", url="http://localhost:8002"))
        assert len(self.registry) == 2


class TestServiceInfo:
    def test_service_info_creation(self):
        service = ServiceInfo(
            name="test",
            url="http://localhost:8000",
            description="Test service",
            prefix="/api/test",
            tags=["api", "test"],
        )
        assert service.name == "test"
        assert service.url == "http://localhost:8000"
        assert service.description == "Test service"
        assert service.prefix == "/api/test"
        assert "api" in service.tags

    def test_default_values(self):
        service = ServiceInfo(name="test", url="http://localhost:8000")
        assert service.description == ""
        assert service.prefix == ""
        assert service.openapi_url == "/openapi.json"
        assert service.health_url == "/health"
        assert service.enabled is True
        assert service.tags == []
        assert service.metadata == {}


class TestHealthCheckResult:
    def test_health_check_result_creation(self):
        result = HealthCheckResult(
            service_name="test",
            status=ServiceStatus.HEALTHY,
            response_time_ms=50.0,
        )
        assert result.service_name == "test"
        assert result.status == ServiceStatus.HEALTHY
        assert result.response_time_ms == 50.0

    def test_health_check_result_to_dict(self):
        result = HealthCheckResult(
            service_name="test",
            status=ServiceStatus.UNHEALTHY,
            error="Connection refused",
        )
        d = result.to_dict()
        assert d["service_name"] == "test"
        assert d["status"] == "unhealthy"
        assert d["error"] == "Connection refused"

    def test_health_check_result_with_details(self):
        result = HealthCheckResult(
            service_name="test",
            status=ServiceStatus.DEGRADED,
            details={"latency": "high"},
        )
        d = result.to_dict()
        assert d["details"]["latency"] == "high"


class TestServiceStatus:
    def test_service_status_values(self):
        assert ServiceStatus.UNKNOWN.value == "unknown"
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.UNHEALTHY.value == "unhealthy"
        assert ServiceStatus.DEGRADED.value == "degraded"


class TestLoadOpenAPISpecFromFileValid:
    def test_load_valid_file(self):
        spec_data = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(spec_data, f)
            f.flush()
            result = load_openapi_spec_from_file(f.name)
        assert result is not None
        assert result["openapi"] == "3.0.3"

    def test_load_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json{{{")
            f.flush()
            result = load_openapi_spec_from_file(f.name)
        assert result is None


class TestMergeOpenAPISpecsAdvanced:
    def test_merge_multiple_specs(self):
        spec1 = {
            "paths": {"/a": {"get": {"summary": "A"}}},
            "components": {"schemas": {"ModelA": {"type": "object"}}},
        }
        spec2 = {
            "paths": {"/b": {"get": {"summary": "B"}}},
            "components": {"schemas": {"ModelB": {"type": "object"}}},
        }
        result = merge_openapi_specs([spec1, spec2])
        assert "/a" in result["paths"]
        assert "/b" in result["paths"]
        assert "ModelA" in result["components"]["schemas"]
        assert "ModelB" in result["components"]["schemas"]

    def test_merge_with_security_schemes(self):
        spec = {
            "components": {
                "schemas": {},
                "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
            },
        }
        result = merge_openapi_specs([spec])
        assert "bearerAuth" in result["components"]["securitySchemes"]

    def test_merge_none_spec_skipped(self):
        result = merge_openapi_specs([None, {"paths": {"/test": {"get": {"summary": "T"}}}}])
        assert "/test" in result["paths"]

    def test_merge_service_name_prefixed_schema(self):
        spec = {
            "_service": "svc",
            "components": {"schemas": {"Model": {"type": "object"}}},
        }
        result = merge_openapi_specs([spec])
        assert "svc_Model" in result["components"]["schemas"]


class TestServiceRegistryAdvanced:
    def test_unregister_nonexistent(self):
        registry = ServiceRegistry()
        assert registry.unregister("nonexistent") is False

    def test_update_nonexistent_service(self):
        registry = ServiceRegistry()
        assert registry.update_service("nonexistent", description="x") is False

    def test_get_all_disabled(self):
        registry = ServiceRegistry()
        registry.register(ServiceInfo(name="disabled", url="http://localhost:8000", enabled=False))
        services = registry.get_all(enabled_only=False)
        assert len(services) == 1

    def test_get_health_status_empty(self):
        registry = ServiceRegistry()
        assert registry.get_health_status("test") is None

    def test_get_all_health_status(self):
        registry = ServiceRegistry()
        result = registry.get_all_health_status()
        assert isinstance(result, dict)

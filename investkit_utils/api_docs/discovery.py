"""API 服务发现和健康检查"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from investkit_utils.utils.data_utils import ToDictMixin


class ServiceStatus(str, Enum):
    """服务状态"""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass
class HealthCheckResult(ToDictMixin):
    service_name: str
    status: ServiceStatus
    response_time_ms: float | None = None
    last_check: datetime = field(default_factory=datetime.now)
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceInfo:
    """服务信息"""

    name: str
    url: str
    description: str = ""
    prefix: str = ""
    openapi_url: str = "/openapi.json"
    health_url: str = "/health"
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ServiceRegistry:
    """服务注册中心

    管理服务注册、发现和健康检查。

    示例:
        registry = ServiceRegistry()

        # 注册服务
        registry.register(ServiceInfo(
            name="asset-lens",
            url="http://localhost:8000",
            prefix="/api/asset"
        ))

        # 获取服务
        service = registry.get("asset-lens")

        # 健康检查
        result = await registry.health_check("asset-lens")
    """

    def __init__(self):
        self._services: dict[str, ServiceInfo] = {}
        self._health_status: dict[str, HealthCheckResult] = {}

    def register(self, service: ServiceInfo) -> None:
        """注册服务"""
        self._services[service.name] = service

    def unregister(self, name: str) -> bool:
        """注销服务"""
        if name in self._services:
            del self._services[name]
            if name in self._health_status:
                del self._health_status[name]
            return True
        return False

    def get(self, name: str) -> ServiceInfo | None:
        """获取服务"""
        return self._services.get(name)

    def get_all(self, enabled_only: bool = True) -> list[ServiceInfo]:
        """获取所有服务"""
        services = list(self._services.values())
        if enabled_only:
            services = [s for s in services if s.enabled]
        return services

    def get_by_tag(self, tag: str) -> list[ServiceInfo]:
        """按标签获取服务"""
        return [s for s in self._services.values() if tag in s.tags]

    async def health_check(self, name: str, timeout: float = 5.0) -> HealthCheckResult:
        """检查单个服务健康状态"""
        service = self.get(name)
        if not service:
            return HealthCheckResult(
                service_name=name,
                status=ServiceStatus.UNKNOWN,
                error="Service not found",
            )

        try:
            import time

            import httpx

            start_time = time.time()
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{service.url}{service.health_url}")
                response_time = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    status = ServiceStatus.HEALTHY
                    error = None
                    details = (
                        response.json()
                        if response.headers.get("content-type", "").startswith("application/json")
                        else {}
                    )
                else:
                    status = ServiceStatus.UNHEALTHY
                    error = f"HTTP {response.status_code}"
                    details = {}

                result = HealthCheckResult(
                    service_name=name,
                    status=status,
                    response_time_ms=round(response_time, 2),
                    error=error,
                    details=details,
                )
        except (httpx.HTTPError, httpx.InvalidURL) as e:
            result = HealthCheckResult(
                service_name=name,
                status=ServiceStatus.UNHEALTHY,
                error=str(e),
            )

        self._health_status[name] = result
        return result

    async def health_check_all(self, timeout: float = 5.0) -> dict[str, HealthCheckResult]:
        """检查所有服务健康状态（并发执行）"""

        names = list(self._services.keys())
        tasks = [self.health_check(name, timeout) for name in names]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        results = {}
        for name, result in zip(names, results_list, strict=True):
            if isinstance(result, Exception):
                results[name] = HealthCheckResult(
                    service_name=name,
                    status=ServiceStatus.UNHEALTHY,
                    error=str(result),
                )
            else:
                results[name] = result
        return results

    def get_health_status(self, name: str) -> HealthCheckResult | None:
        """获取服务健康状态"""
        return self._health_status.get(name)

    def get_all_health_status(self) -> dict[str, HealthCheckResult]:
        """获取所有服务健康状态"""
        return self._health_status.copy()

    def update_service(self, name: str, **kwargs: Any) -> bool:
        """更新服务信息"""
        service = self.get(name)
        if not service:
            return False

        for key, value in kwargs.items():
            if hasattr(service, key):
                setattr(service, key, value)
        return True

    def __len__(self) -> int:
        return len(self._services)

    def __contains__(self, name: str) -> bool:
        return name in self._services


_default_registry: ServiceRegistry | None = None


def get_service_registry() -> ServiceRegistry:
    """获取默认服务注册中心"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ServiceRegistry()
    return _default_registry


def register_service(service: ServiceInfo) -> None:
    """注册服务到默认注册中心"""
    get_service_registry().register(service)


def get_service(name: str) -> ServiceInfo | None:
    """从默认注册中心获取服务"""
    return get_service_registry().get(name)


def get_all_services(enabled_only: bool = True) -> list[ServiceInfo]:
    """获取所有服务"""
    return get_service_registry().get_all(enabled_only)

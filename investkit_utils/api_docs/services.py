"""API 服务定义"""

from dataclasses import dataclass


@dataclass
class APIService:
    """API 服务定义"""

    name: str
    url: str
    description: str = ""
    prefix: str = ""
    openapi_url: str = "/openapi.json"
    enabled: bool = True


INVESTKIT_SERVICES: list[APIService] = [
    APIService(
        name="asset-lens",
        url="http://localhost:8000",
        description="个人资产操作系统 API",
        prefix="/api/asset",
        openapi_url="/openapi.json",
    ),
    APIService(
        name="langchain-llm-toolkit",
        url="http://localhost:8001",
        description="LLM 工具集 API",
        prefix="/api/llm",
        openapi_url="/openapi.json",
    ),
    APIService(
        name="lobster",
        url="http://localhost:8002",
        description="AI 助手 API",
        prefix="/api/lobster",
        openapi_url="/openapi.json",
    ),
]

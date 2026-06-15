"""API 文档服务

提供聚合 API 文档的 Web 服务。
"""

from typing import Any

from investkit_utils.api_docs.discovery import ServiceRegistry


def serve_aggregated_docs(
    services: list | None = None,
    main_info: dict[str, Any] | None = None,
    port: int = 8080,
    registry: ServiceRegistry | None = None,
):
    """启动聚合 API 文档服务

    Args:
        services: 服务列表
        main_info: 主信息
        port: 服务端口
        registry: 服务注册中心

    Returns:
        FastAPI 应用
    """
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse

    from investkit_utils.api_docs.discovery import ServiceInfo, get_service_registry
    from investkit_utils.api_docs.openapi import aggregate_openapi_docs
    from investkit_utils.api_docs.services import INVESTKIT_SERVICES

    services = services or INVESTKIT_SERVICES
    registry = registry or get_service_registry()

    for svc in services:
        registry.register(
            ServiceInfo(
                name=svc.name,
                url=svc.url,
                description=svc.description,
                prefix=svc.prefix,
                openapi_url=svc.openapi_url,
                enabled=svc.enabled,
            )
        )

    app = FastAPI(
        title="InvestKit API Gateway",
        description="InvestKit 统一 API 文档网关",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/", response_class=HTMLResponse)
    async def root():
        services_html = ""
        for svc in registry.get_all():
            services_html += f"""
            <div class="service">
                <h3>{svc.name}</h3>
                <p>{svc.description}</p>
                <a href="/docs/{svc.name}">Swagger UI</a> |
                <a href="/redoc/{svc.name}">ReDoc</a>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>InvestKit API Gateway</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                h1 {{ color: #333; }}
                .service {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 8px; }}
                .service h3 {{ margin: 0 0 10px 0; }}
                .service a {{ color: #0066cc; text-decoration: none; }}
                .service a:hover {{ text-decoration: underline; }}
                .status-healthy {{ color: #28a745; }}
                .status-unhealthy {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <h1>InvestKit API Gateway</h1>
            <p>统一 API 文档入口</p>
            <h2>可用服务</h2>
            {services_html}
            <h2>聚合文档</h2>
            <div class="service">
                <a href="/openapi.json">OpenAPI JSON</a> |
                <a href="/docs">Swagger UI (聚合)</a> |
                <a href="/redoc">ReDoc (聚合)</a>
            </div>
            <h2>系统状态</h2>
            <div class="service">
                <a href="/health">健康检查</a> |
                <a href="/services">服务列表</a>
            </div>
        </body>
        </html>
        """

    @app.get("/openapi.json")
    async def get_aggregated_openapi():
        spec = await aggregate_openapi_docs(services, main_info)
        return JSONResponse(content=spec)

    @app.get("/docs", response_class=HTMLResponse)
    async def swagger_ui():
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
            <script>
                SwaggerUIBundle({
                    url: "/openapi.json",
                    dom_id: '#swagger-ui',
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIBundle.SwaggerUIStandalonePreset
                    ]
                })
            </script>
        </body>
        </html>
        """

    @app.get("/redoc", response_class=HTMLResponse)
    async def redoc():
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>InvestKit API Documentation</title>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>body { margin: 0; padding: 0; }</style>
        </head>
        <body>
            <redoc spec-url='/openapi.json'></redoc>
            <script src="https://unpkg.com/redoc@latest/bundles/redoc.standalone.js"></script>
        </body>
        </html>
        """

    @app.get("/health")
    async def health_check():
        results = await registry.health_check_all()
        return JSONResponse(content={name: result.to_dict() for name, result in results.items()})

    @app.get("/services")
    async def list_services():
        services_list = []
        for svc in registry.get_all():
            health = registry.get_health_status(svc.name)
            services_list.append(
                {
                    "name": svc.name,
                    "url": svc.url,
                    "description": svc.description,
                    "prefix": svc.prefix,
                    "enabled": svc.enabled,
                    "status": health.status.value if health else "unknown",
                }
            )
        return JSONResponse(content={"services": services_list})

    @app.get("/docs/{service_name}", response_class=HTMLResponse)
    async def service_swagger_ui(service_name: str):
        service = registry.get(service_name)
        if not service:
            return HTMLResponse(content="Service not found", status_code=404)

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
            <script>
                SwaggerUIBundle({{
                    url: "{service.url}{service.openapi_url}",
                    dom_id: '#swagger-ui',
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIBundle.SwaggerUIStandalonePreset
                    ]
                }})
            </script>
        </body>
        </html>
        """

    @app.get("/redoc/{service_name}", response_class=HTMLResponse)
    async def service_redoc(service_name: str):
        service = registry.get(service_name)
        if not service:
            return HTMLResponse(content="Service not found", status_code=404)

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{service.name} API Documentation</title>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>body {{ margin: 0; padding: 0; }}</style>
        </head>
        <body>
            <redoc spec-url='{service.url}{service.openapi_url}'></redoc>
            <script src="https://unpkg.com/redoc@latest/bundles/redoc.standalone.js"></script>
        </body>
        </html>
        """

    return app

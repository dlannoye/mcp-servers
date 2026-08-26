import contextlib
import os
from collections.abc import AsyncIterator

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from .server import create_server


def _comma_separated_setting(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


def create_http_app(
    local_timezone: str | None = None,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
) -> Starlette:
    """Create the ASGI application used by Azure App Service."""
    if allowed_hosts is None:
        allowed_hosts = _comma_separated_setting("MCP_ALLOWED_HOSTS")
        if azure_hostname := os.getenv("WEBSITE_HOSTNAME"):
            allowed_hosts.append(azure_hostname)
        if not allowed_hosts:
            allowed_hosts = ["localhost:*", "127.0.0.1:*"]

    if allowed_origins is None:
        allowed_origins = _comma_separated_setting("MCP_ALLOWED_ORIGINS")

    server = create_server(local_timezone or os.getenv("LOCAL_TIMEZONE"))
    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
        stateless=True,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        ),
    )

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "mcp-server-time"})

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    middleware = []
    if allowed_origins:
        middleware.append(
            Middleware(
                CORSMiddleware,
                allow_origins=allowed_origins,
                allow_methods=["GET", "POST", "DELETE"],
                allow_headers=["*"],
                expose_headers=["Mcp-Session-Id"],
            )
        )

    return Starlette(
        routes=[
            Route("/", health),
            Route("/healthz", health),
            Mount("/mcp", app=handle_mcp),
        ],
        middleware=middleware,
        lifespan=lifespan,
    )


app = create_http_app()

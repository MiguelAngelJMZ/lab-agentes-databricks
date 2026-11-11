"""Aplicación del servidor MCP: FastMCP en modo stateless servido por FastAPI en /mcp."""

from fastapi import FastAPI, Request
from fastmcp import FastMCP

from .tools import load_tools
from .utils import header_store

mcp_server = FastMCP(name="mcp-mesa-servicio")
load_tools(mcp_server)

# stateless_http=True: cada request es autocontenido. Genie Code y las réplicas de Apps lo necesitan.
mcp_app = mcp_server.http_app(stateless_http=True)

app = FastAPI(title="MCP Mesa de servicio", lifespan=mcp_app.lifespan)


@app.get("/", include_in_schema=False)
async def index():
    return {"status": "healthy", "mcp": "/mcp", "servidor": "mcp-mesa-servicio"}


combined_app = FastAPI(
    title="MCP Mesa de servicio",
    routes=[*mcp_app.routes, *app.routes],
    lifespan=mcp_app.lifespan,
)


@combined_app.middleware("http")
async def capture_headers(request: Request, call_next):
    """Guarda los headers para poder actuar en nombre del usuario (x-forwarded-access-token)."""
    header_store.set(dict(request.headers))
    return await call_next(request)

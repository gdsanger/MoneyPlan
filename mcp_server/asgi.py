"""
ASGI entry point for the MCP Streamable HTTP endpoint, served as its own
long-running process (see `manage.py mcp_serve`) alongside the Gunicorn/WSGI
Django process — not mounted into config/urls.py, since Streamable HTTP/SSE
needs a persistent ASGI event loop that a synchronous WSGI worker can't
provide.
"""
from .auth import TokenAuthMiddleware
from .server import mcp

application = TokenAuthMiddleware(mcp.streamable_http_app())

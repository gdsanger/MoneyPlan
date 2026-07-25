"""
ASGI middleware guarding the MCP Streamable HTTP endpoint with a static
access token (see settings.MCP_ACCESS_TOKEN).

The token is accepted from either:
- the query string (?token=...) — required by the built-in Claude Desktop
  remote connector, which has no field for a custom Authorization header;
- an `Authorization: Bearer ...` header — for clients that support it
  (Claude Code, the mcp-remote bridge, plain API calls).

Every response gets `Cache-Control: no-store` so the token is never cached
by an intermediary. Requests that don't arrive over HTTPS (per
X-Forwarded-Proto, set by the reverse proxy) are rejected unless
MCP_REQUIRE_HTTPS is disabled (e.g. for local development).
"""
import hmac
import json
from urllib.parse import parse_qs

from django.conf import settings


def _extract_token(scope):
    headers = dict(scope.get('headers') or [])

    auth_header = headers.get(b'authorization', b'').decode('latin-1')
    if auth_header.lower().startswith('bearer '):
        return auth_header[len('bearer '):].strip()

    query_string = scope.get('query_string', b'').decode('latin-1')
    token_values = parse_qs(query_string).get('token')
    if token_values:
        return token_values[0]

    return None


def _is_https(scope):
    if scope.get('scheme') == 'https':
        return True
    headers = dict(scope.get('headers') or [])
    forwarded_proto = headers.get(b'x-forwarded-proto', b'').decode('latin-1').lower()
    return forwarded_proto == 'https'


def token_is_valid(token):
    """Constant-time check against settings.MCP_ACCESS_TOKEN.

    Shared by the MCP ASGI middleware and any WSGI view that wants the same
    token-auth scheme (e.g. the token-authenticated attachment upload API).
    """
    expected = settings.MCP_ACCESS_TOKEN
    if not expected or not token:
        return False
    return hmac.compare_digest(token, expected)


def extract_token_from_django_request(request):
    """Same accepted forms as `_extract_token`, for regular (WSGI) Django views.

    Bearer header takes precedence over the `?token=` query parameter.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.lower().startswith('bearer '):
        return auth_header[len('bearer '):].strip()

    return request.GET.get('token')


async def _send_json_error(send, status, message):
    body = json.dumps({'error': message}).encode('utf-8')
    await send({
        'type': 'http.response.start',
        'status': status,
        'headers': [
            (b'content-type', b'application/json'),
            (b'cache-control', b'no-store'),
        ],
    })
    await send({'type': 'http.response.body', 'body': body})


class TokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        if settings.MCP_REQUIRE_HTTPS and not _is_https(scope):
            await _send_json_error(send, 403, 'HTTPS required')
            return

        if not token_is_valid(_extract_token(scope)):
            await _send_json_error(send, 401, 'Invalid or missing token')
            return

        async def send_with_no_store(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers') or [])
                headers.append((b'cache-control', b'no-store'))
                message = {**message, 'headers': headers}
            await send(message)

        await self.app(scope, receive, send_with_no_store)

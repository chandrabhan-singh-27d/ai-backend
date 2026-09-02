from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response

from app.services.context import RequestContext, reset_request_context, set_request_context

MiddlewareCallable = Callable[[Request], Awaitable[Response]]


async def request_context_middleware(request: Request, call_next: MiddlewareCallable) -> Response:
    request_id = str(uuid4())
    raw_client_id = request.headers.get("X-Request-Id", "")
    client_id = raw_client_id.strip()[:128] or "-"

    token = set_request_context(RequestContext(request_id=request_id, client_id=client_id))

    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        reset_request_context(token)
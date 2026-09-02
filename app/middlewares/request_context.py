from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response

from app.services.context import RequestContext, reset_request_context, set_request_context
from app.services.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS

MiddlewareCallable = Callable[[Request], Awaitable[Response]]


async def request_context_middleware(request: Request, call_next: MiddlewareCallable) -> Response:
    request_id = str(uuid4())
    raw_client_id = request.headers.get("X-Request-Id", "")
    client_id = raw_client_id.strip()[:128] or "-"

    token = set_request_context(RequestContext(request_id=request_id, client_id=client_id))

    status = 500
    start = perf_counter()

    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path: str = getattr(route, "path", "unmatched")
        if path != "/metrics":
            HTTP_REQUESTS.labels(method=request.method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION.labels(method=request.method, path=path).observe(
                perf_counter() - start
            )
        reset_request_context(token)

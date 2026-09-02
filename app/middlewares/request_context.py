import logging
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response

from app.services.context import RequestContext, reset_request_context, set_request_context
from app.services.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS

MiddlewareCallable = Callable[[Request], Awaitable[Response]]
logger = logging.getLogger("app.middlewares.request_context")


async def request_context_middleware(request: Request, call_next: MiddlewareCallable) -> Response:
    request_id = str(uuid4())
    raw_client_id = request.headers.get("X-Request-Id", "")
    client_id = raw_client_id.strip()[:128] or "-"

    token = set_request_context(RequestContext(request_id=request_id, client_id=client_id))

    start = perf_counter()
    status = 500

    try:
        logger.info(
            "request_started",
            extra={"extra_fields": {"method": request.method, "path": request.url.path}},
        )
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        status = response.status_code
        return response
    finally:
        elapsed = perf_counter() - start
        route = request.scope.get("route")
        path: str = getattr(route, "path", "unmatched")
        if path != "/metrics":
            HTTP_REQUESTS.labels(method=request.method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION.labels(method=request.method, path=path).observe(elapsed)
            logger.info(
                "request_completed",
                extra={
                    "extra_fields": {
                        "method": request.method,
                        "path": path,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 2),
                    }
                },
            )
        reset_request_context(token)

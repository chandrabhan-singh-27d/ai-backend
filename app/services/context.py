from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    client_id: str


_current: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def set_request_context(ctx: RequestContext) -> None:
    _current.set(ctx)


def get_request_context() -> RequestContext:
    ctx = _current.get()
    assert ctx is not None, "request context not set"
    return ctx

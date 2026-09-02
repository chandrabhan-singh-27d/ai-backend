from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    client_id: str


_current: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def set_request_context(ctx: RequestContext) -> Token[RequestContext | None]:
    return _current.set(ctx)

def reset_request_context(token: Token[RequestContext | None]) -> None:
    _current.reset(token)

def get_request_context() -> RequestContext:
    ctx = _current.get()
    assert ctx is not None, "request context not set"
    return ctx

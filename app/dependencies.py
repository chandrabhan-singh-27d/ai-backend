from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.api_keys import get_api_keys_store
from app.services.metrics import AUTH_FAILURES
from app.services.rate_limiter import RateLimiter

bearer_scheme = HTTPBearer(auto_error=False)
ApiKeyCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

limiter = RateLimiter(limit=60, window_seconds=60)


def require_api_key(
    request: Request,
    credentials: ApiKeyCredentials,
) -> dict[str, object]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        AUTH_FAILURES.labels(reason="missing_key").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticated": "Bearer"},
        )
    key = get_api_keys_store().find(credentials.credentials)

    if key is None:
        AUTH_FAILURES.labels(reason="invalid_key").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.api_key = key
    return key


def require_rate_limit(request: Request) -> None:
    key_id = int(request.state.api_key["id"])
    allowed, _remaining = limiter.allow(f"key: {key_id}")

    if not allowed:
        AUTH_FAILURES.labels(reason="rate_limited").inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate Limit Exceeded"
        )


PROTECTED = [Depends(require_api_key), Depends(require_rate_limit)]

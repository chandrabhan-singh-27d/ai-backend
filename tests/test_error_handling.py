import asyncio
import json
import os
from typing import Any

os.environ.setdefault("GROQ_API_KEY", "test-key")

import httpx
from starlette.requests import Request

from app.main import app, unhandled_exception_handler

_TEST_SCOPE: dict[str, Any] = {
    "type": "http",
    "method": "GET",
    "path": "/test",
    "raw_path": b"/test",
    "query_string": b"",
    "headers": [],
    "scheme": "http",
    "server": ("test", 80),
    "client": ("test", 1),
    "app": app,
    "root_path": "",
}


def test_unhandled_exception_returns_sanitized_500() -> None:
    response = asyncio.run(
        unhandled_exception_handler(Request(_TEST_SCOPE), RuntimeError("secret internal detail"))
    )

    assert response.status_code == 500
    assert json.loads(bytes(response.body)) == {"detail": "internal server error"}


def test_http_exception_is_not_swallowed_by_catch_all() -> None:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/chat", json={"message": "hi"})

    response = asyncio.run(_call())

    assert response.status_code == 401
import asyncio
import logging
from time import sleep
from typing import TypedDict

import httpx
from fastapi import APIRouter, HTTPException

from app.dependencies import PROTECTED
from app.services.ssrf import InvalidFetchUrl, validate_fetch_url

router = APIRouter()
logger = logging.getLogger("app.routers.demo")

# Cap on fetched response bodies (protects memory from hostile/oversized upstreams).
MAX_FETCH_BYTES = 1_000_000


class FetchResponse(TypedDict):
    url: str
    status: int
    content_length: int


class DemoResponse(TypedDict):
    handler: str
    elapsed: int


@router.get("/fetch", dependencies=PROTECTED)
async def fetch_url(url: str) -> FetchResponse:
    try:
        validate_fetch_url(url)
    except InvalidFetchUrl as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        async with (
            httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length is not None and int(content_length) > MAX_FETCH_BYTES:
                raise HTTPException(status_code=413, detail="response too large")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_FETCH_BYTES:
                    raise HTTPException(status_code=413, detail="response too large")
        return {
            "url": url,
            "status": response.status_code,
            "content_length": len(body),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("fetch_failed url=%s error=%s", url, e)
        raise HTTPException(status_code=502, detail="fetch failed") from e


# Teaching/demo endpoints. Registered only when DEMO_ENDPOINTS=true (default off);
# /slow-blocked intentionally blocks the event loop to demonstrate why that is bad.
demo_router = APIRouter(prefix="/slow", tags=["demo"])


@demo_router.get("/sync")
def sync_demo() -> DemoResponse:
    sleep(3)
    return {"handler": "sync", "elapsed": 3}


@demo_router.get("/async")
async def async_demo() -> DemoResponse:
    await asyncio.sleep(3)
    return {"handler": "async", "elapsed": 3}


@demo_router.get("/blocked")
async def blocked_demo() -> DemoResponse:
    sleep(3)
    return {"handler": "blocked", "elapsed": 3}